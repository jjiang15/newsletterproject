#!/usr/bin/env python3
"""Daily briefing newsletter — reads Gmail, searches web, writes + sends via Claude."""

import os
import base64
import requests
import random
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from ddgs import DDGS
import anthropic

# ── Config ────────────────────────────────────────────────────────────────────
GMAIL_ADDRESS   = "jannahjiang@gmail.com"
RECIPIENT_EMAIL = "jjiang15@wharton.upenn.edu"
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()
Spotify_Client_ID = os.environ.get("SPOTIFY_CLIENT_ID", "").strip()
Spotify_Client_Secret = os.environ.get("SPOTIFY_CLIENT_SECRET", "").strip()
Spotify_refresh_token = os.environ.get("SPOTIFY_REFRESH_TOKEN", "").strip()

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]

NEWSLETTER_QUERIES = [
    "from:(editors@heatmap.news) newer_than:3d",
    "from:(hello@ctvc.co) newer_than:7d",
    "subject:(volts) newer_than:7d",
    "from:(news@daily.therundown.ai) newer_than:3d",
]

Spotify_playlists = [
    '5qAJyZKxjM6b4G3jc6HapS',
]
# ─────────────────────────────────────────────────────────────────────────────

def get_spotify_token(client_id, client_secret, refresh_token):
    credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    response = requests.post(
        "https://accounts.spotify.com/api/token",
        data={"grant_type": "refresh_token", "refresh_token": refresh_token},
        headers={"Authorization": f"Basic {credentials}"},
    )
    return response.json()['access_token']

def fetch_spotify_songs():
    token = get_spotify_token(Spotify_Client_ID, Spotify_Client_Secret, Spotify_refresh_token)
    response = requests.get(
        f"https://api.spotify.com/v1/playlists/{Spotify_playlists[0]}",
        headers={"Authorization": f"Bearer {token}"},
    )
    data = response.json()
    if "error" in data:
        return None
    tracks = [item["item"] for item in data.get("items", {}).get("items", []) if item.get("item")]
    if not tracks:
        return None
    track = random.choice(tracks)
    return {
        "name":   track["name"],
        "artist": track["artists"][0]["name"],
        "url":    track["external_urls"]["spotify"],
    }

def get_gmail_service():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as f:
            f.write(creds.to_json())
    return build("gmail", "v1", credentials=creds)

def fetch_newsletters(service):
    snippets = []
    for query in NEWSLETTER_QUERIES:
        result = service.users().messages().list(
            userId="me", q=query, maxResults=1
        ).execute()
        messages = result.get("messages", [])
        if not messages:
            continue
        msg = service.users().messages().get(
            userId="me", id=messages[0]["id"], format="metadata",
            metadataHeaders=["Subject", "From"]
        ).execute()
        headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
        subject = headers.get("Subject", "")
        sender  = headers.get("From", "")
        snippet = msg.get("snippet", "")
        snippets.append(f"From: {sender}\nSubject: {subject}\nSnippet: {snippet}")

    # Scan primary inbox for relevant energy/AI emails from the last day
    extra_query = (
        "(energy OR solar OR wind OR climate OR battery OR grid OR "
        '"artificial intelligence" OR OpenAI OR Anthropic OR "machine learning") '
        "newer_than:1d in:primary -category:promotions"
    )
    result = service.users().messages().list(
        userId="me", q=extra_query, maxResults=5
    ).execute()
    extra_snippets = []
    for m in result.get("messages", []):
        msg = service.users().messages().get(
            userId="me", id=m["id"], format="metadata",
            metadataHeaders=["Subject", "From"]
        ).execute()
        headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
        subject = headers.get("Subject", "")
        sender  = headers.get("From", "")
        snippet = msg.get("snippet", "")
        extra_snippets.append(f"From: {sender}\nSubject: {subject}\nSnippet: {snippet}")

    return snippets, extra_snippets


def web_search(queries):
    results = []
    with DDGS() as ddgs:
        for query in queries:
            hits = list(ddgs.text(query, max_results=4))
            for h in hits:
                results.append(f"Title: {h['title']}\nURL: {h['href']}\nSummary: {h['body']}")
    return results


