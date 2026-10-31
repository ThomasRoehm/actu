import datetime
import json
import unittest
from unittest.mock import patch

from scripts.collect import article, canonical_url, collect_bebasket, collect_blog, merge_articles, page_objects, parse_date, parse_feed, parse_page


class CollectionTests(unittest.TestCase):
    source = {"id": "test", "name": "Test"}

    def test_rss_date_offset_and_html_title(self):
        content = b'<rss><channel><item><title>A &amp;amp; B</title><link>https://example.com/a?utm_source=rss</link><pubDate>Fri, 23 Oct 2026 18:00:00 +0200</pubDate></item></channel></rss>'
        item = parse_feed(content, self.source)[0]
        self.assertEqual(item["title"], "A & B")
        self.assertEqual(item["url"], "https://example.com/a")
        self.assertEqual(item["publishedAt"], "2026-10-23T16:00:00+00:00")

    def test_atom_alternate_link_and_original_date(self):
        content = b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Title</title><link rel="self" href="https://example.com/api"/><link href="https://example.com/article"/><published>2026-10-22T12:00:00Z</published><updated>2026-10-23T12:00:00Z</updated></entry></feed>'
        item = parse_feed(content, self.source)[0]
        self.assertEqual(item["url"], "https://example.com/article")
        self.assertEqual(item["publishedAt"], "2026-10-22T12:00:00+00:00")

    def test_missing_dates_and_unsafe_urls_are_rejected(self):
        self.assertIsNone(parse_date("not a date"))
        self.assertIsNone(parse_date("2026-10-23"))
        self.assertIsNone(article(self.source, "Title", "javascript:alert(1)", "2026-10-23T12:00:00Z"))

    def test_malformed_and_credential_urls_do_not_break_feed(self):
        for url in ["https://[broken/path", "https://example.com:wrong/a", "https://user:password@example.com/a", "file:///tmp/a"]:
            self.assertIsNone(canonical_url(url))
        content = b'<rss><channel><item><title>Broken</title><link>https://[broken</link><pubDate>Fri, 23 Oct 2026 18:00:00 +0200</pubDate></item><item><title>Valid</title><link>https://example.com/a</link><pubDate>Fri, 23 Oct 2026 18:00:00 +0200</pubDate></item></channel></rss>'
        self.assertEqual([item["title"] for item in parse_feed(content, self.source)], ["Valid"])

    def test_rolling_window_deduplication_and_retention(self):
        now = datetime.datetime(2026, 10, 23, 12, tzinfo=datetime.timezone.utc)
        def item(hours, path):
            return article(self.source, path, "https://example.com/" + path, (now - datetime.timedelta(hours=hours)).isoformat())
        old = [item(49, "old"), item(12, "retained"), item(24, "duplicate"), item(-1, "future")]
        new = [item(24, "duplicate"), item(0, "new"), item(48, "boundary")]
        result = merge_articles(old, new, {"test"}, now)
        self.assertEqual([entry["title"] for entry in result], ["new", "retained", "duplicate", "boundary"])

    def test_next_flight_fragments_and_nfl_article_filter(self):
        value = [{"type": "article", "title": "News", "webLink": "https://www.nfl.com/news/a", "publishDate": "2026-10-23T10:00:00Z"}, {"type": "promo", "title": "Ad", "publishDate": "2026-10-23T10:00:00Z"}]
        flight = "a:" + json.dumps(value) + "\n"
        content = ''.join('<script>self.__next_f.push(' + json.dumps([1, fragment]) + ')</script>' for fragment in [flight[:35], flight[35:]]).encode()
        self.assertEqual(len(list(page_objects(content))), 2)
        self.assertEqual(len(parse_page(content, {"id": "nfl"})), 1)

    def test_bebasket_excludes_other_leagues(self):
        posts = [{"title": "Pro B", "slug": "pro-b-news", "createdAt": {"atom": "2026-10-23T10:00:00Z"}, "tags": [{"league": {"slug": "pro-b"}}]}, {"title": "NBA", "slug": "nba-news", "createdAt": {"atom": "2026-10-23T10:00:00Z"}, "tags": [{"league": {"slug": "nba"}}]}]
        content = ('<script type="application/json">' + json.dumps(posts) + '</script>').encode()
        items = parse_page(content, {"id": "bebasket-prob"})
        self.assertEqual([item["title"] for item in items], ["Pro B"])

    def test_bebasket_pagination_stops_at_old_page(self):
        recent = datetime.datetime.now(datetime.timezone.utc).isoformat()
        def post(date):
            return {"title": "News", "slug": "news", "createdAt": {"atom": date}, "tags": [{"league": {"slug": "pro-b"}}]}
        pages = [json.dumps({"items": [post(recent)]}).encode(), json.dumps({"items": [post("2020-01-01T00:00:00Z")]}).encode()]
        with patch('scripts.collect.fetch', side_effect=pages) as fetch_mock:
            self.assertEqual(len(collect_bebasket({"id": "bebasket-prob"})), 2)
            self.assertEqual(fetch_mock.call_count, 2)

    def test_blog_uses_article_date_and_ignores_external_links(self):
        listing = b'<a href="./blog/test">Post</a><a href="./blog/test">Duplicate</a><a href="https://other.com/blog/test">External</a>'
        post = b'<meta property="og:title" content="A &amp; B"><!-- Published Oct 23, 2026 --><time datetime="2026-10-14T14:43:00.000Z">Date</time>'
        with patch('scripts.collect.fetch', side_effect=[listing, post]) as fetch_mock:
            items = collect_blog({"id": "digitalminimalist", "url": "https://www.digitalminimalist.com/blog"})
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]['title'], 'A & B')
            self.assertEqual(items[0]['publishedAt'], '2026-10-14T14:43:00+00:00')
            self.assertEqual(fetch_mock.call_count, 2)


if __name__ == "__main__":
    unittest.main()
