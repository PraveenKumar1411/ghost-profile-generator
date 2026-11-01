"""Sherlock-backed digital footprint scanning service."""

import asyncio
from html.parser import HTMLParser
import re
import subprocess
import sys
from collections.abc import Awaitable, Callable
from typing import Literal, TypedDict
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from app.config import get_settings


PlatformStatus = Literal["FOUND", "NOT_FOUND", "UNVERIFIED", "BLOCKED"]


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


class _ProfileMetadataParser(HTMLParser):
    """Extract profile identity metadata from server-rendered HTML."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.metadata: dict[str, list[str]] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {name.casefold(): value or "" for name, value in attrs}
        if tag.casefold() == "meta":
            key = attributes.get("property") or attributes.get("name")
            value = attributes.get("content")
            if key and value:
                self.metadata.setdefault(key.casefold(), []).append(value.casefold())
        elif tag.casefold() == "link" and "canonical" in attributes.get("rel", "").casefold():
            href = attributes.get("href")
            if href:
                self.metadata.setdefault("canonical", []).append(href.casefold())


def _profile_metadata(body: str) -> dict[str, list[str]]:
    """Read identity-bearing metadata without relying on visible username text."""

    parser = _ProfileMetadataParser()
    parser.feed(body)
    return parser.metadata


def _metadata_profile_evidence(
    body: str,
    final_url: str,
    username: str,
    expected_path: str,
    allowed_hosts: set[str],
) -> str | None:
    """Return the strongest metadata signal that identifies the requested profile."""

    parsed_final_url = urlsplit(final_url)
    if parsed_final_url.netloc.casefold() not in allowed_hosts:
        return None
    expected_path = expected_path.rstrip("/").casefold()
    metadata = _profile_metadata(body)
    for key in ("canonical", "og:url"):
        for value in metadata.get(key, []):
            parsed_value = urlsplit(value)
            if (
                parsed_value.netloc.casefold() in allowed_hosts
                and parsed_value.path.rstrip("/").casefold() == expected_path
            ):
                return key
    username_marker = f"@{username.casefold()}"
    for key in ("og:title", "og:description", "description", "twitter:title"):
        if any(username_marker in value for value in metadata.get(key, [])):
            return key
    return None


def _log_detection(
    platform_key: str,
    status: int | None,
    final_url: str | None,
    decision: PlatformStatus,
    method: str,
) -> None:
    """Emit the evidence used for a platform decision."""

    print(
        f"Platform detection: platform={platform_key} status={status} "
        f"final_url={final_url} decision={decision} method={method}"
    )


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


def _request_profile(
    platform_key: str,
    username: str,
    timeout: int,
) -> tuple[int, str, str, str] | tuple[None, None, None, None]:
    """Fetch a profile once and return status, final URL, and response body."""

    url = PLATFORM_URL_PATTERNS[platform_key].format(username=username)
    request = Request(url, headers=PROFILE_REQUEST_HEADERS)
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read(65536).decode("utf-8", errors="ignore").casefold()
            return response.status, response.url, body, url
    except HTTPError as exc:
        return exc.code, exc.url, "", url
    except TimeoutError:
        return None, None, "Network Timeout", url
    except (URLError, OSError) as exc:
        detail = exc.reason if isinstance(exc, URLError) else str(exc)
        return None, None, f"Network failure: {detail}", url


def _request_threads_canonical(
    username: str,
    timeout: int,
) -> tuple[int, str, str, str] | tuple[None, None, None, None]:
    """Fetch Threads' canonical profile URL for login-redirect recovery."""

    url = f"https://www.threads.com/@{username}/"
    request = Request(url, headers=PROFILE_REQUEST_HEADERS)
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read(65536).decode("utf-8", errors="ignore").casefold()
            return response.status, response.url, body, url
    except HTTPError as exc:
        return exc.code, exc.url, "", url
    except TimeoutError:
        return None, None, "Network Timeout", url
    except (URLError, OSError) as exc:
        detail = exc.reason if isinstance(exc, URLError) else str(exc)
        return None, None, f"Network failure: {detail}", url


