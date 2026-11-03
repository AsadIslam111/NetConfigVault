"""Report generation formats for compliance evaluation outcomes."""

from typing import List
from netconfigvault.models.compliance import (
    ComplianceSeverity,
    DeviceComplianceReport,
    FleetComplianceSummary,
)

HTML_REPORT_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Compliance Audit - {hostname}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: #0f172a;
            color: #f1f5f9;
            margin: 0;
            padding: 30px;
        }}
        .container {{ max-width: 1000px; margin: 0 auto; }}
        .header {{
            background: #1e293b;
            padding: 24px;
            border-radius: 10px;
            border-left: 6px solid {score_color};
            margin-bottom: 24px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .score-box {{
            text-align: right;
        }}
        .score {{
            font-size: 3em;
            font-weight: 800;
            color: {score_color};
            line-height: 1;
        }}
        .rule-card {{
            background: #1e293b;
            padding: 16px 20px;
            border-radius: 8px;
            margin-bottom: 12px;
            border: 1px solid #334155;
        }}
        .rule-pass {{ border-left: 4px solid #10b981; }}
        .rule-fail {{ border-left: 4px solid #ef4444; }}
        .badge {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.75em;
            font-weight: 700;
            text-transform: uppercase;
            margin-right: 8px;
        }}
        .badge-critical {{ background: #991b1b; color: #fca5a5; }}
        .badge-high {{ background: #9a3412; color: #fdba74; }}
        .badge-medium {{ background: #854d0e; color: #fde047; }}
        .badge-pass {{ background: #065f46; color: #6ee7b7; }}
        .badge-fail {{ background: #7f1d1d; color: #fca5a5; }}
        .remediation {{
            background: #0f172a;
            padding: 10px 14px;
            border-radius: 6px;
            font-family: monospace;
            font-size: 13px;
            margin-top: 10px;
            color: #38bdf8;
            white-space: pre-wrap;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div>
                <h1 style="margin: 0 0 8px 0;">{hostname}</h1>
                <p style="margin: 0; color: #94a3b8;">Platform: {device_type} | Evaluated: {timestamp}</p>
                <p style="margin: 6px 0 0 0; color: #cbd5e1;">Passed: <strong>{passed}/{total}</strong> rules</p>
            </div>
            <div class="score-box">
                <div class="score">{score}%</div>
                <span style="color: #94a3b8; font-size: 0.9em;">COMPLIANCE SCORE</span>
            </div>
        </div>

        <h2>Rule Breakdown</h2>
        {rules_html}
    </div>
</body>
</html>"""


class ComplianceReportGenerator:
    """Generates Markdown and HTML visual reports from compliance audit data."""

    @staticmethod
    def generate_html(report: DeviceComplianceReport) -> str:
        """Create a standalone HTML compliance report for a device."""
        score_color = "#10b981" if report.score_percent >= 80 else "#f59e0b" if report.score_percent >= 60 else "#ef4444"

        rules_cards = []
        for res in report.results:
            rule = res.rule
            status_badge = '<span class="badge badge-pass">PASS</span>' if res.passed else '<span class="badge badge-fail">FAIL</span>'
            sev_badge = f'<span class="badge badge-{rule.severity.value}">{rule.severity.value}</span>'
            card_class = "rule-pass" if res.passed else "rule-fail"

            remediation_html = ""
            if not res.passed and rule.remediation:
                remediation_html = f"""<div class="remediation"><strong>Recommended Remediation:</strong><br>{rule.remediation}</div>"""

            card = f"""<div class="rule-card {card_class}">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
        <strong>{rule.id} — {rule.name}</strong>
        <div>{sev_badge} {status_badge}</div>
    </div>
    <div style="color: #94a3b8; font-size: 0.9em; margin-bottom: 6px;">{rule.description}</div>
    <div style="font-size: 0.85em; color: #cbd5e1;">{res.message}</div>
    {remediation_html}
</div>"""
            rules_cards.append(card)

        return HTML_REPORT_TEMPLATE.format(
            hostname=report.hostname,
            device_type=report.device_type,
            timestamp=report.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            passed=report.passed,
            total=report.total_rules,
            score=report.score_percent,
            score_color=score_color,
            rules_html="\n".join(rules_cards),
        )

    @staticmethod
    def generate_markdown(report: DeviceComplianceReport) -> str:
        """Generate a Markdown document summarizing compliance results."""
        lines = [
            f"# Compliance Audit Report — {report.hostname}",
            f"**Platform:** `{report.device_type}` | **Score:** **{report.score_percent}%** ({report.passed}/{report.total_rules} passed)",
            f"**Audit Timestamp:** {report.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Summary of Violations",
        ]

        violations = [r for r in report.results if not r.passed]
        if not violations:
            lines.append("✅ **No violations detected. Device is 100% compliant with active rules.**")
        else:
            lines.append("| Rule ID | Severity | Name | Remediation |")
            lines.append("|---|---|---|---|")
            for res in violations:
                rule = res.rule
                rem = f"`{rule.remediation.replace(chr(10), ' ')}`" if rule.remediation else "N/A"
                lines.append(f"| **{rule.id}** | `{rule.severity.value.upper()}` | {rule.name} | {rem} |")

        return "\n".join(lines)
