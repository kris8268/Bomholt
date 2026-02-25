from __future__ import annotations
import msal
from src.config import Settings

GRAPH_SCOPE = ["https://graph.microsoft.com/.default"]

def acquire_token(settings: Settings) -> str:
    app = msal.ConfidentialClientApplication(
        client_id=settings.client_id,
        client_credential=settings.client_secret,
        authority=f"https://login.microsoftonline.com/{settings.tenant_id}",
    )
    result = app.acquire_token_silent(GRAPH_SCOPE, account=None)
    if not result:
        result = app.acquire_token_for_client(scopes=GRAPH_SCOPE)

    if "access_token" not in result:
        raise RuntimeError(f"Token error: {result}")
    return result["access_token"]
