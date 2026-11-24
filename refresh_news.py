import hashlib, json, re, urllib.request, urllib.parse, xml.etree.ElementTree as ET, os, time, unicodedata
from urllib.error import HTTPError
from datetime import datetime
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from html import unescape
from pathlib import Path
from zoneinfo import ZoneInfo

TZ=ZoneInfo("Europe/Budapest")
SUMMARY_VERSION="short-v2.1-3-4"
VIVID_STYLE_START=datetime(2026,11,24,17,0,tzinfo=TZ)
now=datetime.now(TZ)
dispatch_mode=os.getenv("NANONEWS_MODE","test" if os.getenv("GITHUB_EVENT_NAME")=="workflow_dispatch" else "").strip().lower()
manual=os.getenv("GITHUB_EVENT_NAME")=="workflow_dispatch" and dispatch_mode=="test"
force_issue=os.getenv("GITHUB_EVENT_NAME")=="workflow_dispatch" and dispatch_mode=="official"
force_backfill=os.getenv("GITHUB_EVENT_NAME")=="workflow_dispatch" and dispatch_mode in {"reito-backfill","style-refresh"}

feeds={
 "Telex":["https://telex.hu/rss"],
 "HVG":["https://hvg.hu/rss"],
 "Nemzeti Sport":["https://www.nemzetisport.hu/publicapi/hu/rss/nso/articles","https://www.nemzetisport.hu/static/rss_hirek.xml"],
 "NBAnews.hu":["https://nbanews.hu/feed/"],
 "Fűzővel kifelé!":["https://fuzovelkifele.com/feed/"],
 "444.hu":["https://444.hu/feed/"],
 "Portfolio.hu":["https://www.portfolio.hu/rss/all.xml"],
 "Origo.hu":["https://www.origo.hu/publicapi/hu/rss/origo/articles"],
}
rules={
 "arsenal":["arsenal"],"man-city":["manchester city","man city"],"bayern":["bayern münchen","bayern munchen","bayern"],
 "man-united":["manchester united","man united"],"como":["como "],
 "premier":["premier league","angol bajnokság","angol liga","premier ligában"],
 "champions-league":["bajnokok ligája","uefa champions league","champions league"],
 "f1":["formula-1","formula 1","forma-1","f1","fernando alonso","nagydíj","nagy díj"],
 "nba":["nba","kosárlabda"],
 "nfl":["nfl","national football league","amerikai foci","amerikai futball","touchdown","quarterback","wide receiver","running back","linebacker","super bowl","superbowl","new england patriots","buffalo bills","miami dolphins","new york jets","baltimore ravens","cincinnati bengals","cleveland browns","pittsburgh steelers","houston texans","indianapolis colts","jacksonville jaguars","tennessee titans","denver broncos","kansas city chiefs","las vegas raiders","los angeles chargers","dallas cowboys","new york giants","philadelphia eagles","washington commanders","chicago bears","detroit lions","green bay packers","minnesota vikings","atlanta falcons","carolina panthers","new orleans saints","tampa bay buccaneers","arizona cardinals","los angeles rams","san francisco 49ers","seattle seahawks"],
 "seahawks":["seattle seahawks","seahawks"],
 "cycling":["kerékpár","kerékpáros","cycling","tour de france","giro d’italia","vuelta"],
 "darts":["darts","pdc","professional darts corporation","darts-vb","darts vb","darts-világbajnokság"],
 "environment":["környezetvédelem","környezetvédelmi","klímaváltozás","klímavédelem","klímavédelmi","klíma","természetvédelem","természetvédelmi","védett természeti terület","inváziós faj","inváziós halfaj","biodiverzitás","ökoszisztéma","élőhely","erdőirtás","légszennyezés","szennyezés","károsanyag-kibocsátás","üvegházhatású gáz","megújuló energia","fenntarthatóság","aszály","hulladék","műanyag-szennyezés"],
 "films":["film","filmes","mozifilm","filmbemutató","filmfesztivál","filmrendező","filmstúdió","mozi","mozis","movie","cinema"],
 "technology":["találmány","feltaláló","új eszköz","új készülék","technológia","technológiai","kutatás","kutatási","kutató","tudomány","felfedezés","kísérlet","tanulmány","szoftver","szoftverfejlesztés","alkalmazás","digitális","digitalizáció","mesterséges intelligencia","chatgpt","kiberbiztonság","adatvédelem","robotika","robot","chip","processzor","okostelefon","laptop","készülék","startup","innováció","fejlesztés"],
 "property":["ingatlanpiac","ingatlanpiaci","ingatlanár","ingatlanárak","ingatlanfejlesztés","ingatlanfejlesztő","ingatlanbefektetés","lakáspiac","lakásár","lakásárak","lakásépítés","lakásvásárlás","lakáshitel","lakóingatlan","bérlakás","albérlet","négyzetméterár","irodapiac","irodaingatlan","ingatlanállomány","lakásállomány"],
 "tennis":["tenisz","teniszező","teniszbajnokság","teniszverseny","tenisztorna","atp","wta","grand slam","wimbledon","roland garros","us open","australian open","davis-kupa","billie jean king-kupa"],
 "parliament":["országgyűlés","parlament","képviselő","törvényjavaslat","frakció","orszaggyules"],
 "hu-market":["bux","budapesti értéktőzsde","magyar tőzsde","otp részvény","mol részvény","richter részvény","mtelekom részvény"],
 "world-market":["nasdaq","s&p 500","dow jones","wall street","stock market","nyse","dax","nikkei","amerikai tőzsde","külföldi tőzsde","részvénypiacokon"],

}

