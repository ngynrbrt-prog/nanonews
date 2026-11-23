import hashlib, json, re, urllib.request, urllib.parse, xml.etree.ElementTree as ET, os, time
from urllib.error import HTTPError
from datetime import datetime
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from zoneinfo import ZoneInfo

TZ=ZoneInfo("Europe/Budapest")
SUMMARY_VERSION="short-v1-2-3"
now=datetime.now(TZ)
dispatch_mode=os.getenv("NANONEWS_MODE","test" if os.getenv("GITHUB_EVENT_NAME")=="workflow_dispatch" else "").strip().lower()
manual=os.getenv("GITHUB_EVENT_NAME")=="workflow_dispatch" and dispatch_mode!="official"
force_issue=os.getenv("GITHUB_EVENT_NAME")=="workflow_dispatch" and dispatch_mode=="official"

feeds={
 "Telex":["https://telex.hu/rss"],
 "HVG":["https://hvg.hu/rss"],
 "Nemzeti Sport":["https://www.nemzetisport.hu/publicapi/hu/rss/nso/articles","https://www.nemzetisport.hu/static/rss_hirek.xml"],
 "NBAnews.hu":["https://nbanews.hu/feed/"],
 "Fűzővel kifelé!":["https://fuzovelkifele.com/feed/"],
}
rules={
 "arsenal":["arsenal"],"man-city":["manchester city","man city"],"bayern":["bayern münchen","bayern munchen","bayern"],
 "man-united":["manchester united","man united"],"como":["como "],
 "premier":["premier league","angol bajnokság","angol liga","premier ligában"],
 "f1":["formula-1","formula 1","forma-1","f1","fernando alonso","nagydíj","nagy díj"],
 "nba":["nba","kosárlabda"],
 "nfl":["nfl","amerikai foci","touchdown"],
 "seahawks":["seattle seahawks","seahawks"],
 "cycling":["kerékpár","kerékpáros","cycling","tour de france","giro d’italia","vuelta"],
 "technology":["találmány","feltaláló","új eszköz","új készülék","technológia","technológiai","kutatás","kutatási","kutató","tudomány","felfedezés","kísérlet","tanulmány","szoftver","szoftverfejlesztés","alkalmazás","digitális","digitalizáció","mesterséges intelligencia","chatgpt","kiberbiztonság","adatvédelem","robotika","robot","chip","processzor","okostelefon","laptop","készülék","startup","innováció","fejlesztés"],
 "parliament":["országgyűlés","parlament","képviselő","törvényjavaslat","frakció","orszaggyules"],
 "hu-market":["bux","budapesti értéktőzsde","magyar tőzsde","otp részvény","mol részvény","richter részvény","mtelekom részvény"],
 "world-market":["nasdaq","s&p 500","dow jones","wall street","stock market","nyse","dax","nikkei","amerikai tőzsde","külföldi tőzsde","részvénypiacokon"],

}

DOMESTIC_MARKERS=["magyarország","magyar","budapest","debrecen","szeged","miskolc","pécs","győr","hazai"]
ECONOMY_MARKERS=["gazdaság","gazdasági","forint","infláció","áfa","adó","költségvetés","gdp","bruttó hazai termék","államháztartás","munkanélküliség","foglalkoztatás","minimálbér","bérek","fizetés","nyugdíj","rezsi","árak","áremelés","árfolyam","lakáspiac","ingatlanpiac","hitel","kamat","kiskereskedelem","ipar","export","import","beruházás","vállalat","vállalkozás","cégek","profit","nyereség","árbevétel","üzemanyagár","energiaár","befektetés","csőd","fizetésképtelenség","bérmegállapodás","értékesítés"]
SPORT_MARKERS=["arsenal","manchester city","manchester united","bayern münchen","premier league","foci","futball","labdarúg","kosárlabda","kézilabda","röplabda","nba","nfl","amerikai foci","touchdown","seattle seahawks","seahawks","kerékpár","kerékpáros","cycling","tour de france","giro d’italia","vuelta","formula 1","formula-1","forma-1","f1","mérkőzés","meccs","bajnoki","bajnokság","gól","csapat","edző","szurkoló","játékos","sport"]
SPORT_CATEGORIES={"arsenal","man-city","bayern","man-united","como","premier","f1","nba","nfl","seahawks","cycling"}

