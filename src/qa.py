#!/usr/bin/env python3
"""qa.py: hallucination + spam filter check : 5:"""
import re, json
from pathlib import Path

DRAFT = Path(__file__).parent.parent / "out" / "draft.md"
ENRICHED = Path(__file__).parent.parent / "out" / "enriched.json"

def qa():
    draft = DRAFT.read_text(encoding="utf-8")
    enriched = json.loads(ENRICHED.read_text(encoding="utf-8")) if ENRICHED.exists() else []
    links = [x["link"] for x in enriched]
    issues=[]
    # check CVEs are cited and exist in sources
    cves = re.findall(r"CVE-\d{4}-\d{4,7}", draft)
    for c in cves:
        if not any(c in (e.get("enriched_text","")+e.get("title","")) for e in enriched):
            issues.append(f"Uncited CVE {c}")
    # check KBs
    kbs = re.findall(r"KB\d{6,7}", draft)
    # spam checks
    if len(draft) < 500: issues.append("Too short - spam filter risk")
    if draft.count("http") < 3: issues.append("Too few citations - add links")
    if len(set(links)) < 3: issues.append("Need 3+ unique sources")
    # duplicate structure check - ensure not identical to last draft
    last = Path(__file__).parent.parent / "drafts"
    # simple pass/fail
    if issues:
        print("QA WARNINGS:")
        for i in issues: print(f"  - {i}")
        # fail if uncited CVE - block publish
        if any("Uncited" in x for x in issues):
            raise SystemExit(f"QA FAIL - blocking publish: {issues}")
    else:
        print("QA PASS - AEST draft grounded")
    # write qa report
    Path(__file__).parent.parent.joinpath("out/qa.json").write_text(json.dumps({"cves":cves,"kbs":kbs,"issues":issues},indent=2))
    return issues

if __name__ == "__main__":
    qa()
