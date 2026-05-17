import subprocess
import sys
from pathlib import Path


def main() -> int:
    reports_dir = Path("reports")
    reports_dir.mkdir(parents=True, exist_ok=True)

    command = [
        sys.executable,
        "-m",
        "pytest",
        "tests",
        "--html=reports/report.html",
        "--self-contained-html",
        "--tracing=retain-on-failure",
        "--screenshot=only-on-failure",
        "--output=reports/traces",
    ]

    return subprocess.call(command)


if __name__ == "__main__":
    raise SystemExit(main())
