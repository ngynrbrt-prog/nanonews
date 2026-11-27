"""Select credited Wikimedia Commons illustrations for the current edition."""

from html import unescape
import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen


TOPICS = (
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
    (r"\btőzsde|részvénypiac|\bbux\b|\bnasdaq\b", "stock market"),
)
CATEGORY_QUERIES = {
    "nba": "basketball court", "nfl": "american football",
    "f1": "formula race car", "cycling": "road cycling",
    "tennis": "tennis court", "darts": "dartboard",
    "property": "apartment buildings",
}


def photo_query(story):
    original = (story.get("variants") or {}).get("original") or {}
    for value in (original.get("body"), story.get("title")):
        plain_text = unescape(re.sub(r"<[^>]*>", " ", value or "")).casefold()
        for pattern, query in TOPICS:
            if re.search(pattern, plain_text):
                return query
    return next((CATEGORY_QUERIES[cat] for cat in story.get("categories", [])
                 if cat in CATEGORY_QUERIES), None)


def on_host(url, hosts):
    parts = urlsplit(url or "")
    return parts.scheme == "https" and parts.netloc in hosts


def search_photo(query):
    params = urlencode({
        "action": "query", "format": "json", "formatversion": 2,
        "generator": "search", "gsrnamespace": 6, "gsrlimit": 5,
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
    for page in sorted(pages, key=lambda item: item.get("index", 0)):
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
        return {"image": image, "page": source, "author": author, "credit": credit,
                "title": page.get("title", "").removeprefix("File:"),
                "license": license_name, "licenseUrl": license_url}
    return None


def enrich_photos(stories, within_budget):
    """Return the article URLs whose Pexels metadata was populated."""
    results = {}
    updated = {}
    for story in stories:
        if not within_budget():
            break
        if story.get("archiveDate") or story.get("commonsPhoto") or not story.get("url"):
            continue
        query = photo_query(story)
        if not query:
            continue
        if query not in results:
            if len(results) >= 4:
                continue
            try:
                results[query] = search_photo(query)
            except HTTPError as error:
                print(f"Wikimedia Commons: HTTP {error.code}", flush=True)
                break
            except (URLError, TimeoutError, ValueError) as error:
                print(f"Wikimedia Commons: {type(error).__name__}", flush=True)
                break
        photo = results[query] or {"unavailable": True}
        story["commonsPhoto"] = photo
        updated[story["url"]] = photo
    return updated
