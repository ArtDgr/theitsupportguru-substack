#!/usr/bin/env python3
"""approve.py - helper for Telegram gate: python src/approve.py approve|reject <draft_file>"""
import sys, json
from pathlib import Path
from datetime import datetime, timezone, timedelta

AEST = timezone(timedelta(hours=10))
STATE = Path(__file__).parent.parent / "out" / "state.json"

if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv)>1 else "status"
    if action == "status":
        print(STATE.read_text() if STATE.exists() else "No publishes yet (gate active)")
    elif action == "approve":
        # called by Telegram bot webhook or manually
        draft = Path(sys.argv[2]) if len(sys.argv)>2 else Path("out/draft.md")
        import publish
        publish.publish_email(draft.read_text(encoding="utf-8"))
        print(f"Approved AEST {datetime.now(AEST).isoformat()}")
    elif action == "reject":
        print(f"Rejected AEST {datetime.now(AEST).isoformat()} - draft kept")
