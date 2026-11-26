import datetime
import html
import json
import re
import time
from decimal import Decimal
from urllib.parse import urljoin, urlsplit

from scripts.collect import ROOT, UTC, clean_title, fetch, parse_date


BASE = "https://mangakatana.com/manga/"


def otl_publication_dates(content):
    dates = {}
    # Une carte de mises à jour associe sa date au dernier chapitre lié.
    for block in re.split(r'<div\b[^>]*\bdata-latest-item\b[^>]*>', content.decode("utf-8", "replace"))[1:]:
        date_match = re.search(r'<time\b[^>]*datetime=[\'\"]([^\'\"]+)', block)
        chapter_match = re.search(r'href=[\'\"](/read/[^/\'\"]+/\d+(?:\.\d+)?)/?[\'\"]', block)
        date = parse_date(date_match[1]) if date_match else None
        if date and chapter_match:
            dates["https://otl.moe" + chapter_match[1]] = date.date().isoformat()
    return dates


def otl_chapters(content, manga):
    series = urlsplit(manga["pageUrl"]).path.strip("/").split("/")[-1]
    candidates = []
    for attributes, label in re.findall(r"<a\b([^>]*)>(.*?)</a>", content.decode("utf-8", "replace"), re.S | re.I):
        href = re.search(r'\bhref=[\'\"]([^\'\"]+)[\'\"]', attributes)
        classes = re.search(r'\bclass=[\'\"]([^\'\"]+)[\'\"]', attributes)
        if not href or not classes or "chapter-title" not in classes[1].split():
            continue
        url = urljoin(manga["pageUrl"], html.unescape(href[1]))
        number = re.fullmatch(r"https://otl\.moe/read/" + re.escape(series) + r"/(\d+(?:\.\d+)?)/?", url)
        chapter = clean_title(label)
        if number and chapter:
            candidates.append((Decimal(number[1]), {"chapter": chapter, "url": url.rstrip("/"), "publishedDate": None}))
    return [chapter for _, chapter in sorted(candidates, key=lambda candidate: candidate[0], reverse=True)]


def gdscans_chapters(content, manga):
    page_url = manga["pageUrl"].rstrip("/") + "/"
    chapter_path = re.escape(page_url) + r"(?:volume-\d+/)?(?:chapter|ch)-(\d+)(?:[-.](\d+))?/?"
    candidates = []
    for item in re.split(r"<li\b", content.decode("utf-8", "replace"), flags=re.I)[1:]:
        attributes, _, row = item.partition(">")
        row = row.split("</li>", 1)[0]
        classes = re.search(r'\bclass=[\'\"]([^\'\"]+)', attributes)
        if not classes or "wp-manga-chapter" not in classes[1].split():
            continue
        link = re.search(r'<a\b[^>]*\bhref=[\'\"]([^\'\"]+)[\'\"][^>]*>(.*?)</a>', row, re.S | re.I)
        if not link:
            continue
        url = urljoin(page_url, html.unescape(link[1]))
        number = re.fullmatch(chapter_path, url)
        chapter = clean_title(link[2])
        if not number or not chapter:
            continue
        date_markup = re.search(r'class=[\'\"]chapter-release-date[\'\"][^>]*>(.*?)</span>', row, re.S | re.I)
        published = None
        if date_markup:
            try:
                published = datetime.datetime.strptime(clean_title(date_markup[1]), "%B %d, %Y").date().isoformat()
            except ValueError:
                pass
        rank = Decimal(f"{number[1]}.{number[2] or '0'}")
        candidates.append((rank, {"chapter": chapter, "url": url, "publishedDate": published}))
    return [chapter for _, chapter in sorted(candidates, key=lambda candidate: candidate[0], reverse=True)]


def mangakatana_chapters(content, manga):
    chapter_path = re.compile(re.escape(BASE + manga["slug"]) + r"/c\d+(?:\.\d+)*(?:[a-z])?")
    chapters = []
    for row in re.findall(r"<tr\b[^>]*>(.*?)</tr>", content.decode("utf-8", "replace"), re.S | re.I):
        for href, label in re.findall(r'<a\b[^>]*href="([^"]+)"[^>]*>(.*?)</a>', row, re.S | re.I):
            url = html.unescape(href)
            if not chapter_path.fullmatch(url):
                continue
            chapter = clean_title(label)
            if not chapter:
                continue
            date_match = re.search(r'class="update_time"[^>]*>(.*?)</div>', row, re.S)
            published = None
            if date_match:
                try:
                    published = datetime.datetime.strptime(clean_title(date_match[1]), "%b-%d-%Y").date().isoformat()
                except ValueError:
                    pass
            chapters.append({"chapter": chapter, "url": url, "publishedDate": published})
            break
    return chapters


