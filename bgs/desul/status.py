"""Read model for the desulphurisation stage."""

from __future__ import annotations

from typing import Any, Mapping

from ..versioning.facade import VersionedArtifacts

OUTLET_KIND = "desul.outlet"
VERIFIED_KIND = "desul.verified"
SUBJECT = "desul"


def compose_status(
    state: Mapping[str, Any],
    *,
    versions: VersionedArtifacts,
    now: int,
) -> dict[str, Any]:
    """Summarise the outlet together with its confirmation state."""

    desul = state.get("desul") if isinstance(state, Mapping) else None
    outlet = desul.get("outlet") if isinstance(desul, Mapping) else None
    verified = desul.get("verified") if isinstance(desul, Mapping) else None
    return {
        "verified": bool(verified.get("active", False)) if isinstance(verified, Mapping) else False,
        "sulfur_ppm": outlet.get("sulfur_ppm") if isinstance(outlet, Mapping) else None,
        "outlet_ok": bool(outlet.get("ok", False)) if isinstance(outlet, Mapping) else False,
        "generation": versions.current_generation(SUBJECT),
        "confirmation": versions.confirmation_state(SUBJECT, now=now),
        "now": now,
    }
