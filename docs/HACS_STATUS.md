# HACS status

The repository follows the current HACS single-integration layout: the only integration is under `custom_components/homekit_manager/`, and `hacs.json` is at repository root.

## Proven cause of the 404

The productive HACS instance is version 2.0.5. Its GitHub authentication is an OAuth token with no repository scopes and read-only access to public information. The repository is now public, so this access model is compatible with HACS.

Therefore the error

`GitHub returned 404 for https://api.github.com/repos/alltours/homeassistant-homekit-manager`

was expected while the repository was private. GitHub returns repository-not-found semantics for an unauthenticated or insufficiently authorized API request; the URL itself was correct.

The repository is now prepared for public HACS validation: the manifest contains documentation, issue-tracker, codeowner, name, domain, version, and IoT-class fields, and the repository includes an MIT license, HACS/Hassfest validation workflows, valid topics, and a brand icon.

## Repository compatibility

The repository has the supported single-integration layout and a root `hacs.json`. The local brand icon satisfies the HACS validation requirement; adding the integration to the central Home Assistant Brands repository remains a separate catalog-submission step.

## Decision

HACS is now an available update channel for the public repository. Do not create a second installation; HACS must take over only after the existing installation and target version have been verified.

Use the documented GitHub-based update process instead: select an existing GitHub release or commit with the authenticated Mac-side GitHub CLI, verify the archive and file hashes, back up the existing Home Assistant integration directory, replace only that directory, and perform a controlled Home Assistant restart only when explicitly planned.