def _blocked_response(status: int, final_url: str, body: str) -> str | None:
    """Return a block reason for common rate-limit, WAF, and login responses."""

    path = urlsplit(final_url).path.casefold()
    if status == 429:
        return "HTTP 429 Too Many Requests"
    if status == 999:
        return "HTTP 999 Platform Blocked Request"
    if status in {401, 403}:
        return f"HTTP {status} Access Restricted"
    if path.startswith("/challenge"):
        return "Redirected to Challenge Page"
    for marker, description in (
        ("captcha", "captcha marker"),
        ("challenge-running", "challenge-running marker"),
        ("cf-chl-", "Cloudflare challenge marker"),
        ("rate limit", "rate-limit marker"),
    ):
        if marker in body:
            return f"Anti-bot protection detected ({description})"
    return None


def _login_wall_response(final_url: str) -> str | None:
    """Identify a login wall without treating it as proof of absence or blocking."""

    path = urlsplit(final_url).path.casefold()
    if path.startswith(("/login", "/accounts/login", "/signin", "/sign-in")):
        return "Login Required"
    return None


def _validate_github(username: str, timeout: int) -> tuple[PlatformStatus, str | None]:
    return _validate_path_profile(
        "github",
        username,
        timeout,
        {"github.com"},
        f"/{username.casefold()}",
        inspect_body=False,
    )


def _validate_reddit(username: str, timeout: int) -> tuple[PlatformStatus, str | None]:
    return _validate_path_profile(
        "reddit", username, timeout, {"reddit.com", "www.reddit.com"}, f"/user/{username.casefold()}"
    )


def _validate_twitter(username: str, timeout: int) -> tuple[PlatformStatus, str | None]:
    return _validate_path_profile("twitter", username, timeout, {"x.com", "www.x.com", "twitter.com"}, f"/{username.casefold()}")


def _validate_instagram(username: str, timeout: int) -> tuple[PlatformStatus, str | None]:
    status, final_url, body, _ = _request_profile("instagram", username, timeout)
    if status is None:
        _log_detection("instagram", status, final_url, "UNVERIFIED", "network result")
        return "UNVERIFIED", body
    if status == 404:
        _log_detection("instagram", status, final_url, "NOT_FOUND", "HTTP 404")
        return "NOT_FOUND", "HTTP 404 Not Found"
    login_wall = _login_wall_response(final_url)
    if login_wall:
        _log_detection("instagram", status, final_url, "UNVERIFIED", "login redirect")
        return "UNVERIFIED", login_wall
    blocked = _blocked_response(status, final_url, body)
    if blocked:
        _log_detection("instagram", status, final_url, "BLOCKED", blocked)
        return "BLOCKED", blocked
    path = urlsplit(final_url).path.rstrip("/").casefold()
    if status in {200, 301, 302} and path == f"/{username.casefold()}":
        method = _metadata_profile_evidence(
            body,
            final_url,
            username,
            f"/{username}",
            {"instagram.com", "www.instagram.com"},
        )
        if method:
            _log_detection("instagram", status, final_url, "FOUND", method)
            return "FOUND", None
        _log_detection("instagram", status, final_url, "UNVERIFIED", "no profile metadata")
        return "UNVERIFIED", "HTTP 200 profile metadata could not be confirmed"
    _log_detection("instagram", status, final_url, "UNVERIFIED", "unexpected redirect")
    return "UNVERIFIED", f"Unexpected redirect to {final_url}"


def _validate_linkedin(username: str, timeout: int) -> tuple[PlatformStatus, str | None]:
    return _validate_path_profile("linkedin", username, timeout, {"linkedin.com", "www.linkedin.com"}, f"/in/{username.casefold()}")


