import datetime
import unittest
from unittest.mock import patch

from scripts.collect import merge_articles
from scripts.mangas import chapter_list, collect_manga, otl_publication_dates


class MangaTests(unittest.TestCase):
    manga = {"slug": "example.123", "title": "Example"}
    now = datetime.datetime(2026, 10, 24, tzinfo=datetime.timezone.utc)

    def test_latest_chapter_uses_table_order_and_preserves_old_date(self):
        content = b'<a href="https://mangakatana.com/manga/example.123/c1">Read first</a><table><tr><td><a href="https://mangakatana.com/manga/example.123/c12.5">Chapter 12.5: A &amp; B</a></td><td><div class="update_time">Feb-11-2026</div></td></tr><tr><td><a href="https://mangakatana.com/manga/example.123/c11">Chapter 11</a></td></tr></table>'
        result = chapter_list(content, self.manga)[0]
        self.assertEqual(result["chapter"], "Chapter 12.5: A & B")
        self.assertEqual(result["publishedDate"], "2026-02-11")

    def test_unrelated_links_are_rejected(self):
        with self.assertRaises(ValueError):
            chapter_list(b'<tr><a href="https://evil.example/c99">Chapter 99</a></tr>', self.manga)

    def test_gdscans_uses_latest_chapter_in_public_list_with_its_date(self):
        manga = dict(self.manga, source="gdscans", pageUrl="https://gdscans.com/manga/example/")
        content = b'''
          <li class="volume"><ul>
            <li class="wp-manga-chapter"><a href="volume-8/ch-98-5/">Ch.98.5</a>
              <span class="chapter-release-date"><i>November 10, 2026</i></span></li>
            <li class="wp-manga-chapter"><a href="volume-8/ch-98/">Ch.98</a></li>
            <li class="wp-manga-chapter"><a href="/manga/unrelated/chapter-100/">Chapter 100</a></li>
          </ul></li>'''
        now = datetime.datetime(2026, 11, 18, tzinfo=datetime.timezone.utc)
        with patch("scripts.mangas.fetch", return_value=content) as request:
            result = collect_manga(manga, {}, now)
        request.assert_called_once_with(manga["pageUrl"] + "ajax/chapters/?t=1", data=b"")
        self.assertTrue(result["ok"])
        self.assertEqual(result["chapter"], "Ch.98.5")
        self.assertEqual(result["publishedDate"], "2026-11-10")
        self.assertEqual(result["url"], "https://gdscans.com/manga/example/volume-8/ch-98-5/")

    def test_otl_selects_highest_chapter_in_either_order(self):
        manga = dict(self.manga, source="otl", pageUrl="https://otl.moe/series/example/")
        links = [b'<a class="chapter-title" href="/read/example/9">Chapter 9</a>', b'<a href="/read/example/10.5" class="chapter-title">Chapter 10.5 &amp; more</a>']
        for content in (b''.join(links), b''.join(reversed(links))):
            result = chapter_list(content, manga)[0]
            self.assertEqual(result, {"chapter": "Chapter 10.5 & more", "url": "https://otl.moe/read/example/10.5", "publishedDate": None})

    def test_otl_dates_are_bound_to_latest_chapter_in_each_card(self):
        content = b'<div data-latest-item><time datetime="2026-10-30T08:13:00Z"></time><a href="/read/example/17">17</a><a href="/read/example/16">16</a></div><div data-latest-item><time datetime="invalid"></time><a href="/read/other/1">1</a></div>'
        self.assertEqual(otl_publication_dates(content), {"https://otl.moe/read/example/17": "2026-10-30"})

    def test_otl_date_is_kept_when_chapter_leaves_homepage(self):
        manga = dict(self.manga, source="otl", pageUrl="https://otl.moe/series/example/")
        previous = {"url": "https://otl.moe/read/example/17", "publishedDate": "2026-10-20"}
        with patch("scripts.mangas.fetch", return_value=b'<a class="chapter-title" href="/read/example/17">17</a>'):
            result = collect_manga(manga, previous, self.now, {})
            self.assertEqual(result["publishedDate"], "2026-10-20")
            result = collect_manga(manga, previous, self.now, {previous["url"]: "2026-10-21"})
            self.assertEqual(result["publishedDate"], "2026-10-21")
        with patch("scripts.mangas.fetch", return_value=b'<a class="chapter-title" href="/read/example/18">18</a>'):
            self.assertIsNone(collect_manga(manga, previous, self.now, {})["publishedDate"])

    def test_otl_rejects_external_other_series_and_reading_button(self):
        manga = dict(self.manga, source="otl", pageUrl="https://otl.moe/series/example/")
        for href, classes in (("https://evil.example/read/example/99", "chapter-title"), ("/read/other/99", "chapter-title"), ("/read/example/1", "button")):
            with self.subTest(href=href, classes=classes), self.assertRaises(ValueError):
                chapter_list(f'<a class="{classes}" href="{href}">Chapter 99</a>'.encode(), manga)

    def test_source_change_fetches_immediately_and_drops_old_link_on_failure(self):
        manga = dict(self.manga, source="otl", pageUrl="https://otl.moe/series/example/")
        previous = {"pageUrl": "https://mangakatana.com/manga/example.123", "url": "https://mangakatana.com/manga/example.123/c12", "checkedAt": self.now.isoformat(), "ok": True}
        with patch("scripts.mangas.fetch", side_effect=ValueError("Indisponible")) as request:
            result = collect_manga(manga, previous, self.now)
        request.assert_called_once_with(manga["pageUrl"])
        self.assertFalse(result["ok"])
        self.assertNotIn("url", result)
        self.assertEqual(result["source"], "otl")

    def test_reading_link_does_not_replace_automatic_chapter_detection(self):
        manga = dict(self.manga, readingUrl="https://inkedscans.com/example")
        previous = dict(manga, pageUrl=manga["readingUrl"], source="inkedscans", pageOnly=True, ok=False)
        content = b'<tr><td><a href="/wrong">Wrong</a><a href="https://mangakatana.com/manga/example.123/c12">Chapter 12</a></td></tr>'
        with patch("scripts.mangas.fetch", return_value=content) as request:
            result = collect_manga(manga, previous, self.now)
        request.assert_called_once_with("https://mangakatana.com/manga/example.123")
        self.assertTrue(result["ok"])
        self.assertEqual(result["chapter"], "Chapter 12")
        self.assertEqual(result["readingUrl"], manga["readingUrl"])
        self.assertEqual(result["source"], "mangakatana")
        self.assertNotIn("pageOnly", result)

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
        with patch("scripts.mangas.fetch", return_value=b""), patch("scripts.mangas.chapter_list", return_value=[chapter]):
            result = collect_manga(self.manga, previous, self.now)
        self.assertEqual(result["firstSeenAt"], previous["firstSeenAt"])
        self.assertEqual(result["publishedDate"], "2026-10-24")

    def test_new_chapter_has_new_observation(self):
        previous = {"url": "https://mangakatana.com/manga/example.123/c11", "firstSeenAt": "2026-10-20T20:00:00+00:00"}
        chapter = {"url": "https://mangakatana.com/manga/example.123/c12", "chapter": "Chapter 12", "publishedDate": "2026-10-25"}
        with patch("scripts.mangas.fetch", return_value=b""), patch("scripts.mangas.chapter_list", return_value=[chapter]):
            result = collect_manga(self.manga, previous, self.now)
        self.assertEqual(result["firstSeenAt"], self.now.isoformat())
        self.assertEqual(result["publishedDate"], "2026-10-25")

    def test_same_day_publications_ignore_duplicates_and_other_dates(self):
        base = "https://mangakatana.com/manga/example.123"
        def row(number, date):
            return f'<tr><a href="{base}/c{number}">Chapter {number}</a><div class="update_time">{date}</div></tr>'
        content = "".join([
            row("13", "Oct-24-2026"), row("12.5", "Oct-24-2026"),
            row("12.5", "Oct-24-2026"), row("12", "Oct-23-2026"),
        ])
        with patch("scripts.mangas.fetch", return_value=content.encode()):
            result = collect_manga(self.manga, {}, self.now)
        self.assertEqual(result["url"], f"{base}/c13")
        self.assertEqual(result["sameDayCount"], 2)
        self.assertEqual(len(result["recentChapters"]), 1)

    def test_undated_releases_are_tracked_across_checks_without_counting_history(self):
        manga = dict(self.manga, source="otl", pageUrl="https://otl.moe/series/example/")
        def collect(numbers, previous, now, dates=None):
            content = "".join(f'<a class="chapter-title" href="/read/example/{n}">Chapter {n}</a>' for n in numbers)
            with patch("scripts.mangas.fetch", return_value=content.encode()):
                return collect_manga(manga, previous, now, dates)

        start = self.now.replace(hour=8)
        initial = collect([9, 8, 7], {}, start)
        self.assertEqual(len(initial["recentChapters"]), 1)
        next_day = start + datetime.timedelta(days=1)
        result = collect([9, 10, 10.5, 8], initial, next_day, {
            "https://otl.moe/read/example/10.5": "2026-10-25",
        })
        self.assertEqual(result["chapter"], "Chapter 10.5")
        self.assertNotIn("sameDayCount", result)
        result = collect([11, 10.5, 10, 9, 8], result, next_day.replace(hour=10))
        recent = result["recentChapters"]
        self.assertEqual([entry["url"].rsplit("/", 1)[-1] for entry in recent], ["11", "10.5", "10", "9"])
        self.assertEqual([entry["firstSeenAt"] for entry in recent], [
            next_day.replace(hour=10).isoformat(), next_day.isoformat(), next_day.isoformat(), start.isoformat(),
        ])
        self.assertEqual(recent[1]["publishedDate"], "2026-10-25")

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