def is_domestic_economy(hay,categories):
    if SPORT_CATEGORIES.intersection(categories) or any(term in hay for term in SPORT_MARKERS):
        return False
    return any(term in hay for term in DOMESTIC_MARKERS) and any(term in hay for term in ECONOMY_MARKERS)

def text(node):
    if node is None:return ""
    return re.sub(r"\s+"," "," ".join(node.itertext())).strip()

def match_term(term,hay):
    if term.casefold() in ("nba","f1"):
        return bool(re.search(r"(?<![a-z0-9])"+re.escape(term.casefold())+r"(?![a-z0-9])",hay))
    return term.casefold() in hay

def image_for(item,desc):
    for node in item.iter():
        tag=node.tag.lower()
        if tag.endswith("thumbnail") or tag.endswith("content") or tag.endswith("enclosure"):
            url=node.attrib.get("url","")
            if url.startswith("http") and any(x in url.lower() for x in (".jpg",".jpeg",".png",".webp","image")):
                return url
    return ""

class ArticleTextParser(HTMLParser):
    blocked={"script","style","nav","footer","aside","noscript","svg","form"}
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip=0; self.article=0; self.scope_tags=[]
        self.capture=False; self.paragraph=[]; self.preferred=[]; self.fallback=[]
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs); classes=(attrs.get("class","")+" "+attrs.get("id","")).casefold()
        if tag in self.blocked:
            self.skip+=1; return
        if self.skip:return
        if tag=="article": self.article+=1
        if any(word in classes for word in ("article-body","article-content","story-body","story-content","post-content","content-body")):
            self.scope_tags.append(tag)
        if tag=="p":
            self.capture=True; self.paragraph=[]
            self.prefer_current=self.article>0 or bool(self.scope_tags)
    def handle_data(self,data):
        if self.capture and not self.skip:
            value=re.sub(r"\s+"," ",data).strip()
            if value:self.paragraph.append(value)
    def handle_endtag(self,tag):
        if tag in self.blocked:
            if self.skip:self.skip-=1
            return
        if self.skip:return
        if tag in self.scope_tags:self.scope_tags.remove(tag)
        if tag=="p" and self.capture:
            value=" ".join(self.paragraph).strip()
            if len(value)>35:
                self.fallback.append(value)
                if self.prefer_current:self.preferred.append(value)
            self.capture=False;self.paragraph=[]
        elif tag=="article" and self.article:self.article-=1

def story_key(url):
    parts=urllib.parse.urlsplit(url)
    return (parts.netloc.lower(),parts.path.rstrip("/"))

def parse_published(value):
    if not value:return None
    try:
        parsed=datetime.fromisoformat(str(value).strip().replace("Z","+00:00"))
    except Exception:
        try:parsed=parsedate_to_datetime(str(value).strip())
        except Exception:return None
    if parsed.tzinfo is None:parsed=parsed.replace(tzinfo=TZ)
    return parsed.astimezone(TZ)

published_before=set()
latest_official_at=None
today_issue_count=0
today_issued_hours=set()
counted_editions=set()
issue_files=list(Path("data/archive").glob("*.json"))+[Path("data/latest.json")]
for file in issue_files:
    if file.name=="index.json" or not file.exists():continue
    try:
        edition_data=json.loads(file.read_text(encoding="utf-8"))
        if edition_data.get("testEdition"):continue
        issue_at=parse_published(edition_data.get("updatedAt"))
        if issue_at and (latest_official_at is None or issue_at>latest_official_at):latest_official_at=issue_at
        issue_id=edition_data.get("updatedAt") or file.name
        if issue_at and issue_at.date()==now.date() and issue_id not in counted_editions:
            today_issue_count+=1
            counted_editions.add(issue_id)
            today_issued_hours.add(issue_at.hour)
        published_before.update(story_key(s.get("url","")) for s in edition_data.get("stories",[]) if s.get("url"))
    except Exception:pass

class ArticleMetadataParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.published=""
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        key=(attrs.get("property") or attrs.get("name") or "").casefold()
        value=attrs.get("content","")
        if key in ("article:published_time","datepublished","datepublishedtime","date","pubdate","parsely-pub-date") and value and not self.published:self.published=value
        if tag=="time" and attrs.get("datetime") and not self.published:self.published=attrs["datetime"]

def fetch_article(url):
    try:
        req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 (compatible; NANONews/1.0; +https://ngynrbrt-prog.github.io/nanonews/)","Accept":"text/html"})
        with urllib.request.urlopen(req,timeout=18) as response:
            raw=response.read(2_000_000)
            charset=response.headers.get_content_charset() or "utf-8"
        page=raw.decode(charset,errors="replace")
        meta=ArticleMetadataParser();meta.feed(page)
        if not meta.published:
            match=re.search(r'"datePublished"\s*:\s*"([^"]+)"',page,re.I)
            if match:meta.published=match.group(1)
        parser=ArticleTextParser();parser.feed(page)
        paras=parser.preferred if parser.preferred else parser.fallback
        body="\n\n".join(paras)
        body=re.sub(r"\s+"," ",body).strip()
        return (body[:18000] if len(body)>250 else "",meta.published)
    except Exception as exc:
        print(f"Article fetch unavailable {url}: {exc}")
        return "",""

def concise_sentences(value,limit=3):
    value=re.sub(r"\s+"," ",str(value)).strip()
    abbreviations=("pl.","dr.","stb.","kb.","u.","sz.","Mr.","Mrs.","Prof.","etc.")
    for index,abbr in enumerate(abbreviations):
        value=re.sub(re.escape(abbr),lambda match:match.group(0).replace(".",f"§{index}§"),value,flags=re.I)
    sentences=re.split(r"(?<=[.!?])\s+",value)
    value=" ".join(sentence.strip() for sentence in sentences[:limit] if sentence.strip())
    for index,abbr in enumerate(abbreviations):
        value=value.replace(f"§{index}§",".")
    return value.strip()


def gemini_rewrites(story,article_text,api_key):
    source_text=article_text or story["summary"]
    basis="a cikk nyilvánosan elérhető törzsszövege" if article_text else "az RSS-ben elérhető kivonat"
    prompt=f"""Feladat: készíts két magyar nyelvű NANONews-változatot ugyanarról a hírről.
Csak a megadott forrás tényeit használd; ne adj hozzá következtetést, idézetet vagy kitalált részletet.
Mindkét összefoglaló legyen rövid és lényegretörő: 2–3 rövid mondatban foglald össze a hírt, csak a legfontosabb tényekkel.
Az "original" mezőbe írj semleges, tárgyilagos, közérthető összefoglalót 2–3 rövid mondatban. Ne készíts hosszú cikket és ne másold a forrást mondatról mondatra.
A "tolkien" mezőbe írj új, önálló címet és 2–3 rövid mondatos összefoglalót. A cím és a szöveg idézze Tolkien magasztos, régies-krónikás hangját, de maradjon közérthető. Ne adj hozzá fantasy-elemet vagy új tényt.
A két összefoglaló tartalma legyen tényhű, és ne legyen egymás másolata. A válasz kizárólag JSON legyen:
{{"original":{{"body":"..."}}, "tolkien":{{"title":"...","body":"..."}}}}
Forrás: {story["source"]}
Eredeti cím: {story["title"]}
Alapanyag ({basis}):
{source_text[:18000]}"""
    payload=json.dumps({"model":"gemini-3.5-flash-lite","input":prompt,"store":False}).encode()
    request=urllib.request.Request("https://generativelanguage.googleapis.com/v1beta/interactions",data=payload,headers={"Content-Type":"application/json","x-goog-api-key":api_key},method="POST")
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request,timeout=50) as response:
                result=json.loads(response.read().decode("utf-8"))
            break
        except HTTPError as exc:
            if exc.code!=503 or attempt==2:raise
            delay=2**attempt
            print(f"Gemini temporarily unavailable (503); retrying in {delay}s.")
            time.sleep(delay)
    raw=result.get("output_text","")
    if not raw:
        parts=[]
        interaction=result.get("interaction",result)
        for step in interaction.get("steps",[]):
            if step.get("type")=="model_output":
                for block in step.get("content",[]):
                    if block.get("type")=="text":parts.append(block.get("text",""))
        raw="\n".join(parts)
    raw=re.sub(r"^\s*```(?:json)?|\s*```\s*$","",raw.strip(),flags=re.I)
    parsed=json.loads(raw)
    variants={}
    original=re.sub(r"\s+"," ",str(parsed.get("original",{}).get("body",""))).strip()
    if not original:
        source=re.sub(r"<[^>]*>"," ",source_text)
        sentences=re.split(r"(?<=[.!?])\s+",re.sub(r"\s+"," ",source).strip())
        original=" ".join(sentences[:3]).strip()
    original=concise_sentences(original,3)
    if original:variants["original"]={"body":original[:900]}
    value=parsed.get("tolkien",{})
    title=re.sub(r"\s+"," ",str(value.get("title",""))).strip()
    body=concise_sentences(value.get("body",""),3)
    if not title or not body:raise ValueError("Missing Tolkien rewrite")
    variants["tolkien"]={"title":title[:180],"body":body[:900]}
    return variants

