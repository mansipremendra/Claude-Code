"""Synthetic data so the report can be previewed without an API key."""

from __future__ import annotations

import random

from .website import analyze_html


def _html(kind: str) -> str:
    base = "<html><head><title>{t}</title>{head}</head><body><h1>Welcome</h1>{body}</body></html>"
    if kind == "good":
        return base.format(
            t="Great local service in your city",
            head='<meta name="viewport" content="width=device-width"><meta name="description" content="x">'
                 '<script src="https://www.googletagmanager.com/gtag/js?id=G-ABC12345"></script>'
                 '<script>fbq("init","1");</script>'
                 '<script type="application/ld+json">{"@type":"LocalBusiness"}</script>',
            body='<a href="tel:5551234567">Call</a><form></form><a href="https://facebook.com/x">fb</a>',
        )
    if kind == "mid":
        return base.format(t="Home", head='<meta name="viewport" content="width=device-width">',
                           body='<a href="tel:5551234567">Call</a>')
    return base.format(t="", head="<script>ga('create','UA-1234567-1')</script>", body="")


def generate(niche: str, cities: list[str], per_city: int = 8, seed: int = 7) -> list[tuple[dict, dict | None]]:
    rng = random.Random(seed)
    out = []
    for city in cities:
        for i in range(per_city):
            has_site = rng.random() > 0.2
            biz = {
                "place_id": f"demo-{city}-{i}",
                "name": f"{rng.choice(['Bright', 'Prime', 'Summit', 'Harbor', 'Oak', 'Metro', 'Pioneer'])} "
                        f"{niche.title()} {rng.choice(['Co', 'Group', 'Pros', 'Studio'])} {i + 1}",
                "niche": niche, "search_city": city, "address": f"{100 + i} Main St, {city}",
                "phone": "" if rng.random() < 0.1 else "(555) 010-0%03d" % i,
                "website": f"https://example-{city.split(',')[0].lower().replace(' ', '')}-{i}.test" if has_site else "",
                "rating": round(rng.uniform(3.3, 5.0), 1),
                "review_count": int(rng.choice([4, 12, 30, 80, 200, 450])),
                "photo_count": rng.choice([0, 3, 6, 10, 10]),
                "has_hours": rng.random() > 0.15,
                "days_since_last_review": rng.choice([5, 20, 70, 150, 400]),
                "reviews_checked": True, "business_status": "OPERATIONAL", "maps_url": "", "category": niche,
            }
            site = None
            if has_site:
                site = analyze_html(_html(rng.choice(["good", "mid", "bad", "bad"])), biz["website"] + "/",
                                    round(rng.uniform(0.8, 5.0), 2))
            out.append((biz, site))
    return out
