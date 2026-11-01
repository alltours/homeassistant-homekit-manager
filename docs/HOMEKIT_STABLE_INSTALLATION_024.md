# HomeKit Manager 0.10.24 – Installation

1. Install the repository through HACS as a custom repository of type
   `Integration`.
2. Restart the isolated Home Assistant instance when HACS requests it.
3. Add `HomeKit Manager` through Settings → Devices & services.
4. Open the administrator-only HomeKit Manager panel.

The integration requires the official Home Assistant Core and the pinned
`ruamel.yaml==0.18.17` runtime dependency. No experimental Core patch,
migration journal or pairing file is installed.

The first-run product is read-only until an administrator deliberately creates
the separate, narrow filter-write authority. Native UI↔YAML migration remains
unavailable.
