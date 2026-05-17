import os
import subprocess
import sys
from pathlib import Path


def env_flag_enabled(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


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
    ]

    if env_flag_enabled("RUN_LIVE_WEATHER_TESTS"):
        command.extend(
            [
                "--tracing=retain-on-failure",
                "--screenshot=only-on-failure",
                "--output=reports/traces",
            ]
        )

    return subprocess.call(command)


if __name__ == "__main__":
    raise SystemExit(main())