DOMESTIC_MARKERS=["magyarország","magyar","budapest","debrecen","szeged","miskolc","pécs","győr","hazai","ferencváros","ftc","fradi","puskás akadémia","újpest","dvtk","diósgyőr","honvéd","mtk","vasas","eto fc","győri eto","kecskemét","paksi fc","paks","nyíregyháza","zalaegerszeg","magyar válogatott","mlsz"]
ECONOMY_MARKERS=["gazdaság","gazdasági","forint","infláció","áfa","adó","költségvetés","gdp","bruttó hazai termék","államháztartás","munkanélküliség","foglalkoztatás","minimálbér","bérek","fizetés","nyugdíj","rezsi","árak","áremelés","árfolyam","lakáspiac","ingatlanpiac","hitel","kamat","kiskereskedelem","ipar","export","import","beruházás","vállalat","vállalkozás","cégek","profit","nyereség","árbevétel","üzemanyagár","energiaár","befektetés","csőd","fizetésképtelenség","bérmegállapodás","értékesítés","sportgazdaság","sportfinanszírozás","átigazolás","átigazolási díj","transzfer","játékoseladás","klubbevétel","bevétel","jegybevétel","szponzor","szponzoráció","közvetítési jog","tv-jog","bérköltség","adósság","tartozás","pénzügyi","stadion","sportlétesítmény"]
NER_MARKERS=["ner","nemzeti együttműködés rendszere","ner-es","ner-közeli","fidesz","orbán viktor","orbán-kormány","mészáros lőrinc","tiborcz istván","közpénz","közbeszerzés","kormányközeli"]
SPORT_MARKERS=["tenisz","teniszező","teniszbajnokság","teniszverseny","tenisztorna","atp","wta","grand slam","wimbledon","roland garros","davis-kupa","billie jean king-kupa","bajnokok ligája","uefa champions league","champions league","darts","pdc","arsenal","manchester city","manchester united","bayern münchen","premier league","foci","futball","labdarúg","kosárlabda","kézilabda","röplabda","nba","nfl","amerikai foci","touchdown","seattle seahawks","seahawks","kerékpár","kerékpáros","cycling","tour de france","giro d’italia","vuelta","formula 1","formula-1","forma-1","f1","mérkőzés","meccs","bajnoki","bajnokság","gól","csapat","edző","szurkoló","játékos","sport"]
SPORT_CATEGORIES={"arsenal","man-city","bayern","man-united","como","premier","champions-league","f1","nba","nfl","seahawks","cycling","darts","tennis"}

