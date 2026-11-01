# HomeKit Manager 0.10.28 – Security Limits

The stable integration is read-only until an administrator explicitly enables a narrow, bridge-bound write authority. A valid operation also requires the current bridge source, complete revision, server-held operation ID and exact confirmation.

Without a valid grant or isolated test mode:

- no HomeKit filter is written;
- no Config Entry source is changed;
- no bridge is created or deleted;
- no pairing is reset or generated;
- no HAP persistence is modified;
- native UI↔YAML migration is unavailable.

Empty positive lists remain blocked because Home Assistant Core can interpret an empty filter as include-all. Unknown bridges, stale revisions, invalid confirmations, unauthorized users, unknown entities and ambiguous filter configurations fail closed.

The Manager does not claim immutable AIDs/IIDs when a user intentionally changes the published accessory set. Unchanged accessories must retain their identity and the existing pairing must reconnect; an unexpected identity or publication change is a failed operation.
