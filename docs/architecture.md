# Architecture

The private system is substantially larger than this showcase. This repository
only demonstrates selected infrastructure patterns.

At a high level, the architecture follows:

```text
External APIs
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

The domain-evaluation and decision-policy implementations are intentionally
excluded from the public repository.

## Components demonstrated here

### HTTP integration

`fpl_client.py` demonstrates typed boundaries around external APIs,
request timeouts, validation and retry behaviour.

### OAuth and credential handling

`dropbox_auth.py` demonstrates PKCE authorization, refresh-token persistence,
short-lived access tokens and defensive handling of authentication failures.

### Dependency execution

`dependency_graph.py` is a domain-neutral extraction of the execution-graph
concept. It performs deterministic topological ordering and rejects malformed
or cyclic graphs.

### Immutable persistence

`immutable_io.py` demonstrates deterministic serialization, atomic installation
and protection against accidental replacement of an occupied immutable slot.

### Publication

`publication.py` demonstrates revision-aware remote storage without exposing
the production package, forecast or decision contracts.
