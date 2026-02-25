from __future__ import annotations
import requests

class GraphClient:
    def __init__(self, access_token: str):
        self.base = "https://graph.microsoft.com/v1.0"
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

    def get(self, path: str, params: dict | None = None) -> dict:
        r = requests.get(self.base + path, headers=self.headers, params=params, timeout=60)
        if not r.ok:
            raise RuntimeError(f"GET {path} failed: {r.status_code} {r.text}")
        return r.json()

    def get_bytes(self, path: str) -> bytes:
        r = requests.get(self.base + path, headers=self.headers, timeout=60)
        if not r.ok:
            raise RuntimeError(f"GET(bytes) {path} failed: {r.status_code} {r.text}")
        return r.content

    def post(self, path: str, json: dict) -> dict:
        r = requests.post(self.base + path, headers=self.headers, json=json, timeout=60)
        if not r.ok:
            raise RuntimeError(f"POST {path} failed: {r.status_code} {r.text}")
        return r.json()
