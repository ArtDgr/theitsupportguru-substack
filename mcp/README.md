# Metricool MCP (Free) + Ayrshare (Free) for theitsupportguru

## Ayrshare Free (headless GitHub Actions) - Recommended for automation
- Sign up https://app.ayrshare.com -> API Key page -> copy `AYRSHARE_API_KEY`
- `gh secret set AYRSHARE_API_KEY --repo ArtDgr/theitsupportguru-substack`
- Optional: `gh secret set AYRSHARE_PLATFORMS --body "twitter,linkedin,facebook"`
- Publishes via `src/publish.py:ayrshare_queue` POST https://api.ayrshare.com/api/post Bearer token (20/mo free, covers 12/mo at 3x/week)

## Metricool MCP Free (AI client, not GitHub API)
- Docs: https://help.metricool.com/mcp-vs-api-access-what-is-the-difference-5y3ib
- MCP works on Free (API needs Advanced). Use with Claude/Cursor/ChatGPT:
- Claude Desktop: Settings > Developer > Edit Config -> merge mcp/metricool-mcp.json
- Cursor: Settings > MCP > Add Server -> npx @metricool/mcp-server
- Then in AI chat: "Schedule this draft to Metricool for Tue 06:15 AEST" + paste draft.md
- Free limits still apply: 1 brand, 20 posts/mo, 30 days analytics