def generate_newsletter(newsletter_snippets, extra_snippets, web_results, today, song=None):
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    newsletter_block = (
        "\n\n".join(newsletter_snippets)
        if newsletter_snippets
        else "No newsletter issues found — rely on web search only."
    )
    extra_block = (
        "\n\n".join(extra_snippets)
        if extra_snippets
        else "No additional inbox emails found."
    )
    web_block = "\n\n".join(web_results)

    song_block = (
        f"Song: \"{song['name']}\" by {song['artist']} — write exactly one sentence (max 20 words) on the mood or feeling this song evokes. Write about the song itself — do not connect it to news, markets, or the day ahead."
        if song else ""
    )

    prompt = f"""Today is {today}. Generate a daily briefing newsletter from the sources below.

=== NEWSLETTER EMAIL SNIPPETS ===
{newsletter_block}

=== ADDITIONAL INBOX EMAILS (last 24 hours, energy/AI relevant, non-promotional) ===
{extra_block}
Use these only if they contain specific, newsworthy information. Ignore any that are promotional or vague.

=== WEB SEARCH RESULTS ===
{web_block}

First, output a subject line on its own line in this exact format (no quotes):
SUBJECT: [pithy comma-separated headline capturing 3–4 of today's top themes across all sections, e.g. "Inflation Slows, Anthropic Wins, PJM Goes Gas"]

Then write the newsletter HTML in two sections:

SECTION 1 — "The World" (3–5 stories):
- These are the genuine top headlines of the day — what's on the front page of WSJ, NYT, BBC, Reuters right now.
- Pick the stories by newsworthiness, not by category. Whatever actually matters today goes here.
- Do NOT include clean energy, climate, renewables, or tech-specific stories — those belong in later sections.
- Draw from web search results, not newsletter snippets (which are climate/tech focused).
- 2 sentences per story. Bold headline inline at the start of the paragraph.
- Include the date of the event where known (e.g., "On May 3," or "Last week,")
- End each story with: <a href="URL" style="color:#111111;">Read →</a>

SECTION 2 — "Clean Energy & Tech" (12–15 stories):
- Synthesize from both newsletter snippets and web results
- 1–2 sentences per story. Same format as above.
- Include the date of the event where known
- Skip non-news content: subscriber milestones, newsletter self-promotion, podcast announcements
- End with a Deals block: list any funding rounds, M&A, or IPOs as simple line items
  (Company name — description — amount)

SECTION 3 — "AI" (3–4 stories):
- Draw from The Rundown AI newsletter snippets and web search results
- 1–2 sentences per story. Same format as above.
- Focus on product launches, model releases, enterprise deals, and policy — not hype

Writing rules (follow precisely):
- Every story must be about a specific named event, decision, number, or person. No vague summaries.
- Never describe a newsletter, publication, or its audience — write the actual news inside it. Subscriber counts, publication cadence, and readership descriptions are never news.
- Never write meta-commentary about what a publication is covering (e.g., "WSJ leads with..." or "headlines reflect uncertainty"). Write the actual news.
- If you don't have enough specific information to write a concrete story, skip it — do not pad with generalities.
- Short sentences. One thought per sentence.
- Never write: "It is worth noting", "In conclusion", "Notably", "This underscores", "Exciting", "reflects", "underscores", "amid"
- No bullet points inside story paragraphs
- Synthesize across sources — do not summarize one source at a time
- Voice: clear, analytical, written for someone working in clean energy investing

Return the SUBJECT line first, then ONLY the inner HTML — no <html>, <head>, or <body> tags.
Use this structure:

SUBJECT: [Theme One, Theme Two, Theme Three]

<h2 style="font-size:11px;letter-spacing:2px;text-transform:uppercase;color:#888888;font-family:Arial,sans-serif;margin:0 0 20px 0;font-weight:normal;">THE WORLD</h2>

<p style="margin:0 0 24px 0;font-size:15px;color:#111111;line-height:1.6;"><strong>Headline here.</strong> Story text here. <a href="URL" style="color:#111111;">Read →</a></p>

(repeat for each story)

<hr style="border:none;border-top:1px solid #e5e5e5;margin:32px 0;">

<h2 style="font-size:11px;letter-spacing:2px;text-transform:uppercase;color:#888888;font-family:Arial,sans-serif;margin:0 0 20px 0;font-weight:normal;">CLEAN ENERGY & TECH</h2>

<p style="margin:0 0 24px 0;font-size:15px;color:#111111;line-height:1.6;"><strong>Headline here.</strong> Story text. <a href="URL" style="color:#111111;">Read →</a></p>

(repeat for each story)

<div style="background-color:#f9f9f7;padding:20px 24px;margin-top:8px;">
  <p style="margin:0 0 8px 0;font-size:11px;letter-spacing:2px;text-transform:uppercase;color:#888888;font-family:Arial,sans-serif;">Deals</p>
  <p style="margin:0;font-size:14px;color:#333333;line-height:1.8;">
    Company — description — $amount<br>
    ...
  </p>
</div>

<hr style="border:none;border-top:1px solid #e5e5e5;margin:32px 0;">

<h2 style="font-size:11px;letter-spacing:2px;text-transform:uppercase;color:#888888;font-family:Arial,sans-serif;margin:0 0 20px 0;font-weight:normal;">AI</h2>

<p style="margin:0 0 24px 0;font-size:15px;color:#111111;line-height:1.6;"><strong>Headline here.</strong> Story text. <a href="URL" style="color:#111111;">Read →</a></p>

(repeat for each story)

{f"=== TODAY'S SONG ==={chr(10)}{song_block}{chr(10)}{chr(10)}Output only one sentence about this song on a line by itself, prefixed with SONG_BLURB: " if song_block else ""}"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=5000,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text

    song_blurb = ""
    if song and "SONG_BLURB:" in raw:
        for line in raw.splitlines():
            if line.startswith("SONG_BLURB:"):
                song_blurb = line[len("SONG_BLURB:"):].strip()
                break
        raw = "\n".join(l for l in raw.splitlines() if not l.startswith("SONG_BLURB:"))

    if raw.startswith("SUBJECT:"):
        first_line, _, rest = raw.partition("\n")
        subject = first_line[len("SUBJECT:"):].strip()
        body_html = rest.lstrip("\n")
    else:
        subject = today
        body_html = raw

    if song:
        body_html += f"""
