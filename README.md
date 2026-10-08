# Panchanga MCP

An [MCP](https://modelcontextprotocol.io) server that lets AI assistants (Claude, Gemini CLI, Cursor, etc.) fetch the daily Panchanga from the Panchanga API instead of guessing.

## Tools

| Tool | Purpose |
|---|---|
| `get_panchanga` | Full daily panchanga: tithi, nakshatra, yoga, karana, vara, masa, samvatsara, sunrise/sunset, muhurtas, special events. `raw=true` returns the API JSON untouched. |
| `get_muhurtas` | Only auspicious (Abhijit, Brahma, Vijaya, Amrita, Godhuli) and inauspicious (Rahu, Yamaganda, Gulika, Durmuhurta, Varjyam) windows. |
| `get_panchanga_text` | Short readable summary, ideal for chat replies. |

All tools accept optional `date` (YYYY-MM-DD, default today), `lat`, `lon`, `tz`, `lang`. Defaults: Bengaluru, `Asia/Kolkata`, `kannada`.

> The API response doesn't currently document a `date` parameter in its `requested` block beyond echoing it. If your backend ignores `date`, the tools simply return today's data.

## Configuration (env vars)

| Variable | Default |
|---|---|
| `PANCHANGA_API_BASE` | `https://panchanga-backend-production.up.railway.app` |
| `PANCHANGA_DEFAULT_LAT` / `_LON` | `12.9716` / `77.5946` |
| `PANCHANGA_DEFAULT_TZ` | `Asia/Kolkata` |
| `PANCHANGA_DEFAULT_LANG` | `kannada` |
| `PANCHANGA_MCP_TRANSPORT` | `stdio` (or `streamable-http`) |

## Use locally (stdio)

```bash
pip install .            # or: uvx --from . panchanga-mcp
```

**Claude Desktop** (`claude_desktop_config.json`):
```json
{ "mcpServers": { "panchanga": { "command": "panchanga-mcp" } } }
```

**Claude Code:** `claude mcp add panchanga -- panchanga-mcp`

**Gemini CLI** (`~/.gemini/settings.json`):
```json
{ "mcpServers": { "panchanga": { "command": "panchanga-mcp" } } }
```

## Host it remotely (for any user, no install)

Deploy the included `Dockerfile` (e.g. as a second Railway service). It serves MCP over streamable HTTP at `https://<your-host>/mcp`. Users then add that URL as a custom connector (Claude) or `httpUrl` (Gemini CLI):

```json
{ "mcpServers": { "panchanga": { "httpUrl": "https://<your-host>/mcp" } } }
```

Add authentication or rate limiting before making a public endpoint widely available.