def is_domestic_economy(hay,categories):
    return any(term in hay for term in DOMESTIC_MARKERS) and any(term in hay for term in ECONOMY_MARKERS)

def is_sport_related(hay,categories):
    return bool(SPORT_CATEGORIES.intersection(categories)) or any(match_term(term,hay) for term in SPORT_MARKERS)

def is_domestic_sport_economy(hay,categories):
    return is_sport_related(hay,categories) and is_domestic_economy(hay,categories)

INTERNATIONAL_MARKERS=["egyesült államok","usa","amerikai","washington","donald trump","kína","kínai","peking","németország","német","franciaország","francia","olaszország","olasz","spanyolország","spanyol","ukrajna","ukrán","oroszország","orosz","izrael","izraeli","gáza","palesztin","irán","iran","japán","indiai","nagy-britannia","brit","london","törökország","török","lengyelország","lengyel","románia","román","szlovákia","szlovák","csehország","cseh","ausztria","osztrák","svájc","svájci","európai unió","európai bizottság","brüsszel","eurozóna","nasdaq","wall street","dax","fed","imf","világbank","nato","china","germany","france","ukraine","russia","united states","middle east"]
FOREIGN_POLITICAL_MARKERS=["politika","politikai","kormány","elnök","államfő","kormányfő","miniszterelnök","választás","elnökválasztás","parlament","törvény","párt","koalíció","diplomácia","szankció","háború","szenátus","kongresszus","képviselő","politikus"]
def is_foreign_political_economic(hay,categories):
    if is_sport_related(hay,categories):return False
    if any(match_term(term,hay) for term in DOMESTIC_MARKERS+NER_MARKERS):return False
    has_foreign_context=any(match_term(term,hay) for term in INTERNATIONAL_MARKERS)
    has_economic_context=any(match_term(term,hay) for term in ECONOMY_MARKERS)
    has_political_context=any(match_term(term,hay) for term in FOREIGN_POLITICAL_MARKERS)
    return has_foreign_context and (has_economic_context or has_political_context)

def text(node):
    if node is None:return ""
    return re.sub(r"\s+"," "," ".join(node.itertext())).strip()

def match_term(term,hay):
    if term.casefold() in ("nba","nfl","f1","ner"):
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

def edition_uses_vivid_styles(edition):
    issue_at=parse_published(edition.get("updatedAt"))
    return bool(issue_at and issue_at>=VIVID_STYLE_START)

SIMILAR_STOPWORDS={"abba","azok","azon","ahol","amely","amelyek","annak","arra","arról","azért","azt","azóta","azonban","csak","egy","egyik","ellen","elmondta","esetében","került","közölte","között","lehet","lett","majd","még","mint","minden","miatt","nagy","nem","szerint","számára","több","után","valamint","volt","van","vagy","végül","viszont","új"}
def story_tokens(value):
    value=unescape(re.sub(r"<[^>]*>"," ",str(value))).casefold()
    value="".join(char for char in unicodedata.normalize("NFKD",value) if not unicodedata.combining(char))
    return {token for token in re.findall(r"[a-z0-9]{4,}",value) if token not in SIMILAR_STOPWORDS}

def nvidia_event_story(story):
    value=unescape(re.sub(r"<[^>]*>"," ",str(story.get("title",""))+" "+str(story.get("summary","")))).casefold()
    value="".join(char for char in unicodedata.normalize("NFKD",value) if not unicodedata.combining(char))
    return "nvidia" in value and any(term in value for term in ("jensen","huang","vezerigazgato","visszavett","igazgatotanacs","kozbenjaras"))

