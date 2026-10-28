"""Generic revision-aware Dropbox publication transport."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Protocol

from .dropbox_auth import (
    default_auth_file,
    load_credentials,
    refresh_access_token,
)
from .errors import ShowcaseError, require


class PublicationTransport(Protocol):
    def read(self, path: str) -> tuple[bytes, str] | None:
        ...

    def add(self, path: str, data: bytes) -> None:
        ...

    def commit(
        self,
        path: str,
        data: bytes,
        previous_revision: str | None,
    ) -> None:
        ...


class DropboxTransport:
    """Explicit Dropbox adapter using refresh-token authentication."""

    def __init__(
        self,
        *,
        allow_network: bool = False,
        auth_file=None,
        token_env: str = "DROPBOX_ACCESS_TOKEN",
        session=None,
        timeout: float = 90,
    ):
        require(
            allow_network,
            "Dropbox publication requires explicit allow_network=True",
        )

        import requests

        self.session = session or requests.Session()
        self.timeout = timeout

        configured = (
            Path(auth_file).expanduser()
            if auth_file
            else default_auth_file()
        )

        if auth_file or configured.exists():
            credentials = load_credentials(configured)
            token = refresh_access_token(
                credentials,
                session=self.session,
                timeout=self.timeout,
            )
        else:
            token = os.environ.get(token_env, "").strip()
            require(
                bool(token),
                "Dropbox credentials unavailable",
            )

        self._token = token

    def _post(self, route, args, data=None):
        headers = {
            "Authorization": "Bearer " + self._token,
            "Dropbox-API-Arg": json.dumps(
                args,
                ensure_ascii=True,
            ),
        }

        if data is not None:
            headers["Content-Type"] = "application/octet-stream"

        try:
            response = self.session.post(
                "https://content.dropboxapi.com/2/files/" + route,
                headers=headers,
                data=data,
                timeout=self.timeout,
                allow_redirects=False,
            )
        except Exception:
            raise ShowcaseError(
                "Dropbox transport failed"
            ) from None

        if response.status_code == 409 and route == "download":
            try:
                missing = (
                    response.json()["error"]["path"][".tag"]
                    == "not_found"
                )
            except (ValueError, KeyError, TypeError):
                missing = False

            if missing:
                return None

        require(
            response.status_code == 200,
            "Dropbox HTTP " + str(response.status_code),
        )

        return response

    def read(self, path: str) -> tuple[bytes, str] | None:
        response = self._post(
            "download",
            {"path": path},
        )

        if response is None:
            return None

        try:
            revision = json.loads(
                response.headers["Dropbox-API-Result"]
            )["rev"]
        except (ValueError, KeyError, TypeError):
            raise ShowcaseError(
                "Invalid Dropbox download envelope"
            ) from None

        require(
            isinstance(revision, str) and bool(revision),
            "Invalid Dropbox revision",
        )

        return response.content, revision

    def _write(
        self,
        path: str,
        data: bytes,
        revision: str | None,
    ) -> None:
        require(
            len(data) <= 150 * 1024 * 1024,
            "Dropbox single upload exceeds 150 MiB",
        )

        mode = (
            "add"
            if revision is None
            else {
                ".tag": "update",
                "update": revision,
            }
        )

        response = self._post(
            "upload",
            {
                "path": path,
                "mode": mode,
                "autorename": False,
                "strict_conflict": True,
                "mute": True,
            },
            data,
        )

        try:
            metadata = response.json()
        except ValueError:
            raise ShowcaseError(
                "Invalid Dropbox upload envelope"
            ) from None

        require(
            isinstance(metadata.get("rev"), str),
            "Missing Dropbox revision",
        )

        require(
            metadata.get("size") == len(data),
            "Dropbox upload size mismatch",
        )

    def add(self, path: str, data: bytes) -> None:
        existing = self.read(path)

        if existing is not None:
            require(
                existing[0] == data,
                "Conflicting immutable remote member",
            )
            return

        self._write(path, data, None)

    def commit(
        self,
        path: str,
        data: bytes,
        previous_revision: str | None,
    ) -> None:
        self._write(
            path,
            data,
            previous_revision,
        )
