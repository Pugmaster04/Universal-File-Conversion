Git Hooks for Universal File Utility Suite
=========================================

This folder stores repository-local hooks used for automatic historical snapshots.

Required local setup:
1) Set hooks path once per clone:
   git config core.hooksPath .githooks

2) Commit as normal.

Behavior:
- After each commit, post-commit calls:
  tools/create_historical_snapshot.ps1 -Reason post-commit

Result:
- A source snapshot is created under:
  archive/history/v<version>/<timestamp>_post-commit/
