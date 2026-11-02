"""Risk scoring service for digital footprint results."""

from app.schemas.scan import PrivacyGrade, RiskLevel
from app.services.scan_service import ScanResult

PLATFORM_WEIGHTS: dict[str, int] = {
    "github": 10,
    "reddit": 10,
    "twitter": 10,
    "instagram": 10,
    "linkedin": 10,
    "facebook": 10,
    "youtube": 10,
    "tiktok": 10,
    "threads": 10,
    "telegram": 10,
}
CATEGORY_PLATFORMS: dict[str, tuple[str, ...]] = {
    "social": ("reddit", "twitter", "instagram", "facebook", "threads"),
    "professional": ("linkedin",),
    "developer": ("github",),
    "messaging": ("telegram",),
    "content": ("youtube", "tiktok"),
}
RECOMMENDATIONS: dict[RiskLevel, tuple[str, ...]] = {
    "LOW": (
        "Great privacy posture",
        "Continue using MFA",
        "Avoid reusing usernames",
    ),
    "MEDIUM": (
        "Review social media visibility",
        "Hide public contact details",
        "Limit profile discoverability",
    ),
    "HIGH": (
        "Enable 2FA immediately",
        "Remove public email addresses",
        "Separate personal and professional identities",
    ),
    "CRITICAL": (
        "Review all public accounts",
        "Audit all exposed information",
        "Create unique usernames per platform",
    ),
}


def calculate_risk_score(scan_result: ScanResult) -> int:
    """Calculate a bounded risk score from platform presence flags."""

    score = sum(
        weight
        for platform, weight in PLATFORM_WEIGHTS.items()
        if scan_result[platform] is True
    )
    categories = category_presence(scan_result)
    if categories["professional"] and categories["social"]:
        score += 5
    if categories["developer"] and categories["content"]:
        score += 5
    return min(score, 100)


def calculate_risk_level(risk_score: int) -> RiskLevel:
    """Map a risk score to its configured risk category."""

    if risk_score <= 30:
        return "LOW"
    if risk_score <= 60:
        return "MEDIUM"
    if risk_score <= 80:
        return "HIGH"
    return "CRITICAL"


def calculate_privacy_grade(risk_score: int) -> PrivacyGrade:
    """Map a score to the public privacy grade shown in reports."""

    if risk_score <= 10:
        return "A+"
    if risk_score <= 20:
        return "A"
    if risk_score <= 35:
        return "B"
    if risk_score <= 50:
        return "C"
    if risk_score <= 70:
        return "D"
    return "F"


def category_presence(scan_result: ScanResult) -> dict[str, bool]:
    """Return whether each exposure category has at least one signal."""

    return {
        category: any(scan_result[platform] for platform in platforms)
        for category, platforms in CATEGORY_PLATFORMS.items()
    }


def recommendations_for(risk_level: RiskLevel) -> list[str]:
    """Return dynamic privacy recommendations for a risk level."""

    return list(RECOMMENDATIONS[risk_level])


def insight_for(scan_result: ScanResult, risk_level: RiskLevel) -> str:
    """Build a concise OSINT insight from detected categories."""

    categories = category_presence(scan_result)
    count = sum(
        scan_result[platform]
        for platform in PLATFORM_WEIGHTS
    )
    unverified = [
        platform
        for platform, status in scan_result["verification_status"].items()
        if status == "RESTRICTED"
    ]
    uncertainty_note = (
        " Some platforms could not be verified due to platform restrictions or "
        "rate limits. These results should not be interpreted as profile absence."
        if unverified
        else ""
    )
    if count == 0:
        return "This identity has a low discoverability footprint." + uncertainty_note
    if categories["professional"] and categories["social"]:
        return (
            "Professional and social exposure are both visible across multiple "
            "public platforms." + uncertainty_note
        )
    if categories["professional"] and not categories["social"]:
        return "Professional exposure is higher than social exposure." + uncertainty_note
    if count >= 5 or risk_level == "CRITICAL":
        return "This username appears on multiple public platforms." + uncertainty_note
    return "A limited public footprint was discovered for this identity." + uncertainty_note


def calculate_risk(scan_result: ScanResult) -> tuple[int, RiskLevel]:
    """Calculate both risk score and risk category."""

    score = calculate_risk_score(scan_result)
    return score, calculate_risk_level(score)