def gemini_tolkien_rewrite(story,article_text,api_key):
    source_text=article_text or story["summary"]
    basis="a cikk nyilvánosan elérhető törzsszövege" if article_text else "az RSS-ben elérhető kivonat"
    prompt=f"""Feladat: készíts kizárólag Tolkien hangulatú NANONews-változatot magyarul.
Csak a megadott forrás tényeit használd; ne adj hozzá következtetést, idézetet vagy kitalált részletet.
Adj új, önálló, Tolkien magasztos, régies-krónikás hangját idéző, de közérthető címet és 2–3 rövid mondatos összefoglalót.
Ne készíts Eredeti változatot, és ne adj hozzá fantasy-elemet vagy új tényt.
A válasz kizárólag JSON legyen:
{{"tolkien":{{"title":"...","body":"..."}}}}
Forrás: {story["source"]}
Eredeti cím: {story["title"]}
Alapanyag ({basis}):
{source_text[:18000]}"""
    payload=json.dumps({"model":"gemini-3.5-flash-lite","input":prompt,"store":False}).encode()
    request=urllib.request.Request("https://generativelanguage.googleapis.com/v1beta/interactions",data=payload,headers={"Content-Type":"application/json","x-goog-api-key":api_key},method="POST")
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request,timeout=50) as response:
                result=json.loads(response.read().decode("utf-8"))
            break
        except HTTPError as exc:
            if exc.code!=503 or attempt==2:raise
            delay=2**attempt
            print(f"Gemini temporarily unavailable (503); retrying in {delay}s.")
            time.sleep(delay)
    raw=result.get("output_text","")
    if not raw:
        parts=[]
        interaction=result.get("interaction",result)
        for step in interaction.get("steps",[]):
            if step.get("type")=="model_output":
                for block in step.get("content",[]):
                    if block.get("type")=="text":parts.append(block.get("text",""))
        raw="\n".join(parts)
    raw=re.sub(r"^\s*```(?:json)?|\s*```\s*$","",raw.strip(),flags=re.I)
    parsed=json.loads(raw)
    value=parsed.get("tolkien",{})
    title=re.sub(r"\s+"," ",str(value.get("title",""))).strip()
    body=concise_sentences(value.get("body",""),3)
    if not title or not body:raise ValueError("Missing Tolkien rewrite")
    return {"title":title[:180],"body":body[:900]}
