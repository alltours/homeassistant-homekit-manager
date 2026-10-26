# HACS status

The repository follows the current HACS single-integration layout: the only integration is under `custom_components/homekit_manager/`, and `hacs.json` is at repository root.

## Proven cause of the 404

The productive HACS instance is version 2.0.5. Its GitHub authentication is an OAuth token with no repository scopes and read-only access to public information. The official HACS documentation states that private GitHub repositories cannot be used with HACS because HACS can only retrieve publicly available information.

Therefore the error

`GitHub returned 404 for https://api.github.com/repos/alltours/homeassistant-homekit-manager`

is expected for this private repository. GitHub returns repository-not-found semantics for an unauthenticated or insufficiently authorized API request; the URL itself is correct and the repository is reachable with the authorized GitHub CLI account.

This cannot be repaired by changing `hacs.json`, adding a release tag, changing the integration domain, or adding manifest metadata. Making the repository public would change the required security model and is not part of this project.

## Repository compatibility

The repository has the supported single-integration layout and a root `hacs.json`. It is not currently suitable for official HACS catalog publication because the repository is private and the tested manifest does not yet include the public-catalog metadata and brand assets required for that separate process. No untested manifest change is made here.

## Decision

HACS is not an available update channel for this private repository. Do not retry adding it as a HACS custom repository and do not create a second installation.

Use the documented GitHub-based update process instead: select an existing GitHub release or commit with the authenticated Mac-side GitHub CLI, verify the archive and file hashes, back up the existing Home Assistant integration directory, replace only that directory, and perform a controlled Home Assistant restart only when explicitly planned.

