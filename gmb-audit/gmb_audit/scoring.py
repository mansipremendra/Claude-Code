"""Turn raw profile + website data into a list of marketing gaps and a score."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median

# Thresholds, tweak to taste.
MIN_REVIEWS = 25
MIN_RATING = 4.0
STALE_REVIEW_DAYS = 90
MIN_PHOTOS = 10  # Places API caps photos at 10
SLOW_SECONDS = 3.0


@dataclass(frozen=True)
class Gap:
    key: str
    label: str
    points: int
    category: str  # "Google profile" | "Website" | "Tracking" | "Conversion"
    advice: str


def _g(key, label, points, category, advice) -> Gap:
    return Gap(key, label, points, category, advice)


def find_gaps(biz: dict, site: dict | None) -> list[Gap]:
    gaps: list[Gap] = []

    # ---- Google Business Profile ----
    if biz["review_count"] < MIN_REVIEWS:
        gaps.append(_g("few_reviews", f"Fewer than {MIN_REVIEWS} Google reviews", 10, "Google profile",
                       "Set up a review request flow (SMS/email after each job or visit)."))
    if biz["rating"] is not None and biz["rating"] < MIN_RATING:
        gaps.append(_g("low_rating", f"Rating below {MIN_RATING}", 8, "Google profile",
                       "Reputation management: respond to negatives, ask happy customers for reviews."))
    days = biz.get("days_since_last_review")
    if biz.get("reviews_checked") and days is not None and days > STALE_REVIEW_DAYS:
        gaps.append(_g("stale_reviews", f"No new review in {STALE_REVIEW_DAYS}+ days", 6, "Google profile",
                       "Fresh reviews help local rankings; start a steady review cadence."))
    if biz["photo_count"] < MIN_PHOTOS:
        gaps.append(_g("few_photos", "Few photos on profile", 4, "Google profile",
                       "Add team, work, storefront and product photos."))
    if not biz["has_hours"]:
        gaps.append(_g("no_hours", "No business hours listed", 4, "Google profile",
                       "Complete the profile: hours, services, attributes."))
    if not biz["phone"]:
        gaps.append(_g("no_phone", "No phone number on profile", 3, "Google profile",
                       "Add a primary phone number to the profile."))

    # ---- Website presence ----
    if not biz["website"]:
        gaps.append(_g("no_website", "No website linked on profile", 20, "Website",
                       "Build a simple local site and link it from the profile."))
        return gaps
    if site is None:
        return gaps
    if site.get("is_social_only"):
        gaps.append(_g("social_only", "Profile links to a social page, not a website", 15, "Website",
                       "A real website owns the brand, ranks in search and supports tracking."))
        return gaps
    if not site["reachable"]:
        gaps.append(_g("site_down", f"Website unreachable ({site.get('error') or 'unknown error'})", 15, "Website",
                       "Site is broken or blocked; confirm manually, it may be a fast win."))
        return gaps

    if not site["https"]:
        gaps.append(_g("no_https", "Site not served over HTTPS", 5, "Website",
                       "Install an SSL certificate; browsers flag HTTP sites as 'Not secure'."))
    if not site["mobile_viewport"]:
        gaps.append(_g("not_mobile", "Not mobile friendly (no viewport tag)", 5, "Website",
                       "Most local searches are on phones; needs a responsive redesign."))
    if site["load_seconds"] and site["load_seconds"] > SLOW_SECONDS:
        gaps.append(_g("slow_site", f"Slow homepage (over {SLOW_SECONDS:g}s)", 3, "Website",
                       "Compress images, add caching, trim plugins."))
    if not site["title"] or len(site["title"]) < 15:
        gaps.append(_g("weak_title", "Missing or very short page title", 2, "Website",
                       "Write a title with service + city."))
    if not site["meta_description"]:
        gaps.append(_g("no_meta_desc", "No meta description", 3, "Website",
                       "Add a meta description to lift search click-through."))
    if site["h1_count"] == 0:
        gaps.append(_g("no_h1", "No H1 heading on homepage", 2, "Website",
                       "Add one clear H1 with the main service and city."))
    if not site["schema_local"]:
        gaps.append(_g("no_schema", "No LocalBusiness structured data", 4, "Website",
                       "Add LocalBusiness schema (name, address, phone, hours, reviews)."))

    # ---- Tracking ----
    if not (site["ga4"] or site["gtm"]):
        label = "Only legacy Universal Analytics (stopped collecting data)" if site["legacy_ua"] else "No analytics detected"
        gaps.append(_g("no_analytics", label, 8, "Tracking",
                       "Install GA4 (ideally via Tag Manager) so they can see what marketing works."))
    if not (site["meta_pixel"] or site["google_ads_tag"]):
        gaps.append(_g("no_retargeting", "No Meta Pixel or Google Ads tag", 5, "Tracking",
                       "No retargeting or conversion tracking set up for paid ads."))

    # ---- Conversion ----
    if not site["click_to_call"]:
        gaps.append(_g("no_click_to_call", "No tap-to-call link", 3, "Conversion",
                       "Make the phone number a tel: link, especially in the header."))
    if not (site["has_form"] or site["booking_cta"]):
        gaps.append(_g("no_lead_capture", "No contact form or online booking", 6, "Conversion",
                       "Add a form or booking widget so visitors can convert after hours."))
    if not site["chat_widget"]:
        gaps.append(_g("no_chat", "No chat or messaging widget", 2, "Conversion",
                       "Web chat / text-back captures leads that would otherwise bounce."))
    if not site["socials"]:
        gaps.append(_g("no_social_links", "No social media links on site", 3, "Conversion",
                       "No linked social presence; content and community channels look unused."))

    return gaps


def score(gaps: list[Gap]) -> int:
    """0-100. Higher means more marketing gaps, i.e. a bigger opportunity."""
    return min(100, sum(g.points for g in gaps))


def audit(biz: dict, site: dict | None) -> dict:
    gaps = find_gaps(biz, site)
    return {**biz, "site": site, "gaps": gaps, "gap_score": score(gaps)}


def niche_summary(results: list[dict]) -> dict:
    """Aggregate across every audited business."""
    n = len(results)
    counts: dict[str, dict] = {}
    for r in results:
        for g in r["gaps"]:
            c = counts.setdefault(g.key, {"label": g.label, "category": g.category, "count": 0})
            c["count"] += 1
    ranked = sorted(counts.items(), key=lambda kv: kv[1]["count"], reverse=True)
    reviews = [r["review_count"] for r in results]
    ratings = [r["rating"] for r in results if r["rating"] is not None]
    return {
        "businesses": n,
        "median_reviews": median(reviews) if reviews else 0,
        "median_rating": round(median(ratings), 2) if ratings else None,
        "avg_gap_score": round(sum(r["gap_score"] for r in results) / n, 1) if n else 0,
        "common_gaps": [
            {"key": k, "label": v["label"], "category": v["category"], "count": v["count"],
             "percent": round(100 * v["count"] / n) if n else 0}
            for k, v in ranked
        ],
    }
