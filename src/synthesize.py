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

def synthesize_fallback(enriched):
    """Heuristic fallback when OPENAI_API_KEY invalid - uses local template : 4b:"""
    aest_now = datetime.now(AEST)
    top = enriched[:7]
    title = f"The Windows Stack Brief \u2014 {aest_now.strftime('%d %b %Y')} AEST"
    def fmt(it): return f"[{it['title']}]({it['link']})"
    md = f"""# {title}

> **TL;DR** \u2014 What to patch, what to block, what to automate before Monday stand-up (AEST).
*   **Patch:** {fmt(top[0])} + Windows 365 / Insider updates
*   **Threat:** {fmt(top[3]) if len(top)>3 else fmt(top[0])} + active exploitation signals
*   **Action:** Check Monday checklist below.

## What Happened
Windows platform and threat signals from top {len(top)} sources. See sources for detail.

## Why It Matters to You
| Persona | Impact |
|---|---|
| **MSP / Helpdesk** | Teams/email phishing bypass - brief helpdesk |
| **Sysadmin / Entra** | Identity + driver abuse risk - audit admin |
| **Enthusiast** | Insider / AI tooling updates |

## What To Do \u2014 Monday Checklist (AEST)
1. Review top links: {', '.join([fmt(t) for t in top[:3]])}
2. Patch / verify Entra ID and Windows updates in non-prod
3. Harden Teams external access

<!-- paid -->
## Paid Playbook
Full scripts and KQL in paid edition. AEST {aest_now.isoformat()}

*Synthesised with fallback (no valid OPENAI_API_KEY), reviewed via human gate. AEST {aest_now.strftime('%Y-%m-%d %H:%M AEST')}*
Sources: {', '.join([f"[{i+1}]({t['link']})" for i,t in enumerate(top)])}
"""
    DRAFTS.mkdir(parents=True, exist_ok=True)
    edition = "Fallback"
    if aest_now.weekday()==1: edition="Patch"
    elif aest_now.weekday()==3: edition="Threat"
    else: edition="Lab"
    fname = f"{aest_now.strftime('%Y-%m-%d')}-{edition.lower()}.md"
    (DRAFTS / fname).write_text(md, encoding="utf-8")
    OUT.write_text(md, encoding="utf-8")
    print(f"Fallback draft -> drafts/{fname} ({len(md)} chars) AEST {aest_now.isoformat()}")
    return md

def synthesize():
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
    # try Gemini free first, then OpenAI, then fallback
    gem_key=os.environ.get("GEMINI_API_KEY","")
    if gem_key and not gem_key.startswith("dummy") and gem_key!="":
        try:
            try:
                from google import genai as genai2
                client=genai2.Client(api_key=gem_key)
                resp=client.models.generate_content(model="gemini-2.5-flash", contents=system + "\n\n" + user)
                draft=resp.text.strip()
            except ImportError:
                import google.generativeai as genai
                genai.configure(api_key=gem_key)
                model=genai.GenerativeModel("gemini-2.5-flash")
                resp=model.generate_content(system + "\n\n" + user)
                draft=resp.text.strip()
            if "<!-- paid -->" not in draft:
                draft=draft.replace("## Paid Playbook","<!-- paid -->\n## Paid Playbook")
            DRAFTS.mkdir(parents=True, exist_ok=True)
            fname = f"{aest_now.strftime('%Y-%m-%d')}-{edition.split()[0].lower()}.md"
            (DRAFTS / fname).write_text(draft, encoding="utf-8")
            OUT.write_text(draft, encoding="utf-8")
            print(f"Gemini draft -> drafts/{fname} ({len(draft)} chars) AEST {aest_now.isoformat()}")
            return draft
        except Exception as e:
            print(f"Gemini synthesize failed ({e}) -> try OpenAI fallback")
    # try OpenAI, fallback to heuristic if invalid key
    try:
        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        if not os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY","").startswith("sk-dummy"):
            raise ValueError("No valid OPENAI_API_KEY")
        resp = client.chat.completions.create(
            model=os.environ.get("OPENAI_MODEL","gpt-4o"),
            messages=[{"role":"system","content": system},{"role":"user","content": user}],
            temperature=0.6, max_tokens=3500
        )
        draft = resp.choices[0].message.content.strip()
        if "<!-- paid -->" not in draft:
            draft = draft.replace("## Paid Playbook","<!-- paid -->\n## Paid Playbook")
        DRAFTS.mkdir(parents=True, exist_ok=True)
        fname = f"{aest_now.strftime('%Y-%m-%d')}-{edition.split()[0].lower()}.md"
        (DRAFTS / fname).write_text(draft, encoding="utf-8")
        OUT.write_text(draft, encoding="utf-8")
        print(f"Draft -> drafts/{fname} ({len(draft)} chars) AEST {aest_now.isoformat()}")
        return draft
    except Exception as e:
        print(f"OpenAI synthesize failed ({e}) -> fallback heuristic")
        return synthesize_fallback(enriched)

if __name__ == "__main__":
    synthesize()
