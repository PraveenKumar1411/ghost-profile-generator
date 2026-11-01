"""Sherlock-backed digital footprint scanning service."""

import asyncio
import re
import subprocess
import sys
from collections.abc import Awaitable, Callable
from typing import Literal, TypedDict
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from app.config import get_settings


PlatformStatus = Literal["FOUND", "NOT_FOUND", "UNVERIFIED"]


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
    verification_status: dict[str, PlatformStatus]
    verification_reasons: dict[str, str]


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
    "github",
    "reddit",
    "twitter",
    "instagram",
    "linkedin",
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


def _empty_scan_result() -> ScanResult:
    """Create a result with every platform initially unverified."""

    return {
        **{platform_key: False for platform_key in PLATFORM_NAMES.values()},
        "verification_status": {
            platform_key: "UNVERIFIED"
            for platform_key in PLATFORM_NAMES.values()
        },
        "verification_reasons": {},
    }


def _parse_sherlock_output(output: str) -> ScanResult:
    """Convert Sherlock's found-result lines into the API's flat result shape."""

    result = _empty_scan_result()
    for match in FOUND_RESULT_PATTERN.finditer(output):
        platform_name = match.group("platform").strip()
        platform = PLATFORM_KEYS_BY_NAME.get(platform_name.casefold())
        print(f"Sherlock matched platform: {platform_name!r} -> {platform!r}")
        if platform:
            result[platform] = True
            result["verification_status"][platform] = "FOUND"
    print(f"Final parsed Sherlock result: {result}")
    return result


def _detect_profile_with_http(
    platform_key: str,
    username: str,
    timeout: int,
) -> tuple[PlatformStatus, str | None]:
    """Detect a missing Sherlock result using its public profile URL."""

    url = PLATFORM_URL_PATTERNS[platform_key].format(username=username)
    request = Request(url, headers=PROFILE_REQUEST_HEADERS)
    try:
        with urlopen(request, timeout=timeout) as response:
            final_path = urlsplit(response.geturl()).path.rstrip("/").casefold()
            if (
                final_path.startswith("/login")
                or platform_key == "tiktok"
                and final_path == "/in/about"
                or platform_key == "telegram"
                and urlsplit(response.geturl()).netloc.casefold() not in {"t.me", "telegram.me"}
            ):
                print(
                    f"Fallback detector: {platform_key} redirected to a "
                    f"non-profile page ({response.geturl()})"
                )
                if final_path.startswith("/login"):
                    return "UNVERIFIED", "Redirected to Login Page"
                if platform_key == "tiktok":
                    return "UNVERIFIED", "Redirected to generic landing page"
                return "UNVERIFIED", "Redirected away from profile host"
            print(
                f"Fallback detector: {platform_key} returned "
                f"{response.status} after redirect to {response.geturl()}"
            )
            return ("FOUND", None) if response.status == 200 else (
                "UNVERIFIED",
                f"Unexpected HTTP {response.status}",
            )
    except HTTPError as exc:
        print(f"Fallback detector: {platform_key} returned HTTP {exc.code}")
        if exc.code == 404:
            return "NOT_FOUND", "HTTP 404 Not Found"
        if exc.code == 429:
            return "UNVERIFIED", "HTTP 429 Too Many Requests"
        if exc.code == 999:
            return "UNVERIFIED", "HTTP 999 Platform Blocked Request"
        if exc.code in {401, 403}:
            return "UNVERIFIED", f"HTTP {exc.code} Access Restricted"
        return "UNVERIFIED", f"HTTP {exc.code} {exc.reason or 'Request failed'}"
    except TimeoutError:
        return "UNVERIFIED", "Network Timeout"
    except (URLError, OSError) as exc:
        detail = exc.reason if isinstance(exc, URLError) else str(exc)
        return "UNVERIFIED", f"Network failure: {detail}"


async def _detect_unsupported_platform(
    platform_key: str,
    username: str,
    timeout: int,
) -> tuple[PlatformStatus, str | None]:
    """Run a blocking fallback detector without blocking the event loop."""

    return await asyncio.to_thread(
        _detect_profile_with_http,
        platform_key,
        username,
        timeout,
    )


