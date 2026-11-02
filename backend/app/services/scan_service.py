"""Sherlock-backed digital footprint scanning service."""

import asyncio
from html.parser import HTMLParser
import re
import subprocess
import sys
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from time import perf_counter, sleep
from typing import Literal, TypedDict
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus, unquote, urlsplit
from urllib.request import Request, urlopen

from app.config import get_settings


PlatformStatus = Literal["FOUND", "LIKELY_FOUND", "NOT_FOUND", "RESTRICTED"]


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
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
}


class _ProfileMetadataParser(HTMLParser):
    """Extract profile identity metadata from server-rendered HTML."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.metadata: dict[str, list[str]] = {}
        self._json_ld_depth = 0
        self._json_ld_parts: list[str] = []
        self._title_depth = 0
        self._title_parts: list[str] = []

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
        elif tag.casefold() == "script" and attributes.get("type", "").casefold() == "application/ld+json":
            self._json_ld_depth = 1
        elif tag.casefold() == "title":
            self._title_depth = 1

    def handle_data(self, data: str) -> None:
        if self._json_ld_depth:
            self._json_ld_parts.append(data)
        if self._title_depth:
            self._title_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "script" and self._json_ld_depth:
            json_ld = "".join(self._json_ld_parts).casefold()
            if json_ld:
                self.metadata.setdefault("json-ld", []).append(json_ld)
            self._json_ld_depth = 0
            self._json_ld_parts = []
        elif tag.casefold() == "title" and self._title_depth:
            title = "".join(self._title_parts).casefold()
            if title:
                self.metadata.setdefault("title", []).append(title)
            self._title_depth = 0
            self._title_parts = []


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

    expected_path = expected_path.rstrip("/").casefold()
    metadata = _profile_metadata(body)
    final_path = urlsplit(final_url).path.rstrip("/").casefold()
    if final_path == expected_path and metadata.get("profile:id"):
        return "profile:id"
    for key in ("canonical", "og:url"):
        for value in metadata.get(key, []):
            parsed_value = urlsplit(value)
            if (
                parsed_value.netloc.casefold() in allowed_hosts
                and parsed_value.path.rstrip("/").casefold() == expected_path
            ):
                return key
    username_casefolded = username.casefold()
    username_marker = f"@{username_casefolded}"
    for key in ("og:title", "og:description", "description", "twitter:title", "title", "profile:id", "json-ld"):
        if any(
            username_marker in value
            or re.search(rf"(?<![a-z0-9]){re.escape(username_casefolded)}(?![a-z0-9])", value)
            for value in metadata.get(key, [])
        ):
            return key
    return None


NOT_FOUND_MARKERS = (
    "page isn't available",
    "page is not available",
    "sorry, this page isn't available",
    "the link you followed may be broken",
    "this page could not be found",
    "user not found",
    "profile not found",
    "account doesn't exist",
    "account does not exist",
    "username isn't available",
    "username is not available",
)
SEARCH_ENGINE_URLS = (
    "https://www.google.com/search?q={query}",
    "https://www.bing.com/search?q={query}",
    "https://html.duckduckgo.com/html/?q={query}",
)
PLATFORM_RESTRICTED_MESSAGES = {
    "instagram": "Public verification restricted by platform.",
    "facebook": "Public verification restricted by platform.",
    "threads": "Insufficient public profile data available.",
}


def _explicit_not_found(body: str) -> bool:
    """Recognize platform absence language without treating access failures as absence."""

    return any(marker in body for marker in NOT_FOUND_MARKERS)


def _search_public_references(
    platform_key: str,
    username: str,
    timeout: int,
) -> list[str]:
    """Collect distinct indexed profile references from public search engines."""

    host_patterns = {
        "instagram": ("instagram.com",),
        "facebook": ("facebook.com",),
        "threads": ("threads.net", "threads.com"),
    }
    query = quote_plus(f"site:{host_patterns[platform_key][0]} {username}")
    references: set[str] = set()
    for engine_url in SEARCH_ENGINE_URLS:
        status, final_url, body, _ = _request_url(
            engine_url.format(query=query),
            timeout,
        )
        if status is None or not body:
            continue
        candidates = re.findall(r"https?://[^\"'<>\\s]+", body)
        for candidate in candidates:
            candidate = unquote(candidate).rstrip(").,;")
            parsed = urlsplit(candidate)
            host = parsed.netloc.casefold().split(":", 1)[0]
            path = parsed.path.rstrip("/").casefold()
            if not any(host == allowed or host.endswith(f".{allowed}") for allowed in host_patterns[platform_key]):
                continue
            username_segment = username.casefold()
            if platform_key == "threads":
                matches = path == f"/@{username_segment}" or f"/@{username_segment}/" in path
            else:
                matches = path.strip("/").split("/")[0] == username_segment
            if matches:
                references.add(f"{parsed.scheme}://{parsed.netloc}{parsed.path}".casefold())
    return sorted(references)


def _request_url(
    url: str,
    timeout: int,
) -> tuple[int | None, str | None, str, str]:
    """Fetch a URL with the same retry and browser-header policy as profile requests."""

    last_result: tuple[int | None, str | None, str, str] = (None, None, "Network failure", url)
    for attempt in range(3):
        request = Request(url, headers=PROFILE_REQUEST_HEADERS)
        try:
            with urlopen(request, timeout=timeout) as response:
                body = response.read(131072).decode("utf-8", errors="ignore").casefold()
                return response.status, response.url, body, url
        except HTTPError as exc:
            last_result = (
                exc.code,
                exc.url,
                exc.read(131072).decode("utf-8", errors="ignore").casefold(),
                url,
            )
            if exc.code not in {408, 425, 429} and exc.code < 500:
                return last_result
        except (TimeoutError, URLError, OSError) as exc:
            detail = getattr(exc, "reason", str(exc))
            last_result = (None, None, f"Network failure: {detail}", url)
        if attempt < 2:
            sleep(0.2 * (attempt + 1))
    return last_result


def _fallback_platform_status(
    platform_key: str,
    username: str,
    timeout: int,
) -> tuple[PlatformStatus, str | None]:
    """Use independent public references before declaring a platform restricted."""

    references = _search_public_references(platform_key, username, timeout)
    if len(references) >= 2:
        _log_detection(
            platform_key,
            None,
            None,
            "LIKELY_FOUND",
            f"independent public references={len(references)}",
        )
        return "LIKELY_FOUND", "Detected through independent public sources."
    message = PLATFORM_RESTRICTED_MESSAGES[platform_key]
    _log_detection(platform_key, None, None, "RESTRICTED", message)
    return "RESTRICTED", message


def _validate_public_profile(
    platform_key: str,
    username: str,
    timeout: int,
    expected_path: str,
    allowed_hosts: set[str],
) -> tuple[PlatformStatus, str | None]:
    """Verify a profile using direct metadata, explicit absence, then public references."""

    status, final_url, body, _ = _request_profile(platform_key, username, timeout)
    if status == 404 or _explicit_not_found(body):
        _log_detection(platform_key, status, final_url, "NOT_FOUND", "explicit absence evidence")
        return "NOT_FOUND", None
    metadata_method = (
        _metadata_profile_evidence(body, final_url or "", username, expected_path, allowed_hosts)
        if final_url
        else None
    )
    if metadata_method:
        _log_detection(platform_key, status, final_url, "FOUND", metadata_method)
        return "FOUND", None
    if platform_key == "threads":
        canonical_status, canonical_url, canonical_body, _ = _request_threads_canonical(
            username,
            timeout,
        )
        canonical_method = (
            _metadata_profile_evidence(
                canonical_body,
                canonical_url or "",
                username,
                expected_path,
                allowed_hosts,
            )
            if canonical_url and canonical_body
            else None
        )
        if canonical_method:
            _log_detection(
                platform_key,
                canonical_status,
                canonical_url,
                "FOUND",
                f"canonical metadata {canonical_method}",
            )
            return "FOUND", None
    return _fallback_platform_status(platform_key, username, timeout)


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
            platform_key: "RESTRICTED"
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
    return _request_url(url, timeout)


def _request_threads_canonical(
    username: str,
    timeout: int,
) -> tuple[int, str, str, str] | tuple[None, None, None, None]:
    """Fetch Threads' canonical profile URL for login-redirect recovery."""

    url = f"https://www.threads.com/@{username}/"
    return _request_url(url, timeout)


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
    """Identify a login redirect without treating it as proof of absence."""

    path = urlsplit(final_url).path.casefold()
    if path.startswith(("/login", "/accounts/login", "/signin", "/sign-in")):
        return "login redirect"
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
    return _validate_public_profile(
        "instagram",
        username,
        timeout,
        f"/{username}",
        {"instagram.com", "www.instagram.com"},
    )


