# GMB Audit

Pick a niche and a list of cities. The tool pulls the local businesses from Google, checks each Google Business Profile and website, and shows what they are missing in their digital marketing.

## Setup

```bash
cd gmb-audit
pip install -r requirements.txt
export GOOGLE_PLACES_API_KEY=your_key
```

Get a key in Google Cloud: enable "Places API (New)" and create an API key. This tool uses the official API on purpose, because scraping Google Maps breaks Google's terms and gets blocked.

## Run

```bash
python -m gmb_audit --niche "dentist" --cities "Austin, TX" "Denver, CO" --limit 40
```

No key yet? Preview the report with sample data:

```bash
python -m gmb_audit --niche plumber --cities "Austin, TX" --demo
```

Output goes to `./output`:

- `report.html`: niche-wide gap chart plus a sortable, searchable list. Click a business for every gap and the fix to pitch.
- `audit.csv`: one row per business, sorted by opportunity, with gaps and pitch notes.
- `audit.json`: full data.

Options: `--skip-reviews` (cheaper API tier, drops the stale-reviews check), `--skip-websites` (profile only), `--workers N`, `--out DIR`.

## What it checks

| Area | Checks |
|---|---|
| Google profile | review count, rating, review freshness, photos, hours, phone, website linked |
| Website | HTTPS, mobile viewport, load time, title, meta description, H1, LocalBusiness schema, unreachable or social-only sites |
| Tracking | GA4 or Tag Manager (flags legacy Universal Analytics), Meta Pixel, Google Ads tag |
| Conversion | tap-to-call link, contact form or booking, chat widget, social links |

Each gap carries points. The gap score (0-100) is their sum, so higher means a bigger opportunity. Thresholds and weights are at the top of `gmb_audit/scoring.py`.

## Limits

- Places API returns at most 60 results per niche and city query. Use more specific cities or neighborhoods to go wider.
- The API returns at most 10 photos and the 5 most relevant reviews, so photo and review-freshness checks are approximate.
- It cannot see owner replies, posts, Q&A or the owner-written description.
- Website checks read the homepage HTML only. Tags loaded after page render, or injected by consent tools, can show as missing, so confirm manually before pitching.
- Cost: review data uses a higher-priced field tier. Check current Places API pricing and use `--limit` and `--skip-reviews` while testing.

## Tests

```bash
python -m unittest discover -s tests
```
