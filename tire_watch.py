#!/usr/bin/env python3
"""Watch Craigslist for 15" winter tires (Prius 2010: stock size 195/65R15).

Runs on a schedule (GitHub Actions), remembers listings it has already
reported in seen.json, and notifies by email and/or SMS (Twilio) on new ones.
Standard library only.
"""
import base64
import json
import os
import re
import smtplib
import sys
import urllib.parse
import urllib.request
from email.message import EmailMessage
from html import unescape
from pathlib import Path

SEARCH_URL = os.environ.get(
    "SEARCH_URL",
    "https://boston.craigslist.org/search/sse?query=winter%20tires",
)
SEEN_FILE = Path(os.environ.get("SEEN_FILE", "seen.json"))
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

# Matches 15" rims / tire sizes that fit a 2010 Prius (195/65R15 stock).
SIZE_RE = re.compile(
    r"""(\b15\s?(?:"|”|in\b|inch|-inch)|\br\s?15\b|/\d{2}\s?r?\s?15\b|\b195/65|\b185/65|\b205/65|\b195/60)""",
    re.I,
)


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-US"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def parse_listings(html):
    """Return [{id,title,url,price}] from the page's JSON-LD (no-JS fallback)."""
    out = []
    for blob in re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.S):
        try:
            data = json.loads(blob)
        except ValueError:
            continue
        for el in data.get("itemListElement", []) if isinstance(data, dict) else []:
            item = el.get("item", el)
            title = unescape(item.get("name", ""))
            offers = item.get("offers") or {}
            out.append({"title": title, "price": offers.get("price", ""), "url": item.get("url", ""),
                        "text": title + " " + unescape(item.get("description", ""))})
    if not out:  # fallback: plain anchors to posting pages
        for url, title in re.findall(r'<a[^>]+href="(https://[^"]*craigslist\.org/[^"]*/\d{8,}\.html)"[^>]*>(.*?)</a>', html, re.S):
            title = unescape(re.sub(r"<[^>]+>", "", title)).strip()
            if title:
                out.append({"title": title, "price": "", "url": url, "text": title})
    for o in out:
        m = re.search(r"/(\d{8,})\.html", o["url"])
        o["id"] = m.group(1) if m else o["url"]
    return out


def send_email(subject, body):
    user, pw, to = os.environ.get("SMTP_USER"), os.environ.get("SMTP_PASS"), os.environ.get("EMAIL_TO")
    if not (user and pw and to):
        return False
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = user, to, subject
    msg.set_content(body)
    with smtplib.SMTP_SSL(os.environ.get("SMTP_HOST", "smtp.gmail.com"), 465) as s:
        s.login(user, pw)
        s.send_message(msg)
    return True


def send_sms(body):
    sid, tok = os.environ.get("TWILIO_SID"), os.environ.get("TWILIO_TOKEN")
    frm, to = os.environ.get("TWILIO_FROM"), os.environ.get("SMS_TO")
    if not (sid and tok and frm and to):
        return False
    data = urllib.parse.urlencode({"From": frm, "To": to, "Body": body[:1500]}).encode()
    req = urllib.request.Request(f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json", data=data)
    req.add_header("Authorization", "Basic " + base64.b64encode(f"{sid}:{tok}".encode()).decode())
    urllib.request.urlopen(req, timeout=30).read()
    return True


def main():
    html = fetch(SEARCH_URL)
    listings = parse_listings(html)
    print(f"parsed {len(listings)} listings")
    if not listings:
        print("No listings parsed (blocked or page layout changed).", file=sys.stderr)
        return 1  # fails the workflow run so you get a GitHub failure email

    seen = set(json.loads(SEEN_FILE.read_text())) if SEEN_FILE.exists() else set()
    new = [l for l in listings if l["id"] not in seen and SIZE_RE.search(l["text"])]
    SEEN_FILE.write_text(json.dumps(sorted(seen | {l["id"] for l in listings}), indent=0))

    if not new:
        print("nothing new")
        return 0
    lines = [f"- {l['title']} {('$' + str(l['price'])) if l['price'] else ''}\n  {l['url']}" for l in new]
    body = f"{len(new)} new 15\" winter tire listing(s):\n\n" + "\n".join(lines)
    subject = f"Winter tires: {len(new)} new Craigslist listing(s)"
    sent = send_email(subject, body)
    sent = send_sms(body) or sent
    if not sent:
        print("No notifier configured!\n" + body, file=sys.stderr)
        return 1
    print(body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
