#!/usr/bin/env python3
"""Automated Changelog Generator for RealityTunnel Releases."""

import argparse
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def generate_changelog(version: str, output_file: str | None = None) -> str:
    try:
        # Get git log since last tag or all if no previous tag
        tags_output = subprocess.check_output(
            ["git", "tag", "--sort=-creatordate"], text=True
        ).splitlines()
        range_arg = []
        if len(tags_output) > 1 and tags_output[0] == version:
            range_arg = [f"{tags_output[1]}..HEAD"]
        elif tags_output:
            range_arg = [f"{tags_output[0]}..HEAD"]

        cmd = ["git", "log", "--pretty=format:%h|%s|%an|%ad", "--date=short"] + range_arg
        log_output = subprocess.check_output(cmd, text=True).splitlines()
    except Exception as exc:
        print(f"Warning: Could not fetch git log ({exc}). Using fallback history.")
        log_output = [
            f"0000000|feat: release version {version}|System|{datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
        ]

    categories: dict[str, list[str]] = {
        "Features": [],
        "Bug Fixes": [],
        "Performance & Scalability": [],
        "Security & Hardening": [],
        "Documentation": [],
        "Other Changes": [],
    }

    for line in log_output:
        if not line.strip():
            continue
        parts = line.split("|", 3)
        if len(parts) < 2:
            continue
        commit_hash, subject = parts[0], parts[1]
        author = parts[2] if len(parts) > 2 else "Contributor"
        
        entry = f"- **{commit_hash}**: {subject} *(by {author})*"
        
        lower_sub = subject.lower()
        if lower_sub.startswith("feat:") or lower_sub.startswith("feature:"):
            categories["Features"].append(entry)
        elif lower_sub.startswith("fix:") or lower_sub.startswith("bug:"):
            categories["Bug Fixes"].append(entry)
        elif lower_sub.startswith("perf:") or lower_sub.startswith("performance:"):
            categories["Performance & Scalability"].append(entry)
        elif lower_sub.startswith("sec:") or lower_sub.startswith("security:"):
            categories["Security & Hardening"].append(entry)
        elif lower_sub.startswith("docs:") or lower_sub.startswith("doc:"):
            categories["Documentation"].append(entry)
        else:
            categories["Other Changes"].append(entry)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    md_lines = [
        f"# Release {version} ({today})",
        "",
        "Welcome to the official production release of the RealityTunnel VPN billing and authentication backend.",
        "",
    ]

    for cat_name, entries in categories.items():
        if entries:
            md_lines.append(f"## {cat_name}")
            md_lines.extend(entries)
            md_lines.append("")

    content = "\n".join(md_lines)
    if output_file:
        out_path = Path(output_file)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content, encoding="utf-8")
        print(f"Changelog written to {output_file}")

    return content


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate markdown changelog from git commits.")
    parser.add_argument("--version", default="v1.0.0", help="Release version tag")
    parser.add_argument("--output", "-o", default=None, help="Output file path (optional)")
    args = parser.parse_args()

    changelog = generate_changelog(args.version, args.output)
    if not args.output:
        print(changelog)


if __name__ == "__main__":
    main()
