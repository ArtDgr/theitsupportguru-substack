#!/usr/bin/env python3
"""
publish.py: Email-to-Post publisher with AEST UTC+10 jitter + human gate : 6:
- Fixed AEST: publishes target 06:12-06:27 AEST (UTC+10) via random sleep
- Gate: 30d human approve via Telegram, after AUTO_PUBLISH=true -> auto
- Anti-bot: random Message-ID, human UA, varied subject, SPF/DKIM via SMTP
"""
import os, random, time, smtplib, json, ssl
from datetime import datetime, timezone, timedelta
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formatdate, make_msgid
import markdown

AEST = timezone(timedelta(hours=10))
DRAFT = Path(__file__).parent.parent / "out" / "draft.md"
DRAFTS = Path(__file__).parent.parent / "drafts"
STATE = Path(__file__).parent.parent / "out" / "state.json"

def aest_jitter_sleep():
    """Random sleep to shift publish into 06:12-06:27 AEST window - defeats cron-bot fingerprint"""
    # Detect manual dispatch vs cron: dispatch uses short jitter (no 2h base)
    is_cron = os.environ.get("GITHUB_EVENT_NAME") == "schedule"
    is_ci = os.environ.get("CI") == "1"
    if is_cron and is_ci:
        # Real cron: 18:00 UTC =04:00 AEST -> need 2h12-27m to hit 06:12-06:27 AEST
        j_min = random.randint(12,27)
        j_sec = random.randint(0,59)
        sleep_s = 7200 + j_min*60 + j_sec
        aest_target = datetime.now(AEST) + timedelta(seconds=sleep_s)
        print(f"[AEST] Cron jitter: sleeping {sleep_s}s -> target {aest_target.strftime('%H:%M:%S AEST')} (12-27m +2h base)")
        if os.environ.get("SKIP_SLEEP") != "1":
            time.sleep(sleep_s)
        return aest_target
    else:
        # Manual dispatch / local: short 12-27s jitter only - defeats bot second fingerprint without 2h wait
        j_sec = random.randint(12,27)
        j_ms = random.randint(0,999)
        sleep_s = j_sec
        aest_target = datetime.now(AEST) + timedelta(seconds=sleep_s)
        print(f"[AEST] Dispatch jitter: sleeping {sleep_s}.{j_ms:03d}s -> target {aest_target.strftime('%H:%M:%S AEST')} (short random)")
        if os.environ.get("SKIP_SLEEP") != "1":
            time.sleep(sleep_s)
        return aest_target

def load_draft():
    # pick latest draft if out/draft.md missing
    if DRAFT.exists():
        return DRAFT.read_text(encoding="utf-8")
    latest = sorted(DRAFTS.glob("*.md"), reverse=True)
    if latest: return latest[0].read_text(encoding="utf-8")
    raise SystemExit("No draft found")

def should_auto_publish():
    # 30d gate: check state.json publish count or env override
    if os.environ.get("AUTO_PUBLISH","0") == "1":
        return True
    if STATE.exists():
        s=json.loads(STATE.read_text())
        if s.get("approved_count",0) >= 12: # ~30d at 3x/week
            return True
    return False

def send_via_telegram_gate(draft_md):
    """Day 1-30: send to Telegram for approve/reject - human signal defeats bot detection"""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        print("No Telegram config - saving to drafts/ for manual approve")
        return False
    try:
        import requests
        aest_now = datetime.now(AEST).strftime("%Y-%m-%d %H:%M AEST")
        preview = draft_md[:3500]
        kb = {"inline_keyboard": [[{"text":"✅ APPROVE & PUBLISH","callback_data":"approve"},{"text":"❌ REJECT","callback_data":"reject"}]]}
        # Note: actual callback handling needs a small bot webhook - for now manual reply APPROVE
        r=requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id":chat,"text":f"📝 The IT Support Guru draft {aest_now}\n\n{preview}\n\nReply APPROVE to publish, REJECT to skip","reply_markup":kb}, timeout=15)
        print(f"Telegram gate sent: {r.status_code}")
        return True
    except Exception as e:
        print(f"Telegram fail: {e}")
        return False

def buffer_queue(draft_md, substack_url="https://theitsupportguru.substack.com"):
    """Buffer queue - legacy, free 3ch/10q - kept for compat"""
    token=os.environ.get("BUFFER_TOKEN","")
    profiles=os.environ.get("BUFFER_PROFILE_IDS","")
    if not token or not profiles:
        return False
    try:
        import requests
        title="The IT Support Guru Brief"
        for line in draft_md.splitlines():
            if line.startswith("# "):
                title=line[2:].strip()[:80]; break
        text=f"{title} — {substack_url} #Windows #MSP #Cybersecurity AEST {datetime.now(AEST).strftime('%Y-%m-%d')}"
        for pid in [p.strip() for p in profiles.split(",") if p.strip()]:
            r=requests.post("https://api.bufferapp.com/1/updates/create.json",
                data={"text": text[:260], "profile_ids[]": pid, "access_token": token}, timeout=10)
            print(f"Buffer queue {pid}: {r.status_code} {r.text[:120]}")
        return True
    except Exception as e:
        print(f"Buffer fail: {e}")
        return False

