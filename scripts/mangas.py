import datetime
import html
import json
import re
import time

from scripts.collect import ROOT, UTC, clean_title, fetch, parse_date


BASE = "https://mangakatana.com/manga/"


def latest_chapter(content, manga):
    page_url = BASE + manga["slug"]
    for row in re.findall(r"<tr\b[^>]*>(.*?)</tr>", content.decode("utf-8", "replace"), re.S | re.I):
        for href, label in re.findall(r'<a\b[^>]*href="([^"]+)"[^>]*>(.*?)</a>', row, re.S | re.I):
            url = html.unescape(href)
            if not re.fullmatch(re.escape(page_url) + r"/c\d+(?:\.\d+)*(?:[a-z])?", url):
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
            return {"chapter": chapter, "url": url, "publishedDate": published}
    raise ValueError("Aucun lien de chapitre reconnu")


def collect_manga(manga, previous, now):
    item = {"slug": manga["slug"], "title": manga["title"], "pageUrl": BASE + manga["slug"]}
    previous = dict(previous)
    # Migration : dernière observation réussie du chapitre déjà enregistré.
    if previous.get("url") and not previous.get("firstSeenAt") and parse_date(previous.get("lastSuccessAt")):
        previous["firstSeenAt"] = previous["lastSuccessAt"]
    checked = parse_date(previous.get("checkedAt"))
    if checked and datetime.timedelta(0) <= now - checked < datetime.timedelta(minutes=30):
        return dict(previous, **item)
    try:
        chapter = latest_chapter(fetch(item["pageUrl"]), manga)
        first_seen = previous.get("firstSeenAt") if previous.get("url") == chapter["url"] else None
        return dict(item, **chapter, firstSeenAt=first_seen or now.isoformat(), ok=True, checkedAt=now.isoformat(), lastSuccessAt=now.isoformat())
    except Exception as error:
        return dict(previous, **item, ok=False, checkedAt=now.isoformat(), error=str(error)[:180])


def main():
    target = ROOT / "data" / "mangas.json"
    previous = json.loads(target.read_text()) if target.exists() else {"mangas": []}
    saved = {item["slug"]: item for item in previous["mangas"]}
    now = datetime.datetime.now(UTC)
    items = []
    for manga in json.loads((ROOT / "mangas.json").read_text()):
        item = collect_manga(manga, saved.get(manga["slug"], {}), now)
        items.append(item)
        print(manga["title"] + ": " + (item.get("chapter", "Sans chapitre") if item["ok"] else item["error"]), flush=True)
        if item["checkedAt"] == now.isoformat():
            time.sleep(1)
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps({"mangas": items}, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(target)


if __name__ == "__main__":
    main()
