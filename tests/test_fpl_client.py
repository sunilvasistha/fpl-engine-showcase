from __future__ import annotations

import unittest
from typing import Any

from fpl_showcase.fpl_client import FPLClient


class FakeResponse:
    def __init__(self, payload: Any) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        pass

    def json(self) -> Any:
        return self.payload


class FakeSession:
    def __init__(self, payload: Any) -> None:
        self.headers: dict[str, str] = {}
        self.payload = payload
        self.calls: list[dict[str, Any]] = []

    def get(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"url": url, **kwargs})
        return FakeResponse(self.payload)


class FPLClientTests(unittest.TestCase):
    def test_my_team_uses_bearer_header_only_for_authenticated_request(self) -> None:
        session = FakeSession({"picks": [], "transfers": {}, "chips": []})
        client = FPLClient(
            session=session,  # type: ignore[arg-type]
            base_url="https://fantasy.premierleague.com/api",
            timeout=17,
        )

        payload = client.fetch_my_team(123456, "access-secret")

        self.assertEqual(payload["picks"], [])
        self.assertEqual(
            session.calls,
            [
                {
                    "url": (
                        "https://fantasy.premierleague.com/api/"
                        "my-team/123456/"
                    ),
                    "headers": {"Authorization": "Bearer access-secret"},
                    "timeout": 17,
                }
            ],
        )
        self.assertNotIn("Authorization", session.headers)

    def test_entry_picks_uses_public_gameweek_specific_endpoint(self) -> None:
        session = FakeSession(
            {"picks": [], "active_chip": None, "entry_history": {"event": 5}}
        )
        client = FPLClient(
            session=session,  # type: ignore[arg-type]
            base_url="https://fantasy.premierleague.com/api",
            timeout=17,
        )

        payload = client.fetch_entry_picks(123456, 5)

        self.assertEqual(payload["active_chip"], None)
        self.assertEqual(
            session.calls,
            [
                {
                    "url": (
                        "https://fantasy.premierleague.com/api/"
                        "entry/123456/event/5/picks/"
                    ),
                    "timeout": 17,
                }
            ],
        )

    def test_entry_picks_rejects_invalid_identity_before_request(self) -> None:
        session = FakeSession({})
        client = FPLClient(session=session)  # type: ignore[arg-type]

        with self.assertRaises(ValueError):
            client.fetch_entry_picks(0, 5)
        with self.assertRaises(ValueError):
            client.fetch_entry_picks(123456, 0)

        self.assertEqual(session.calls, [])

    def test_my_team_rejects_invalid_team_id_before_request(self) -> None:
        session = FakeSession({})
        client = FPLClient(session=session)  # type: ignore[arg-type]

        with self.assertRaises(ValueError):
            client.fetch_my_team(0, "access-secret")

        self.assertEqual(session.calls, [])


if __name__ == "__main__":
    unittest.main()