<hr style="border:none;border-top:1px solid #e5e5e5;margin:32px 0;">
<h2 style="font-size:11px;letter-spacing:2px;text-transform:uppercase;color:#888888;font-family:Arial,sans-serif;margin:0 0 12px 0;font-weight:normal;">NOW PLAYING: WILL'S SONG OF THE DAY</h2>
<p style="margin:0;font-size:15px;color:#111111;line-height:1.6;"><strong>{song['name']}</strong> — {song['artist']}. {song_blurb} <a href="{song['url']}" style="color:#111111;">Listen →</a></p>"""

    return subject, body_html


def wrap_html(body_html, today, tagline=""):
    tagline_html = (
        f'<p style="margin:6px 0 0 0;font-size:14px;color:#555555;font-family:Georgia,serif;font-style:italic;">{tagline}</p>'
        if tagline else ""
    )
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background-color:#f9f9f7;font-family:Georgia,serif;">
  <div style="max-width:600px;margin:40px auto;background-color:#ffffff;padding:48px;">

    <div style="border-bottom:2px solid #111111;padding-bottom:16px;margin-bottom:32px;">
      <p style="margin:0;font-size:11px;letter-spacing:2px;text-transform:uppercase;color:#888888;font-family:Arial,sans-serif;">Daily Briefing</p>
      <h1 style="margin:8px 0 0 0;font-size:22px;font-weight:normal;color:#111111;">{today}</h1>
      {tagline_html}
    </div>

    {body_html}

    <div style="border-top:1px solid #e5e5e5;margin-top:40px;padding-top:20px;">
      <p style="margin:0;font-size:12px;color:#aaaaaa;font-family:Arial,sans-serif;">
        Sources: Heatmap Daily · CTVC by Sightline Climate · Volts · The Rundown AI · Web Search
      </p>
    </div>

  </div>
</body>
</html>"""


def send_email(service, subject, html):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = GMAIL_ADDRESS
    msg["To"]      = RECIPIENT_EMAIL
    msg.attach(MIMEText(html, "html"))
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    service.users().messages().send(userId="me", body={"raw": raw}).execute()
    print(f"Sent: {subject}")


def main():
    now = datetime.now()
    today = now.strftime(f"%B {now.day}, %Y")      # e.g. "May 5, 2026"

    print("Authenticating...")
    service = get_gmail_service()

    print("Fetching newsletters from Gmail...")
    snippets, extra_snippets = fetch_newsletters(service)
    print(f"  Found {len(snippets)} newsletter(s), {len(extra_snippets)} additional inbox email(s)")

    print("Running web searches...")
    web_results = web_search([
        f"top news headlines today {today} WSJ NYT Reuters",
        f"US economy markets geopolitics breaking news {today}",
        f"clean energy climate tech news {today}",
        "artificial intelligence AI news Anthropic OpenAI Google latest announcements this week",
    ])

    print("Fetching song from Spotify...")
    song = fetch_spotify_songs()
    if song:
        print(f"  Song: {song['name']} — {song['artist']}")

    print("Generating newsletter with Claude...")
    subject, body_html = generate_newsletter(snippets, extra_snippets, web_results, today, song)
    full_html = wrap_html(body_html, today, tagline=subject)

    print("Sending email...")
    send_email(service, f"{subject} · {today}", full_html)
    print("Done.")


if __name__ == "__main__":
    main()