def _validate_facebook(username: str, timeout: int) -> tuple[PlatformStatus, str | None]:
    status, final_url, body, _ = _request_profile("facebook", username, timeout)
    if status is None:
        return "UNVERIFIED", body
    if status == 404:
        return "NOT_FOUND", "HTTP 404 Not Found"
    login_wall = _login_wall_response(final_url)
    if login_wall:
        return "UNVERIFIED", login_wall
    blocked = _blocked_response(status, final_url, body)
    if blocked:
        return "BLOCKED", blocked
    parsed = urlsplit(final_url)
    if parsed.netloc.casefold() not in {"facebook.com", "www.facebook.com"}:
        return "BLOCKED", f"Redirected away from Facebook to {final_url}"
    if status in {200, 301, 302} and parsed.path.rstrip("/").casefold() == f"/{username.casefold()}":
        if username.casefold() in body:
            return "FOUND", None
        return "UNVERIFIED", "HTTP 200 Facebook content could not be confirmed"
    return "UNVERIFIED", f"Unexpected redirect to {final_url}"


def _validate_youtube(username: str, timeout: int) -> tuple[PlatformStatus, str | None]:
    return _validate_path_profile("youtube", username, timeout, { "youtube.com", "www.youtube.com" }, f"/@{username.casefold()}")


def _validate_tiktok(username: str, timeout: int) -> tuple[PlatformStatus, str | None]:
    status, final_url, body, _ = _request_profile("tiktok", username, timeout)
    if status is None:
        _log_detection("tiktok", status, final_url, "UNVERIFIED", "network result")
        return "UNVERIFIED", body
    if status == 404:
        _log_detection("tiktok", status, final_url, "NOT_FOUND", "HTTP 404")
        return "NOT_FOUND", "HTTP 404 Not Found"
    blocked = _blocked_response(status, final_url, body)
    if blocked:
        _log_detection("tiktok", status, final_url, "BLOCKED", blocked)
        return "BLOCKED", blocked
    expected_path = f"/@{username.casefold()}"
    parsed_path = urlsplit(final_url).path.rstrip("/").casefold()
    if status in {200, 301, 302} and parsed_path == expected_path:
        method = _metadata_profile_evidence(
            body,
            final_url,
            username,
            expected_path,
            {"tiktok.com", "www.tiktok.com"},
        )
        if method:
            _log_detection("tiktok", status, final_url, "FOUND", method)
            return "FOUND", None
        _log_detection("tiktok", status, final_url, "UNVERIFIED", "profile metadata unavailable")
        return "UNVERIFIED", "TikTok profile metadata could not be confirmed"
    if parsed_path == "/in/about":
        _log_detection("tiktok", status, final_url, "BLOCKED", "generic TikTok access wall")
        return "BLOCKED", "Redirected to TikTok /in/about; profile access wall or regional restriction"
    _log_detection("tiktok", status, final_url, "UNVERIFIED", "unexpected redirect")
    return "UNVERIFIED", f"Unexpected redirect to {final_url}"


def _validate_threads(username: str, timeout: int) -> tuple[PlatformStatus, str | None]:
    status, final_url, body, _ = _request_profile("threads", username, timeout)
    if status is None:
        _log_detection("threads", status, final_url, "UNVERIFIED", "network result")
        return "UNVERIFIED", body
    if status == 404:
        _log_detection("threads", status, final_url, "NOT_FOUND", "HTTP 404")
        return "NOT_FOUND", "HTTP 404 Not Found"
    blocked = _blocked_response(status, final_url, body)
    if blocked:
        _log_detection("threads", status, final_url, "BLOCKED", blocked)
        return "BLOCKED", blocked
    expected_path = f"/@{username.casefold()}"
    parsed_path = urlsplit(final_url).path.rstrip("/").casefold()
    allowed_hosts = {"threads.net", "www.threads.net", "threads.com", "www.threads.com"}
    if status in {200, 301, 302} and parsed_path == expected_path:
        method = _metadata_profile_evidence(
            body,
            final_url,
            username,
            expected_path,
            allowed_hosts,
        )
        if method:
            _log_detection("threads", status, final_url, "FOUND", method)
            return "FOUND", None
    login_wall = _login_wall_response(final_url)
    if login_wall:
        canonical_status, canonical_url, canonical_body, _ = _request_threads_canonical(
            username,
            timeout,
        )
        canonical_method = (
            _metadata_profile_evidence(
                canonical_body,
                canonical_url,
                username,
                expected_path,
                allowed_hosts,
            )
            if canonical_status in {200, 301, 302}
            and canonical_url is not None
            and canonical_body is not None
            else None
        )
        if canonical_method:
            _log_detection(
                "threads",
                canonical_status,
                canonical_url,
                "FOUND",
                f"canonical retry {canonical_method}",
            )
            return "FOUND", None
        _log_detection("threads", status, final_url, "UNVERIFIED", "login redirect without profile evidence")
        return (
            "UNVERIFIED",
            "Login Required; canonical retry contained no profile metadata",
        )
    _log_detection("threads", status, final_url, "UNVERIFIED", "no profile metadata")
    return "UNVERIFIED", f"Unable to confirm Threads profile at {final_url}"


