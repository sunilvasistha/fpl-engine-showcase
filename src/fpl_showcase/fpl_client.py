"""HTTP client for public and authenticated Fantasy Premier League APIs."""

from __future__ import annotations

from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

DEFAULT_BASE_URL = "https://fantasy.premierleague.com/api"


class IncompleteFetchError(RuntimeError):
    """Raised when a multi-player history fetch cannot be completed."""


class FPLClient:
    """Fetch the public API resources used by the market data layer."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 30.0,
        session: requests.Session | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = session or self._retrying_session()
        self.session.headers.setdefault(
            "User-Agent", "fpl-market-data/2.1 (+local data refresh)"
        )

    @staticmethod
    def _retrying_session() -> requests.Session:
        session = requests.Session()
        retry = Retry(
            total=3,
            connect=3,
            read=3,
            backoff_factor=0.5,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET"}),
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def get_json(self, endpoint: str) -> Any:
        response = self.session.get(
            f"{self.base_url}/{endpoint.strip('/')}/", timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()

    def fetch_bootstrap(self) -> dict[str, Any]:
        payload = self.get_json("bootstrap-static")
        if not isinstance(payload, dict):
            raise TypeError("bootstrap-static response must be a JSON object")
        return payload

    def fetch_fixtures(self) -> list[dict[str, Any]]:
        payload = self.get_json("fixtures")
        if not isinstance(payload, list):
            raise TypeError("fixtures response must be a JSON array")
        return payload

    def fetch_my_team(self, team_id: int, access_token: str) -> dict[str, Any]:
        """Fetch the authenticated current squad and transfer/chip state."""
        if (
            isinstance(team_id, bool)
            or not isinstance(team_id, int)
            or team_id <= 0
        ):
            raise ValueError("team_id must be a positive integer")
        response = self.session.get(
            f"{self.base_url}/my-team/{team_id}/",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise TypeError("my-team response must be a JSON object")
        return payload

    def fetch_entry_picks(
        self, team_id: int, gameweek: int
    ) -> dict[str, Any]:
        """Fetch the public locked 15-player squad for one completed/locked GW."""
        for value, label in ((team_id, "team_id"), (gameweek, "gameweek")):
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{label} must be a positive integer")
        payload = self.get_json(f"entry/{team_id}/event/{gameweek}/picks")
        if not isinstance(payload, dict):
            raise TypeError("entry picks response must be a JSON object")
        return payload

    def fetch_element_summaries(
        self, player_ids: list[int]
    ) -> dict[int, dict[str, Any]]:
        """Fetch one complete element-summary response for every player ID."""
        summaries: dict[int, dict[str, Any]] = {}
        for player_id in player_ids:
            try:
                payload = self.get_json(f"element-summary/{player_id}")
            except requests.RequestException as error:
                raise IncompleteFetchError(
                    f"element-summary fetch failed for player {player_id} "
                    f"after {len(summaries)} of {len(player_ids)} players"
                ) from error
            if not isinstance(payload, dict):
                raise IncompleteFetchError(
                    f"element-summary response for player {player_id} "
                    "must be a JSON object"
                )
            summaries[player_id] = payload
        return summaries
