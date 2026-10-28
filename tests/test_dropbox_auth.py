from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from fpl_showcase.dropbox_auth import (
    exchange_authorization_code,
    load_credentials,
    pkce_authorization,
    refresh_access_token,
    save_credentials,
)
from fpl_showcase.publication import DropboxTransport
from fpl_showcase.errors import ShowcaseError as AuthoringError


class Response:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


class Session:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if not self.responses:
            raise AssertionError("unexpected HTTP call")
        return self.responses.pop(0)


def test_credentials_persist_refresh_token_not_access_token(tmp_path):
    path = tmp_path / "dropbox-auth.json"
    saved = save_credentials("app-key", "refresh-secret", path=path)
    assert saved == path
    value = json.loads(path.read_text(encoding="utf-8"))
    assert value == {
        "app_key": "app-key",
        "provider": "dropbox",
        "refresh_token": "refresh-secret",
        "schema_version": 1,
    }
    assert "access_token" not in value
    assert load_credentials(path)["refresh_token"] == "refresh-secret"
    if os.name != "nt":
        assert path.stat().st_mode & 0o077 == 0


def test_invalid_credential_file_fails_closed_without_echoing_secret(tmp_path):
    path = tmp_path / "dropbox-auth.json"
    secret = "do-not-echo-this-secret"
    path.write_text(json.dumps({"schema_version": 1, "provider": "dropbox", "refresh_token": secret}), encoding="utf-8")
    with pytest.raises(AuthoringError) as exc:
        load_credentials(path)
    assert secret not in str(exc.value)


def test_pkce_authorization_requests_offline_s256_access():
    url, verifier = pkce_authorization("app-key")
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    assert parsed.scheme == "https"
    assert parsed.netloc == "www.dropbox.com"
    assert query["client_id"] == ["app-key"]
    assert query["response_type"] == ["code"]
    assert query["token_access_type"] == ["offline"]
    assert query["code_challenge_method"] == ["S256"]
    expected = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).decode("ascii").rstrip("=")
    assert query["code_challenge"] == [expected]
    assert 43 <= len(verifier) <= 128


def test_authorization_exchange_uses_pkce_and_returns_refresh_token():
    session = Session([Response(payload={
        "access_token": "short-lived",
        "refresh_token": "long-lived",
        "token_type": "bearer",
    })])
    result = exchange_authorization_code("app-key", "one-time-code", "verifier-value", session=session)
    assert result == {"access_token": "short-lived", "refresh_token": "long-lived"}
    url, kwargs = session.calls[0]
    assert url.endswith("/oauth2/token")
    assert kwargs["data"] == {
        "code": "one-time-code",
        "grant_type": "authorization_code",
        "client_id": "app-key",
        "code_verifier": "verifier-value",
    }
    assert "client_secret" not in kwargs["data"]


def test_refresh_mints_short_lived_access_token_without_rotating_persisted_secret():
    session = Session([Response(payload={"access_token": "fresh-access", "token_type": "bearer", "expires_in": 14400})])
    token = refresh_access_token({
        "schema_version": 1,
        "provider": "dropbox",
        "app_key": "app-key",
        "refresh_token": "refresh-secret",
    }, session=session)
    assert token == "fresh-access"
    _, kwargs = session.calls[0]
    assert kwargs["data"] == {
        "grant_type": "refresh_token",
        "refresh_token": "refresh-secret",
        "client_id": "app-key",
    }
    assert "code_verifier" not in kwargs["data"]


def test_refresh_failure_does_not_echo_refresh_token():
    secret = "very-sensitive-refresh-token"
    session = Session([Response(status_code=400, payload={"error": "invalid_grant", "secret": secret})])
    with pytest.raises(AuthoringError) as exc:
        refresh_access_token({
            "schema_version": 1,
            "provider": "dropbox",
            "app_key": "app-key",
            "refresh_token": secret,
        }, session=session)
    assert secret not in str(exc.value)


def test_transport_prefers_persistent_credentials_over_legacy_access_token(tmp_path, monkeypatch):
    path = tmp_path / "dropbox-auth.json"
    save_credentials("app-key", "refresh-secret", path=path)
    monkeypatch.setenv("DROPBOX_ACCESS_TOKEN", "legacy-access")
    session = Session([Response(payload={"access_token": "fresh-access", "token_type": "bearer"})])
    transport = DropboxTransport(allow_network=True, auth_file=path, session=session)
    assert transport._token == "fresh-access"
    assert session.calls[0][1]["data"]["refresh_token"] == "refresh-secret"


def test_transport_legacy_environment_fallback_still_works(tmp_path, monkeypatch):
    missing = tmp_path / "not-configured.json"
    monkeypatch.setenv("FPL_SHOWCASE_DROPBOX_AUTH_FILE", str(missing))
    monkeypatch.setenv("DROPBOX_ACCESS_TOKEN", "legacy-access")
    session = Session([])
    transport = DropboxTransport(allow_network=True, session=session)
    assert transport._token == "legacy-access"
    assert session.calls == []


def test_explicit_missing_auth_file_does_not_silently_ignore_configuration(tmp_path, monkeypatch):
    monkeypatch.setenv("DROPBOX_ACCESS_TOKEN", "legacy-access")
    with pytest.raises(AuthoringError, match="credential file not found"):
        DropboxTransport(allow_network=True, auth_file=tmp_path / "missing.json", session=Session([]))

