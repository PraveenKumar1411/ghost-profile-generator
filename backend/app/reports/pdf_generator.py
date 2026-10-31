"""PDF report generation for username scans."""

from datetime import datetime
from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.schemas.scan import RiskLevel, ScanResponse

PLATFORM_LABELS: dict[str, str] = {
    "github": "GitHub",
    "reddit": "Reddit",
    "twitter": "Twitter",
    "instagram": "Instagram",
    "linkedin": "LinkedIn",
    "facebook": "Facebook",
    "youtube": "YouTube",
    "tiktok": "TikTok",
    "threads": "Threads",
    "telegram": "Telegram",
}
PLATFORM_MARKS: dict[str, str] = {
    "github": "GH", "reddit": "R", "twitter": "X", "instagram": "IG",
    "linkedin": "in", "facebook": "f", "youtube": "YT", "tiktok": "TT",
    "threads": "@", "telegram": "TG",
}
PLATFORM_COLORS: dict[str, str] = {
    "github": "#6e7681", "reddit": "#FF4500", "twitter": "#111827",
    "instagram": "#dd2a7b", "linkedin": "#0A66C2", "facebook": "#1877F2",
    "youtube": "#FF0000", "tiktok": "#00F2EA", "threads": "#111827",
    "telegram": "#229ED9",
}

RECOMMENDATIONS: dict[RiskLevel, tuple[str, ...]] = {
    "LOW": ("Continue good privacy practices",),
    "MEDIUM": ("Enable MFA", "Review public profiles"),
    "HIGH": (
        "Enable MFA",
        "Hide public email",
        "Restrict social profile visibility",
        "Review privacy settings",
    ),
}
LOGO_PATH = Path(__file__).with_name("ghost-logo.png")


def _recommendations(risk_level: RiskLevel) -> list[str]:
    """Return recommendations configured for a risk level."""

    return list(RECOMMENDATIONS[risk_level])


def _threat_summary(risk_level: RiskLevel) -> str:
    """Return a concise threat summary for the report."""

    return {
        "LOW": "Low Exposure - Few public signals were discovered. Continue reviewing new profiles before sharing sensitive details.",
        "MEDIUM": "Moderate Exposure - Several public signals are connected to this identity. Strengthen account security and reduce unnecessary visibility.",
        "HIGH": "High Exposure - This identity has a broad public footprint. Prioritize MFA, privacy reviews, and removal of redundant identifiers.",
    }[risk_level]


def generate_pdf_report(
    scan: ScanResponse,
    *,
    scan_date: datetime | None = None,
) -> bytes:
    """Generate a downloadable PDF report for a completed scan."""

    generated_at = scan_date or datetime.now().astimezone()
    found = [
        label
        for field, label in PLATFORM_LABELS.items()
        if getattr(scan, field)
    ]
    missing = [
        label
        for field, label in PLATFORM_LABELS.items()
        if not getattr(scan, field)
    ]

    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"Ghost Profile Report - {scan.username}",
        author="Ghost Profile Generator",
    )
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="ReportTitle",
            parent=styles["Title"],
            alignment=TA_CENTER,
            fontSize=22,
            leading=28,
            textColor=colors.HexColor("#12304a"),
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SectionHeading",
            parent=styles["Heading2"],
            fontSize=13,
            leading=16,
            textColor=colors.HexColor("#12304a"),
            spaceBefore=14,
            spaceAfter=7,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Body",
            parent=styles["BodyText"],
            fontSize=10,
            leading=15,
            textColor=colors.HexColor("#334155"),
        )
    )

    logo = Image(str(LOGO_PATH), width=27 * mm, height=27 * mm)
    logo.hAlign = "CENTER"
    story = [
        logo,
        Spacer(1, 4),
        Paragraph("Ghost Profile Generator", styles["ReportTitle"]),
        Paragraph("Digital Footprint Report", styles["Heading2"]),
        Spacer(1, 6),
    ]

    summary = [
        ["Username", scan.username],
        ["Scan date", generated_at.strftime("%Y-%m-%d %H:%M %Z")],
        ["Risk score", f"{scan.risk_score} / 100"],
        ["Risk level", scan.risk_level],
        ["Platforms scanned", str(len(PLATFORM_LABELS))],
        ["Platforms found", str(len(found))],
        ["Platforms missing", str(len(missing))],
    ]
    summary_table = Table(summary, colWidths=[42 * mm, 118 * mm])
    summary_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#e8f3fa")),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#12304a")),
                ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor("#334155")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.append(summary_table)

    story.append(Paragraph("Threat intelligence summary", styles["SectionHeading"]))
    story.append(Paragraph(_threat_summary(scan.risk_level), styles["Body"]))
    story.append(Paragraph("Platform signal map", styles["SectionHeading"]))
    platform_rows = [["Logo", "Platform", "Public signal"]]
    for field, label in PLATFORM_LABELS.items():
        platform_rows.append([
            Paragraph(
                f'<font color="{PLATFORM_COLORS[field]}"><b>{PLATFORM_MARKS[field]}</b></font>',
                styles["Body"],
            ),
            label,
            "FOUND" if getattr(scan, field) else "NOT FOUND",
        ])
    platform_table = Table(platform_rows, colWidths=[18 * mm, 82 * mm, 60 * mm])
    platform_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#12304a")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("TEXTCOLOR", (1, 1), (1, -1), colors.HexColor("#334155")),
                ("TEXTCOLOR", (2, 1), (2, -1), colors.HexColor("#0f766e")),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd5e1")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(platform_table)
    story.append(Paragraph("Platforms found", styles["SectionHeading"]))
    story.append(
        Paragraph(
            ", ".join(found) if found else "No public platforms found.",
            styles["Body"],
        )
    )
    story.append(Paragraph("Platforms missing", styles["SectionHeading"]))
    story.append(
        Paragraph(
            ", ".join(missing) if missing else "No platforms missing.",
            styles["Body"],
        )
    )
    story.append(Paragraph("Recommendations", styles["SectionHeading"]))
    recommendations = _recommendations(scan.risk_level)
    story.extend(
        Paragraph(f"• {recommendation}", styles["Body"])
        for recommendation in recommendations
    )
    story.append(Spacer(1, 20))
    story.append(
        Paragraph(
            "This report reflects publicly discoverable profile indicators at the time of the scan.",
            styles["Body"],
        )
    )

    document.build(story)
    return output.getvalue()
