# 🛡️ NetConfigVault

> Automated network configuration backup, change detection, and compliance auditing for Cisco IOS/IOS-XE and MikroTik RouterOS environments.

## ✨ Features

### 🟢 Tier 1: Core Engine
- **Multi-Vendor Support**: Out-of-the-box handlers for **Cisco IOS/IOS-XE** and **MikroTik RouterOS**.
- **Automated Collection**: Extracts running configuration (`show running-config` on Cisco, `/export compact` on MikroTik) via Netmiko SSH with automatic terminal paging and privilege elevation handling.
- **Git Version Control**: Automatically versions backups into an isolated Git repository, tracking changes over time with commit messages reflecting run status.
- **Noise Sanitization**: Automatically strips volatile dynamic timestamps, NTP clock lines, and export IDs to eliminate false-positive diffs.
- **Resilient Execution**: Configurable exponential backoff retries on transient network failures and immediate failure isolation on authentication errors.
- **Concurrent Processing**: Multi-threaded execution using `ThreadPoolExecutor` to scale across large network fleets.
- **Rich CLI**: Built with Typer and Rich for formatted terminal tables and status reporting.

### 🟡 Tier 2: Operational Maturity
- **Semantic Diff Engine**: Understands configuration structure beyond line-by-line text matching.
- **Section-Aware Change Detection**: Classifies changes into functional domains (interfaces, routing, ACLs, firewall filters, AAA, system services).
- **Interactive Visual HTML Diffs**: Generates standalone, dark-mode side-by-side HTML diff reports for operational review.
- **Multi-Channel Alerting**: Instant dispatch of change notifications and critical backup failures via **Slack Webhooks** and **SMTP Email**.
- **Diff CLI Inspection**: Dedicated `diff` command with syntax-highlighted terminal output.

---

## 🚀 Quick Start

### 1. View Inventory
```bash
python -m netconfigvault.cli inventory
```

### 2. Run Backups
```bash
# Run backup for all enabled devices
python -m netconfigvault.cli backup

# Filter by device group or site
python -m netconfigvault.cli backup --group production
python -m netconfigvault.cli backup --site dc-east --verbose
```

### 3. Inspect Configuration Diffs
```bash
# Compare the two latest backups for a device in terminal
python -m netconfigvault.cli diff core-rtr-01

# Generate a standalone visual HTML diff report
python -m netconfigvault.cli diff edge-gw-01 --html diff_report.html
```