def stories_are_similar(left,right,allow_same_source=False):
    if not left.get("source") or (not allow_same_source and left.get("source")==right.get("source")):return False
    if nvidia_event_story(left) and nvidia_event_story(right):return True
    left_title=story_tokens(left.get("title",""))
    right_title=story_tokens(right.get("title",""))
    shared_title=left_title&right_title
    left_tokens=story_tokens(left.get("title","")+" "+left.get("summary",""))
    right_tokens=story_tokens(right.get("title","")+" "+right.get("summary",""))
    shared=left_tokens&right_tokens
    union=left_tokens|right_tokens
    title_ratio=len(shared_title)/max(1,min(len(left_title),len(right_title)))
    overlap=len(shared)/max(1,len(union))
    return (len(shared_title)>=2 and title_ratio>=0.3) or (len(shared)>=5 and overlap>=0.12)

def group_similar_stories(items):
    pending=list(items);grouped=[]
    while pending:
        lead=pending.pop(0)
        matches=[item for item in pending if stories_are_similar(lead,item)]
        if not matches:
            grouped.append(lead);continue
        match_ids={id(item) for item in matches}
        pending=[item for item in pending if id(item) not in match_ids]
        lead["relatedStories"]=matches
        lead["categories"]=sorted(set(lead.get("categories",[])).union(*(set(item.get("categories",[])) for item in matches)))
        grouped.append(lead)
        print(f"Grouped {len(matches)} related stories under {lead.get('source')}: {lead.get('title')}")
    return grouped

def all_story_records(story):
    yield story
    for related in story.get("relatedStories",[]) or []:
        yield from all_story_records(related)

def attach_archived_stories(items,archive_records):
    candidates=sorted(archive_records,key=lambda pair:pair[0],reverse=True)
    for lead in items:
        current_group=[lead]+list(lead.get("relatedStories",[]) or [])
        related=lead.setdefault("relatedStories",[])
        known_urls={story_key(record.get("url","")) for record in current_group if record.get("url")}
        for archived_at,archived_story in candidates:
            key=story_key(archived_story.get("url",""))
            if not key or key in known_urls:continue
            if any(stories_are_similar(current,archived_story,allow_same_source=True) for current in current_group):
                item=dict(archived_story)
                item["archiveDate"]=archived_at.strftime("%Y. %m. %d.")
                item.pop("relatedStories",None)
                related.append(item)
                known_urls.add(key)
                print(f"Linked archive story from {item['archiveDate']}: {item.get('source')} · {item.get('title')}")
    return items

published_before=set()
archived_similarity_records={}
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
        edition_stories=edition_data.get("stories",[])
        published_before.update(story_key(record.get("url","")) for story in edition_stories for record in all_story_records(story) if record.get("url"))
        if file.parent.name=="archive" and issue_at:
            for grouped_story in edition_stories:
                for record in all_story_records(grouped_story):
                    url_key=story_key(record.get("url",""))
                    if not url_key:continue
                    previous_archive=archived_similarity_records.get(url_key)
                    if previous_archive is None or issue_at>previous_archive[0]:
                        archived_story=dict(record)
                        archived_story.pop("relatedStories",None)
                        archived_similarity_records[url_key]=(issue_at,archived_story)
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