def _validate_linkedin(username: str, timeout: int) -> tuple[PlatformStatus, str | None]:
    return _validate_path_profile("linkedin", username, timeout, {"linkedin.com", "www.linkedin.com"}, f"/in/{username.casefold()}")


def _validate_facebook(username: str, timeout: int) -> tuple[PlatformStatus, str | None]:
    return _validate_public_profile(
        "facebook",
        username,
        timeout,
        f"/{username}",
        {"facebook.com", "www.facebook.com"},
    )


def _validate_youtube(username: str, timeout: int) -> tuple[PlatformStatus, str | None]:
    return _validate_path_profile("youtube", username, timeout, { "youtube.com", "www.youtube.com" }, f"/@{username.casefold()}")


def _validate_tiktok(username: str, timeout: int) -> tuple[PlatformStatus, str | None]:
    status, final_url, body, _ = _request_profile("tiktok", username, timeout)
    if status is None:
        _log_detection("tiktok", status, final_url, "RESTRICTED", "network result")
        return "RESTRICTED", None
    if status == 404:
        _log_detection("tiktok", status, final_url, "NOT_FOUND", "HTTP 404")
        return "NOT_FOUND", "HTTP 404 Not Found"
    blocked = _blocked_response(status, final_url, body)
    if blocked:
        _log_detection("tiktok", status, final_url, "RESTRICTED", blocked)
        return "RESTRICTED", None
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
        _log_detection("tiktok", status, final_url, "RESTRICTED", "profile metadata unavailable")
        return "RESTRICTED", None
    if parsed_path == "/in/about":
        _log_detection("tiktok", status, final_url, "RESTRICTED", "generic TikTok access wall")
        return "RESTRICTED", None
    _log_detection("tiktok", status, final_url, "RESTRICTED", "unexpected redirect")
    return "RESTRICTED", None


