# The IT Support Guru - Headless Substack Publisher (Fixed AEST UTC+10)

Automated pipeline for `https://theitsupportguru.substack.com` — 3x/week neutral analyst brief (Tue/Thu/Sun 06:12-06:27 AEST ± jitter, fixed UTC+10 year-round).

## Quick Start
1. Copy `.env.example` -> `.env`, fill `OPENAI_API_KEY, TAVILY_API_KEY, SUBSTACK_EMAIL, SMTP_*`
2. `pip install -r requirements.txt`
3. `python src/ingest.py && python src/score.py && python src/enrich.py && python src/synthesize.py && python src/qa.py`
4. `SKIP_SLEEP=1 python src/publish.py` -> writes `out/email.eml` + Telegram draft (AEST)

## Deploy Headless (GitHub Actions)
- Push to GitHub, add Secrets (`SUBSTACK_EMAIL, SMTP_*, TELEGRAM_*, OPENAI_API_KEY, TAVILY_API_KEY, AUTO_PUBLISH=0`)
- Cron `.github/workflows/publish.yml:10` fires Mon/Wed/Sat 18:00 UTC (= Tue/Thu/Sun 04:00 AEST) then jitters to 06:12-06:27 AEST for bot-randomness.
- 30d gate: Telegram shows draft with APPROVE/REJECT. Reply APPROVE or run `python src/approve.py approve drafts/2026-xx-xx-xxx.md`
- After 12 approved (~30d), set Secret `AUTO_PUBLISH=1` -> fully headless.

## Anti-Bot Design (AEST Fixed + Randomness)
- **Email-to-Post** is whitelisted (no `sid` cookie, no fingerprint). GitHub IP not flagged.
- **Jitter**: `publish.py:45` sleeps 2h12m-2h27m (12-27m + 0-59s random) so publish second/millis varies, defeats cron-bot heuristic.
- **Variance**: Varying subject `variants[]`, 3 templates, `User-Agent: TheITSupportGuru-publisher/1.0`, unique `Message-ID`, 3+ citations/draft.
- Warm-up: 1 post/week week 1, then 3x/week.

## Schedule (Fixed AEST UTC+10)
| Edition | Local AEST | UTC Cron |
|---|---|---|
| Patch Brief | Tue 06:15 AEST | Mon 18:00 UTC + jitter |
| Threat Watch | Thu 06:15 AEST | Wed 18:00 UTC + jitter |
| Copilot Lab | Sun 06:15 AEST | Sat 18:00 UTC + jitter |

## Structure
`config/sources.yaml` (38 feeds) | `prompts/analyst_system.md` (neutral voice) | `src/` pipeline | `drafts/*.md` | `out/` artifacts

Verify: `python -m py_compile src/*.py`
