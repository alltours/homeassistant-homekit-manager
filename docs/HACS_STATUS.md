# HACS preparation status

The repository follows the current HACS single-integration layout: the only integration is under `custom_components/homekit_manager/`, and `hacs.json` is at repository root.

The repository is not yet declared HACS-ready. Current HACS publishing requirements also call for `documentation` and `issue_tracker` in `manifest.json`, and repository brand assets. The tested release manifest does not contain those fields and no brand asset is included in the release candidate. Adding them requires a new tested release; this repository must not be added to production HACS before that work is complete.

Private repositories are not treated as publicly published HACS repositories. Access and installation behavior must be validated separately before any HACS use.

