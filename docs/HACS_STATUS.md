# HACS status

The repository follows the current HACS single-integration layout: the only integration is under `custom_components/homekit_manager/`, and `hacs.json` is at repository root.

## Proven cause of the 404

The productive HACS instance is version 2.0.5. Its GitHub authentication is an OAuth token with no repository scopes and read-only access to public information. The official HACS documentation states that private GitHub repositories cannot be used with HACS because HACS can only retrieve publicly available information.

Therefore the error

`GitHub returned 404 for https://api.github.com/repos/alltours/homeassistant-homekit-manager`

is expected for this private repository. GitHub returns repository-not-found semantics for an unauthenticated or insufficiently authorized API request; the URL itself is correct and the repository is reachable with the authorized GitHub CLI account.

This cannot be repaired while the repository is private. The repository is now prepared for public HACS validation: the manifest contains documentation, issue-tracker, codeowner, name, domain, and version fields, and the repository includes an MIT license plus HACS and Hassfest validation workflows.

## Repository compatibility

The repository has the supported single-integration layout and a root `hacs.json`. Home Assistant Brands remains a separate catalog/publication requirement and must be verified by the validation workflow before any catalog submission.

## Decision

HACS is not an available update channel until the repository is public. Do not retry adding it as a HACS custom repository while it remains private and do not create a second installation.

Use the documented GitHub-based update process instead: select an existing GitHub release or commit with the authenticated Mac-side GitHub CLI, verify the archive and file hashes, back up the existing Home Assistant integration directory, replace only that directory, and perform a controlled Home Assistant restart only when explicitly planned.

