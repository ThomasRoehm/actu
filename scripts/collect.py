import concurrent.futures
import datetime
import email.utils
import html
from html.parser import HTMLParser
import json
import pathlib
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET


ROOT = pathlib.Path(__file__).resolve().parents[1]
UTC = datetime.timezone.utc
HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/rss+xml, application/atom+xml, text/html, */*"}


def fetch(url):
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=35) as response:
        content = response.read(8_000_001)
        if len(content) > 8_000_000:
            raise ValueError("Réponse trop volumineuse")
        return content


def parse_date(value):
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        date = datetime.datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        try:
            date = email.utils.parsedate_to_datetime(value)
        except (ValueError, TypeError, IndexError):
            return None
    if date.tzinfo is None:
        return None
    return date.astimezone(UTC)


def clean_title(value):
    return " ".join(html.unescape(re.sub(r"<[^>]*>", "", str(value or ""))).split())


def canonical_url(value):
    if not isinstance(value, str):
        return None
    parsed = urllib.parse.urlsplit(html.unescape(value))
    if parsed.scheme not in ("https", "http") or not parsed.hostname:
        return None
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    query = [(key, item) for key, item in query if not key.startswith("utm_") and key not in ("fbclid", "gclid")]
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(query), ""))


def article(source, title, url, published):
    date = parse_date(published)
    url = canonical_url(url)
    title = clean_title(title)
    if not date or not url or not title:
        return None
    return {"source": source["id"], "title": title, "url": url, "publishedAt": date.isoformat()}


def parse_feed(content, source):
    root = ET.fromstring(content)
    entries = root.findall(".//item") + root.findall("{http://www.w3.org/2005/Atom}entry")
    if not entries:
        raise ValueError("Flux sans entrée reconnue")
    result = []
    for entry in entries:
        fields = {}
        for child in entry:
            tag = child.tag.split("}")[-1]
            if tag == "link" and child.attrib.get("href"):
                if child.attrib.get("rel", "alternate") == "alternate":
                    fields["link"] = child.attrib["href"]
            elif child.text:
                fields.setdefault(tag, child.text)
        item = article(source, fields.get("title"), fields.get("link"), fields.get("pubDate") or fields.get("published") or fields.get("date") or fields.get("updated"))
        if item:
            result.append(item)
    if not result:
        raise ValueError("Aucune entrée avec date et lien valides")
    return result


def walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def page_objects(content):
    text = content.decode("utf-8", "replace")
    for match in re.finditer(r'<script[^>]*type="application/(?:ld\+json|json)"[^>]*>(.*?)</script>', text, re.S):
        try:
            yield from walk(json.loads(match.group(1)))
        except ValueError:
            pass
    fragments = []
    for match in re.finditer(r'self\.__next_f\.push\((\[.*?\])\)</script>', text, re.S):
        try:
            block = json.loads(match.group(1))
            if len(block) > 1 and isinstance(block[1], str):
                fragments.append(block[1])
        except ValueError:
            pass
    for line in "".join(fragments).splitlines():
        try:
            yield from walk(json.loads(line.partition(":")[2]))
        except ValueError:
            pass


def bebasket_article(obj, source):
    league = "betclic-elite" if source["id"] == "bebasket-elite" else "pro-b"
    matching = any(tag.get("league", {}).get("slug") == league for tag in obj.get("tags", []) if isinstance(tag, dict) and isinstance(tag.get("league"), dict))
    if matching and obj.get("slug") and isinstance(obj.get("createdAt"), dict):
        return article(source, obj.get("title"), "https://www.bebasket.fr/" + obj["slug"], obj["createdAt"].get("atom"))
    return None


def collect_bebasket(source):
    result = []
    cutoff = datetime.datetime.now(UTC) - datetime.timedelta(hours=48)
    for page in range(1, 13):
        payload = json.loads(fetch(f"https://admin.bebasket.fr/api/v1/fr/blog/post?page={page}"))
        items = payload.get("items")
        if not isinstance(items, list):
            raise ValueError("Liste d’articles BeBasket non reconnue")
        if not items:
            break
        dates = []
        for obj in items:
            item = bebasket_article(obj, source)
            if item:
                result.append(item)
            date = parse_date(obj.get("createdAt", {}).get("atom"))
            if date:
                dates.append(date)
        if dates and max(dates) < cutoff:
            break
    return result


def parse_page(content, source):
    result = []
    for obj in page_objects(content):
        if source["id"] == "nba" and obj.get("type") == "post":
            item = article(source, obj.get("title"), obj.get("permalink"), obj.get("date"))
        elif source["id"] == "nfl" and obj.get("type") == "article":
            item = article(source, obj.get("title"), obj.get("webLink") or obj.get("href"), obj.get("publishDate"))
        elif source["id"].startswith("bebasket-") and isinstance(obj.get("createdAt"), dict) and obj.get("slug"):
            item = bebasket_article(obj, source)
        else:
            item = None
        if item:
            result.append(item)
    if not result:
        raise ValueError("Métadonnées d’articles non reconnues")
    return result


class BlogPage(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.title = None
        self.published = None

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag == "a" and attrs.get("href"):
            self.links.append(attrs["href"])
        if tag == "meta" and attrs.get("property") == "og:title":
            self.title = attrs.get("content")
        if tag == "time" and attrs.get("datetime") and self.published is None:
            self.published = attrs["datetime"]


def collect_blog(source):
    listing = BlogPage()
    listing.feed(fetch(source["url"]).decode("utf-8", "replace"))
    urls = []
    for link in listing.links:
        url = urllib.parse.urljoin(source["url"], link)
        parsed = urllib.parse.urlsplit(url)
        if parsed.hostname == "www.digitalminimalist.com" and parsed.path.startswith("/blog/") and url not in urls:
            urls.append(url)
    if not urls:
        raise ValueError("Aucun lien d’article reconnu")
    result = []
    for url in urls[:12]:
        page = BlogPage()
        page.feed(fetch(url).decode("utf-8", "replace"))
        item = article(source, page.title, url, page.published)
        if item:
            result.append(item)
    if not result:
        raise ValueError("Aucune date de publication reconnue")
    return result


def collect_source(source):
    try:
        if source.get("mode") == "blog":
            return source, collect_blog(source), None
        if source["id"].startswith("bebasket-"):
            return source, collect_bebasket(source), None
        content = fetch(source.get("feed") or source["url"])
        items = parse_feed(content, source) if source.get("feed") else parse_page(content, source)
        return source, items, None
    except Exception as error:
        return source, [], str(error)[:180]


def merge_articles(previous, incoming, source_ids, now):
    cutoff = now - datetime.timedelta(hours=48)
    merged = {}
    for item in previous + incoming:
        date = parse_date(item.get("publishedAt"))
        url = canonical_url(item.get("url"))
        if date and cutoff <= date <= now and url and item.get("source") in source_ids:
            merged[url] = dict(item, url=url)
    return sorted(merged.values(), key=lambda item: parse_date(item["publishedAt"]), reverse=True)


def main():
    sources = json.loads((ROOT / "sources.json").read_text())
    target = ROOT / "data" / "articles.json"
    previous = json.loads(target.read_text()) if target.exists() else {"articles": [], "sources": []}
    previous_status = {source["id"]: source for source in previous.get("sources", [])}
    now = datetime.datetime.now(UTC)
    incoming, statuses = [], []
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        for source, items, error in pool.map(collect_source, sources):
            incoming.extend(items)
            status = {key: source[key] for key in ("id", "name", "url", "group")}
            extension = "jpg" if (ROOT / "icons" / (source["id"] + ".jpg")).exists() else "png"
            status["icon"] = "icons/" + source["id"] + "." + extension
            status.update(ok=error is None, error=error, lastSuccessAt=now.isoformat() if error is None else previous_status.get(source["id"], {}).get("lastSuccessAt"))
            statuses.append(status)
            print(f'{source["name"]}: {error or str(len(items)) + " articles lus"}', flush=True)
    if not any(source["ok"] for source in statuses):
        raise RuntimeError("Toutes les collectes ont échoué ; publication annulée")
    articles = merge_articles(previous.get("articles", []), incoming, {source["id"] for source in sources}, now)
    target.parent.mkdir(exist_ok=True)
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps({"generatedAt": now.isoformat(), "sources": statuses, "articles": articles}, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(target)
    print(f"{len(articles)} articles conservés sur les dernières 48 heures.")


if __name__ == "__main__":
    main()