def _validate_threads(username: str, timeout: int) -> tuple[PlatformStatus, str | None]:
    return _validate_public_profile(
        "threads",
        username,
        timeout,
        f"/@{username}",
        {"threads.net", "www.threads.net", "threads.com", "www.threads.com"},
    )


def _validate_telegram(username: str, timeout: int) -> tuple[PlatformStatus, str | None]:
    status, final_url, body, _ = _request_profile("telegram", username, timeout)
    if status is None:
        return "RESTRICTED", None
    if status == 404:
        return "NOT_FOUND", "HTTP 404 Not Found"
    login_wall = _login_wall_response(final_url)
    if login_wall:
        return "RESTRICTED", None
    blocked = _blocked_response(status, final_url, body)
    if blocked:
        return "RESTRICTED", None
    host = urlsplit(final_url).netloc.casefold()
    path = urlsplit(final_url).path.rstrip("/").casefold()
    if host not in {"t.me", "telegram.me"}:
        return "RESTRICTED", None
    if status in {200, 301, 302} and path == f"/{username.casefold()}":
        if f"@{username.casefold()}" in body or "contact @" in body:
            return "FOUND", None
        return "RESTRICTED", None
    return "RESTRICTED", None


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
        return "RESTRICTED", None
    if status == 404:
        return "NOT_FOUND", "HTTP 404 Not Found"
    login_wall = _login_wall_response(final_url)
    if login_wall:
        return "RESTRICTED", None
    blocked = _blocked_response(status, final_url, body if inspect_body else "")
    if blocked:
        return "RESTRICTED", None
    parsed = urlsplit(final_url)
    if parsed.netloc.casefold() not in allowed_hosts:
        return "RESTRICTED", None
    if status in {200, 301, 302} and parsed.path.rstrip("/").casefold() == expected_path:
        return "FOUND", None
    return "RESTRICTED", None


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
    result[platform_key] = status in {"FOUND", "LIKELY_FOUND"}
    if status == "LIKELY_FOUND":
        result["verification_reasons"][platform_key] = (
            "Detected through independent public sources."
        )
    elif status == "RESTRICTED":
        result["verification_reasons"][platform_key] = (
            reason or PLATFORM_RESTRICTED_MESSAGES.get(
                platform_key,
                "Public verification restricted by platform.",
            )
        )
    else:
        result["verification_reasons"].pop(platform_key, None)


