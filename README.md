# FPL Decision Engine — Engineering Showcase

This repository contains selected, sanitized engineering components from a
larger private football decision-engine project.

The purpose of this repository is to demonstrate software-engineering work,
not to publish the underlying decision methodology or commercial logic.

## What is included

- resilient HTTP API integration
- authenticated and public API access
- retry and timeout handling
- persistent OAuth using PKCE and refresh tokens
- secret-conscious credential handling
- deterministic dependency execution
- cycle and contract validation
- immutable JSON persistence
- atomic no-replace writes
- revision-aware remote publication
- automated tests

## What is deliberately excluded

The private project contains the football evaluation methodology, calibrated
models, player valuation logic, transfer optimisation, forecasting,
decision policies, production data, manager state and other domain-specific
intellectual property.

Those components are intentionally not present here.

## Background

The full private system evolved into a configuration-driven decision engine
with extensive automated testing. It currently contains more than 2,000
automated tests.

This public repository is a deliberately small engineering sample rather than
a runnable clone of the private product.

## Running the tests

```powershell
py -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python -m pytest -q
```

## Repository layout

```text
src/fpl_showcase/
    fpl_client.py
    dropbox_auth.py
    publication.py
    immutable_io.py
    dependency_graph.py

tests/
examples/
docs/
```

See `docs/architecture.md` for the high-level design.
