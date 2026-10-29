# Versioned HomeKit capability boundary for 0.10.5

The authoritative source for the entries below is the installed, version-pinned
Home Assistant Core code in `homeassistant/components/homekit/` and
`homeassistant/helpers/entityfilter.py`. The Manager's compatibility result
is a side-effect-free projection. It does not invoke Core's identity-allocating
accessory constructor and cannot prove HAP publication or Apple Home visibility.

| Core | Native SOURCE_USER filter Apply | YAML SOURCE_IMPORT filter Apply | Entity compatibility projection | Broad positive-list migration |
| --- | --- | --- | --- | --- |
| 2026.10.4 | Supported for existing bridge-mode entries, filter-only | Supported for unambiguous direct YAML and direct `!include` when all HomeKit entries are imports | Version-gated Core 2026.10.4 mappings | Only with separate HAP/inventory evidence and explicit migration confirmation |
| 2026.11.0b0 | Supported for existing bridge-mode entries, filter-only | Read-only: Core reload path not validated for this source | Version-gated mappings; ozone and sulphur-dioxide sensor dispatch added | Blocked: HAP migration evidence path not validated on beta |
| Any other version | Blocked | Blocked | Unknown, never reported as zero supported | Blocked |

Core's entity filter and HomeKit's registry gate have separate effects.
`include_entities`, `exclude_entities`, domains and globs determine a
configuration selection. Core then requires runtime states to construct
accessories and normally skips disabled entities; hidden or categorized
entities need an explicit include override. A selected entity can therefore
have no HAP accessory. The Manager reports registry presence, state presence,
availability, compatibility, filter selection and runtime publication
separately. Apple Home visibility requires independent client evidence.

Automatic bulk actions are deliberately stricter than Core's explicit
override rules. They require a present registry entry and state, no
`disabled_by` or `hidden_by`, no technical `entity_category`, a valid linked
device listed as a main or child registry device and a version-verified
`supported` compatibility result. Synthetic composite lookups remain out of
automatic actions. Conditional
compatibility is omitted by default. The backend resolves the full area or
device, checks these facts and blocks forged new includes in the change
planner. Existing includes are not silently removed. Single exclusions can
still be planned explicitly; all writes remain filter-only and require a
separate operation confirmation.

An empty `include_entities` list is not a deny-all policy in Core. The
Manager blocks a positive-list conversion unless it can preserve or prove
the exact published set and protect unobserved future entities. This is
intentionally narrower than the ordinary explicit override writer.

This matrix is valid only for the exact Core builds named above. New Core
releases require a source comparison and isolated contract tests before
their compatibility status or writer gate changes.