def _validate_telegram(username: str, timeout: int) -> tuple[PlatformStatus, str | None]:
    status, final_url, body, _ = _request_profile("telegram", username, timeout)
    if status is None:
        return "UNVERIFIED", body
    if status == 404:
        return "NOT_FOUND", "HTTP 404 Not Found"
    login_wall = _login_wall_response(final_url)
    if login_wall:
        return "UNVERIFIED", login_wall
    blocked = _blocked_response(status, final_url, body)
    if blocked:
        return "BLOCKED", blocked
    host = urlsplit(final_url).netloc.casefold()
    path = urlsplit(final_url).path.rstrip("/").casefold()
    if host not in {"t.me", "telegram.me"}:
        return "BLOCKED", f"Redirected away from Telegram to {final_url}"
    if status in {200, 301, 302} and path == f"/{username.casefold()}":
        if f"@{username.casefold()}" in body or "contact @" in body:
            return "FOUND", None
        return "UNVERIFIED", "HTTP 200 Telegram profile content could not be confirmed"
    return "UNVERIFIED", f"Unexpected redirect to {final_url}"


def _validate_path_profile(
    platform_key: str,
    username: str,
    timeout: int,
    allowed_hosts: set[str],
    expected_path: str,
    inspect_body: bool = True,
) -> tuple[PlatformStatus, str | None]:
    """Validate a platform whose canonical profile is identified by its path."""

    status, final_url, body, _ = _request_profile(platform_key, username, timeout)
    if status is None:
        return "UNVERIFIED", body
    if status == 404:
        return "NOT_FOUND", "HTTP 404 Not Found"
    login_wall = _login_wall_response(final_url)
    if login_wall:
        return "UNVERIFIED", login_wall
    blocked = _blocked_response(status, final_url, body if inspect_body else "")
    if blocked:
        return "BLOCKED", blocked
    parsed = urlsplit(final_url)
    if parsed.netloc.casefold() not in allowed_hosts:
        return "UNVERIFIED", f"Generic redirect to {final_url}"
    if status in {200, 301, 302} and parsed.path.rstrip("/").casefold() == expected_path:
        return "FOUND", None
    return "UNVERIFIED", f"Unexpected redirect to {final_url}"


PLATFORM_VALIDATORS: dict[str, Callable[[str, int], tuple[PlatformStatus, str | None]]] = {
    "github": _validate_github,
    "reddit": _validate_reddit,
    "twitter": _validate_twitter,
    "instagram": _validate_instagram,
    "linkedin": _validate_linkedin,
    "facebook": _validate_facebook,
    "youtube": _validate_youtube,
    "tiktok": _validate_tiktok,
    "threads": _validate_threads,
    "telegram": _validate_telegram,
}


def _detect_profile_with_http(
    platform_key: str,
    username: str,
    timeout: int,
) -> tuple[PlatformStatus, str | None]:
    """Run the platform-specific validator for a profile."""

    return PLATFORM_VALIDATORS[platform_key](username, timeout)


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
    if status in {"UNVERIFIED", "BLOCKED"} and reason:
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
