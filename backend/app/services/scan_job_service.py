"""Background execution and progress persistence for asynchronous scans."""

from datetime import datetime

from app.database import session_factory
from app.services.risk_service import (
    calculate_privacy_grade,
    calculate_risk,
    category_presence,
    insight_for,
    recommendations_for,
)
from app.services.scan_history_service import get_scan_by_scan_id, update_scan_job
from app.services.scan_service import (
    PLATFORM_NAMES,
    SherlockScanError,
    scan_username_with_progress,
)


async def run_scan_job(scan_id: str, username: str) -> None:
    """Execute a queued scan in the background with durable checkpoints."""

    async with session_factory() as session:
        await update_scan_job(
            session,
            scan_id,
            status="running",
            progress=0,
            current_platform=None,
            started_at=datetime.now().astimezone(),
            failure_reason=None,
        )

        completed_count = 0

        async def record_platform(display_name: str, found: bool) -> None:
            nonlocal completed_count
            completed_count += 1
            platform_key = PLATFORM_NAMES[display_name]
            await update_scan_job(
                session,
                scan_id,
                **{
                    platform_key: found,
                    "progress": round(completed_count / len(PLATFORM_NAMES) * 100),
                    "current_platform": display_name,
                },
            )

        try:
            scan_result = await scan_username_with_progress(
                username,
                record_platform,
            )
            risk_score, risk_level = calculate_risk(scan_result)
            await update_scan_job(
                session,
                scan_id,
                **scan_result,
                status="completed",
                progress=100,
                current_platform=None,
                risk_score=risk_score,
                risk_level=risk_level,
                privacy_grade=calculate_privacy_grade(risk_score),
                recommendations=recommendations_for(risk_level),
                insight=insight_for(scan_result, risk_level),
                category_exposure=category_presence(scan_result),
                completed_at=datetime.now().astimezone(),
            )
        except SherlockScanError as exc:
            await update_scan_job(
                session,
                scan_id,
                status="failed",
                current_platform=None,
                failure_reason=str(exc),
                completed_at=datetime.now().astimezone(),
            )
        except Exception as exc:
            await update_scan_job(
                session,
                scan_id,
                status="failed",
                current_platform=None,
                failure_reason="Unexpected scan failure",
                completed_at=datetime.now().astimezone(),
            )
            raise


async def get_job_snapshot(scan_id: str) -> dict[str, object] | None:
    """Return a normalized status snapshot for an asynchronous scan."""

    async with session_factory() as session:
        scan = await get_scan_by_scan_id(session, scan_id)
        if scan is None:
            return None
        platforms = list(PLATFORM_NAMES.values())
        completed = [
            display_name
            for display_name, key in PLATFORM_NAMES.items()
            if scan.progress >= round(
                (platforms.index(key) + 1) / len(platforms) * 100
            )
        ]
        return {
            "scan_id": scan.scan_id,
            "status": scan.status,
            "progress": scan.progress,
            "current_platform": scan.current_platform,
            "completed_platforms": completed,
            "remaining_platforms": [
                display_name
                for display_name, key in PLATFORM_NAMES.items()
                if key not in [PLATFORM_NAMES.get(name) for name in completed]
            ],
            "failure_reason": scan.failure_reason,
        }
