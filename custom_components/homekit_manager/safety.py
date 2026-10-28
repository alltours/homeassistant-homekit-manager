"""Fail-closed policy for legacy writes and ungranted operations."""

WRITE_LOCK_REASON = (
    "HomeKit-Änderungen benötigen eine lokale, befristete und Bridge-gebundene Schreibfreigabe. "
    "Ohne diese Freigabe bleiben nur Entwurf, Vorschau und Export verfügbar. "
    "Ein unbekannter Apply-Ausgang wird niemals automatisch wiederholt."
)


def write_policy() -> dict:
    """The legacy direct apply route is always disabled; use operation policy."""
    return {"enabled": False, "reason": "Direkter Options-Apply-Pfad ist gesperrt; nur validierte Operationen mit lokaler Freigabe sind möglich.", "automatic_retry": False}
