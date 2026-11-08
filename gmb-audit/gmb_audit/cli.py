"""Command line entry point: python -m gmb_audit --niche dentist --cities "Austin, TX" "Denver, CO"."""

from __future__ import annotations

import argparse
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import demo, places, report, scoring, website


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="gmb_audit", description=__doc__)
    p.add_argument("--niche", required=True, help='Business type, e.g. "dentist" or "roofing contractor"')
    p.add_argument("--cities", required=True, nargs="+", help='One or more cities, e.g. "Austin, TX" "Denver, CO"')
    p.add_argument("--limit", type=int, default=40, help="Max businesses per city (API caps at 60). Default 40")
    p.add_argument("--out", default="output", help="Output directory. Default ./output")
    p.add_argument("--api-key", default=os.environ.get("GOOGLE_PLACES_API_KEY"),
                   help="Google Places API key (or set GOOGLE_PLACES_API_KEY)")
    p.add_argument("--skip-reviews", action="store_true",
                   help="Do not request review data (cheaper API tier, disables the stale-reviews check)")
    p.add_argument("--skip-websites", action="store_true", help="Only audit the Google profile, do not crawl sites")
    p.add_argument("--workers", type=int, default=8, help="Parallel website checks. Default 8")
    p.add_argument("--demo", action="store_true", help="Use synthetic sample data (no API key or network needed)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    pairs: list[tuple[dict, dict | None]]
    if args.demo:
        pairs = demo.generate(args.niche, args.cities)
    else:
        if not args.api_key:
            print("Missing API key. Set GOOGLE_PLACES_API_KEY or pass --api-key.", file=sys.stderr)
            return 2
        businesses: dict[str, dict] = {}
        for city in args.cities:
            print(f"Searching '{args.niche}' in {city} ...", flush=True)
            try:
                found = places.search(args.niche, city, args.api_key, args.limit,
                                      include_reviews=not args.skip_reviews)
            except places.PlacesError as exc:
                print(f"  {exc}", file=sys.stderr)
                return 1
            new = 0
            for b in found:
                if b["place_id"] not in businesses:
                    businesses[b["place_id"]] = b
                    new += 1
            print(f"  {len(found)} found, {new} new", flush=True)
        biz_list = list(businesses.values())

        sites: list[dict | None] = [None] * len(biz_list)
        if not args.skip_websites:
            print(f"Checking {sum(1 for b in biz_list if b['website'])} websites ...", flush=True)
            with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
                sites = list(pool.map(lambda b: website.analyze(b["website"]) if b["website"] else None, biz_list))
        pairs = list(zip(biz_list, sites))

    results = [scoring.audit(b, s) for b, s in pairs]
    if not results:
        print("No businesses found. Try a broader niche or different city names.", file=sys.stderr)
        return 1
    summary = scoring.niche_summary(results)

    report.write_csv(results, out_dir / "audit.csv")
    report.write_json(results, summary, out_dir / "audit.json")
    report.write_html(results, summary, args.niche, args.cities, out_dir / "report.html", demo=args.demo)

    print(f"\n{summary['businesses']} businesses audited, average gap score {summary['avg_gap_score']}/100")
    print("Most common gaps:")
    for g in summary["common_gaps"][:8]:
        print(f"  {g['percent']:>3}%  {g['label']}")
    print(f"\nReport: {out_dir / 'report.html'}\nSpreadsheet: {out_dir / 'audit.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
