"""Sherlock-backed digital footprint scanning service."""

import asyncio
import re
import subprocess
import sys
from collections.abc import Awaitable, Callable
from typing import TypedDict

from app.config import get_settings


class ScanResult(TypedDict):
    """Social-platform presence flags returned by a scanner."""

    github: bool
    reddit: bool
    twitter: bool
    instagram: bool
    linkedin: bool
    facebook: bool
    youtube: bool
    tiktok: bool
    threads: bool
    telegram: bool


class SherlockScanError(RuntimeError):
    """Base error for Sherlock execution failures."""


class SherlockUnavailableError(SherlockScanError):
    """Raised when Sherlock cannot be started or is not installed."""


class SherlockTimeoutError(SherlockScanError):
    """Raised when Sherlock exceeds the configured execution timeout."""


PLATFORM_NAMES = {
    "GitHub": "github",
    "Reddit": "reddit",
    "Twitter": "twitter",
    "Instagram": "instagram",
    "LinkedIn": "linkedin",
    "Facebook": "facebook",
    "YouTube": "youtube",
    "TikTok": "tiktok",
    "Threads": "threads",
    "Telegram": "telegram",
}
PLATFORM_URL_PATTERNS = {
    "github": "https://github.com/{username}",
    "reddit": "https://www.reddit.com/user/{username}",
    "twitter": "https://x.com/{username}",
    "instagram": "https://www.instagram.com/{username}",
    "linkedin": "https://www.linkedin.com/in/{username}",
    "facebook": "https://www.facebook.com/{username}",
    "youtube": "https://www.youtube.com/@{username}",
    "tiktok": "https://www.tiktok.com/@{username}",
    "threads": "https://www.threads.net/@{username}",
    "telegram": "https://t.me/{username}",
}
FOUND_RESULT_PATTERN = re.compile(r"^\[\+\]\s+(?P<platform>[^:]+):\s+\S+", re.MULTILINE)


def _parse_sherlock_output(output: str) -> ScanResult:
    """Convert Sherlock's found-result lines into the API's flat result shape."""

    result: ScanResult = {
        "github": False,
        "reddit": False,
        "twitter": False,
        "instagram": False,
        "linkedin": False,
        "facebook": False,
        "youtube": False,
        "tiktok": False,
        "threads": False,
        "telegram": False,
    }
    for match in FOUND_RESULT_PATTERN.finditer(output):
        platform = PLATFORM_NAMES.get(match.group("platform").strip())
        if platform is not None:
            result[platform] = True
    return result


async def scan_username(username: str) -> ScanResult:
    """Run Sherlock for a username and return supported platform matches."""

    settings = get_settings()
    command = [
        sys.executable,
        "-m",
        "sherlock_project.sherlock",
        username,
        "--no-color",
        "--print-found",
        "--timeout",
        str(settings.sherlock_request_timeout),
    ]
    for platform in PLATFORM_NAMES:
        command.extend(["--site", platform])

    try:
        completed_process = await asyncio.to_thread(
            subprocess.run,
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=settings.sherlock_process_timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise SherlockTimeoutError(
            "Sherlock scan exceeded the configured timeout"
        ) from exc
    except (FileNotFoundError, OSError) as exc:
        raise SherlockUnavailableError(
            "Sherlock is not available in the backend environment"
        ) from exc

    if completed_process.returncode not in (0, 1):
        error = completed_process.stderr.strip()
        raise SherlockUnavailableError(
            f"Sherlock failed to complete the scan: {error or 'unknown error'}"
        )
    return _parse_sherlock_output(completed_process.stdout)


async def scan_username_with_progress(
    username: str,
    on_platform_complete: Callable[[str, bool], Awaitable[None]],
) -> ScanResult:
    """Run one Sherlock site at a time and report durable progress checkpoints."""

    settings = get_settings()
    result: ScanResult = {
        "github": False,
        "reddit": False,
        "twitter": False,
        "instagram": False,
        "linkedin": False,
        "facebook": False,
        "youtube": False,
        "tiktok": False,
        "threads": False,
        "telegram": False,
    }

    for display_name, platform_key in PLATFORM_NAMES.items():
        command = [
            sys.executable,
            "-m",
            "sherlock_project.sherlock",
            username,
            "--no-color",
            "--print-found",
            "--timeout",
            str(settings.sherlock_request_timeout),
            "--site",
            display_name,
        ]
        try:
            completed_process = await asyncio.to_thread(
                subprocess.run,
                command,
                capture_output=True,
                text=True,
                check=False,
                timeout=settings.sherlock_process_timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise SherlockTimeoutError(
                f"Sherlock timed out while checking {display_name}"
            ) from exc
        except (FileNotFoundError, OSError) as exc:
            raise SherlockUnavailableError(
                "Sherlock is not available in the backend environment"
            ) from exc

        if completed_process.returncode not in (0, 1):
            error = completed_process.stderr.strip()
            raise SherlockUnavailableError(
                f"Sherlock failed for {display_name}: {error or 'unknown error'}"
            )
        found = _parse_sherlock_output(completed_process.stdout)[platform_key]
        result[platform_key] = found
        await on_platform_complete(display_name, found)

    return result
