from __future__ import annotations

import os
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText

from flask import Flask, render_template, request, redirect, url_for
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

def get_sb():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL / SUPABASE_KEY mangler i .env")
    return create_client(url, key)


def send_notification(to: str, subject: str, body: str) -> None:
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    smtp_from = os.getenv("SMTP_FROM", smtp_user)
    if not smtp_user or not smtp_pass:
        print(f"[NOTIFY] SMTP ikke konfigureret. Ville have sendt til {to}: {subject}")
        return
    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = smtp_from
        msg["To"] = to
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(smtp_user, smtp_pass)
            s.send_message(msg)
        print(f"[NOTIFY] Sendt til {to}: {subject}")
    except Exception as e:
        print(f"[NOTIFY] Fejl ved afsendelse: {e}")


# ── Forside: opgaver i dag og fremover ───────────────────────
@app.route("/")
def index():
    sb = get_sb()
    today = datetime.now().date().isoformat()
    res = sb.table("tasks").select("*").gte("plan_date", today).order("plan_date").execute()
    return render_template("index.html", tasks=res.data, today=today)


# ── Opgave-detalje ────────────────────────────────────────────
@app.route("/task/<task_id>")
def task_detail(task_id):
    sb = get_sb()
    res = sb.table("tasks").select("*").eq("task_id", task_id).single().execute()
    return render_template("task.html", task=res.data, msg=None)


# ── Meld forsinkelse ──────────────────────────────────────────
@app.route("/delay/<task_id>", methods=["POST"])
def delay(task_id):
    sb = get_sb()
    resource  = request.form["resource"]    # 'carpenter' / 'painter' / 'cleaning'
    new_start = request.form["new_start"]   # 'HH:MM'
    minutes   = int(request.form["minutes"])

    task_res = sb.table("tasks").select("*").eq("task_id", task_id).single().execute()
    task = task_res.data
    plan = task.get("plan") or {}
    blocks = plan.get("blocks", [])
    plan_date = task.get("plan_date", datetime.now().date().isoformat())

    new_dt  = datetime.fromisoformat(f"{plan_date}T{new_start}")
    new_end = new_dt + timedelta(minutes=minutes)

    # Konflikt-check: overlapper ny tid med en ANDEN ressources blok?
    conflict_with = None
    for b in blocks:
        if b.get("kind") == resource:
            continue
        try:
            b_start = datetime.fromisoformat(b["start"])
            b_end   = datetime.fromisoformat(b["end"])
            if new_dt < b_end and new_end > b_start:
                conflict_with = b.get("label", b.get("kind"))
                break
        except Exception:
            continue

    if conflict_with:
        # Gem til admin-godkendelse
        sb.table("pending_changes").insert({
            "task_id":    task_id,
            "resource":   resource,
            "new_start":  new_start,
            "minutes":    minutes,
            "status":     "PENDING",
            "created_at": datetime.now().isoformat(),
        }).execute()

        # Advisér admin
        admin_email = os.getenv("ADMIN_EMAIL")
        if admin_email:
            send_notification(
                admin_email,
                f"Konflikt: {task.get('address')} — {resource} ønsker {new_start}",
                f"Opgave: {task.get('address')}\n"
                f"Ressource: {resource} ønsker at starte {new_start} ({minutes} min)\n"
                f"Konflikt med: {conflict_with}\n\n"
                f"Godkend eller afvis på: {request.host_url}admin",
            )

        return render_template("task.html", task=task,
            msg=f"⚠ Konflikt med {conflict_with} — admin er adviseret og vender tilbage.")
    else:
        # Opdater blokken direkte
        for b in blocks:
            if b.get("kind") == resource:
                b["start"] = f"{plan_date}T{new_start}"
                b["end"]   = new_end.isoformat()

        sb.table("tasks").update({"plan": plan}).eq("task_id", task_id).execute()

        # Notificér de andre ressourcer på opgaven
        notify_emails = _get_other_emails(resource, task)
        for email in notify_emails:
            send_notification(
                email,
                f"Opdateret tidspunkt: {task.get('address')}",
                f"Opgave: {task.get('address')}\n"
                f"{resource.capitalize()} har meldt nyt starttidspunkt: {new_start}\n"
                f"Se opdateret plan på: {request.host_url}task/{task_id}",
            )

        return render_template("task.html", task=task,
            msg=f"✓ Tidspunkt opdateret til {new_start}. Øvrige parter er notificeret.")


def _get_other_emails(changed_resource: str, task: dict) -> list[str]:
    """Returnerer e-mails til de ressourcer der IKKE selv lavede ændringen."""
    emails = []
    # Disse er gemt på task hvis du tilføjer dem i pipeline — ellers fra env
    mapping = {
        "carpenter": os.getenv("CARPENTER_EMAILS", "").split(","),
        "painter":   [],  # malere har typisk ikke individuelle mails i dette setup
        "cleaning":  os.getenv("CLEANING_EMAILS", "").split(","),
    }
    for resource, mails in mapping.items():
        if resource != changed_resource:
            emails.extend([m.strip() for m in mails if m.strip()])
    return emails


# ── Admin: vis konflikter der venter ─────────────────────────
@app.route("/admin")
def admin():
    # Simpel beskyttelse — sæt ADMIN_TOKEN i .env og send som ?token=xxx
    token = request.args.get("token", "")
    admin_token = os.getenv("ADMIN_TOKEN", "")
    if admin_token and token != admin_token:
        return "Adgang nægtet — tilføj ?token=<ADMIN_TOKEN> til URL", 403

    sb = get_sb()
    changes = sb.table("pending_changes").select("*, tasks(address)").eq("status", "PENDING").execute()
    return render_template("admin.html", changes=changes.data, token=token)


@app.route("/admin/approve/<int:change_id>", methods=["POST"])
def approve(change_id):
    token = request.args.get("token", "")
    sb = get_sb()

    # Hent ændringen
    ch_res = sb.table("pending_changes").select("*").eq("id", change_id).single().execute()
    ch = ch_res.data

    # Opdater selve opgaven
    task_res = sb.table("tasks").select("*").eq("task_id", ch["task_id"]).single().execute()
    task = task_res.data
    plan = task.get("plan") or {}
    blocks = plan.get("blocks", [])
    plan_date = task.get("plan_date", "")
    new_end = (datetime.fromisoformat(f"{plan_date}T{ch['new_start']}") + timedelta(minutes=ch["minutes"])).isoformat()

    for b in blocks:
        if b.get("kind") == ch["resource"]:
            b["start"] = f"{plan_date}T{ch['new_start']}"
            b["end"]   = new_end

    sb.table("tasks").update({"plan": plan}).eq("task_id", ch["task_id"]).execute()
    sb.table("pending_changes").update({"status": "APPROVED"}).eq("id", change_id).execute()

    return redirect(url_for("admin", token=token))


@app.route("/admin/reject/<int:change_id>", methods=["POST"])
def reject(change_id):
    token = request.args.get("token", "")
    sb = get_sb()
    sb.table("pending_changes").update({"status": "REJECTED"}).eq("id", change_id).execute()
    return redirect(url_for("admin", token=token))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=False)
