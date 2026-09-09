# Release notes — 2026-06-20 (Release Candidate)

Summary:
- Hotfixes to caching, non-blocking model loads, structural parsing regex, and frontend saliency contract.
- Improved local fallback and offline SMT translation via `backend/app/services/local_smt_translator.py`.
- Added `DISABLE_API_FALLBACK` and `HF_MODEL_ID` environment config for controlled API fallback behavior.
- ONNX migration for Stage 1/2 to improve CPU performance and reduce VRAM dependency.
- Added a manual production smoke-test script and CI workflow snippet for maintainers.

Important notes for maintainers:
- Rotate any exposed tokens and remove secrets from history if needed.
- To run smoke tests locally: `python scripts/production_smoke_test.py` (sets skip_cache=True). Use DISABLE_API_FALLBACK=true for local-only runs.
- CI: set `HUGGINGFACE_API_TOKEN` and `HF_MODEL_ID` in repository secrets to enable the manual smoke job.

Changelog source: docs/CHANGELOG_AI.md
