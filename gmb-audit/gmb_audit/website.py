"""Inspect a business website for marketing and tracking signals."""

from __future__ import annotations

import json
import re
import time
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

USER_AGENT = "Mozilla/5.0 (compatible; gmb-audit/0.1; +local-marketing-audit)"

SOCIAL_DOMAINS = {
    "facebook": ("facebook.com", "fb.com"),
    "instagram": ("instagram.com",),
    "linkedin": ("linkedin.com",),
    "youtube": ("youtube.com", "youtu.be"),
    "tiktok": ("tiktok.com",),
    "x": ("twitter.com", "x.com"),
}

LOCAL_SCHEMA_HINTS = (
    "localbusiness", "dentist", "physician", "medical", "restaurant", "store",
    "lawyer", "attorney", "legalservice", "plumber", "electrician", "roofing",
    "hvac", "autorepair", "autodealer", "realestate", "healthandbeautybusiness",
    "hairsalon", "beautysalon", "gym", "sportsactivitylocation", "veterinary",
    "accountingservice", "financialservice", "homeandconstructionbusiness",
    "professionalservice", "organization",
)

BOOKING_WORDS = re.compile(
    r"book (online|now|an? appointment)|schedule (online|now|an? appointment)|"
    r"request (an? )?(appointment|quote|estimate)|get (a )?(free )?(quote|estimate)|"
    r"calendly\.com|acuityscheduling|setmore|squareup\.com/appointments|"
    r"opentable\.com|resy\.com|zocdoc|mindbodyonline|vagaro|booksy|jobber|housecallpro",
    re.I,
)
CHAT_WORDS = re.compile(
    r"intercom|drift\.com|tawk\.to|livechatinc|crisp\.chat|tidio|hs-scripts|"
    r"podium|birdeye|smith\.ai|ruby\.com|olark|zendesk",
    re.I,
)


def _empty(url: str) -> dict:
    return {
        "url": url,
        "reachable": False,
        "error": "",
        "https": False,
        "load_seconds": None,
        "mobile_viewport": False,
        "title": "",
        "meta_description": "",
        "h1_count": 0,
        "ga4": False,
        "legacy_ua": False,
        "gtm": False,
        "meta_pixel": False,
        "google_ads_tag": False,
        "schema_any": False,
        "schema_local": False,
        "click_to_call": False,
        "has_form": False,
        "booking_cta": False,
        "chat_widget": False,
        "socials": [],
        "is_social_only": False,
    }


def _host(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def social_network_for(url: str) -> str | None:
    host = _host(url)
    for name, domains in SOCIAL_DOMAINS.items():
        if any(host == d or host.endswith("." + d) for d in domains):
            return name
    return None


def _schema_types(soup: BeautifulSoup) -> list[str]:
    types: list[str] = []

    def walk(node):
        if isinstance(node, dict):
            t = node.get("@type")
            if isinstance(t, str):
                types.append(t)
            elif isinstance(t, list):
                types.extend(x for x in t if isinstance(x, str))
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            walk(json.loads(tag.string or tag.get_text() or ""))
        except (ValueError, TypeError):
            continue
    return types


def analyze_html(html: str, final_url: str, load_seconds: float | None = None) -> dict:
    """Pure function: derive signals from page HTML (easy to unit test)."""
    out = _empty(final_url)
    out.update(reachable=True, https=final_url.lower().startswith("https://"), load_seconds=load_seconds)
    soup = BeautifulSoup(html, "html.parser")

    out["mobile_viewport"] = bool(soup.find("meta", attrs={"name": re.compile("^viewport$", re.I)}))
    out["title"] = (soup.title.get_text(strip=True) if soup.title else "")
    desc = soup.find("meta", attrs={"name": re.compile("^description$", re.I)})
    out["meta_description"] = (desc.get("content", "").strip() if desc else "")
    out["h1_count"] = len(soup.find_all("h1"))

    out["ga4"] = bool(re.search(r"gtag\(\s*['\"]config['\"]\s*,\s*['\"]G-[A-Z0-9]{6,}|gtag/js\?id=G-[A-Z0-9]{6,}", html))
    out["legacy_ua"] = bool(re.search(r"\bUA-\d{4,}-\d+\b", html))
    out["gtm"] = bool(re.search(r"\bGTM-[A-Z0-9]{4,}\b", html))
    out["meta_pixel"] = bool(re.search(r"fbq\(\s*['\"]init|connect\.facebook\.net/[^'\"]*fbevents", html))
    out["google_ads_tag"] = bool(re.search(r"\bAW-\d{6,}\b|googleadservices\.com|doubleclick\.net", html))

    types = _schema_types(soup)
    out["schema_any"] = bool(types)
    out["schema_local"] = any(any(h in t.lower() for h in LOCAL_SCHEMA_HINTS) for t in types)

    hrefs = [a.get("href", "") for a in soup.find_all("a", href=True)]
    out["click_to_call"] = any(h.lower().startswith("tel:") for h in hrefs)
    out["has_form"] = bool(soup.find("form"))
    out["booking_cta"] = bool(BOOKING_WORDS.search(html))
    out["chat_widget"] = bool(CHAT_WORDS.search(html))

    socials = {n for h in hrefs if (n := social_network_for(h))}
    out["socials"] = sorted(socials)
    return out


def analyze(url: str, timeout: float = 15.0, session: requests.Session | None = None) -> dict:
    """Fetch `url` and return its marketing signals. Never raises."""
    if not url:
        return _empty(url)
    if social_network_for(url):
        res = _empty(url)
        res.update(is_social_only=True, reachable=True)
        return res
    http = session or requests.Session()
    try:
        start = time.monotonic()
        resp = http.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout, allow_redirects=True)
        elapsed = round(time.monotonic() - start, 2)
        if resp.status_code >= 400:
            res = _empty(url)
            res["error"] = f"HTTP {resp.status_code}"
            return res
        return analyze_html(resp.text, resp.url, elapsed)
    except requests.RequestException as exc:
        res = _empty(url)
        res["error"] = type(exc).__name__
        return res
