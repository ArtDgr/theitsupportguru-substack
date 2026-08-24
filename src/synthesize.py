#!/usr/bin/env python3
"""synthesize.py: Neutral analyst synthesis -> draft.md : 4: AEST dated"""
import json, os, random
from datetime import datetime, timezone, timedelta
from pathlib import Path
from openai import OpenAI

AEST = timezone(timedelta(hours=10))
ENRICHED = Path(__file__).parent.parent / "out" / "enriched.json"
PROMPT_FILE = Path(__file__).parent.parent / "prompts" / "analyst_system.md"
DRAFTS = Path(__file__).parent.parent / "drafts"
OUT = Path(__file__).parent.parent / "out" / "draft.md"

EDITION_MAP = {1:"Patch & Platform Brief", 3:"Threat Watch", 6:"Copilot Lab"} # Mon=0

def synthesize():
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    enriched = json.loads(ENRICHED.read_text(encoding="utf-8"))
    system = PROMPT_FILE.read_text(encoding="utf-8")
    aest_now = datetime.now(AEST)
    # Determine edition by weekday (AEST)
    wd = aest_now.weekday() # 0 Mon
    # Our crons run Tue/Thu/Sun -> map to templates
    if wd == 1: edition = "Patch & Platform Brief (Tue)"
    elif wd == 3: edition = "Threat Watch (Thu)"
    else: edition = "Copilot Lab (Sun)"
    # pick 5-7 top items for synthesis
    top = enriched[:7]
    context = "\n\n".join([f"[{i+1}] {t['title']} ({t['link']}) Score {t['score']}\n{t.get('enriched_text','')[:1200]}" for i,t in enumerate(top)])
    # vary template to avoid duplicate structure fingerprint
    vary = random.choice(["Use tables for persona impact","Use bullets for checklist","Use numbered steps for Lab"])
    user = f"""Date AEST: {aest_now.strftime('%Y-%m-%d %A %H:%M AEST')}
Edition: {edition}
Instruction variance: {vary}
Sources to synthesize (cite each claim):
{context}

Output markdown with title "# {{Title}} — {{Date AEST}}" and all required sections from system prompt. Include <!-- paid --> before Paid Playbook. Footer disclosure required.
"""
    resp = client.chat.completions.create(
        model=os.environ.get("OPENAI_MODEL","gpt-4o"),
        messages=[{"role":"system","content": system},{"role":"user","content": user}],
        temperature=0.6, max_tokens=3500
    )
    draft = resp.choices[0].message.content.strip()
    # ensure paid marker exists
    if "<!-- paid -->" not in draft:
        draft = draft.replace("## Paid Playbook","<!-- paid -->\n## Paid Playbook")
    # write dated draft
    DRAFTS.mkdir(parents=True, exist_ok=True)
    fname = f"{aest_now.strftime('%Y-%m-%d')}-{edition.split()[0].lower()}.md"
    (DRAFTS / fname).write_text(draft, encoding="utf-8")
    OUT.write_text(draft, encoding="utf-8")
    print(f"Draft -> drafts/{fname} ({len(draft)} chars) AEST {aest_now.isoformat()}")
    return draft

if __name__ == "__main__":
    synthesize()