# Reuse generated rewrites for unchanged stories so the free API quota is spent only on new/updated links.
previous={}
previous_edition={}
pending_current=[]
current_archive_path=None
try:
    previous_edition=json.loads(Path("data/latest.json").read_text(encoding="utf-8"))
    previous={s.get("url"):s for s in previous_edition.get("stories",[]) if s.get("url")}
    if not previous_edition.get("testEdition"):
        issue_at=parse_published(previous_edition.get("updatedAt"))
        if issue_at:
            current_archive_path=Path("data/archive")/f"{issue_at.strftime('%Y-%m-%d-%H%M')}.json"
        for saved_story in previous_edition.get("stories",[]):
            tolkien=saved_story.get("variants",{}).get("tolkien",{})
            if not tolkien.get("title") or not tolkien.get("body"):
                pending_current.append(saved_story)
except Exception:pass
api_key=os.getenv("GEMINI_API_KEY","").strip()
stories=[];seen=set()
scheduled_issue_number={6:1,17:2}.get(now.hour)
official_slot_available=scheduled_issue_number is not None and now.hour not in today_issued_hours
if force_issue and not official_slot_available:
    raise SystemExit("Manual official issue can only be generated in an unused 06:00 or 17:00 Budapest slot.")
collect_new_edition=manual or force_issue or official_slot_available
for source,urls in feeds.items():
 if not collect_new_edition:break
 for url in urls:
    try:
        req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 NANONews RSS reader"})
        root=ET.fromstring(urllib.request.urlopen(req,timeout=20).read())
        feed_items=root.findall(".//item")
        for item in feed_items:
            title=text(item.find("title"));link=text(item.find("link"));desc=text(item.find("description"))
            if not title or not link:continue
            key=story_key(link)
            if key in seen or key in published_before:continue
            feed_published=text(item.find("pubDate"))
            feed_date=parse_published(feed_published)
            if latest_official_at and feed_date and feed_date<=latest_official_at:continue
            hay=(title+" "+desc+" "+link).casefold()
            cats=[key for key,terms in rules.items() if any(match_term(term,hay) for term in terms)]
            if source=="Fűzővel kifelé!" and "nfl" not in cats:cats.append("nfl")
            if "technology" in cats and (SPORT_CATEGORIES.intersection(cats) or any(term in hay for term in SPORT_MARKERS)):
                cats.remove("technology")
            if is_domestic_economy(hay,cats):cats.append("domestic")
            if not cats:continue
            seen.add(key)
            story={"source":source,"title":title,"summary":concise_sentences(desc,3)[:500],"url":link,"published":feed_published,"categories":cats,"image":image_for(item,desc),"summaryVersion":SUMMARY_VERSION}
            article_text,article_published=fetch_article(link)
            if not story["published"] and article_published:story["published"]=article_published
            article_date=parse_published(story["published"])
            if latest_official_at and (not article_date or article_date<=latest_official_at):
                print(f"Skipping story without a post-issue publication date: {link}")
                continue
            basis_text=article_text or story["summary"]
            story["contentBasis"]="article" if article_text else "rss"
            story["sourceHash"]=hashlib.sha256(basis_text.encode("utf-8")).hexdigest()
            cached=previous.get(link,{})
            if cached.get("summaryVersion")==SUMMARY_VERSION and cached.get("sourceHash")==story["sourceHash"] and cached.get("variants",{}).get("original",{}).get("body") and cached.get("variants",{}).get("tolkien",{}).get("body"):
                story["variants"]=cached["variants"]
            elif api_key:
                try:
                    story["variants"]=gemini_rewrites(story,article_text,api_key)
                except Exception as exc:print(f"Rewrite unavailable {link}: {exc}")
                finally:
                    time.sleep(4)
            stories.append(story)
    except Exception as e: print(f"Feed error {source} {url}: {e}")

