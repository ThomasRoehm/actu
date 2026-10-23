import datetime
import json
import unittest

from scripts.collect import article, merge_articles, page_objects, parse_date, parse_feed, parse_page


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


if __name__ == "__main__":
    unittest.main()
