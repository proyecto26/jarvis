"""DANTE UI bridge server.

Exposes the Executor over a single WebSocket (protocol v1, see
ui/ARCHITECTURE.md §2 and ui/web/src/protocol.ts).

INVARIANT: importing this package must never require fastapi/google-adk —
heavy imports are guarded in the submodules. ``triforce.server.app`` holds
the ASGI ``app``; ``python -m triforce.server`` runs it on 127.0.0.1:8420.
"""

__all__ = ["protocol"]