pending_updated=False
if api_key and not manual and not collect_new_edition:
    for pending_story in pending_current:
        current_variants=pending_story.setdefault("variants",{})
        current_tolkien=current_variants.setdefault("tolkien",{})
        if current_tolkien.get("title") and current_tolkien.get("body"):continue
        article_text,_=fetch_article(pending_story.get("url",""))
        try:
            generated=gemini_tolkien_rewrite(pending_story,article_text,api_key)
            if not current_tolkien.get("title"):current_tolkien["title"]=generated["title"]
            if not current_tolkien.get("body"):current_tolkien["body"]=generated["body"]
            if current_tolkien.get("title") and current_tolkien.get("body"):
                if current_variants.get("original",{}).get("body"):
                    pending_story["summaryVersion"]=SUMMARY_VERSION
                if article_text:
                    pending_story["contentBasis"]="article"
                    pending_story["sourceHash"]=hashlib.sha256(article_text.encode("utf-8")).hexdigest()
                pending_updated=True
                print(f"Completed missing Tolkien rewrite for {pending_story.get('url')}")
            else:
                print(f"Tolkien rewrite still incomplete for {pending_story.get('url')}")
        except Exception as exc:
            print(f"Pending Tolkien rewrite unavailable {pending_story.get('url')}: {exc}")
        finally:
            time.sleep(4)

def sync_pending_archive():
    if not pending_updated or not current_archive_path or not current_archive_path.exists():return
    try:
        archived=json.loads(current_archive_path.read_text(encoding="utf-8"))
        archived_by_url={item.get("url"):item for item in archived.get("stories",[]) if item.get("url")}
        for pending_story in pending_current:
            tolkien=pending_story.get("variants",{}).get("tolkien",{})
            if not tolkien.get("title") or not tolkien.get("body"):continue
            target=archived_by_url.get(pending_story.get("url"))
            if target:
                target["variants"]=pending_story["variants"]
                target["summaryVersion"]=pending_story.get("summaryVersion",SUMMARY_VERSION)
                if pending_story.get("contentBasis"):target["contentBasis"]=pending_story["contentBasis"]
                if pending_story.get("sourceHash"):target["sourceHash"]=pending_story["sourceHash"]
        current_archive_path.write_text(json.dumps(archived,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    except Exception as exc:print(f"Could not sync pending summaries to current issue archive: {exc}")

if not stories:
    if not pending_updated and not (force_issue or official_slot_available):
        print("No new stories or missing Tolkien rewrites; leaving the current edition and archive unchanged.")
        raise SystemExit(0)
    if force_issue or official_slot_available:
        print("No new matching stories; publishing the official issue with an empty story list.")
    Path("data/latest.json").write_text(json.dumps(previous_edition,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    sync_pending_archive()
    print(f"Completed missing Tolkien rewrites in the current issue; {len(pending_current)} stories were checked.")
    raise SystemExit(0)
sync_pending_archive()
stories.sort(key=lambda s:s["published"],reverse=True)
issue_number=None if manual else scheduled_issue_number
edition={"updatedAt":now.isoformat(),"testEdition":manual,"issueNumber":issue_number,"stories":stories[:80]}
Path("data").mkdir(exist_ok=True)
Path("data/latest.json").write_text(json.dumps(edition,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
archive=Path("data/archive");archive.mkdir(exist_ok=True)
stamp=now.strftime("%Y-%m-%d-%H%M")
(archive/f"{stamp}.json").write_text(json.dumps(edition,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
items=[]
for file in archive.glob("*.json"):
    if file.name=="index.json": continue
    try:
        d=json.loads(file.read_text(encoding="utf-8"))
        items.append({"file":file.name,"updatedAt":d.get("updatedAt"),"count":len(d.get("stories",[])),"testEdition":d.get("testEdition",False),"issueNumber":d.get("issueNumber")})
    except Exception: pass
items.sort(key=lambda item: item.get("updatedAt") or "", reverse=True)
(archive/"index.json").write_text(json.dumps({"editions":items},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(f"Saved {len(edition['stories'])} stories, {sum(bool(s['image']) for s in edition['stories'])} images at {edition['updatedAt']}; rewrites {sum(bool(s.get('variants')) for s in edition['stories'])}")
