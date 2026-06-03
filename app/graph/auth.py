import time
import msal
from ..config import get_settings

settings = get_settings()

_app = None
_cache = {"token": None, "exp": 0.0}


def _get_app() -> msal.ConfidentialClientApplication:
    """Return a lazily-initialised MSAL ConfidentialClientApplication singleton.

    Using a module-level singleton avoids re-parsing the certificate/secret
    on every token acquisition call.
    """
    global _app
    if _app is None:
        _app = msal.ConfidentialClientApplication(
            client_id=settings.client_id,
            client_credential=settings.client_secret,
            authority=f"https://login.microsoftonline.com/{settings.tenant_id}",
        )
    return _app


def get_token() -> str:
    """App-only (daemon) token via client credentials. Cached until ~60s before expiry."""
    if _cache["token"] and time.time() < _cache["exp"] - 60:
        return _cache["token"]

    result = _get_app().acquire_token_for_client(scopes=[settings.graph_scope])
    if "access_token" not in result:
        raise RuntimeError(
            f"Token acquisition failed: {result.get('error')} - {result.get('error_description')}"
        )
    _cache["token"] = result["access_token"]
    _cache["exp"] = time.time() + int(result.get("expires_in", 3600))
    return _cache["token"]
