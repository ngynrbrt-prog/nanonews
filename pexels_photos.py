"""Select credited Pexels illustrations for the current edition."""

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


def search_photo(query, api_key):
    params = urlencode({"query": query, "orientation": "landscape", "per_page": 5})
    request = Request("https://api.pexels.com/v1/search?" + params,
                      headers={"Authorization": api_key})
    with urlopen(request, timeout=4) as response:
        payload = json.load(response)
    for photo in payload.get("photos", []):
        image = (photo.get("src") or {}).get("large")
        page = photo.get("url")
        photographer = (photo.get("photographer") or "").strip()
        profile = photo.get("photographer_url")
        if not photographer or not on_host(image, {"images.pexels.com"}):
            continue
        if not on_host(page, {"www.pexels.com", "pexels.com"}):
            continue
        return {
            "image": image, "page": page, "photographer": photographer,
            "profile": profile if on_host(profile, {"www.pexels.com", "pexels.com"}) else None,
        }
    return None


def enrich_photos(stories, api_key, within_budget):
    """Return the article URLs whose Pexels metadata was populated."""
    results = {}
    updated = {}
    for story in stories:
        if not within_budget():
            break
        if story.get("archiveDate") or story.get("pexelsPhoto") or not story.get("url"):
            continue
        query = photo_query(story)
        if not query:
            continue
        if query not in results:
            if len(results) >= 4:
                continue
            try:
                results[query] = search_photo(query, api_key)
            except HTTPError as error:
                print(f"Pexels: HTTP {error.code}", flush=True)
                break
            except (URLError, TimeoutError, ValueError) as error:
                print(f"Pexels: {type(error).__name__}", flush=True)
                break
        photo = results[query] or {"unavailable": True}
        story["pexelsPhoto"] = photo
        updated[story["url"]] = photo
    return updated
