#!/usr/bin/env python3
"""Automated Software Bill of Materials (SBOM) Generator for RealityTunnel."""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def generate_local_sbom(output_dir: str = ".") -> dict[str, str]:
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    
    cdx_file = out_path / "cyclonedx.json"
    spdx_file = out_path / "spdx.json"

    # Attempt to use cyclonedx-py CLI or generate minimal valid CycloneDX structure
    try:
        subprocess.run(
            ["cyclonedx-py", "environment", "--outfile", str(cdx_file), "--format", "json"],
            check=True,
            capture_output=True,
        )
        print(f"Generated CycloneDX SBOM at {cdx_file}")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("cyclonedx-py CLI not available or failed; generating fallback CycloneDX JSON.")
        cdx_payload = {
            "bomFormat": "CycloneDX",
            "specVersion": "1.5",
            "version": 1,
            "metadata": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "component": {
                    "type": "application",
                    "name": "RealityTunnel Billing & Auth Service",
                    "version": "1.0.0",
                },
            },
            "components": [],
        }
        cdx_file.write_text(json.dumps(cdx_payload, indent=2), encoding="utf-8")
        print(f"Generated fallback CycloneDX SBOM at {cdx_file}")

    # Generate minimal valid SPDX JSON structure
    spdx_payload = {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": "RealityTunnel-SBOM",
        "documentNamespace": f"https://realitytunnel.io/spdx/{datetime.now(timezone.utc).timestamp()}",
        "creationInfo": {
            "created": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "creators": ["Tool: RealityTunnel-SBOM-Generator"],
        },
        "packages": [
            {
                "name": "realitytunnel-billing-server",
                "SPDXID": "SPDXRef-Package-Root",
                "versionInfo": "1.0.0",
                "downloadLocation": "NOASSERTION",
                "licenseConcluded": "MIT",
                "licenseDeclared": "MIT",
            }
        ],
    }
    spdx_file.write_text(json.dumps(spdx_payload, indent=2), encoding="utf-8")
    print(f"Generated SPDX SBOM at {spdx_file}")

    return {
        "cyclonedx": str(cdx_file),
        "spdx": str(spdx_file),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate CycloneDX and SPDX SBOMs.")
    parser.add_argument("--output-dir", "-o", default=".", help="Directory to store generated SBOM files")
    args = parser.parse_args()

    generate_local_sbom(args.output_dir)


if __name__ == "__main__":
    main()
