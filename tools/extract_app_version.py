import re
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    app_file = root / "modular_file_utility_suite.py"
    text = app_file.read_text(encoding="utf-8", errors="replace")
    match = re.search(r'^APP_VERSION = "([^"]+)"', text, re.MULTILINE)
    if not match:
        print("APP_VERSION not found in modular_file_utility_suite.py", file=sys.stderr)
        return 1
    print(match.group(1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
