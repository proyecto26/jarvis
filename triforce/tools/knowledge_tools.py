"""Knowledge base tools — persist agent output to the OKF bundle."""

import logging

logger = logging.getLogger(__name__)


def _normalize_decision_link(ref: str) -> str:
    """Coerce a decision reference into a bundle-absolute link."""
    link = ref if ref.startswith("/") else f"/decisions/{ref}"
    if not link.endswith(".md"):
        link += ".md"
    return link


def write_reflection(
    reflection: str,
    title: str = "",
    decision_refs: list[str] | None = None,
) -> dict:
    """Persist a reflection as an OKF Reflection document.

    Use this after integrating a significant event: pass your synthesized
    reflection and, when known, references to the Decision documents it
    evaluates (filenames like '2026-07-12-approve-deploy.md' or
    bundle-absolute links like '/decisions/2026-07-12-approve-deploy.md').

    Args:
        reflection: The integrated understanding — what happened, what was
            learned, and how it connects to existing beliefs.
        title: Short title for the reflection (optional).
        decision_refs: Decision documents this reflection evaluates (optional).

    Returns:
        A dict with 'status' and, on success, the 'path' of the document.
    """
    try:
        from triforce.memory.okf import OKFBundle, OKFDocument

        links = [_normalize_decision_link(ref) for ref in (decision_refs or [])]

        body_lines = [reflection.strip(), ""]
        if links:
            body_lines.extend(["## Decisions evaluated", ""])
            body_lines.extend(
                f"* [{link.rsplit('/', 1)[-1].removesuffix('.md')}]({link})"
                for link in links
            )
            body_lines.append("")

        first_line = reflection.strip().splitlines()[0] if reflection.strip() else ""
        doc = OKFDocument(
            type="Reflection",
            title=title or "Reflection",
            description=(first_line[:160] or None),
            tags=["reflective"],
            body="\n".join(body_lines),
        )
        path = OKFBundle().write(doc, "reflections", action="Reflection")
        return {"status": "written", "path": str(path)}
    except Exception as exc:
        # Graceful degradation — reflection must not crash the session.
        logger.warning("write_reflection failed: %s", exc)
        return {"status": "error", "detail": str(exc)}
