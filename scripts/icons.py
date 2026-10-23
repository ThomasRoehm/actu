import concurrent.futures
import json
import pathlib
import urllib.parse
import urllib.request


ROOT = pathlib.Path(__file__).resolve().parents[1]


def download(source):
    host = urllib.parse.urlsplit(source["url"]).hostname
    url = "https://www.google.com/s2/favicons?" + urllib.parse.urlencode({"domain": host, "sz": 32})
    try:
        with urllib.request.urlopen(url, timeout=25) as response:
            data = response.read(100_000)
        extension = "png" if data.startswith(b"\x89PNG") else "jpg" if data.startswith(b"\xff\xd8\xff") else None
        if not extension:
            raise ValueError("Format PNG ou JPEG attendu")
        (ROOT / "icons" / (source["id"] + "." + extension)).write_bytes(data)
        return source["name"] + " : icône enregistrée"
    except Exception as error:
        return source["name"] + " : initiale utilisée (" + str(error) + ")"


if __name__ == "__main__":
    (ROOT / "icons").mkdir(exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        for message in pool.map(download, json.loads((ROOT / "sources.json").read_text())):
            print(message)
