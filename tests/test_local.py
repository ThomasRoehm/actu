import unittest
from unittest.mock import patch

from scripts.collect import collect_local


class LocalTests(unittest.TestCase):
    def test_only_communal_articles_are_collected_and_deduplicated(self):
        source = {"id": "local", "url": "https://actu.fr/normandie/grand-bourgtheroulde_27105"}
        url = source["url"] + "/article_123.html"
        listing = f'<a href="{url}">Article</a><a href="{url}">Doublon</a><a href="https://actu.fr/autre/article.html">Autre commune</a>'.encode()
        page = b'<script type="application/ld+json">{"headline":"Titre local","datePublished":"2026-10-23T10:00:00+02:00","dateModified":"2026-10-24T12:00:00+02:00"}</script>'
        with patch("scripts.collect.fetch", side_effect=[listing, page]) as request:
            items = collect_local(source)
        self.assertEqual(request.call_count, 2)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["url"], url)
        self.assertEqual(items[0]["publishedAt"], "2026-10-23T08:00:00+00:00")

    def test_missing_dates_are_reported(self):
        source = {"id": "local", "url": "https://actu.fr/normandie/grand-bourgtheroulde_27105"}
        listing = f'<a href="{source["url"]}/article.html">Article</a>'.encode()
        with patch("scripts.collect.fetch", side_effect=[listing, b'<html></html>']):
            with self.assertRaises(ValueError):
                collect_local(source)
