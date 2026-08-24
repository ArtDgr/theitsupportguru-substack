#!/usr/bin/env python3
"""enrich.py: Tavily scrape top scored items for grounded synthesis : 3:"""
import json, os, time
from pathlib import Path

SCORED = Path(__file__).parent.parent / "out" / "scored.json"
ENRICHED = Path(__file__).parent.parent / "out" / "enriched.json"

def enrich():
    try:
        from tavily import TavilyClient
        has_tavily = True
    except ImportError:
        has_tavily=False
    items = json.loads(SCORED.read_text(encoding="utf-8"))
    if not has_tavily or not os.environ.get("TAVILY_API_KEY"):
        print("No Tavily - using RSS summary only")
        for it in items: it["enriched_text"]=it["summary"]
        ENRICHED.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")
        return items
    client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    for it in items[:8]: # enrich top 8 only - cost control
        try:
            res = client.extract(urls=[it["link"]], query="Windows patch, CVE, Intune, Entra")
            txt = ""
            if res.get("results"):
                txt = res["results"][0].get("content","")[:5000]
            it["enriched_text"]= txt or it["summary"]
            print(f"  enriched {it['title'][:50]} -> {len(it['enriched_text'])} chars")
            time.sleep(1.2)
        except Exception as e:
            print(f"  enrich fail {it['link']}: {e}")
            it["enriched_text"]=it["summary"]
    ENRICHED.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")
    return items

if __name__ == "__main__":
    enrich()
