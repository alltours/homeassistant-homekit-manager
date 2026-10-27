"""Release policy: production HomeKit writes remain unavailable in 0.9.24."""

WRITE_LOCK_REASON = (
    "HomeKit-Änderungen sind in Version 0.9.24 gesperrt. "
    "Entwürfe, Vorschau und Export bleiben verfügbar. "
    "Ein unbekannter Aktivierungsstatus wird nicht automatisch wiederholt oder bestätigt."
)


def write_policy() -> dict:
    """Expose the same immutable policy to every backend and frontend caller."""
    return {"enabled": False, "reason": WRITE_LOCK_REASON, "automatic_retry": False}
