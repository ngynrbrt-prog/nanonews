"""Select credited Wikimedia Commons illustrations for the current edition."""

from html import unescape
import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen


PHOTO_VERSION = 4
NAME = re.compile(r"\b[A-ZÀ-ÖØ-Þ][a-zà-öø-ÿ-]{2,}(?: [A-ZÀ-ÖØ-Þ][a-zà-öø-ÿ-]{2,}){1,2}\b")

TOPICS = (
    (r"kézilabd|kézi bl", "handball match"),
    (r"megélhet|szegénység|energiaszegénység|fűteni", "household heating radiator"),
    (r"\b(?:f1|formula[- ]?1|forma[- ]?1)\b", "formula race car"),
    (r"\b(?:nfl|super bowl|touchdown)\b|seahawks|amerikai futball", "american football"),
    (r"\bnba\b|kosárlabda", "basketball court"),
    (r"labdarúg|futball|premier league|bajnokok ligája|arsenal", "soccer stadium"),
    (r"kerékpár|\bvuelta\b|tour de france", "road cycling"),
    (r"sípály|síel|alpesi sí|síverseny", "ski slope"),
    (r"tenisz|\bwta\b|\batp\b", "tennis court"),
    (r"\bdarts\b", "dartboard"),
    (r"infláci|élelmiszerár|bevásárl", "grocery shopping"),
    (r"napenerg|napelem", "solar panels"),
    (r"szélenerg|szélerőmű", "wind turbines"),
    (r"ingatlan|lakáspiac", "apartment buildings"),
    (r"\btőzsde|részvénypiac|\bbux\b|\bnasdaq\b", "stock exchange trading floor"),
)
def photo_query(story):
    original = (story.get("variants") or {}).get("original") or {}
    for value in (story.get("title"), original.get("body")):
        plain_text = unescape(re.sub(r"<[^>]*>", " ", value or ""))
        topic = next((query for pattern, query in TOPICS
                      if re.search(pattern, plain_text.casefold())), None)
        if not topic:
            continue
        name = NAME.search(plain_text)
        if name and name.group() not in {"Premier League", "Tour de France", "Super Bowl"}:
            return '"' + name.group() + '" ' + topic.split()[0]
        return topic
    return None


def on_host(url, hosts):
    parts = urlsplit(url or "")
    return parts.scheme == "https" and parts.netloc in hosts


def search_photos(query):
    params = urlencode({
        "action": "query", "format": "json", "formatversion": 2,
        "generator": "search", "gsrnamespace": 6, "gsrlimit": 10,
        "gsrsearch": query + " filetype:bitmap",
        "prop": "imageinfo", "iiprop": "url|mime|extmetadata", "iiurlwidth": 800,
        "iiextmetadatafilter": "Artist|Credit|Attribution|LicenseShortName|LicenseUrl",
    })
    request = Request("https://commons.wikimedia.org/w/api.php?" + params,
                      headers={"User-Agent": "NANONews/1.10 (https://github.com/ngynrbrt-prog/nanonews)"})
    with urlopen(request, timeout=4) as response:
        payload = json.load(response)
    if "error" in payload:
        raise ValueError("Commons API error")
    pages = payload.get("query", {}).get("pages", [])
    photos = []
    for page in sorted(pages, key=lambda item: item.get("index") or 0):
        if query.startswith('"'):
            name = query.split('"')[1].casefold()
            filename = page.get("title", "").replace("_", " ").casefold()
            if name not in filename:
                continue
        info = next(iter(page.get("imageinfo", [])), {})
        if info.get("mime") not in {"image/jpeg", "image/png", "image/webp"}:
            continue
        metadata = info.get("extmetadata", {})
        def field(name):
            return metadata.get(name, {}).get("value", "")
        author = " ".join(unescape(re.sub(r"<[^>]*>", " ",
                          field("Attribution") or field("Artist"))).split())
        license_name = field("LicenseShortName")
        license_url = field("LicenseUrl")
        image = info.get("thumburl") or info.get("url")
        source = info.get("descriptionurl")
        if not author or license_name not in {"CC BY 4.0", "CC BY-SA 4.0", "CC0"}:
            continue
        if not on_host(license_url, {"creativecommons.org"}):
            continue
        if not on_host(image, {"upload.wikimedia.org", "thumb.wikimedia.org"}) or not on_host(source, {"commons.wikimedia.org"}):
            continue
        credit = " ".join(unescape(re.sub(r"<[^>]*>", " ", field("Credit"))).split())
        photos.append({"image": image, "page": source, "author": author, "credit": credit,
                "title": page.get("title", "").removeprefix("File:"),
                "license": license_name, "licenseUrl": license_url})
    return photos


def enrich_photos(stories, within_budget):
    """Return the article URLs whose Commons metadata was populated."""
    used_pages = {
        photo["page"] for story in stories
        if (photo := story.get("commonsPhoto") or {}).get("version") in {3, PHOTO_VERSION}
        and photo.get("image") and photo.get("page")
    }
    results = {}
    updated = {}
    for story in stories:
        if not within_budget():
            break
        existing = story.get("commonsPhoto") or {}
        if story.get("archiveDate") or not story.get("url"):
            continue
        if existing.get("version") == PHOTO_VERSION or (
            existing.get("version") == 3 and existing.get("image")
        ):
            continue
        query = photo_query(story)
        if query and query not in results:
            if len(results) >= 4:
                continue
            try:
                results[query] = search_photos(query)
            except HTTPError as error:
                print(f"Wikimedia Commons: HTTP {error.code}", flush=True)
                break
            except (URLError, TimeoutError, ValueError) as error:
                print(f"Wikimedia Commons: {type(error).__name__}", flush=True)
                break
        candidates = results.get(query) or []
        candidate = next((photo for photo in candidates if photo["page"] not in used_pages),
                         candidates[0] if candidates else None)
        if candidate:
            used_pages.add(candidate["page"])
        photo = dict(candidate or {"unavailable": True}, version=PHOTO_VERSION)
        story["commonsPhoto"] = photo
        updated[story["url"]] = photo
    return updated
