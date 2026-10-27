"""Minimal Microsoft Graph client: app-only auth, paging, throttling, CSV reports."""

import csv
import io
import time

import msal
import requests

GRAPH = "https://graph.microsoft.com/v1.0"
SCOPE = ["https://graph.microsoft.com/.default"]
MAX_RETRIES = 5


class GraphError(Exception):
    def __init__(self, status, code, message, path):
        super().__init__(f"{status} {code} on {path}: {message}")
        self.status = status
        self.code = code
        self.path = path


def load_certificate(pem_path):
    """Return MSAL client_credential from a PEM holding the private key and certificate."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes

    with open(pem_path, "rb") as f:
        pem = f.read()
    cert = x509.load_pem_x509_certificate(pem)
    return {
        "private_key": pem.decode(),
        "thumbprint": cert.fingerprint(hashes.SHA1()).hex(),
    }


class GraphClient:
    def __init__(self, tenant_id, client_id, *, cert_path=None, client_secret=None):
        if cert_path:
            credential = load_certificate(cert_path)
        elif client_secret:
            credential = client_secret
        else:
            raise ValueError("Provide CERT_PATH (preferred) or CLIENT_SECRET")
        try:
            self._app = msal.ConfidentialClientApplication(
                client_id,
                authority=f"https://login.microsoftonline.com/{tenant_id}",
                client_credential=credential,
            )
        except ValueError as e:
            raise RuntimeError(f"Could not reach tenant '{tenant_id}' — check TENANT_ID. ({e})")
        self._session = requests.Session()

    def _token(self):
        result = self._app.acquire_token_for_client(scopes=SCOPE)
        if "access_token" not in result:
            raise RuntimeError(
                f"Auth failed: {result.get('error')}: {result.get('error_description')}"
            )
        return result["access_token"]

    def _request(self, url, params=None):
        for attempt in range(MAX_RETRIES):
            resp = self._session.get(
                url,
                params=params,
                headers={"Authorization": f"Bearer {self._token()}"},
                timeout=60,
            )
            if resp.status_code in (429, 503, 504):
                time.sleep(int(resp.headers.get("Retry-After", 2 ** attempt)))
                continue
            if resp.status_code >= 400:
                try:
                    err = resp.json().get("error", {})
                except ValueError:
                    err = {}
                raise GraphError(
                    resp.status_code,
                    err.get("code", ""),
                    err.get("message", resp.text[:200]),
                    url.replace(GRAPH, ""),
                )
            return resp
        raise GraphError(429, "Throttled", "gave up after retries", url.replace(GRAPH, ""))

    def get(self, path, params=None):
        return self._request(GRAPH + path, params).json()

    def get_all(self, path, params=None):
        """GET a collection, following @odata.nextLink."""
        items = []
        data = self.get(path, params)
        items.extend(data.get("value", []))
        while data.get("@odata.nextLink"):
            data = self._request(data["@odata.nextLink"]).json()
            items.extend(data.get("value", []))
        return items

    def get_report_csv(self, path):
        """Usage reports return CSV (via a redirect to a download URL)."""
        resp = self._request(GRAPH + path)
        text = resp.content.decode("utf-8-sig")
        return list(csv.DictReader(io.StringIO(text)))