def _apply_platform_result(
    result: ScanResult,
    platform_key: str,
    status: PlatformStatus,
    reason: str | None = None,
) -> None:
    """Apply a verification outcome without conflating uncertainty with absence."""

    result["verification_status"][platform_key] = status
    result[platform_key] = status == "FOUND"
    if status == "UNVERIFIED" and reason:
        result["verification_reasons"][platform_key] = reason
    else:
        result["verification_reasons"].pop(platform_key, None)


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

    result = _empty_scan_result()
    sherlock_reason: str | None = None
    try:
        completed_process = await asyncio.to_thread(
            subprocess.run,
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=settings.sherlock_process_timeout,
        )
    except subprocess.TimeoutExpired:
        sherlock_reason = "Sherlock scan timeout"
    except (FileNotFoundError, OSError) as exc:
        sherlock_reason = f"Sherlock unavailable: {exc}"

    if sherlock_reason is None and completed_process.returncode in (0, 1):
        print(f"Sherlock stdout:\n{completed_process.stdout}")
        print(f"Sherlock stderr:\n{completed_process.stderr}")
        result = _parse_sherlock_output(completed_process.stdout)
        for platform_key in PLATFORM_NAMES.values():
            if result["verification_status"][platform_key] != "FOUND":
                _apply_platform_result(result, platform_key, "NOT_FOUND")
    elif sherlock_reason is None:
        sherlock_reason = (
            f"Sherlock failed with process status {completed_process.returncode}"
        )

    if sherlock_reason:
        for platform_key in PLATFORM_NAMES.values():
            _apply_platform_result(result, platform_key, "UNVERIFIED", sherlock_reason)

    for platform_key in FALLBACK_PLATFORM_KEYS:
        if result["verification_status"][platform_key] != "FOUND":
            detected, reason = await _detect_unsupported_platform(
                platform_key,
                username,
                settings.sherlock_request_timeout,
            )
            _apply_platform_result(result, platform_key, detected, reason)
    print(f"Final scan result: {result}")
    return result


async def scan_username_with_progress(
    username: str,
    on_platform_complete: Callable[[str, bool], Awaitable[None]],
) -> ScanResult:
    """Run one Sherlock site at a time and report durable progress checkpoints."""

    settings = get_settings()
    result = _empty_scan_result()

    for display_name, platform_key in PLATFORM_NAMES.items():
        site_name = SHERLOCK_SITE_NAMES[display_name]
        if site_name is None:
            platform_status, reason = await _detect_unsupported_platform(
                platform_key,
                username,
                settings.sherlock_request_timeout,
            )
            _apply_platform_result(result, platform_key, platform_status, reason)
            await on_platform_complete(display_name, platform_status == "FOUND")
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
        except subprocess.TimeoutExpired:
            _apply_platform_result(result, platform_key, "UNVERIFIED", "Network Timeout")
            await on_platform_complete(display_name, False)
            continue
        except (FileNotFoundError, OSError) as exc:
            _apply_platform_result(
                result, platform_key, "UNVERIFIED", f"Sherlock unavailable: {exc}"
            )
            await on_platform_complete(display_name, False)
            continue

        if completed_process.returncode not in (0, 1):
            error = completed_process.stderr.strip()
            _apply_platform_result(
                result,
                platform_key,
                "UNVERIFIED",
                error or f"Sherlock failed for {display_name}",
            )
            await on_platform_complete(display_name, False)
            continue
        print(f"Sherlock stdout for {display_name}:\n{completed_process.stdout}")
        print(f"Sherlock stderr for {display_name}:\n{completed_process.stderr}")
        parsed = _parse_sherlock_output(completed_process.stdout)
        status_value: PlatformStatus = "FOUND" if parsed[platform_key] else "NOT_FOUND"
        reason = None
        if status_value != "FOUND" and platform_key in FALLBACK_PLATFORM_KEYS:
            status_value, reason = await _detect_unsupported_platform(
                platform_key,
                username,
                settings.sherlock_request_timeout,
            )
        _apply_platform_result(result, platform_key, status_value, reason)
        await on_platform_complete(display_name, status_value == "FOUND")

    return result