async def scan_username(username: str) -> ScanResult:
    """Run a bounded platform-by-platform scan for a username."""

    async def ignore_progress(_: str, __: bool) -> None:
        return None

    return await scan_username_with_progress(username, ignore_progress)


async def scan_username_with_progress(
    username: str,
    on_platform_complete: Callable[[str, bool], Awaitable[None]],
) -> ScanResult:
    """Run one Sherlock site at a time and report durable progress checkpoints."""

    settings = get_settings()
    result = _empty_scan_result()

    for display_name, platform_key in PLATFORM_NAMES.items():
        started_at = datetime.now(timezone.utc)
        started = perf_counter()
        print(
            f"Platform verification started: platform={display_name} "
            f"started_at={started_at.isoformat()}"
        )
        try:
            platform_status, reason = await asyncio.wait_for(
                _verify_platform_with_timeout(
                    display_name,
                    platform_key,
                    username,
                    settings.sherlock_request_timeout,
                    settings.sherlock_process_timeout,
                    settings.scan_platform_timeout,
                ),
                timeout=settings.scan_platform_timeout,
            )
        except asyncio.TimeoutError:
            platform_status = "RESTRICTED"
            reason = (
                f"Platform verification timeout after "
                f"{settings.scan_platform_timeout}s"
            )
        except Exception as exc:
            platform_status = "RESTRICTED"
            reason = f"Platform verification failed: {exc}"
        _apply_platform_result(result, platform_key, platform_status, reason)
        completed_at = datetime.now(timezone.utc)
        duration = perf_counter() - started
        print(
            f"Platform verification completed: platform={display_name} "
            f"completed_at={completed_at.isoformat()} duration={duration:.3f}s "
            f"status={platform_status} reason={reason or 'verified'}"
        )
        await on_platform_complete(
            display_name,
            platform_status in {"FOUND", "LIKELY_FOUND"},
        )

    return result


async def _verify_platform_with_timeout(
    display_name: str,
    platform_key: str,
    username: str,
    request_timeout: int,
    process_timeout: int,
    platform_timeout: int,
) -> tuple[PlatformStatus, str | None]:
    """Run one platform check with bounded Sherlock and HTTP work."""

    site_name = SHERLOCK_SITE_NAMES[display_name]
    if site_name is None:
        fallback_started = perf_counter()
        outcome = await _detect_unsupported_platform(
            platform_key,
            username,
            min(request_timeout, platform_timeout),
        )
        print(
            f"HTTP fallback completed: platform={display_name} "
            f"duration={perf_counter() - fallback_started:.3f}s"
        )
        return outcome

    command = [
        sys.executable,
        "-m",
        "sherlock_project.sherlock",
        username,
        "--no-color",
        "--print-found",
        "--timeout",
        str(min(request_timeout, platform_timeout)),
        "--site",
        site_name,
    ]
    sherlock_started = perf_counter()
    try:
        completed_process = await asyncio.to_thread(
            subprocess.run,
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=min(process_timeout, platform_timeout),
        )
    except subprocess.TimeoutExpired:
        return "RESTRICTED", None
    except (FileNotFoundError, OSError) as exc:
        return "RESTRICTED", None
    print(
        f"Sherlock completed: platform={display_name} "
        f"duration={perf_counter() - sherlock_started:.3f}s "
        f"returncode={completed_process.returncode}"
    )

    if completed_process.returncode not in (0, 1):
        error = completed_process.stderr.strip()
        return "RESTRICTED", None

    parsed = _parse_sherlock_output(completed_process.stdout)
    if parsed[platform_key]:
        return "FOUND", None
    fallback_started = perf_counter()
    outcome = await _detect_unsupported_platform(
        platform_key,
        username,
        min(request_timeout, platform_timeout),
    )
    print(
        f"HTTP fallback completed: platform={display_name} "
        f"duration={perf_counter() - fallback_started:.3f}s"
    )
    return outcome