def chapter_list(content, manga):
    parser = {"otl": otl_chapters, "gdscans": gdscans_chapters}.get(manga.get("source"), mangakatana_chapters)
    chapters = parser(content, manga)
    if not chapters:
        raise ValueError("Aucun lien de chapitre reconnu")
    unique = {}
    for chapter in chapters:
        unique.setdefault(chapter["url"], chapter)
    return list(unique.values())


def recent_observations(chapters, previous, now):
    previous_url = previous.get("url", "").rstrip("/")
    observations = {entry["url"]: entry for entry in previous.get("recentChapters", [])}
    if previous_url and previous.get("firstSeenAt"):
        observations.setdefault(previous_url, {"url": previous_url, "firstSeenAt": previous["firstSeenAt"], "publishedDate": previous.get("publishedDate")})
    # Sans chapitre de référence dans la liste, initialiser avec le premier seul.
    listed = {chapter["url"].rstrip("/"): chapter for chapter in chapters}
    boundary = next((index for index, url in enumerate(listed) if url == previous_url), 1)
    cutoff = now - datetime.timedelta(days=2)
    recent = []
    for index, (url, chapter) in enumerate(listed.items()):
        if index < boundary:
            observations.setdefault(url, {"url": url, "firstSeenAt": now.isoformat(), "publishedDate": None})
        observation = observations.get(url)
        if observation and (parse_date(observation["firstSeenAt"]) or cutoff) > cutoff:
            recent.append(dict(observation, publishedDate=chapter["publishedDate"] or observation["publishedDate"]))
    return recent


def collect_manga(manga, previous, now, otl_dates=None):
    item = {"slug": manga["slug"], "title": manga["title"], "pageUrl": manga.get("pageUrl", BASE + manga["slug"]), "source": manga.get("source", "mangakatana")}
    if manga.get("readingUrl"):
        item["readingUrl"] = manga["readingUrl"]
    previous = dict(previous)
    previous.pop("readingUrl", None)
    if previous.get("pageUrl") and previous["pageUrl"] != item["pageUrl"]:
        previous = {}
    # Migration : dernière observation réussie du chapitre déjà enregistré.
    if previous.get("url") and not previous.get("firstSeenAt") and parse_date(previous.get("lastSuccessAt")):
        previous["firstSeenAt"] = previous["lastSuccessAt"]
    checked = parse_date(previous.get("checkedAt"))
    if checked and datetime.timedelta(0) <= now - checked < datetime.timedelta(minutes=30):
        return dict(previous, **item)
    try:
        if item["source"] == "gdscans":
            url = item["pageUrl"].rstrip("/") + "/ajax/chapters/?t=1"
            content = fetch(url, data=b"")
        else:
            content = fetch(item["pageUrl"])
        chapters = chapter_list(content, manga)
        previous_url = previous.get("url", "").rstrip("/")
        if item["source"] == "otl":
            known_dates = {entry["url"]: entry["publishedDate"] for entry in previous.get("recentChapters", [])}
            known_dates[previous_url] = previous.get("publishedDate")
            for chapter in chapters:
                url = chapter["url"]
                chapter["publishedDate"] = (otl_dates or {}).get(url) or known_dates.get(url)
        latest = chapters[0]
        same_day_count = sum(chapter["publishedDate"] == latest["publishedDate"] for chapter in chapters) if latest["publishedDate"] else 0
        first_seen = previous.get("firstSeenAt") if previous_url == latest["url"].rstrip("/") else None
        recent = recent_observations(chapters, previous, now)
        result = dict(item, **latest, firstSeenAt=first_seen or now.isoformat(), ok=True, checkedAt=now.isoformat(), lastSuccessAt=now.isoformat())
        if same_day_count > 1:
            result["sameDayCount"] = same_day_count
        if recent:
            result["recentChapters"] = recent
        return result
    except Exception as error:
        return dict(previous, **item, ok=False, checkedAt=now.isoformat(), error=str(error)[:180])


def main():
    target = ROOT / "data" / "mangas.json"
    previous = json.loads(target.read_text()) if target.exists() else {"mangas": []}
    saved = {item["slug"]: item for item in previous["mangas"]}
    now = datetime.datetime.now(UTC)
    items = []
    selection = json.loads((ROOT / "mangas.json").read_text())
    otl_dates = {}
    if any(manga.get("source") == "otl" for manga in selection):
        try:
            otl_dates = otl_publication_dates(fetch("https://otl.moe/"))
        except Exception:
            print("Dates OTL indisponibles ; conservation des dates déjà connues.", flush=True)
        time.sleep(1)
    for manga in selection:
        item = collect_manga(manga, saved.get(manga["slug"], {}), now, otl_dates)
        items.append(item)
        print(manga["title"] + ": " + (item.get("chapter", "Sans chapitre") if item["ok"] else item["error"]), flush=True)
        if item["checkedAt"] == now.isoformat():
            time.sleep(1)
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps({"mangas": items}, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(target)


if __name__ == "__main__":
    main()
