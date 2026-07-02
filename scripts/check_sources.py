#!/usr/bin/env python3
"""Check known sources for new free AI credit opportunities.

Outputs a JSON report of candidate platforms discovered.
This script is designed to be run in CI via GitHub Actions weekly.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA_FILE = ROOT / "data" / "platforms.json"

# Known platform identifiers we already track
def get_known_ids() -> set[str]:
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    return {p["id"] for p in data}


def check_github_repos() -> list[dict]:
    """Scan known GitHub aggregator repos for mentions."""
    import urllib.request

    found = []
    # Key repos that list free AI tools/credits
    urls = [
        "https://raw.githubusercontent.com/xx025/carrot/main/README.md",
    ]
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                text = resp.read().decode("utf-8", errors="replace")
            # Look for platform names + benefit patterns
            for line in text.splitlines():
                # Match lines with benefit patterns (tokens, free, credit)
                m = re.search(r'[-*]\s*(.+?)[：:：]\s*(.+?)(?:\n|$)', line)
                if m and any(kw in line for kw in ["免费", "token", "Token", "credit", "额度", "代金"]):
                    name = m.group(1).strip()[:30]
                    benefit = m.group(2).strip()[:80]
                    found.append({"source": url, "name": name, "benefit": benefit, "raw": line.strip()[:150]})
        except Exception as e:
            print(f"  [WARN] Failed to fetch {url}: {e}", file=sys.stderr)
    return found


def generate_report(candidates: list[dict]) -> dict:
    known = get_known_ids()
    new_candidates = [c for c in candidates if c["name"] not in known]
    return {
        "known_platforms": list(known),
        "candidates_total": len(candidates),
        "new_candidates": new_candidates[:20],
    }


def main():
    print("Checking GitHub aggregator repos...")
    candidates = check_github_repos()
    report = generate_report(candidates)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["new_candidates"]:
        print(f"\n{len(report['new_candidates'])} new candidates found. Review and add to platforms.json.")
        sys.exit(1 if len(report["new_candidates"]) > 5 else 0)
    else:
        print("\nNo new candidates found.")


if __name__ == "__main__":
    main()
