"""Risk scoring service for digital footprint results."""

from app.schemas.scan import RiskLevel
from app.services.scan_service import ScanResult

PLATFORM_WEIGHTS: dict[str, int] = {
    "github": 20,
    "twitter": 20,
    "instagram": 30,
    "reddit": 15,
    "linkedin": 15,
}


def calculate_risk_score(scan_result: ScanResult) -> int:
    """Calculate a bounded risk score from platform presence flags."""

    return sum(
        weight
        for platform, weight in PLATFORM_WEIGHTS.items()
        if scan_result[platform] is True
    )


def calculate_risk_level(risk_score: int) -> RiskLevel:
    """Map a risk score to its configured risk category."""

    if risk_score <= 30:
        return "LOW"
    if risk_score <= 60:
        return "MEDIUM"
    return "HIGH"


def calculate_risk(scan_result: ScanResult) -> tuple[int, RiskLevel]:
    """Calculate both risk score and risk category."""

    score = calculate_risk_score(scan_result)
    return score, calculate_risk_level(score)
