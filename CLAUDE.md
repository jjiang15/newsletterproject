# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Purpose

A daily personalized newsletter that pulls from four source newsletters in Gmail, web search, and a random Spotify song, then writes and delivers an email each morning.

## Two Pipelines

**1. Cloud Routine** (no local machine needed)
- Runs daily at 7am ET via Claude Code Routines
- Uses MCP tools: `mcp__claude_ai_Gmail__search_threads`, `mcp__claude_ai_Gmail__create_draft`, `WebSearch`, `WebFetch`
- Reads Gmail at `jjiang15@wharton.upenn.edu` and creates a **draft** (does not send)
- Routine ID: `trig_01Ebkq7ewN4VEszFVWGePjGE`
- Manage at: https://claude.ai/code/routines/trig_01Ebkq7ewN4VEszFVWGePjGE

**2. Python script** (`newsletter.py`)
- Run locally: `python newsletter.py`
- **Sends the email directly** (does not create a draft)
- Reads Gmail at `jannahjiang@gmail.com` via OAuth2 (`credentials.json` + `token.json`)
- First run opens a browser for OAuth consent; subsequent runs use cached `token.json`

The cloud Routine is the primary pipeline. The Python script is the local/GitHub Actions version and source of truth for the prompt logic.

## Running the Python Script

All five env vars must be set before running:

```
$env:ANTHROPIC_API_KEY = "..."
$env:SPOTIFY_CLIENT_ID = "..."
$env:SPOTIFY_CLIENT_SECRET = "..."
$env:SPOTIFY_REFRESH_TOKEN = "..."
python newsletter.py
```

Env vars reset when the terminal closes — they're stored permanently in GitHub Actions secrets.

## Python Script Architecture

`main()` calls these functions in order:

1. `get_gmail_service()` — OAuth2 Gmail auth
2. `fetch_newsletters()` — fetches metadata snippets (not full bodies) from 4 source newsletters + extra inbox scan
3. `web_search()` — 4 DuckDuckGo queries covering headlines, economy, clean energy, AI
4. `fetch_spotify_songs()` — picks a random track from `Spotify_playlists` via Spotify API
5. `generate_newsletter()` — builds prompt, calls `claude-sonnet-4-6` (`max_tokens=5000`), parses `SUBJECT:` line
6. `wrap_html()` + `send_email()` — wraps inner HTML in full email template and sends

## Spotify Integration

Uses OAuth2 Authorization Code flow (not Client Credentials — Spotify removed public playlist access in Feb 2026).

- `get_spotify_token()` — exchanges the refresh token for a short-lived access token on each run
- `fetch_spotify_songs()` — shuffles `Spotify_playlists`, calls `GET /v1/playlists/{id}` (note: `/items` endpoint removed Feb 2026 — tracks are at `data['items']['items'][n]['item']`), returns `{name, artist, url}`
- `spotify_auth.py` — one-time script to get the initial refresh token; runs a local server on `http://127.0.0.1:8888/callback` to catch the OAuth redirect. Only needs to be run once; the refresh token is then stored as a secret.

## Source Newsletters

All subscribed at **jannahjiang@gmail.com**.

| Newsletter | Gmail query |
|---|---|
| Heatmap Daily | `from:(editors@heatmap.news)` |
| CTVC by Sightline Climate | `from:(hello@ctvc.co)` |
| Volts | `subject:(volts)` |
| The Rundown AI | `from:(news@daily.therundown.ai)` |

## Newsletter Structure

Four sections. See `Newsletter_2026-05-04.md` as the reference for tone and format.

**Section 1 — "The World" (3–5 stories)**
- Top front-page news: economy, geopolitics — no clean energy or tech
- Draw from web search only; 2 sentences per story; `Read →` link

**Section 2 — "Clean Energy & Tech" (12–15 stories)**
- Synthesized from source newsletters + web search; 1–2 sentences per story
- Ends with a **Deals** block: `Company — description — $amount`

**Section 3 — "AI" (3–4 stories)**
- From The Rundown AI + web search; product launches, model releases, enterprise deals

**Section 4 — "Now Playing"**
- Random song from `Spotify_playlists`; Claude writes one sentence (max 20 words) on mood/connection to the day; `Listen →` link

## Writing Style

Target voice: `Writing Sample 4.pdf` — confident, analytical, no filler. Every story must name a specific event, decision, number, or person.

Avoid: "It is worth noting", "Notably", "This underscores", "reflects", "amid", "exciting", "game-changing", bullet points inside story paragraphs, meta-commentary about publications, vague summaries.

## HTML Email Format

The prompt in `generate_newsletter()` is the authoritative source for inline styles. Key specs:
- Container: max-width 600px, white background, 48px padding, outer `#f9f9f7`
- Header: "Daily Briefing" (11px uppercase gray Arial) + date (22px normal serif), 2px solid black border below
- Section labels: 11px uppercase gray Arial, letter-spacing 2px
- Body: 15px Georgia, `#111111`, line-height 1.6; headlines bolded inline
- Deals block: `#f9f9f7` background, 14px `#333333`
- Footer: 12px gray Arial, source credits

Subject line: `Theme One, Theme Two, Theme Three · May 8, 2026`
Recipient: jjiang15@wharton.upenn.edu

## GitHub Actions

`.github/workflows/newsletter.yml` runs daily at 11:00 UTC (7am ET). Required secrets: `ANTHROPIC_API_KEY`, `GMAIL_CREDENTIALS`, `GMAIL_TOKEN`, `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `SPOTIFY_REFRESH_TOKEN`.
