#!/usr/bin/env python3
# <bitbar.title>DisChargeRate</bitbar.title>
# <bitbar.version>1.0.0</bitbar.version>
# <bitbar.author>StavrUA</bitbar.author>
# <bitbar.author.github>StavrUA</bitbar.author.github>
# <bitbar.desc>Shows battery discharge rate in X%/hr in the menu bar.</bitbar.desc>
# <bitbar.abouturl>https://github.com/StavrUA/dchrate</bitbar.abouturl>
"""SwiftBar plugin showing the average battery discharge rate over 30 days."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

HISTORY_DAYS = 30
HISTORY_SECONDS = HISTORY_DAYS * 24 * 60 * 60
DEFAULT_HISTORY_FILE = (
    Path.home() / "Library" / "Application Support" / "SwiftBar" / "dchrate-history.json"
)


def battery_status() -> tuple[int, bool]:
    """Return (percentage, is_charging) from macOS's pmset output."""
    output = subprocess.check_output(["pmset", "-g", "batt"], text=True)
    match = re.search(r"(\d+)%", output)
    if not match:
        raise RuntimeError("pmset did not report a battery percentage")

    state_match = re.search(r"\b(AC Power|Battery Power)\b", output)
    is_charging = "AC Power" in output and not re.search(r"\bdischarging\b", output, re.I)
    if state_match and state_match.group(1) == "Battery Power":
        is_charging = False
    return int(match.group(1)), is_charging


def history_path() -> Path:
    configured_path = os.environ.get("DCHRATE_HISTORY_FILE")
    return Path(configured_path).expanduser() if configured_path else DEFAULT_HISTORY_FILE


def load_history(path: Path) -> list[dict[str, Any]]:
    try:
        entries = json.loads(path.read_text())
    except FileNotFoundError:
        return []
    except (OSError, json.JSONDecodeError):
        return []
    return entries if isinstance(entries, list) else []


def save_history(path: Path, history: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    temporary_path.write_text(json.dumps(history, separators=(",", ":")) + "\n")
    temporary_path.replace(path)


def add_sample(
    history: list[dict[str, Any]], now: float, percentage: int, is_charging: bool
) -> list[dict[str, Any]]:
    cutoff = now - HISTORY_SECONDS
    retained = [
        entry
        for entry in history
        if isinstance(entry, dict)
        and isinstance(entry.get("timestamp"), (int, float))
        and entry["timestamp"] >= cutoff
    ]
    retained.append(
        {"timestamp": now, "percentage": percentage, "charging": is_charging}
    )
    return retained


def discharge_rate(history: list[dict[str, Any]]) -> float | None:
    samples = [
        entry
        for entry in history
        if entry.get("charging") is False
        and isinstance(entry.get("timestamp"), (int, float))
        and isinstance(entry.get("percentage"), (int, float))
    ]
    samples.sort(key=lambda entry: entry["timestamp"])
    if len(samples) < 2:
        return None

    elapsed_hours = (samples[-1]["timestamp"] - samples[0]["timestamp"]) / 3600
    if elapsed_hours <= 0:
        return None
    return max(0.0, (samples[0]["percentage"] - samples[-1]["percentage"]) / elapsed_hours)


def format_rate(rate: float | None) -> str:
    return "--%/hr" if rate is None else f"{rate:.1f}%/hr"


def print_menu(
    percentage: int, is_charging: bool, rate: float | None, history: list[dict[str, Any]]
) -> None:
    status = "Charging" if is_charging else "Discharging"
    print(f"Charging {percentage}%" if is_charging else format_rate(rate))
    print("---")
    print(f"Battery: {percentage}%")
    print(f"Status: {status}")
    print(f"30-day average discharge: {format_rate(rate)}")
    print(f"Samples: {len(history)}")
    print("---")
    print("History is stored locally for 30 days.")


def main() -> int:
    try:
        percentage, is_charging = battery_status()
        now = time.time()
        path = history_path()
        history = add_sample(load_history(path), now, percentage, is_charging)
        save_history(path, history)
        print_menu(percentage, is_charging, discharge_rate(history), history)
        return 0
    except (OSError, subprocess.CalledProcessError, RuntimeError) as error:
        print("Battery unavailable")
        print("---")
        print(f"Error: {error}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
