import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gmb_audit import cli, places, scoring, website

GOOD_HTML = """<html><head><title>Austin Family Dentistry | Cleanings</title>
<meta name="viewport" content="width=device-width"><meta name="description" content="d">
<script async src="https://www.googletagmanager.com/gtag/js?id=G-ABCDEF123"></script>
<script>fbq('init','123');</script>
<script type="application/ld+json">{"@context":"https://schema.org","@graph":[{"@type":"Dentist"}]}</script>
</head><body><h1>Hi</h1><a href="tel:+15125550100">Call</a><form></form>
<a href="https://www.instagram.com/x">ig</a></body></html>"""

BAD_HTML = "<html><head><script>ga('create','UA-1234567-1')</script></head><body></body></html>"


def biz(**kw):
    base = {"place_id": "1", "name": "A", "niche": "dentist", "search_city": "Austin", "address": "",
            "phone": "555", "website": "http://a.test", "rating": 4.8, "review_count": 100,
            "photo_count": 10, "has_hours": True, "days_since_last_review": 5, "reviews_checked": True,
            "business_status": "", "maps_url": "", "category": ""}
    base.update(kw)
    return base


class WebsiteTests(unittest.TestCase):
    def test_good_site_has_signals(self):
        s = website.analyze_html(GOOD_HTML, "https://a.test/", 1.0)
        for k in ("https", "mobile_viewport", "ga4", "meta_pixel", "schema_local",
                  "click_to_call", "has_form"):
            self.assertTrue(s[k], k)
        self.assertEqual(s["socials"], ["instagram"])

    def test_bad_site_flags_legacy_ua_only(self):
        s = website.analyze_html(BAD_HTML, "http://a.test/", 1.0)
        self.assertTrue(s["legacy_ua"])
        self.assertFalse(s["ga4"])
        self.assertFalse(s["https"])

    def test_social_only_url(self):
        s = website.analyze("https://www.facebook.com/somebiz")
        self.assertTrue(s["is_social_only"])

    def test_unreachable_never_raises(self):
        import requests
        sess = mock.Mock()
        sess.get.side_effect = requests.ConnectionError()
        s = website.analyze("http://nope.test", session=sess)
        self.assertFalse(s["reachable"])
        self.assertEqual(s["error"], "ConnectionError")


class ScoringTests(unittest.TestCase):
    def keys(self, b, s):
        return {g.key for g in scoring.find_gaps(b, s)}

    def test_healthy_business_has_no_gaps(self):
        s = website.analyze_html(GOOD_HTML + "<script src='https://x.tawk.to/a'></script>", "https://a.test/", 1.0)
        self.assertEqual(self.keys(biz(), s), set())

    def test_no_website(self):
        k = self.keys(biz(website=""), None)
        self.assertIn("no_website", k)

    def test_profile_gaps(self):
        k = self.keys(biz(review_count=3, rating=3.5, photo_count=2, has_hours=False,
                          days_since_last_review=300), None)
        self.assertTrue({"few_reviews", "low_rating", "few_photos", "no_hours", "stale_reviews"} <= k)

    def test_bad_site_gaps(self):
        s = website.analyze_html(BAD_HTML, "http://a.test/", 5.0)
        k = self.keys(biz(), s)
        self.assertTrue({"no_https", "not_mobile", "slow_site", "no_analytics", "no_retargeting",
                         "no_schema", "no_lead_capture"} <= k)

    def test_score_capped(self):
        s = website.analyze_html(BAD_HTML, "http://a.test/", 5.0)
        r = scoring.audit(biz(review_count=0, rating=3.0, photo_count=0, has_hours=False, phone=""), s)
        self.assertLessEqual(r["gap_score"], 100)

    def test_summary_percentages(self):
        a = scoring.audit(biz(website=""), None)
        b = scoring.audit(biz(), website.analyze_html(GOOD_HTML, "https://a.test/", 1.0))
        top = scoring.niche_summary([a, b])["common_gaps"]
        self.assertEqual(next(g for g in top if g["key"] == "no_website")["percent"], 50)


class PlacesTests(unittest.TestCase):
    def test_pagination_and_normalize(self):
        page1 = {"places": [{"id": "a", "displayName": {"text": "A"}, "userRatingCount": 3,
                             "reviews": [{"publishTime": "2020-01-01T00:00:00Z"}]}],
                 "nextPageToken": "t"}
        page2 = {"places": [{"id": "b", "displayName": {"text": "B"}, "businessStatus": "CLOSED_PERMANENTLY"},
                            {"id": "c", "displayName": {"text": "C"}, "websiteUri": "https://c.test"}]}
        sess = mock.Mock()
        sess.post.side_effect = [mock.Mock(status_code=200, json=lambda: page1),
                                 mock.Mock(status_code=200, json=lambda: page2)]
        with mock.patch("gmb_audit.places.time.sleep"):
            out = places.search("dentist", "Austin", "KEY", limit=40, session=sess)
        self.assertEqual([p["place_id"] for p in out], ["a", "c"])  # closed business dropped
        self.assertGreater(out[0]["days_since_last_review"], 365)
        self.assertEqual(sess.post.call_args_list[1].kwargs["json"]["pageToken"], "t")

    def test_api_error(self):
        sess = mock.Mock()
        sess.post.return_value = mock.Mock(status_code=403, json=lambda: {"error": {"message": "denied"}})
        with self.assertRaises(places.PlacesError):
            places.search("x", "y", "bad", session=sess)


class CliTests(unittest.TestCase):
    def test_demo_run_writes_outputs(self):
        with tempfile.TemporaryDirectory() as d:
            rc = cli.main(["--niche", "plumber", "--cities", "Austin, TX", "Denver, CO", "--demo", "--out", d])
            self.assertEqual(rc, 0)
            for f in ("report.html", "audit.csv", "audit.json"):
                self.assertTrue((Path(d) / f).stat().st_size > 0, f)

    def test_missing_key(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            self.assertEqual(cli.main(["--niche", "x", "--cities", "y", "--out", tempfile.mkdtemp()]), 2)


if __name__ == "__main__":
    unittest.main()
