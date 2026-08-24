#!/usr/bin/env python3
"""schedule_gate.py - Random AEST schedule, max 12/mo, IT admin/enterprise focus : 7:
- Fixed AEST UTC+10, random 06:12-09:47, random day, max 12/month for Substack algo compliance
"""
import random, json, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

AEST = timezone(timedelta(hours=10))
STATE = Path(__file__).parent.parent / "out" / "state.json"
CONFIG = Path(__file__).parent.parent / "out" / "schedule.json"

def should_publish(randomize=True):
    now = datetime.now(AEST)
    yyyymm = now.strftime("%Y-%m")
    day = now.weekday() # 0 Mon
    # No Sunday spam? Allow but rarer. Exclude? Allow all but weight weekends lower.
    # Load state
    state = {}
    if STATE.exists():
        try: state=json.loads(STATE.read_text())
        except: state={}
    month_key = f"published_{yyyymm}"
    count = state.get(month_key, 0)
    # Max 12/month hard cap
    if count >= 12:
        print(f"[GATE] SKIP - monthly cap 12 reached ({count}/12) for {yyyymm} AEST")
        return False, f"cap-{yyyymm}"
    if not randomize:
        return True, "dispatch"
    # Random day roll: ~40% daily chance -> ~12/mo (12/30=0.40), but add weekday weights for IT admin
    # Mon/Tue/Thu highest (patch/triage days), Sat/Sun lower (enterprise rarely reads)
    weights = {0:0.55, 1:0.60, 2:0.35, 3:0.60, 4:0.30, 5:0.15, 6:0.10} # Mon-Sun
    p = weights.get(day, 0.35)
    # Near end of month, increase p if behind target to hit ~12
    days_left = 30 - now.day
    expected = 12 * (now.day / 30)
    if count < expected -1 and days_left > 0:
        p = min(0.85, p + 0.25) # catch up
    elif count > expected +1:
        p = max(0.10, p - 0.20) # slow down
    roll = random.random()
    will = roll < p
    print(f"[GATE] Day {now.strftime('%a %Y-%m-%d %H:%M AEST')} p={p:.2f} roll={roll:.3f} -> {'PUBLISH' if will else 'SKIP'} ({count}/12 {yyyymm})")
    # Save decision log
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps({"date": now.isoformat(), "p": p, "roll": roll, "will": will, "count": count, "yyyymm": yyyymm}, indent=2))
    return will, f"p{p:.2f}"

if __name__ == "__main__":
    # called by workflow before heavy steps to save LLM credits
    import os
    force = os.environ.get("FORCE_PUBLISH")=="1" or os.environ.get("GITHUB_EVENT_NAME")=="workflow_dispatch"
    ok, reason = should_publish(randomize=not force)
    if not ok:
        print(f"::notice::Skipped - {reason} (random AEST gate, max 12/mo)")
        # Exit 0 but create marker so publish.py also skips
        Path("out/skip_gate").write_text(reason)
        sys.exit(0)
    # Mark publish
    Path("out/skip_gate").unlink(missing_ok=True)
