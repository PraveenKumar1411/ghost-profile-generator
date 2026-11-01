"""Sherlock-backed digital footprint scanning service."""

import asyncio
import re
import subprocess
import sys
from collections.abc import Awaitable, Callable
from typing import TypedDict
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

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
SHERLOCK_SITE_NAMES = {
    "GitHub": "GitHub",
    "Reddit": "Reddit",
    "Twitter": "Twitter",
    "Instagram": "Instagram",
    "LinkedIn": "LinkedIn",
    "Facebook": None,
    "YouTube": "YouTube",
    "TikTok": "TikTok",
    "Threads": "threads",
    "Telegram": "Telegram",
}
FALLBACK_PLATFORM_KEYS = {
    "instagram",
    "facebook",
    "youtube",
    "tiktok",
    "threads",
    "telegram",
}
PLATFORM_KEYS_BY_NAME = {
    display_name.casefold(): platform_key
    for display_name, platform_key in PLATFORM_NAMES.items()
}
PLATFORM_KEYS_BY_NAME.update(
    {
        "github.com": "github",
        "youtube.com": "youtube",
        "twitter.com": "twitter",
        "x.com": "twitter",
        "instagram.com": "instagram",
        "facebook.com": "facebook",
        "tiktok.com": "tiktok",
        "threads.net": "threads",
        "telegram.me": "telegram",
    }
)
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
FOUND_RESULT_PATTERN = re.compile(
    r"^\s*\[\+\]\s+(?P<platform>[^:]+):\s+\S+",
    re.MULTILINE,
)
PROFILE_REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; GhostProfileGenerator/1.0; "
        "+https://github.com/PraveenKumar1411/ghost-profile-generator)"
    )
}


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
        platform_name = match.group("platform").strip()
        platform = PLATFORM_KEYS_BY_NAME.get(platform_name.casefold())
        print(f"Sherlock matched platform: {platform_name!r} -> {platform!r}")
        if platform:
            result[platform] = True
    print(f"Final parsed Sherlock result: {result}")
    return result


def _detect_profile_with_http(platform_key: str, username: str, timeout: int) -> bool:
    """Detect a missing Sherlock result using its public profile URL."""

    url = PLATFORM_URL_PATTERNS[platform_key].format(username=username)
    request = Request(url, headers=PROFILE_REQUEST_HEADERS)
    try:
        with urlopen(request, timeout=timeout) as response:
            final_path = urlsplit(response.geturl()).path.rstrip("/").casefold()
            if (
                platform_key == "tiktok"
                and final_path == "/in/about"
                or platform_key == "threads"
                and final_path.startswith("/login")
                or platform_key == "telegram"
                and urlsplit(response.geturl()).netloc.casefold() not in {"t.me", "telegram.me"}
            ):
                print(
                    f"Fallback detector: {platform_key} redirected to a "
                    f"non-profile page ({response.geturl()})"
                )
                return False
            print(
                f"Fallback detector: {platform_key} returned "
                f"{response.status} after redirect to {response.geturl()}"
            )
            return response.status == 200
    except HTTPError as exc:
        print(f"Fallback detector: {platform_key} returned HTTP {exc.code}")
        if exc.code == 404:
            return False
        raise SherlockUnavailableError(
            f"Fallback detector failed for {platform_key}: HTTP {exc.code}"
        ) from exc
    except (TimeoutError, URLError, OSError) as exc:
        raise SherlockUnavailableError(
            f"Fallback detector failed for {platform_key}: {exc}"
        ) from exc


async def _detect_unsupported_platform(
    platform_key: str,
    username: str,
    timeout: int,
) -> bool:
    """Run a blocking fallback detector without blocking the event loop."""

    return await asyncio.to_thread(
        _detect_profile_with_http,
        platform_key,
        username,
        timeout,
    )


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
    for site_name in SHERLOCK_SITE_NAMES.values():
        if site_name is not None:
            command.extend(["--site", site_name])

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
    print(f"Sherlock stdout:\n{completed_process.stdout}")
    print(f"Sherlock stderr:\n{completed_process.stderr}")
    result = _parse_sherlock_output(completed_process.stdout)
    for platform_key in FALLBACK_PLATFORM_KEYS:
        if not result[platform_key]:
            result[platform_key] = await _detect_unsupported_platform(
                platform_key,
                username,
                settings.sherlock_request_timeout,
            )
    print(f"Final scan result: {result}")
    return result


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
        site_name = SHERLOCK_SITE_NAMES[display_name]
        if site_name is None or (
            platform_key in FALLBACK_PLATFORM_KEYS and not result[platform_key]
        ):
            found = await _detect_unsupported_platform(
                platform_key,
                username,
                settings.sherlock_request_timeout,
            )
            result[platform_key] = found
            await on_platform_complete(display_name, found)
            continue
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
            site_name,
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
        print(f"Sherlock stdout for {display_name}:\n{completed_process.stdout}")
        print(f"Sherlock stderr for {display_name}:\n{completed_process.stderr}")
        found = _parse_sherlock_output(completed_process.stdout)[platform_key]
        result[platform_key] = found
        await on_platform_complete(display_name, found)

    return result
