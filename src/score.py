#!/usr/bin/env python3
"""score.py: LLM relevance scoring 0-10 : 2: filters >7 only"""
import json, os, yaml
from pathlib import Path
from openai import OpenAI

INGEST = Path(__file__).parent.parent / "out" / "ingest.json"
SCORED = Path(__file__).parent.parent / "out" / "scored.json"
CONFIG = Path(__file__).parent.parent / "config" / "sources.yaml"

PROMPT = """Score 0-10 for relevance to IT admin & enterprise Windows fleet (MSP/Sysadmin/Entra) in Australia (AEST).
Prioritize: Intune/MSP/Entra ID/Defender/AD/GPO/Patch Tuesday/CVE/KEV. Downrank consumer/gaming.
10=Patch Tuesday/KEV/Intune/Entra/Admin breaking. 5=generic AI. 0=irrelevant consumer.
Return JSON: {{"score": int, "reason": "1 sentence"}}"""

def heuristic_score(it):
    t=(it['title']+' '+it['summary']).lower()
    s=4.0+it.get('weight',1)
    # IT admin & enterprise bias (higher weight)
    if any(k in t for k in ['intune','entra id','defender','active directory','group policy','wsus','sccm','patch tuesday','kb50','windows server','azure ad','conditional access']): s+=3
    if any(k in t for k in ['msp','helpdesk','sophos','datto','kaseya','n-able','passportal','rce','privilege escalation','cve','kev','cisa','exploit','ransom']): s+=2
    if any(k in t for k in ['copilot','windows 11','outlook','teams','sharepoint']): s+=1
    if 'entra' in t: s+=1.0
    if 'cisa' in t: s+=0.8
    return min(10,s)

def gemini_score(text):
    """Gemini Flash free tier scorer - google.genai"""
    try:
        from google import genai
        client=genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
        # Use flash-latest (available to new users) - 2.5-flash deprecated per 404
        for m in ["gemini-flash-latest", "gemini-2.0-flash", "gemini-pro-latest"]:
            try:
                resp=client.models.generate_content(model=m, contents=PROMPT + "\n\n" + text)
                return resp.text
            except Exception as e:
                if "404" in str(e) or "503" in str(e): continue
                raise
        raise ValueError("No Gemini model available")
    except ImportError:
        import google.generativeai as genai2
        genai2.configure(api_key=os.environ.get("GEMINI_API_KEY"))
        for m in ["gemini-flash-latest", "gemini-1.5-flash"]:
            try:
                model=genai2.GenerativeModel(m)
                resp=model.generate_content(PROMPT + "\n\n" + text)
                return resp.text
            except: continue
        raise

def score_items():
    gem_key=os.environ.get("GEMINI_API_KEY","")
    use_gemini = gem_key and not gem_key.startswith("dummy") and gem_key != ""
    api_key=os.environ.get("OPENAI_API_KEY","")
    use_openai = not use_gemini and api_key and not api_key.startswith("sk-dummy")
    client = OpenAI(api_key=api_key) if use_openai else None
    items = json.loads(INGEST.read_text(encoding="utf-8"))
    cfg = yaml.safe_load(CONFIG.read_text())
    thresholds = cfg.get("thresholds", {"patch":7,"threat":7,"lab":6.5})
    scored=[]
    for it in items[:60]: # cap cost
        pillar = it.get("pillar","all")
        th = thresholds.get(pillar, thresholds.get("all",7)) if pillar!="all" else 7
        if use_gemini:
            try:
                txt=gemini_score(f"Title: {it['title']}\nSummary: {it['summary']}\nSource: {it['source_url']}")
                import re, json as j
                m=re.search(r'\{.*\}',txt, re.S)
                data=j.loads(m.group(0)) if m else {"score":5,"reason":"parse fail"}
                it["score"]=float(data.get("score",5))
                it["score_reason"]=data.get("reason","")+" (gemini)"
            except Exception as e:
                # Fix charmap emoji error on Windows cp1252
                safe_e=str(e).encode('utf-8', errors='replace').decode('utf-8', errors='replace')
                print(f"gemini score fail: {safe_e[:80]} -> heuristic")
                it["score"]=round(heuristic_score(it),1)
                it["score_reason"]="heuristic fallback"
        elif not use_openai:
            it["score"]=round(heuristic_score(it),1)
            it["score_reason"]="heuristic AEST fallback"
        else:
            try:
                resp = client.chat.completions.create(
                    model=os.environ.get("OPENAI_MODEL","gpt-4o-mini"),
                    messages=[
                        {"role":"system","content":PROMPT},
                        {"role":"user","content": f"Title: {it['title']}\nSummary: {it['summary']}\nSource: {it['source_url']}"}
                    ],
                    temperature=0.2, max_tokens=80
                )
                txt = resp.choices[0].message.content
                import re, json as j
                m=re.search(r'\{.*\}',txt, re.S)
                data=j.loads(m.group(0)) if m else {"score":5,"reason":"parse fail"}
                it["score"]=float(data.get("score",5))
                it["score_reason"]=data.get("reason","")
            except Exception as e:
                print(f"score fail {it['title'][:40]}: {e} -> heuristic")
                it["score"]=round(heuristic_score(it),1)
                it["score_reason"]="heuristic fallback"
        if it["score"] >= th:
            scored.append(it)
    scored.sort(key=lambda x: x["score"], reverse=True)
    # keep top 12 to avoid spam filter duplicate content
    scored = scored[:12]
    SCORED.write_text(json.dumps(scored, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Scored {len(items)} -> {len(scored)} passed threshold")
    return scored

if __name__ == "__main__":
    if not INGEST.exists():
        raise SystemExit("Run ingest.py first")
    score_items()