def gemini_rewrites(story,article_text,api_key,vivid_styles=False):
    source_text=article_text or story["summary"]
    basis="a cikk nyilvánosan elérhető törzsszövege" if article_text else "az RSS-ben elérhető kivonat"
    tolkien_direction=("merészen epikus, gazdag képekben és erőteljes ritmusban, ősi krónikák emelkedettségével; használj emlékezetes, költői címet és bátrabb, kevésbé visszafogott szóképeket. A képek és hasonlatok maradjanak egyértelműen költőiek, ne állítsanak új tényt." if vivid_styles else "határozottan emelkedett, ünnepélyes, régies krónikás hangú, gazdagabb ritmussal és választékos szóhasználattal")
    reito_direction=("szabadjára engedett, csattanós kalandregényes hangon: száraz humorral, pimasz fordulatokkal, merész kontrasztokkal, váratlan, de tényekhez kötött szóképekkel és emlékezetes címmel. A humor és a képek legyenek bátrabbak, de ne állítsanak új tényt." if vivid_styles else "markánsan csattanós, száraz humorú, pörgős kalandregényes hangon")
    prompt=f"""Feladat: készíts három magyar nyelvű NANONews-változatot ugyanarról a hírről.
Csak a megadott forrás tényeit használd; ne adj hozzá következtetést, idézetet vagy kitalált részletet.
Mindhárom összefoglaló legyen tartalmas, 3–4 jól olvasható mondatban. Őrizd meg a cikk lényegi részleteit: ki érintett, mi történt, mi lett az eredmény vagy következmény, továbbá a forrásban szereplő fontos számokat, időpontokat és feltételeket. Ne hagyj ki olyan részletet, amely érdemben megváltoztatná a hír jelentését; ne találj ki tényt.
Az "original" mezőben írj semleges, pontos, közérthető összefoglalót 3–4 mondatban. Fogalmazd át önállóan, de ne hagyd el a hír lényeges részleteit.
A "tolkien" mezőhöz alkoss önálló címet és 3–4 mondatos, {tolkien_direction} átfogalmazást. A cím is ezt a hangot tükrözze. A tények és azok viszonyai maradjanak pontosak; ne adj hozzá fantasy-elemet, új tényt, szereplői szándékot vagy nem igazolt következtetést.
A "reito" mezőhöz alkoss önálló címet és 3–4 mondatos, {reito_direction} átfogalmazást. A humor kizárólag a forrásban szereplő tények szellemes egymás mellé állításából vagy megfogalmazásából eredjen. Ne találj ki jelenetet, párbeszédet, szereplői szándékot, reakciót, tanulságot vagy lezáró poént. Ez a hang legyen könnyed és földközeli, jól elkülönülve a Tolkien-féle emelkedettségtől. Ne idézz vagy másolj konkrét műrészletet, és ne változtass a tényeken.\nMindhárom változat legyen tényhű, és ne legyen egymás másolata. A válasz kizárólag JSON legyen:\n{{"original":{{"body":"..."}}, "tolkien":{{"title":"...","body":"..."}}, "reito":{{"title":"...","body":"..."}}}}
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
        original=" ".join(sentences[:4]).strip()
    original=concise_sentences(original,4)
    if original:variants["original"]={"body":original[:1400]}
    value=parsed.get("tolkien",{})
    title=re.sub(r"\s+"," ",str(value.get("title",""))).strip()
    body=concise_sentences(value.get("body",""),4)
    if not title or not body:raise ValueError("Missing Tolkien rewrite")
    variants["tolkien"]={"title":title[:180],"body":body[:1400]}
    value=parsed.get("reito",{})
    reito_title=re.sub(r"\s+"," ",str(value.get("title",""))).strip()
    reito_body=concise_sentences(value.get("body",""),4)
    if not reito_title or not reito_body:raise ValueError("Missing Rejto rewrite")
    variants["reito"]={"title":reito_title[:180],"body":reito_body[:1400]}
    return variants

def gemini_tolkien_rewrite(story,article_text,api_key,vivid_styles=False):
    source_text=article_text or story["summary"]
    basis="a cikk nyilvánosan elérhető törzsszövege" if article_text else "az RSS-ben elérhető kivonat"
    tolkien_direction=("merészen epikus, gazdag képekben és erőteljes ritmusban, ősi krónikák emelkedettségével; használj emlékezetes, költői címet és bátrabb, kevésbé visszafogott szóképeket. A képek és hasonlatok maradjanak egyértelműen költőiek, ne állítsanak új tényt." if vivid_styles else "emelkedett, ünnepélyes, régies krónikás hangú, választékos ritmusú")
    prompt=f"""Feladat: készíts kizárólag Tolkien hangulatú NANONews-változatot magyarul.
