"""Semantic configuration diff engine with multi-vendor section awareness and HTML reports."""

import difflib
import logging
import re
from typing import Dict, List, Optional, Pattern
from netconfigvault.models.diff import DiffResult

logger = logging.getLogger(__name__)

HTML_DIFF_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Config Diff - {hostname}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: #0f172a;
            color: #e2e8f0;
            margin: 0;
            padding: 20px;
        }}
        .diff-header {{
            background: #1e293b;
            padding: 16px 24px;
            border-radius: 8px;
            margin-bottom: 20px;
            border-left: 4px solid #38bdf8;
        }}
        .diff-header h2 {{ margin: 0 0 8px 0; color: #38bdf8; }}
        .diff-meta {{ font-size: 0.9em; color: #94a3b8; }}
        .badge {{
            display: inline-block;
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 0.8em;
            font-weight: 600;
            margin-right: 6px;
        }}
        .badge-add {{ background: #065f46; color: #34d399; }}
        .badge-sub {{ background: #7f1d1d; color: #f87171; }}
        .badge-sec {{ background: #312e81; color: #a5b4fc; }}
        table.diff {{
            font-family: "JetBrains Mono", Consolas, "Courier New", monospace;
            font-size: 13px;
            border-collapse: collapse;
            width: 100%;
            background: #1e293b;
            border-radius: 8px;
            overflow: hidden;
        }}
        table.diff th {{
            background: #334155;
            color: #f1f5f9;
            padding: 8px;
            text-align: left;
        }}
        table.diff td {{
            padding: 2px 8px;
            white-space: pre-wrap;
            word-break: break-all;
        }}
        .diff_header {{
            background: #0f172a;
            color: #64748b;
            text-align: right;
            user-select: none;
            width: 40px;
        }}
        .diff_next {{ display: none; }}
        .diff_add {{ background-color: rgba(16, 185, 129, 0.2); color: #6ee7b7; }}
        .diff_chg {{ background-color: rgba(245, 158, 11, 0.2); color: #fde68a; }}
        .diff_sub {{ background-color: rgba(239, 68, 68, 0.2); color: #fca5a5; }}
    </style>
</head>
<body>
    <div class="diff-header">
        <h2>{hostname} — Configuration Change Analysis</h2>
        <div class="diff-meta">
            <span class="badge badge-add">+{added} lines</span>
            <span class="badge badge-sub">-{removed} lines</span>
            {sections_html}
        </div>
    </div>
    {diff_table}
</body>
</html>"""


class DiffEngine:
    """Computes semantic diffs across configuration snapshots."""

    # Section recognition patterns
    SECTION_RULES: Dict[str, str] = {
        # Cisco
        "interfaces": r"^interface\s+\S+",
        "routing": r"^(router\s+\S+|ip\s+route\s+|ipv6\s+route\s+)",
        "acls": r"^(ip\s+)?access-list\s+",
        "aaa_security": r"^aaa\s+",
        "snmp": r"^snmp-server\s+",
        "ntp": r"^ntp\s+",
        "vlan": r"^vlan\s+\d+",
        "lines": r"^line\s+(vty|con|aux)",
        # MikroTik
        "ros_interface": r"^/interface\s+",
        "ros_ip_address": r"^/ip\s+address\s+",
        "ros_firewall": r"^/ip\s+firewall\s+",
        "ros_routing": r"^/(routing|ip\s+route)\s+",
        "ros_services": r"^/ip\s+service\s+",
        "ros_system": r"^/system\s+",
        "ros_users": r"^/user\s+",
    }

    def __init__(self, custom_ignore_patterns: Optional[List[str]] = None):
        patterns = custom_ignore_patterns or []
        self.ignore_regexes: List[Pattern] = [re.compile(p, re.IGNORECASE) for p in patterns]
        self._compiled_sections = {name: re.compile(pat, re.IGNORECASE) for name, pat in self.SECTION_RULES.items()}

    def _filter_lines(self, lines: List[str]) -> List[str]:
        """Strip lines matching custom ignore expressions."""
        if not self.ignore_regexes:
            return lines
        return [
            line for line in lines
            if not any(regex.search(line) for regex in self.ignore_regexes)
        ]

    def _detect_sections(self, diff_lines: List[str]) -> List[str]:
        """Identify which high-level sections were modified in the diff."""
        detected = set()
        for line in diff_lines:
            if line.startswith(("+", "-")) and not line.startswith(("+++", "---")):
                content = line[1:].strip()
                for section_name, pattern in self._compiled_sections.items():
                    if pattern.search(content):
                        # Clean prefix for display
                        clean_name = section_name.replace("ros_", "")
                        detected.add(clean_name)
        return sorted(detected)

    def compare(
        self,
        hostname: str,
        old_config: str,
        new_config: str,
        generate_html: bool = True,
    ) -> DiffResult:
        """Execute semantic comparison between prior and current configurations."""
        old_lines = self._filter_lines(old_config.splitlines())
        new_lines = self._filter_lines(new_config.splitlines())

        # Generate standard unified diff
        diff_generator = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"{hostname} (prior snapshot)",
            tofile=f"{hostname} (latest snapshot)",
            lineterm="",
        )
        diff_lines = list(diff_generator)
        has_changes = len(diff_lines) > 0

        added = sum(1 for line in diff_lines if line.startswith("+") and not line.startswith("+++"))
        removed = sum(1 for line in diff_lines if line.startswith("-") and not line.startswith("---"))
        sections = self._detect_sections(diff_lines) if has_changes else []

        unified_diff_text = "\n".join(diff_lines)

        # Summary text
        if has_changes:
            summary = f"+{added} / -{removed} lines changed"
            if sections:
                summary += f" | Sections: {', '.join(sections)}"
        else:
            summary = "No configuration changes detected."

        html_output = None
        if generate_html and has_changes:
            html_diff_engine = difflib.HtmlDiff(wrapcolumn=90)
            diff_table = html_diff_engine.make_table(
                old_lines,
                new_lines,
                fromdesc="Prior Configuration",
                todesc="Latest Configuration",
                context=True,
                numlines=4,
            )
            sections_html = "".join([f'<span class="badge badge-sec">{s}</span>' for s in sections])
            html_output = HTML_DIFF_TEMPLATE.format(
                hostname=hostname,
                added=added,
                removed=removed,
                sections_html=sections_html,
                diff_table=diff_table,
            )

        return DiffResult(
            hostname=hostname,
            has_changes=has_changes,
            added_lines=added,
            removed_lines=removed,
            changed_sections=sections,
            unified_diff=unified_diff_text,
            html_diff=html_output,
            summary=summary,
        )
