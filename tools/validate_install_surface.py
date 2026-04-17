import argparse
import sys
from pathlib import Path


def collect_artifact_names(paths: list[Path]) -> set[str]:
    names: set[str] = set()
    for root in paths:
        if not root.exists():
            continue
        if root.is_file():
            names.add(root.name)
            continue
        for child in root.rglob("*"):
            if child.is_file():
                names.add(child.name)
    return names


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate that install-facing asset names are documented and actually produced by the build."
    )
    parser.add_argument("--readme", required=True, help="Path to the README to validate.")
    parser.add_argument(
        "--artifacts",
        nargs="+",
        required=True,
        help="Artifact files or directories to scan for built outputs.",
    )
    parser.add_argument(
        "--required-asset",
        action="append",
        dest="required_assets",
        default=[],
        help="Asset filename that must appear in the README and exist in the artifact outputs.",
    )
    args = parser.parse_args()

    readme_path = Path(args.readme).resolve()
    if not readme_path.exists():
        print(f"README not found: {readme_path}", file=sys.stderr)
        return 1

    readme_text = readme_path.read_text(encoding="utf-8", errors="replace")
    artifact_names = collect_artifact_names([Path(item).resolve() for item in args.artifacts])

    failures: list[str] = []
    for asset_name in args.required_assets:
        if asset_name not in readme_text:
            failures.append(f"README is missing install-surface reference for: {asset_name}")
        if asset_name not in artifact_names:
            failures.append(f"Build output is missing required asset: {asset_name}")

    if failures:
        print("Install surface validation failed:", file=sys.stderr)
        for item in failures:
            print(f"- {item}", file=sys.stderr)
        return 1

    for asset_name in args.required_assets:
        print(f"Validated install surface asset: {asset_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
