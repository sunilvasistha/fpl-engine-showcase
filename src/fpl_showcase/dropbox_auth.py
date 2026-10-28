"""Persistent Dropbox OAuth credentials for explicit local publication.

Only the long-lived refresh token and app identity are persisted. Short-lived
access tokens exist in memory only and are never written into runtime evidence,
bundles or publication metadata.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
from pathlib import Path
from urllib.parse import urlencode

from .errors import ShowcaseError as AuthoringError, require

AUTH_SCHEMA = 1
AUTH_PROVIDER = "dropbox"
AUTH_ENV = "FPL_SHOWCASE_DROPBOX_AUTH_FILE"
TOKEN_URL = "https://api.dropboxapi.com/oauth2/token"
AUTHORIZE_URL = "https://www.dropbox.com/oauth2/authorize"


def default_auth_file() -> Path:
    """Return the private per-user Dropbox credential path.

    An explicit FPL_SHOWCASE_DROPBOX_AUTH_FILE wins. Otherwise use the normal OS config
    directory so credentials do not live in the repository or runtime bundle.
    """
    override = os.environ.get(AUTH_ENV, "").strip()
    if override:
        return Path(override).expanduser()
    if os.name == "nt":
        root = os.environ.get("APPDATA", "").strip()
        base = Path(root) if root else Path.home() / "AppData" / "Roaming"
    else:
        xdg = os.environ.get("XDG_CONFIG_HOME", "").strip()
        base = Path(xdg).expanduser() if xdg else Path.home() / ".config"
    return base / "fpl-engine-showcase" / "dropbox-auth.json"


def _nonempty(value, label: str) -> str:
    value = str(value or "").strip()
    require(bool(value), f"Dropbox {label} is required")
    return value


def validate_credentials(value: object) -> dict[str, str | int]:
    require(isinstance(value, dict), "invalid Dropbox credential file")
    require(value.get("schema_version") == AUTH_SCHEMA, "unsupported Dropbox credential schema")
    require(value.get("provider") == AUTH_PROVIDER, "invalid Dropbox credential provider")
    allowed = {"schema_version", "provider", "app_key", "refresh_token", "app_secret"}
    require(set(value) <= allowed, "unexpected Dropbox credential field")
    result: dict[str, str | int] = {
        "schema_version": AUTH_SCHEMA,
        "provider": AUTH_PROVIDER,
        "app_key": _nonempty(value.get("app_key"), "app key"),
        "refresh_token": _nonempty(value.get("refresh_token"), "refresh token"),
    }
    if value.get("app_secret") is not None:
        result["app_secret"] = _nonempty(value.get("app_secret"), "app secret")
    return result


def load_credentials(path: str | Path | None = None) -> dict[str, str | int]:
    path = Path(path).expanduser() if path else default_auth_file()
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise AuthoringError(f"Dropbox credential file not found: {path}") from None
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise AuthoringError(f"Dropbox credential file is unreadable: {path}") from None
    return validate_credentials(value)


def save_credentials(
    app_key: str,
    refresh_token: str,
    *,
    path: str | Path | None = None,
    app_secret: str | None = None,
) -> Path:
    """Atomically persist long-lived credentials with best-effort private mode."""
    destination = Path(path).expanduser() if path else default_auth_file()
    value: dict[str, object] = {
        "schema_version": AUTH_SCHEMA,
        "provider": AUTH_PROVIDER,
        "app_key": _nonempty(app_key, "app key"),
        "refresh_token": _nonempty(refresh_token, "refresh token"),
    }
    if app_secret:
        value["app_secret"] = _nonempty(app_secret, "app secret")
    validate_credentials(value)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".tmp")
    try:
        temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        try:
            os.chmod(temporary, 0o600)
        except OSError:
            pass
        os.replace(temporary, destination)
        try:
            os.chmod(destination, 0o600)
        except OSError:
            pass
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
    return destination


def _token_response(response, context: str) -> dict:
    require(getattr(response, "status_code", None) == 200, f"Dropbox OAuth {context} failed")
    try:
        value = response.json()
    except (ValueError, TypeError):
        raise AuthoringError(f"invalid Dropbox OAuth {context} response") from None
    require(isinstance(value, dict), f"invalid Dropbox OAuth {context} response")
    return value


def refresh_access_token(credentials: dict, *, session=None, timeout: float = 30.0) -> str:
    """Mint one short-lived access token from a persisted refresh token."""
    credentials = validate_credentials(credentials)
    import requests

    client = session or requests.Session()
    data = {
        "grant_type": "refresh_token",
        "refresh_token": credentials["refresh_token"],
        "client_id": credentials["app_key"],
    }
    if credentials.get("app_secret"):
        data["client_secret"] = credentials["app_secret"]
    try:
        response = client.post(TOKEN_URL, data=data, timeout=timeout, allow_redirects=False)
    except Exception:
        raise AuthoringError("Dropbox OAuth refresh failed") from None
    value = _token_response(response, "refresh")
    token = _nonempty(value.get("access_token"), "OAuth access token")
    token_type = str(value.get("token_type") or "bearer").casefold()
    require(token_type == "bearer", "unexpected Dropbox OAuth token type")
    return token


def pkce_authorization(app_key: str) -> tuple[str, str]:
    """Create a no-redirect Dropbox offline PKCE authorization URL and verifier."""
    app_key = _nonempty(app_key, "app key")
    verifier = secrets.token_urlsafe(64).rstrip("=")
    # token_urlsafe produces RFC3986-safe characters and comfortably satisfies
    # Dropbox/OAuth's 43..128 verifier length requirement.
    require(43 <= len(verifier) <= 128, "invalid generated PKCE verifier")
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    query = urlencode({
        "client_id": app_key,
        "response_type": "code",
        "token_access_type": "offline",
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    })
    return AUTHORIZE_URL + "?" + query, verifier


def exchange_authorization_code(
    app_key: str,
    code: str,
    verifier: str,
    *,
    session=None,
    timeout: float = 30.0,
) -> dict[str, str]:
    """Exchange one PKCE authorization code for a long-lived refresh token."""
    app_key = _nonempty(app_key, "app key")
    code = _nonempty(code, "authorization code")
    verifier = _nonempty(verifier, "PKCE verifier")
    import requests

    client = session or requests.Session()
    try:
        response = client.post(
            TOKEN_URL,
            data={
                "code": code,
                "grant_type": "authorization_code",
                "client_id": app_key,
                "code_verifier": verifier,
            },
            timeout=timeout,
            allow_redirects=False,
        )
    except Exception:
        raise AuthoringError("Dropbox OAuth authorization exchange failed") from None
    value = _token_response(response, "authorization exchange")
    result = {
        "access_token": _nonempty(value.get("access_token"), "OAuth access token"),
        "refresh_token": _nonempty(value.get("refresh_token"), "OAuth refresh token"),
    }
    token_type = str(value.get("token_type") or "bearer").casefold()
    require(token_type == "bearer", "unexpected Dropbox OAuth token type")
    return result

