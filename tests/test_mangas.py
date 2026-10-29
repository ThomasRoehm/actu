import datetime
import unittest
from unittest.mock import patch

from scripts.collect import merge_articles
from scripts.mangas import collect_manga, latest_chapter


class MangaTests(unittest.TestCase):
    manga = {"slug": "example.123", "title": "Example"}
    now = datetime.datetime(2026, 10, 24, tzinfo=datetime.timezone.utc)

    def test_latest_chapter_uses_table_order_and_preserves_old_date(self):
        content = b'<a href="https://mangakatana.com/manga/example.123/c1">Read first</a><table><tr><td><a href="https://mangakatana.com/manga/example.123/c12.5">Chapter 12.5: A &amp; B</a></td><td><div class="update_time">Feb-11-2026</div></td></tr><tr><td><a href="https://mangakatana.com/manga/example.123/c11">Chapter 11</a></td></tr></table>'
        result = latest_chapter(content, self.manga)
        self.assertEqual(result["chapter"], "Chapter 12.5: A & B")
        self.assertEqual(result["publishedDate"], "2026-02-11")

    def test_unrelated_links_are_rejected(self):
        with self.assertRaises(ValueError):
            latest_chapter(b'<tr><a href="https://evil.example/c99">Chapter 99</a></tr>', self.manga)

    def test_otl_selects_highest_chapter_in_either_order(self):
        manga = dict(self.manga, source="otl", pageUrl="https://otl.moe/series/example/")
        links = [b'<a class="chapter-title" href="/read/example/9">Chapter 9</a>', b'<a href="/read/example/10.5" class="chapter-title">Chapter 10.5 &amp; more</a>']
        for content in (b''.join(links), b''.join(reversed(links))):
            result = latest_chapter(content, manga)
            self.assertEqual(result, {"chapter": "Chapter 10.5 & more", "url": "https://otl.moe/read/example/10.5", "publishedDate": None})

    def test_otl_rejects_external_other_series_and_reading_button(self):
        manga = dict(self.manga, source="otl", pageUrl="https://otl.moe/series/example/")
        for href, classes in (("https://evil.example/read/example/99", "chapter-title"), ("/read/other/99", "chapter-title"), ("/read/example/1", "button")):
            with self.subTest(href=href, classes=classes), self.assertRaises(ValueError):
                latest_chapter(f'<a class="{classes}" href="{href}">Chapter 99</a>'.encode(), manga)

    def test_source_change_fetches_immediately_and_drops_old_link_on_failure(self):
        manga = dict(self.manga, source="otl", pageUrl="https://otl.moe/series/example/")
        previous = {"pageUrl": "https://mangakatana.com/manga/example.123", "url": "https://mangakatana.com/manga/example.123/c12", "checkedAt": self.now.isoformat(), "ok": True}
        with patch("scripts.mangas.fetch", side_effect=ValueError("Indisponible")) as request:
            result = collect_manga(manga, previous, self.now)
        request.assert_called_once_with(manga["pageUrl"])
        self.assertFalse(result["ok"])
        self.assertNotIn("url", result)
        self.assertEqual(result["source"], "otl")

    def test_failed_collection_preserves_last_known_chapter(self):
        previous = {"chapter": "Chapter 12", "url": "https://mangakatana.com/manga/example.123/c12"}
        with patch("scripts.mangas.fetch", side_effect=ValueError("Indisponible")):
            result = collect_manga(self.manga, previous, self.now)
        self.assertFalse(result["ok"])
        self.assertEqual(result["chapter"], previous["chapter"])

    def test_recent_check_does_not_request_site(self):
        previous = {"checkedAt": self.now.isoformat(), "chapter": "Chapter 12", "ok": True}
        with patch("scripts.mangas.fetch") as request:
            result = collect_manga(self.manga, previous, self.now)
        request.assert_not_called()
        self.assertEqual(result["chapter"], "Chapter 12")

    def test_first_observation_is_stable_for_same_chapter(self):
        previous = {"url": "https://mangakatana.com/manga/example.123/c12", "firstSeenAt": "2026-10-23T20:00:00+00:00"}
        chapter = {"url": previous["url"], "chapter": "Chapter 12", "publishedDate": "2026-10-24"}
        with patch("scripts.mangas.fetch", return_value=b""), patch("scripts.mangas.latest_chapter", return_value=chapter):
            result = collect_manga(self.manga, previous, self.now)
        self.assertEqual(result["firstSeenAt"], previous["firstSeenAt"])
        self.assertEqual(result["publishedDate"], "2026-10-24")

    def test_new_chapter_has_new_observation(self):
        previous = {"url": "https://mangakatana.com/manga/example.123/c11", "firstSeenAt": "2026-10-20T20:00:00+00:00"}
        chapter = {"url": "https://mangakatana.com/manga/example.123/c12", "chapter": "Chapter 12", "publishedDate": "2026-10-25"}
        with patch("scripts.mangas.fetch", return_value=b""), patch("scripts.mangas.latest_chapter", return_value=chapter):
            result = collect_manga(self.manga, previous, self.now)
        self.assertEqual(result["firstSeenAt"], self.now.isoformat())
        self.assertEqual(result["publishedDate"], "2026-10-25")

    def test_migration_even_when_check_is_throttled(self):
        previous = {"url": "https://mangakatana.com/manga/example.123/c12", "checkedAt": self.now.isoformat(), "lastSuccessAt": "2026-10-23T23:55:00+00:00"}
        with patch("scripts.mangas.fetch") as request:
            result = collect_manga(self.manga, previous, self.now)
        request.assert_not_called()
        self.assertEqual(result["firstSeenAt"], previous["lastSuccessAt"])

    def test_bd_keeps_only_latest_without_48_hour_limit(self):
        older = {"source": "bd", "title": "Old", "url": "https://example.com/old", "publishedAt": "2025-01-01T00:00:00+00:00"}
        latest = dict(older, url="https://example.com/latest", publishedAt="2026-01-01T00:00:00+00:00")
        news = dict(latest, source="tech", url="https://example.com/tech")
        result = merge_articles([older, latest, news], [], {"bd", "tech"}, self.now, {"bd"})
        self.assertEqual(result, [latest])