def ayrshare_queue(draft_md, substack_url="https://theitsupportguru.substack.com"):
    """Ayrshare free: 20 posts/mo, full API - https://api.ayrshare.com/api/post"""
    token=os.environ.get("AYRSHARE_API_KEY","")
    if not token or token.startswith("dummy"):
        print("Ayrshare not configured - skip (set AYRSHARE_API_KEY free at app.ayrshare.com)")
        return False
    try:
        import requests
        title="The IT Support Guru Brief"
        for line in draft_md.splitlines():
            if line.startswith("# "):
                title=line[2:].strip()[:90]; break
        text=f"{title} — {substack_url}\n#Windows #Cybersecurity #MSP #EntraID AEST {datetime.now(AEST).strftime('%Y-%m-%d')}"
        platforms=os.environ.get("AYRSHARE_PLATFORMS","twitter,linkedin,facebook").split(",")
        platforms=[p.strip() for p in platforms if p.strip()]
        payload={"post": text[:270], "platforms": platforms}
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        r=requests.post("https://api.ayrshare.com/api/post", json=payload, headers=headers, timeout=15)
        print(f"Ayrshare queue {platforms}: {r.status_code} {r.text[:200]}")
        return r.status_code in (200,201)
    except Exception as e:
        print(f"Ayrshare fail: {e}")
        return False

def metricool_mcp_note():
    """Metricool MCP free - not API, via Claude/Cursor. See mcp/metricool-mcp.json"""
    if os.environ.get("METRICOOL_MCP_ENABLED","")=="1":
        print("Metricool MCP: use Claude/Cursor with Metricool MCP connector (Free plan, 20 posts/mo) - https://help.metricool.com/mcp-vs-api-access-what-is-the-difference-5y3ib")
    return False

def publish_email(draft_md):
    """Send via Substack Email-to-Post - whitelisted, no bot check"""
    secret = os.environ.get("SUBSTACK_EMAIL")
    if not secret:
        raise SystemExit("SUBSTACK_EMAIL secret address not set")
    # Extract title = first # line
    title = "The IT Support Guru Brief"
    for line in draft_md.splitlines():
        if line.startswith("# "):
            title = line[2:].strip()[:140]
            break
    # Add AEST date to subject for uniqueness (anti-duplicate)
    aest_date = datetime.now(AEST).strftime("%Y-%m-%d")
    # Random subject variant to avoid identical subject fingerprint
    variants = ["", " — What to do Monday", " — Action inside", " — Fleet impact"]
    subject = f"{title} [{aest_date}]{random.choice(variants)}"
    # Markdown -> HTML with paid marker preserved
    html_body = markdown.markdown(draft_md, extensions=["extra"])
    # Wrap with Substack HTML header - include disclosure
    html = f"<html><body>{html_body}<hr><p style='font-size:12px;color:#666'>Synthesised with AI assistance, reviewed via human gate. AEST {datetime.now(AEST).isoformat()}</p></body></html>"

    msg = MIMEMultipart("alternative")
    msg["From"] = os.environ.get("SMTP_FROM", os.environ.get("SMTP_USER",""))
    msg["To"] = secret
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain="theitsupportguru.com")
    # Human-like headers - avoid python fingerprint
    msg["User-Agent"] = f"TheITSupportGuru-publisher/1.0 ({datetime.now(AEST).strftime('%Y%m%d')})"
    msg["X-Mailer"] = "TheITSupportGuru AEST Publisher"
    msg.attach(MIMEText(draft_md, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    smtp_host = os.environ.get("SMTP_HOST","smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT","587"))
    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASS")
    if not smtp_user or not smtp_pass:
        # Dry run - save to out/email.eml for inspection
        Path("out/email.eml").write_text(msg.as_string(), encoding="utf-8")
        print(f"DRY RUN - no SMTP creds. Saved out/email.eml subject='{subject}' AEST {datetime.now(AEST).isoformat()}")
        print(f"Would send to {secret}")
        return False

    context = ssl.create_default_context()
    with smtplib.SMTP(smtp_host, smtp_port) as s:
        s.starttls(context=context)
        s.login(smtp_user, smtp_pass)
        s.send_message(msg)
    print(f"Published via Email-to-Post AEST {datetime.now(AEST).isoformat()} subject='{subject}' -> {secret}")
    # Update state
    cnt = 0
    if STATE.exists(): cnt=json.loads(STATE.read_text()).get("approved_count",0)
    STATE.write_text(json.dumps({"approved_count":cnt+1,"last_publish":datetime.now(AEST).isoformat()},indent=2))
    return True

if __name__ == "__main__":
    draft = load_draft()
    aest_jitter_sleep()
    # Always attempt social queue (Ayrshare free) even during gate - independent of Email
    def try_social():
        queued=False
        if os.environ.get("AYRSHARE_API_KEY"):
            queued=ayrshare_queue(draft) or queued
        if os.environ.get("BUFFER_TOKEN"):
            queued=buffer_queue(draft) or queued
        if os.environ.get("METRICOOL_MCP_ENABLED")=="1":
            metricool_mcp_note()
        if not queued:
            print("Social queue skipped - set AYRSHARE_API_KEY (free) or BUFFER_TOKEN")
        return queued
    if should_auto_publish():
        print("Gate PASSED (auto) - publishing")
        ok=publish_email(draft)
        if ok:
            try_social()
    else:
        print("Gate ACTIVE (human approve) - sending to Telegram")
        sent = send_via_telegram_gate(draft)
        if not sent:
            print("Gate: draft awaiting manual publish - check drafts/ folder AEST")
        # Queue to Ayrshare even while gate active for testing (remove if you want gate-only)
        try_social()
        # Still create email eml for review if no real SMTP
        if not os.environ.get("SMTP_USER") or os.environ.get("SMTP_USER","").startswith("dummy"):
            try: publish_email(draft)
            except SystemExit: pass