Csak a megadott forrás tényeit használd; ne adj hozzá következtetést, idézetet vagy kitalált részletet.
Adj új címet és 3–4 mondatos, {tolkien_direction} átfogalmazást; a ritmus különüljön el az Eredeti és a Rejtő-változattól. A cím is tükrözze ezt a hangot. Őrizd meg a cikk lényegi részleteit és minden ténykapcsolatot.
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
    body=concise_sentences(value.get("body",""),4)
    if not title or not body:raise ValueError("Missing Tolkien rewrite")
    return {"title":title[:180],"body":body[:1400]}
def gemini_reito_rewrite(story,article_text,api_key,vivid_styles=False):
    source_text=article_text or story["summary"]
    basis="a cikk nyilvánosan elérhető törzsszövege" if article_text else "az RSS-ben elérhető kivonat"
    reito_direction=("szabadjára engedett, csattanós kalandregényes hangon: száraz humorral, pimasz fordulatokkal, merész kontrasztokkal, váratlan, de tényekhez kötött szóképekkel és emlékezetes címmel. A humor és a képek legyenek bátrabbak, de ne állítsanak új tényt." if vivid_styles else "csattanós, száraz humorú, pörgős kalandregényes hangon")
    prompt=f"""Feladat: készíts kizárólag Rejtő hangulatú NANONews-változatot magyarul.
Csak a megadott forrás tényeit használd; ne adj hozzá következtetést, idézetet vagy kitalált részletet.
Adj új címet és 3–4 mondatos, {reito_direction} átfogalmazást. Az irónia kizárólag a forrásban szereplő tények szellemes egymás mellé állításából vagy megfogalmazásából eredjen. Ne találj ki jelenetet, párbeszédet, szereplői szándékot, reakciót, tanulságot vagy lezáró poént, és ne következtess a forrásban nem szereplő eredményre. Őrizd meg a cikk lényegi részleteit és tényeit.
Ne készíts Eredeti vagy Tolkien-változatot, ne idézz vagy másolj konkrét műrészletet, és ne adj hozzá új tényt.
A válasz kizárólag JSON legyen:
{{"reito":{{"title":"...","body":"..."}}}}
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
    value=parsed.get("reito",{})
    title=re.sub(r"\s+"," ",str(value.get("title",""))).strip()
    body=concise_sentences(value.get("body",""),4)
    if not title or not body:raise ValueError("Missing Rejto rewrite")
    return {"title":title[:180],"body":body[:1400]}
# Reuse generated rewrites for unchanged stories so the free API quota is spent only on new/updated links.
previous={}
previous_edition={}
pending_current=[]
current_archive_path=None
try:
    previous_edition=json.loads(Path("data/latest.json").read_text(encoding="utf-8"))
    previous={record.get("url"):record for story in previous_edition.get("stories",[]) for record in all_story_records(story) if record.get("url")}
    if not previous_edition.get("testEdition"):
        issue_at=parse_published(previous_edition.get("updatedAt"))
        if issue_at:
            current_archive_path=Path("data/archive")/f"{issue_at.strftime('%Y-%m-%d-%H%M')}.json"
        for grouped_story in previous_edition.get("stories",[]):
          for saved_story in all_story_records(grouped_story):
            tolkien=saved_story.get("variants",{}).get("tolkien",{})
            reito=saved_story.get("variants",{}).get("reito",{})
            if (saved_story.get("summaryVersion")!=SUMMARY_VERSION or
                not saved_story.get("variants",{}).get("original",{}).get("body") or
                not tolkien.get("title") or not tolkien.get("body") or
                not reito.get("title") or not reito.get("body")):
                pending_current.append(saved_story)
except Exception:pass
api_key=os.getenv("GEMINI_API_KEY","").strip()
stories=[]
scheduled_issue_number={6:1,17:2}.get(now.hour)
official_slot_available=scheduled_issue_number is not None and now.hour not in today_issued_hours and not force_backfill
if force_issue and not official_slot_available:
    raise SystemExit("Manual official issue can only be generated in an unused 06:00 or 17:00 Budapest slot.")
collect_new_edition=manual or force_issue or official_slot_available
# Keep items between issue runs, even when a source's RSS list rolls over.
inbox_path=Path("data/rss-pending.json")
try:
    inbox={story_key(record["link"]):record for record in json.loads(inbox_path.read_text(encoding="utf-8"))}
except FileNotFoundError:
    inbox={}

for key,record in list(inbox.items()):
    published=parse_published(record["published"])
    observed=parse_published(record["observed"])
    if key in published_before or (latest_official_at and (published or observed)<=latest_official_at):
        del inbox[key]

for source,urls in feeds.items():
    for url in urls:
        try:
            request=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 NANONews RSS reader"})
            with urllib.request.urlopen(request,timeout=20) as response:
                root=ET.fromstring(response.read())
            for item in root.findall(".//item"):
                link=text(item.find("link"))
                title=text(item.find("title"))
                if not link or not title:
                    continue
                key=story_key(link)
                published=text(item.find("pubDate"))
                published_at=parse_published(published)
                if key in published_before or (latest_official_at and published_at and published_at<=latest_official_at):
                    continue
                desc=text(item.find("description"))
                existing=inbox.get(key)
                inbox[key]={
                    "source":source,
                    "published":published,
                    "observed":existing["observed"] if existing else now.isoformat(),
                    "title":title,
                    "link":link,
                    "description":desc,
                    "image":image_for(item,desc),
                }
        except Exception as exc:
            print(f"Feed error {source} {url}: {exc}")

inbox_path.parent.mkdir(exist_ok=True)
inbox_path.write_text(json.dumps(list(inbox.values()),ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

for record in inbox.values() if collect_new_edition else ():
    source=record["source"]
    title=record["title"]
    link=record["link"]
    desc=record["description"]
    feed_published=record["published"]
    hay=(title+" "+desc+" "+link).casefold()
    cats=[key for key,terms in rules.items() if any(match_term(term,hay) for term in terms)]
    if source=="NBAnews.hu" and "nba" not in cats:cats.append("nba")
    if source=="Fűzővel kifelé!" and "nfl" not in cats:cats.append("nfl")
    if "technology" in cats and (SPORT_CATEGORIES.intersection(cats) or any(term in hay for term in SPORT_MARKERS)):
        cats.remove("technology")
    if (("parliament" in cats or is_domestic_economy(hay,cats) or any(match_term(term,hay) for term in NER_MARKERS)) and not is_sport_related(hay,cats)) or is_domestic_sport_economy(hay,cats):cats.append("belfold")
    if is_foreign_political_economic(hay,cats):cats.append("foreign")
    if not cats:continue
    story={"source":source,"title":title,"summary":concise_sentences(desc,3)[:500],"url":link,"published":feed_published,"categories":cats,"image":record["image"],"summaryVersion":SUMMARY_VERSION}
    article_text,article_published=fetch_article(link)
    if not story["published"] and article_published:story["published"]=article_published
    article_date=parse_published(story["published"])
    if article_date and article_date>now:continue
    if latest_official_at and (not article_date or article_date<=latest_official_at):
        print(f"Skipping story without a post-issue publication date: {link}")
        continue
    basis_text=article_text or story["summary"]
    story["contentBasis"]="article" if article_text else "rss"
    story["sourceHash"]=hashlib.sha256(basis_text.encode("utf-8")).hexdigest()
    cached=previous.get(link,{})
    if cached.get("summaryVersion")==SUMMARY_VERSION and cached.get("sourceHash")==story["sourceHash"] and cached.get("variants",{}).get("original",{}).get("body") and cached.get("variants",{}).get("tolkien",{}).get("body") and cached.get("variants",{}).get("reito",{}).get("body"):
        story["variants"]=cached["variants"]
    elif api_key:
        try:
            story["variants"]=gemini_rewrites(story,article_text,api_key,vivid_styles=now>=VIVID_STYLE_START)
        except Exception as exc:print(f"Rewrite unavailable {link}: {exc}")
        finally:
            time.sleep(4)
    stories.append(story)

pending_updated=False
if api_key and not manual and not collect_new_edition:
    for pending_story in pending_current[:3]:
        current_variants=pending_story.setdefault("variants",{})
        if pending_story.get("summaryVersion")!=SUMMARY_VERSION:
            article_text,_=fetch_article(pending_story.get("url",""))
            try:
                generated=gemini_rewrites(pending_story,article_text,api_key,vivid_styles=edition_uses_vivid_styles(previous_edition))
                pending_story["variants"]=generated
                pending_story["summaryVersion"]=SUMMARY_VERSION
                if article_text:
                    pending_story["contentBasis"]="article"
                    pending_story["sourceHash"]=hashlib.sha256(article_text.encode("utf-8")).hexdigest()
                pending_updated=True
                print(f"Refreshed v2 summary and styles for {pending_story.get('url')}")
            except Exception as exc:
                print(f"Pending v2 summary unavailable {pending_story.get('url')}: {exc}")
            time.sleep(4)
            continue
        current_tolkien=current_variants.setdefault("tolkien",{})
        current_reito=current_variants.setdefault("reito",{})
        article_text,_=fetch_article(pending_story.get("url",""))
        if not current_tolkien.get("title") or not current_tolkien.get("body"):
            try:
                generated=gemini_tolkien_rewrite(pending_story,article_text,api_key,vivid_styles=edition_uses_vivid_styles(previous_edition))
                if not current_tolkien.get("title"):current_tolkien["title"]=generated["title"]
                if not current_tolkien.get("body"):current_tolkien["body"]=generated["body"]
                pending_updated=True
                print(f"Completed missing Tolkien rewrite for {pending_story.get('url')}")
            except Exception as exc:print(f"Pending Tolkien rewrite unavailable {pending_story.get('url')}: {exc}")
            time.sleep(4)
        if not current_reito.get("title") or not current_reito.get("body"):
            try:
                generated=gemini_reito_rewrite(pending_story,article_text,api_key,vivid_styles=edition_uses_vivid_styles(previous_edition))
                if not current_reito.get("title"):current_reito["title"]=generated["title"]
                if not current_reito.get("body"):current_reito["body"]=generated["body"]
                pending_updated=True
                print(f"Completed missing Rejto rewrite for {pending_story.get('url')}")
            except Exception as exc:print(f"Pending Rejto rewrite unavailable {pending_story.get('url')}: {exc}")
            time.sleep(4)
        if current_tolkien.get("title") and current_tolkien.get("body") and current_reito.get("title") and current_reito.get("body"):
            if current_variants.get("original",{}).get("body"):
                pending_story["summaryVersion"]=SUMMARY_VERSION
            if article_text:
                pending_story["contentBasis"]="article"
                pending_story["sourceHash"]=hashlib.sha256(article_text.encode("utf-8")).hexdigest()


def sync_pending_archive():
    if not pending_updated or not current_archive_path or not current_archive_path.exists():return
    try:
        archived=json.loads(current_archive_path.read_text(encoding="utf-8"))
        archived_by_url={record.get("url"):record for item in archived.get("stories",[]) for record in all_story_records(item) if record.get("url")}
        for pending_story in pending_current:
            variants=pending_story.get("variants",{})
            tolkien=variants.get("tolkien",{})
            reito=variants.get("reito",{})
            if not variants:continue
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
        print("No new stories or missing Tolkien/Rejto rewrites; leaving the current edition and archive unchanged.")
        raise SystemExit(0)
    if force_issue or official_slot_available:
        print("No new matching stories; publishing the official issue with an empty story list.")
    Path("data/latest.json").write_text(json.dumps(previous_edition,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    sync_pending_archive()
    print(f"Completed missing style rewrites in the current issue; {len(pending_current)} stories were checked.")
    raise SystemExit(0)
sync_pending_archive()
stories.sort(key=lambda s:s["published"],reverse=True)
stories=group_similar_stories(stories)
stories=attach_archived_stories(stories,archived_similarity_records.values())
issue_number=None if manual else scheduled_issue_number
edition={"updatedAt":now.isoformat(),"testEdition":manual,"issueNumber":issue_number,"stories":stories}
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
