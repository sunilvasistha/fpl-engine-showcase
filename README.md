# FPL Decision Engine - Engineering Showcase

A selected engineering showcase from a larger Fantasy Premier League analytics and decision-support system.

The full project ingests football data, manages changing state, evaluates multi-step decisions and produces reproducible recommendations. This repository focuses on the underlying software-engineering infrastructure rather than the proprietary decision methodology.

## Engineering highlights

- Resilient HTTP API integration with retry and timeout handling
- Public and authenticated Fantasy Premier League API access
- OAuth 2.0 PKCE flow with persistent refresh-token support
- Defensive credential handling and secret-conscious failure paths
- Deterministic dependency-graph execution
- Topological ordering and cycle validation
- Canonical JSON serialization and integrity checks
- Immutable persistence with atomic no-replace writes
- Revision-aware remote publication
- Automated regression and edge-case testing

The complete private system currently contains **2,000+ automated tests**. This public showcase contains a smaller representative test suite covering the components included here.

## Architecture

At a high level, the full system follows:

```text
External football data
        |
        v
Data acquisition
        |
        v
Validation / normalisation
        |
        v
Dependency-driven computation
        |
        v
Domain evaluation
        |
        v
Decision output
        |
        v
Immutable persistence / publication

```

See [`docs/architecture.md`](docs/architecture.md) for more detail.

## Included components

### FPL API client

`fpl_client.py` provides a defensive client around public and authenticated Fantasy Premier League endpoints, including validation, retries and bounded request timeouts.

### OAuth integration

`dropbox_auth.py` implements PKCE authorization and refresh-token-based authentication while keeping short-lived access tokens out of persisted state.

### Dependency graph

`dependency_graph.py` demonstrates the deterministic execution model used to order dependent computations and reject invalid or cyclic graphs.

### Immutable persistence

`immutable_io.py` provides canonical serialization and atomic installation of immutable state, including protection against accidental replacement or malformed persisted data.

### Remote publication

`publication.py` demonstrates revision-aware publication and conflict handling for external storage.

## Scope of this repository

This is intentionally a **portfolio subset**, not a runnable copy of the complete decision engine.

Domain-specific ranking models, player valuation, forecasting, transfer optimisation, decision policies, calibrated parameters, production datasets and live manager state remain in the private project.

## Running the tests

Requires Python 3.11+.

```powershell
py -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python -m pytest -q
```

Current showcase suite:

```text
21 passed
```

## Repository structure

```text
src/fpl_showcase/
    fpl_client.py
    dropbox_auth.py
    publication.py
    immutable_io.py
    dependency_graph.py
    errors.py
    json_utils.py

tests/
examples/
docs/
```

## Development

The larger project has been developed iteratively with extensive automated testing and AI-assisted implementation using OpenAI Codex, with architecture, requirements and system invariants defined and reviewed by the project author.

(c) 2026 Sunil Vasistha. No license is granted for commercial reuse.