from __future__ import annotations
import base64
from dataclasses import dataclass
from typing import Iterable
from src.graph.client import GraphClient

@dataclass
class GraphMessage:
    id: str
    subject: str
    received_datetime: str
    from_address: str | None
    body_preview: str | None
    has_attachments: bool

@dataclass
class DownloadedAttachment:
    filename: str
    content: bytes

def list_messages_in_date_range(
    gc: GraphClient,
    mailbox_upn: str,
    start_iso: str,
    end_iso: str,
    top: int = 200,
) -> list[GraphMessage]:
    # Vi bruger $filter på receivedDateTime og sorterer desc.
    # (Query-parametre i Graph) :contentReference[oaicite:5]{index=5}
    params = {
        "$top": str(top),
        "$orderby": "receivedDateTime desc",
        "$select": "id,subject,receivedDateTime,from,hasAttachments,bodyPreview",
        "$filter": f"receivedDateTime ge {start_iso} and receivedDateTime lt {end_iso}",
    }
    data = gc.get(f"/users/{mailbox_upn}/mailFolders/Inbox/messages", params=params)
    out: list[GraphMessage] = []
    for item in data.get("value", []):
        frm = None
        try:
            frm = item.get("from", {}).get("emailAddress", {}).get("address")
        except Exception:
            frm = None
        out.append(
            GraphMessage(
                id=item["id"],
                subject=item.get("subject", ""),
                received_datetime=item.get("receivedDateTime", ""),
                from_address=frm,
                body_preview=item.get("bodyPreview"),
                has_attachments=bool(item.get("hasAttachments")),
            )
        )
    return out

def list_attachments(gc: GraphClient, mailbox_upn: str, message_id: str) -> list[dict]:
    data = gc.get(f"/users/{mailbox_upn}/messages/{message_id}/attachments", params={"$top": "50"})
    return data.get("value", [])

def download_file_attachments(
    gc: GraphClient, mailbox_upn: str, message_id: str
) -> list[DownloadedAttachment]:
    atts = list_attachments(gc, mailbox_upn, message_id)
    downloaded: list[DownloadedAttachment] = []
    for a in atts:
        name = a.get("name") or "attachment.bin"
        odata_type = a.get("@odata.type", "")
        if "fileAttachment" not in odata_type:
            continue  # ignorer itemAttachment etc. i MVP

        # Nogle fileAttachment svar indeholder contentBytes direkte, ellers kan man hente rå-indhold.
        content_b64 = a.get("contentBytes")
        if content_b64:
            content = base64.b64decode(content_b64)
        else:
            att_id = a["id"]
            # Hent attachment raw via $value :contentReference[oaicite:6]{index=6}
            content = gc.get_bytes(f"/users/{mailbox_upn}/messages/{message_id}/attachments/{att_id}/$value")

        downloaded.append(DownloadedAttachment(filename=name, content=content))
    return downloaded

def move_message_to_folder(
    gc: GraphClient,
    mailbox_upn: str,
    message_id: str,
    dest_folder_id: str,
) -> None:
    # Flyt mail (udkommenter det i pipeline; endpoint her er klar) :contentReference[oaicite:7]{index=7}
    gc.post(f"/users/{mailbox_upn}/messages/{message_id}/move", json={"destinationId": dest_folder_id})

def find_folder_id_by_name(gc: GraphClient, mailbox_upn: str, folder_name: str) -> str | None:
    data = gc.get(f"/users/{mailbox_upn}/mailFolders", params={"$top": "200"})
    for f in data.get("value", []):
        if (f.get("displayName") or "").strip().lower() == folder_name.strip().lower():
            return f["id"]
    return None
