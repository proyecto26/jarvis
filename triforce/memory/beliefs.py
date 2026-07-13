"""Judge beliefs persistence — read/write judge_beliefs.json.

``judge_beliefs.json`` is the fast runtime store the Judge consults on every
decision. The OKF knowledge bundle (``knowledge/beliefs/``) is the append-only
audit trail: belief documents are superseded (invalidated) rather than
overwritten, and never deleted. OKF writes are additive — failures there are
logged and never break the runtime store.
"""

import json
import logging
from datetime import datetime

from triforce.config import Config

logger = logging.getLogger(__name__)


def load_beliefs() -> list[dict]:
    """Load beliefs from judge_beliefs.json."""
    try:
        data = json.loads(Config.BELIEFS_PATH.read_text())
        return data.get("beliefs", [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_beliefs(beliefs: list[dict]):
    """Save beliefs to judge_beliefs.json."""
    Config.BELIEFS_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = {"beliefs": beliefs}
    Config.BELIEFS_PATH.write_text(json.dumps(data, indent=2))


def add_belief(belief: str, strength: float = 0.5, reason: str = "") -> dict:
    """Add a new belief with strength score and timestamp."""
    beliefs = load_beliefs()
    entry = {
        "belief": belief,
        "strength": strength,
        "reason": reason,
        "created": datetime.utcnow().isoformat(),
        "updated": datetime.utcnow().isoformat(),
    }
    beliefs.append(entry)
    save_beliefs(beliefs)
    # Additive OKF audit trail — must never break the runtime store.
    try:
        _write_belief_doc(
            belief, reason=reason, valid_at=entry["created"], supersedes=None,
            ssgm_score=None, action="Creation",
        )
    except Exception as exc:
        logger.warning("OKF belief doc emission failed (store updated): %s", exc)
    return entry


def update_belief(
    belief: str, strength: float | None = None, reason: str | None = None
) -> dict | None:
    """Update an existing belief by text match. Returns updated belief or None."""
    beliefs = load_beliefs()
    for b in beliefs:
        if b["belief"] == belief:
            if strength is not None:
                b["strength"] = strength
            if reason is not None:
                b["reason"] = reason
            b["updated"] = datetime.utcnow().isoformat()
            save_beliefs(beliefs)
            return b
    return None


def remove_belief(belief: str) -> bool:
    """Remove a belief by text match. Returns True if removed."""
    beliefs = load_beliefs()
    original_len = len(beliefs)
    beliefs = [b for b in beliefs if b["belief"] != belief]
    if len(beliefs) < original_len:
        save_beliefs(beliefs)
        return True
    return False


def supersede_belief(
    old_belief: str,
    new_belief: str,
    reason: str = "",
    ssgm_score: float | None = None,
    strength: float | None = None,
) -> dict:
    """Replace a belief in the runtime store and record the supersede chain in OKF.

    In one call:
    - ``judge_beliefs.json``: the old belief entry is updated in place with the
      new text (unchanged schema); if the old belief is missing, the new one is
      added.
    - OKF ``knowledge/beliefs/``: a new Belief document is written with
      frontmatter ``valid_at``, ``invalidated_at: null``, ``supersedes``
      (bundle-absolute link to the prior belief doc, when found), and
      ``ssgm_score``; the OLD document gains ``invalidated_at``. Documents are
      never deleted — the chain is the audit trail.

    OKF failures are logged and never break the runtime store update.

    Returns a dict with the updated JSON ``belief`` entry plus:
    - ``okf_new_path``: path of the new Belief doc, or None when it could
      not be written at all;
    - ``okf_old_path``: path of the superseded doc (None when none existed);
    - ``okf_old_invalidated``: False when a prior doc exists but could NOT
      be stamped ``invalidated_at`` (partial supersede — the new doc IS on
      disk; the next supersede of this belief text retries the stamp).
    """
    now = datetime.utcnow().isoformat()
    beliefs = load_beliefs()
    entry = None
    for b in beliefs:
        if b["belief"] == old_belief:
            b["belief"] = new_belief
            if strength is not None:
                b["strength"] = strength
            b["reason"] = reason
            b["updated"] = now
            entry = b
            break
    if entry is None:
        entry = {
            "belief": new_belief,
            "strength": strength if strength is not None else 0.5,
            "reason": reason,
            "created": now,
            "updated": now,
        }
        beliefs.append(entry)
    save_beliefs(beliefs)

    result = {
        "belief": entry,
        "okf_new_path": None,
        "okf_old_path": None,
        "okf_old_invalidated": False,
    }
    try:
        result.update(
            _supersede_belief_docs(old_belief, new_belief, reason, ssgm_score, now)
        )
    except Exception as exc:
        logger.warning("OKF belief supersede failed (store updated): %s", exc)
    return result


def find_current_belief_doc(belief: str):
    """Locate the current (not invalidated) OKF Belief doc for a belief text.

    Returns ``(path, OKFDocument)`` or ``(None, None)``. Import of the OKF
    module is lazy so a missing optional dependency never breaks callers.
    """
    from triforce.memory.okf import OKFBundle

    bundle = OKFBundle()
    for path, doc in bundle.documents("beliefs"):
        if doc.title == belief and not doc.extras.get("invalidated_at"):
            return path, doc
    return None, None


def _write_belief_doc(
    belief: str,
    reason: str,
    valid_at: str,
    supersedes: str | None,
    ssgm_score: float | None,
    action: str,
):
    """Write one OKF Belief document. Returns the path written."""
    from triforce.memory.okf import OKFBundle, OKFDocument

    body_lines = [belief, ""]
    if reason:
        body_lines.extend(["## Reason", "", reason, ""])
    if supersedes:
        body_lines.extend([f"Supersedes [previous belief]({supersedes}).", ""])
    doc = OKFDocument(
        type="Belief",
        title=belief,
        description=reason or None,
        tags=["judge", "belief"],
        timestamp=valid_at,
        extras={
            "valid_at": valid_at,
            "invalidated_at": None,
            "supersedes": supersedes,
            "ssgm_score": ssgm_score,
        },
        body="\n".join(body_lines),
    )
    return OKFBundle().write(doc, "beliefs", action=action)


def _supersede_belief_docs(
    old_belief: str,
    new_belief: str,
    reason: str,
    ssgm_score: float | None,
    now: str,
) -> dict:
    """Write the new Belief doc and invalidate (never delete) the old one.

    The two writes are not atomic. The new doc is written first; if it fails
    the exception propagates (nothing was recorded). If invalidating a prior
    doc then fails, that partial state is NEVER hidden behind a success
    shape: the returned dict carries the real ``okf_new_path`` plus
    ``okf_old_invalidated: False`` and the failure is logged at WARNING.
    Every still-current doc with the old belief text is invalidated — this
    also repairs stragglers left by an earlier partial failure.
    """
    from triforce.memory.okf import OKFBundle
    from triforce.memory.okf import _atomic_write as _okf_atomic_write

    bundle = OKFBundle()
    stale = [
        (path, doc)
        for path, doc in bundle.documents("beliefs")
        if doc.title == old_belief and not doc.extras.get("invalidated_at")
    ]
    old_path = stale[0][0] if stale else None
    supersedes = f"/beliefs/{old_path.name}" if old_path is not None else None
    new_path = _write_belief_doc(
        new_belief, reason=reason, valid_at=now, supersedes=supersedes,
        ssgm_score=ssgm_score, action="Supersede",
    )
    invalidated_all = True
    for path, doc in stale:
        try:
            doc.extras["invalidated_at"] = now
            _okf_atomic_write(path, doc.to_markdown())
        except Exception as exc:
            invalidated_all = False
            logger.warning(
                "OKF belief supersede is PARTIAL: new doc %s was written but "
                "old doc %s could not be invalidated (still marked current): %s",
                new_path,
                path,
                exc,
            )
    return {
        "okf_new_path": new_path,
        "okf_old_path": old_path,
        "okf_old_invalidated": invalidated_all,
    }
