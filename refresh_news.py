import subprocess
import hashlib, json, re, urllib.request, urllib.parse, xml.etree.ElementTree as ET, os, time, unicodedata
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from urllib.error import HTTPError
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from html import unescape
from pathlib import Path
from zoneinfo import ZoneInfo

TZ=ZoneInfo("Europe/Budapest")
ISSUE_HOURS={5:1,16:2}
SUMMARY_VERSION="short-v2.1-3-4"
VIVID_STYLE_START=datetime(2026,11,24,17,0,tzinfo=TZ)
now=datetime.now(TZ)
dispatch_mode=os.getenv("NANONEWS_MODE","test" if os.getenv("GITHUB_EVENT_NAME")=="workflow_dispatch" else "").strip().lower()
manual=os.getenv("GITHUB_EVENT_NAME")=="workflow_dispatch" and dispatch_mode=="test"
publish_only=dispatch_mode=="official"
collect_only=dispatch_mode=="collect"
background=dispatch_mode=="background"
work_deadline=time.monotonic()+150
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
 "Mafab":["https://www.mafab.hu/rss"],
 "A Hetedik Sor Közepe":["https://hetediksor.hu/feed/"],
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

WINTER_WEATHER_HEADLINE = re.compile(
    r"\b(?:havaz\w*|ónos eső|hótérkép|havas\s*eső|hózápor\w*|hószállingóz\w*)", re.I,
)


def is_nature_story(title):
    return bool(WINTER_WEATHER_HEADLINE.search(title) or re.search(
        r"\b(?:élővilág|vadon élő|vadállat|vadmadár|madárvonulás|madárfaj|halfaj|állatfaj|növényfaj|fajmegőrzés|fészkel|beporzó|nemzeti park|természeti jelenség|természeti érték|természetvéd|ökoszisztéma|biodiverzitás|élőhely|erdőirtás|erdőtűz|esőerdő|vizes élőhely|gleccser|vízállás|vízgazdálkodás|vízügyi|vízhiány|vízminőség|árvíz|aszály|havazás|ónos eső|hőhullám|vulkánkitörés|földrengés|égi együttállás|hullócsillag|meteorraj|sarki fény|napfogyatkozás|holdfogyatkozás)",
        title,
        re.IGNORECASE,
    ))


DOMESTIC_ISSUER = re.compile(r"\b(?:otp|mol|richter|magyar telekom|mtelekom)\b", re.I)
MARKET_CONTEXT = re.compile(r"részvény|árfolyam|tőzsd|medvepiac|bikapiac", re.I)
PRICE_MOVE = r"(?:esik|esés\w*|esett|zuhan\w*|emelked\w*|erősöd\w*|gyengül\w*|drágul\w*|olcsóbbod\w*|raliz\w*)"
ISSUER_MOVE = re.compile(
    rf"\b{PRICE_MOVE}\s+(?:az?\s+)?{DOMESTIC_ISSUER.pattern}|"
    rf"{DOMESTIC_ISSUER.pattern}\s+{PRICE_MOVE}\b",
    re.I,
)


def is_domestic_market_story(title, summary):
    return bool(DOMESTIC_ISSUER.search(title) and (
        MARKET_CONTEXT.search(title + " " + summary) or ISSUER_MOVE.search(title)
    ))


FILM_TERMS = re.compile(r"\b(?:(?:mozi|dokumentum|játék|rajz|animációs|rövid|néma|tévé|nagyjáték|kis|mese)?film(?:es|et|ek(?:et|ben|hez|ről|nek|kel|ből)?|ben|ből|hez|nek|ről|re|ért|je|jét|jének|jével|jéről|jében|jei|jeit|ünk|ünkben|gyártás[^\W\d_]*|bemutató[^\W\d_]*|fesztivál[^\W\d_]*|rendező[^\W\d_]*|stúdió[^\W\d_]*|kritik[^\W\d_]*|ipar[^\W\d_]*|színház[^\W\d_]*|szerep[^\W\d_]*|világ[^\W\d_]*)?|mozi(?:s|t|k(?:at|ban)?|ba|ban|ból|hoz|nak|ról|val|zás[^\W\d_]*|zik|műsor[^\W\d_]*|premier[^\W\d_]*)?|movies?|cinemas?)\b", re.I)

def is_film_story(title, summary):
    text = unescape(re.sub(r"<[^>]*>", " ", title + " " + summary))
    return bool(FILM_TERMS.search(unicodedata.normalize("NFC", text)))

TENNIS_TERMS = re.compile(
    r"\b(?:tenisz\w*|atp|wta|grand[ -]slam|wimbledon\w*|roland[ -]garros\w*|"
    r"us open\w*|australian open\w*|davis[ -]kupa\w*|billie jean king[ -]kupa\w*)\b", re.I,
)

def is_tennis_story(title, summary):
    context = unescape(re.sub(r"<[^>]*>", " ", title + " " + summary))
    return bool(TENNIS_TERMS.search(unicodedata.normalize("NFC", context)))

def apply_subject_categories(title, summary, categories):
    categories = [category for category in categories if category not in {"films", "tennis"}]
    if is_tennis_story(title, summary):
        categories.append("tennis")
    if is_film_story(title, summary):
        categories.append("films")
    if is_nature_story(title):
        return ["environment"]
    if is_domestic_market_story(title, summary) and "hu-market" not in categories:
        return [*categories, "hu-market"]
    return categories


def match_term(term,hay):
    if term.casefold() in ("atp", "wta"):
        return bool(re.search(r"\b" + term.casefold() + r"\b", hay))
    if term.casefold() in ("nba","nfl","f1","ner"):
        return bool(re.search(r"(?<![a-z0-9])"+re.escape(term.casefold())+r"(?![a-z0-9])",hay))
    return term.casefold() in hay


def football_overrides(title, description, url):
    arsenal = bool(re.search(r"\barsenal\b", title, re.I) or re.search(
        r"(?:\bfogadja\s+az arsenal\b|\baz arsenal\s+(?:fogadja|utazik|játszik|lép pályára|mérkőzik))",
        description, re.I,
    ))
    football = bool(re.search(
        r"labdarúg|labdarugas|foci|futball|szabadrúgás|mérkőzés|bajnoki|gól|arsenal|donnarumma|napoli|manchester",
        " ".join((title, description, url)), re.I,
    ))
    article_text = title + " " + description
    ranking = urllib.parse.urlsplit(url).path.rstrip("/").endswith("/seruleshullam-az-ellovasoknal-a-como-a-legjobb-tizben-az-ns-bl-erosorrendjeben")
    return {
        "arsenal": arsenal or ranking,
        "bayern": ranking,
        "como": ranking,
        "champions-league": "/bajnokok-ligaja/" in url.lower() or (football and bool(re.search(r"\bBL\b", article_text))),
        "premier": "/premier-league/" in url.lower() or (football and bool(re.search(r"\bPL\b", article_text))),
    }

def is_technology_story(title, summary):
    context = title + " " + summary
    return (
        not re.search(r"fidesz|orbán|álcivil|házkutatás|hűtlen kezelés|nyomozóiroda|közbeszerzés|földhasználat|lakópark|tőzsd|részvénypiac|vámokkal|bírság|adatvédelmi incidens|lesz az.{0,40}elnöke|felhívást intéztek|katonai támogatás|komoly dicséretet|nem lesz magyar keret", title, re.I)
        and not re.search(r"fideszes|orbán-kormány|álcivil", context, re.I)
        and (
            bool(re.search(r"találmány|feltalál|új eszköz|új készülék|kütyü|kindle|űrmisszió|űrszonda|mesterséges intelligencia|\bai\b|chatgpt|szoftver|robotika|robotot|\bchip|processzor|okostelefon|laptop|kvantum|kutatás|kutatók|kutatási eredmény|vérvizsgálat|felfedez|innováció|prototípus", title, re.I))
            or (bool(re.search(r"megmutatta|bemutat|fejleszt|kipróbál|tesztel|felfedez|kísérlet|tanulmány|mérnök|kutató|úttörő|kimutatt|készítenek|mérőműszer", title, re.I)) and bool(re.search(r"találmány|feltalál|új eszköz|új készülék|kütyü|kindle|űrmisszió|űrszonda|mesterséges intelligencia|\bai\b|chatgpt|szoftver|robotika|robotot|\bchip|processzor|okostelefon|laptop|kvantum|kutatás|kutatók|kutatási eredmény|vérvizsgálat|felfedez|innováció|prototípus", context, re.I)))
            or (
                bool(re.search(r"riasztás|leállás|üzemzavar|szoftverhiba", title, re.I))
                and bool(re.search(r"microsoft 365|outlook|windows|\bteams\b|\bazure\b", context, re.I))
                and bool(re.search(r"leállás|üzemzavar|elérhetetlenné|szoftverhiba", context, re.I))
            )
            or ("kimutatt" in title.casefold() and bool(re.search(r"egészség|tanulmány|kutatás", context, re.I)))
        )
    )

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
        self.article_links=[]; self.related_sections=[]
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs); classes=(attrs.get("class","")+" "+attrs.get("id","")).casefold()
        if tag in self.blocked:
            self.skip+=1; return
        if self.skip:return
        if tag=="article": self.article+=1
        if any(word in classes for word in ("article-body","article-content","story-body","story-content","post-content","content-body")):
            self.scope_tags.append(tag)
        if tag in {"div", "section", "ul", "ol"} and (
            self.related_sections or re.search(r"related[-_ ]*(?:article|stor)|kapcsolodo[-_ ]*cikk", classes)
        ):
            self.related_sections.append(tag)
        if tag=="a" and (self.article or self.scope_tags or self.related_sections) and attrs.get("href"):
            self.article_links.append(attrs["href"])
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
        if self.related_sections and tag==self.related_sections[-1]:self.related_sections.pop()
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

def reference_key(url):
    host, path = story_key(url)
    return host.removeprefix("www."), path

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

def winter_weather_day(story):
    title = story.get("title", "")
    if not WINTER_WEATHER_HEADLINE.search(title):
        return None
    headline = title.casefold()
    if any(match_term(term, headline) for term in INTERNATIONAL_MARKERS):
        return None
    published = parse_published(story.get("published"))
    return published.date() if published else None


def stories_are_similar(left,right,allow_same_source=False):
    if not left.get("source") or not right.get("source"):
        return False
    left_weather_day = winter_weather_day(left)
    right_weather_day = winter_weather_day(right)
    if left_weather_day or right_weather_day:
        return left_weather_day == right_weather_day
    if not allow_same_source and left["source"] == right["source"]:
        return False
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
        lead["relatedStories"] = [*matches, *lead.get("relatedStories", [])]
        lead["categories"]=sorted(set(lead.get("categories",[])).union(*((set(item.get("categories",[]))-{"technology", "tennis"}) for item in matches)))
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
        known_urls={reference_key(record["url"]) for record in current_group + related if record.get("url")}
        for archived_at,archived_story in candidates:
            key=reference_key(archived_story.get("url",""))
            if not all(key) or key in known_urls:continue
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
latest_official_path=None
today_issued_numbers=set()
issue_files=list(Path("data/archive").glob("*.json"))+[Path("data/latest.json")]
for file in issue_files:
    if file.name=="index.json" or not file.exists():continue
    try:
        edition_data=json.loads(file.read_text(encoding="utf-8"))
        if edition_data.get("testEdition"):continue
        issue_at=parse_published(edition_data.get("updatedAt"))
        if issue_at and (latest_official_at is None or issue_at>=latest_official_at):
            latest_official_at=issue_at
            latest_official_path=file
        scheduled_at=parse_published(edition_data.get("scheduledAt")) or issue_at
        if scheduled_at and scheduled_at.date()==now.date():
            today_issued_numbers.add(edition_data.get("issueNumber") or ISSUE_HOURS.get(scheduled_at.hour))
        edition_stories=edition_data.get("stories",[])
        published_before.update(story_key(record.get("url","")) for story in edition_stories for record in all_story_records(story) if record.get("url"))
        if file.parent.name=="archive" and issue_at:
            for grouped_story in edition_stories:
                for record in all_story_records(grouped_story):
                    if record.get("archiveDate"):continue
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
            source_url=response.geturl()
        page=raw.decode(charset,errors="replace")
        meta=ArticleMetadataParser();meta.feed(page)
        if not meta.published:
            match=re.search(r'"datePublished"\s*:\s*"([^"]+)"',page,re.I)
            if match:meta.published=match.group(1)
        parser=ArticleTextParser();parser.feed(page)
        paras=parser.preferred if parser.preferred else parser.fallback
        body="\n\n".join(paras)
        body=re.sub(r"\s+"," ",body).strip()
        links={}
        for href in parser.article_links:
            try:
                target=urllib.parse.urljoin(source_url,href)
                parts=urllib.parse.urlsplit(target)
                if parts.scheme in {"http", "https"} and parts.netloc and parts.path.strip("/"):
                    links.setdefault(reference_key(target), parts._replace(query="", fragment="").geturl())
            except ValueError:
                continue
        return (body[:18000] if len(body)>250 else "",meta.published,list(links.values()))
    except Exception as exc:
        print(f"Article fetch unavailable {url}: {exc}")
        return "","",None

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


TOPIC_LABELS = {
    "arsenal": "Arsenal", "man-city": "Manchester City", "bayern": "Bayern München",
    "man-united": "Manchester United", "como": "Como", "premier": "Premier League",
    "champions-league": "Bajnokok ligája", "f1": "F1", "nba": "NBA", "nfl": "NFL",
    "seahawks": "Seattle Seahawks", "cycling": "Kerékpár", "darts": "Darts",
    "environment": "Környezetvédelem", "films": "Filmek", "property": "Ingatlan",
    "technology": "Technológia / Fejlesztések", "tennis": "Tenisz", "parliament": "Belföldi parlament",
    "belfold": "Belföld", "domestic": "Belföld", "foreign": "Külföld",
    "hu-market": "Belföldi tőzsde", "world-market": "Külföldi tőzsde", "market": "Tőzsde",
}


def topic_summary_direction(story):
    labels = list(dict.fromkeys(
        TOPIC_LABELS[key] for key in (story.get("categories") or ()) if key in TOPIC_LABELS
    ))
    if not labels:
        return ""
    return (
        "A cikk kijelölt rovatai: " + ", ".join(labels) + ". "
        "Minden kért változat összefoglalójába természetesen építsd be azokat a konkrét "
        "forrástényeket, amelyek megmutatják, hogyan kapcsolódik a cikk az egyes rovatokhoz. "
        "A rovatnevek felsorolása helyett nevezd meg az érintett szereplőt, eseményt vagy fejlesztést. "
        "Ha valamelyik kapcsolatra az alapanyag nem ad bizonyítékot, ne találj ki indoklást.\n"
    )


GEMINI_WORKERS = 2
gemini_next_request = 0.0
gemini_request_lock = Lock()


def request_gemini(request):
    global gemini_next_request
    for attempt in range(3):
        while True:
            with gemini_request_lock:
                started = time.monotonic()
                remaining = gemini_next_request - started
                if (background or force_backfill) and started + max(remaining, 0) >= work_deadline:
                    raise TimeoutError("Gemini request deferred to a later processing batch")
                if remaining <= 0:
                    gemini_next_request = started + 1
                    break
            time.sleep(remaining)
        try:
            print("Requesting Gemini style processing.", flush=True)
            with urllib.request.urlopen(request, timeout=50) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            if exc.code not in (429, 503):
                raise
            delay = (4 if exc.code == 429 else 2) * 2**attempt
            retry_after = exc.headers.get("Retry-After", "") if exc.headers else ""
            if retry_after.isdecimal():
                delay = max(delay, int(retry_after))
            elif retry_after:
                try:
                    delay = max(delay, parsedate_to_datetime(retry_after).timestamp() - time.time())
                except (TypeError, ValueError, OverflowError):
                    pass
            with gemini_request_lock:
                gemini_next_request = max(gemini_next_request, time.monotonic() + delay)
            print(f"Gemini HTTP {exc.code}; next request after {delay:.0f}s.")
            if attempt == 2:
                raise


def gemini_rewrites(story,article_text,api_key,vivid_styles=False,*,styles_only=False):
    source_text=article_text or story["summary"]
    basis="a cikk nyilvánosan elérhető törzsszövege" if article_text else "az RSS-ben elérhető kivonat"
    tolkien_direction=("merészen epikus, gazdag képekben és erőteljes ritmusban, ősi krónikák emelkedettségével; használj emlékezetes, költői címet és bátrabb, kevésbé visszafogott szóképeket. A képek és hasonlatok maradjanak egyértelműen költőiek, ne állítsanak új tényt." if vivid_styles else "határozottan emelkedett, ünnepélyes, régies krónikás hangú, gazdagabb ritmussal és választékos szóhasználattal")
    reito_direction=("szabadjára engedett, csattanós kalandregényes hangon: száraz humorral, pimasz fordulatokkal, merész kontrasztokkal, váratlan, de tényekhez kötött szóképekkel és emlékezetes címmel. A humor és a képek legyenek bátrabbak, de ne állítsanak új tényt." if vivid_styles else "markánsan csattanós, száraz humorú, pörgős kalandregényes hangon")
    requested = (
        "kizárólag Tolkien és Rejtő magyar NANONews-változatot"
        if styles_only else "három magyar nyelvű NANONews-változatot"
    )
    output_fields = '"tolkien":{"title":"...","body":"..."}, "reito":{"title":"...","body":"..."}'
    original_direction = ""
    if not styles_only:
        output_fields = '"original":{"body":"..."}, ' + output_fields
        original_direction = 'Az "original" mezőbe írj semleges, pontos, közérthető összefoglalót.\n'
    prompt=f"""Feladat: készíts {requested} ugyanarról a hírről.
Minden kért összefoglaló első mondatában nevezd meg, mi történt és pontosan kit vagy mit érint a változás. Ha a forrás megadja az érintett modelleket, szolgáltatásokat vagy a határidőt, írd ki őket konkrétan. A második mondatban tedd világossá a legfontosabb gyakorlati következményt. Kerüld a tartalmat nem közlő felvezetést.\nCsak a megadott forrás tényeit használd; ne adj hozzá következtetést, idézetet vagy kitalált részletet.
{topic_summary_direction(story)}Minden kért összefoglaló legyen tartalmas, 3–4 jól olvasható mondatban. Őrizd meg a cikk lényegi részleteit: ki érintett, mi történt, mi lett az eredmény vagy következmény, továbbá a forrásban szereplő fontos számokat, időpontokat és feltételeket. Ne hagyj ki olyan részletet, amely érdemben megváltoztatná a hír jelentését; ne találj ki tényt.
{original_direction}A "tolkien" mezőhöz alkoss önálló címet és 3–4 mondatos, {tolkien_direction} átfogalmazást. A cím is ezt a hangot tükrözze. A tények és azok viszonyai maradjanak pontosak; ne adj hozzá fantasy-elemet, új tényt, szereplői szándékot vagy nem igazolt következtetést.
A "reito" mezőhöz alkoss önálló címet és 3–4 mondatos, {reito_direction} átfogalmazást. A humor kizárólag a forrásban szereplő tények szellemes egymás mellé állításából vagy megfogalmazásából eredjen. Ne találj ki jelenetet, párbeszédet, szereplői szándékot, reakciót, tanulságot vagy lezáró poént. Ez a hang legyen könnyed és földközeli, jól elkülönülve a Tolkien-féle emelkedettségtől. Ne idézz vagy másolj konkrét műrészletet, és ne változtass a tényeken.\nMinden kért változat legyen tényhű, és különbözzön a többitől. A válasz kizárólag JSON legyen:\n{{{output_fields}}}
Forrás: {story["source"]}
Eredeti cím: {story["title"]}
Alapanyag ({basis}):
{source_text[:18000]}"""
    payload=json.dumps({"model":"gemini-3.5-flash-lite","input":prompt,"store":False}).encode()
    request=urllib.request.Request("https://generativelanguage.googleapis.com/v1beta/interactions",data=payload,headers={"Content-Type":"application/json","x-goog-api-key":api_key},method="POST")
    result = request_gemini(request)
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
    if not styles_only:
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
Minden kért összefoglaló első mondatában nevezd meg, mi történt és pontosan kit vagy mit érint a változás. Ha a forrás megadja az érintett modelleket, szolgáltatásokat vagy a határidőt, írd ki őket konkrétan. A második mondatban tedd világossá a legfontosabb gyakorlati következményt. Kerüld a tartalmat nem közlő felvezetést.\nCsak a megadott forrás tényeit használd; ne adj hozzá következtetést, idézetet vagy kitalált részletet.
{topic_summary_direction(story)}Adj új címet és 3–4 mondatos, {tolkien_direction} átfogalmazást; a ritmus különüljön el az Eredeti és a Rejtő-változattól. A cím is tükrözze ezt a hangot. Őrizd meg a cikk lényegi részleteit és minden ténykapcsolatot.
Ne készíts Eredeti változatot, és ne adj hozzá fantasy-elemet vagy új tényt.
A válasz kizárólag JSON legyen:
{{"tolkien":{{"title":"...","body":"..."}}}}
Forrás: {story["source"]}
Eredeti cím: {story["title"]}
Alapanyag ({basis}):
{source_text[:18000]}"""
    payload=json.dumps({"model":"gemini-3.5-flash-lite","input":prompt,"store":False}).encode()
    request=urllib.request.Request("https://generativelanguage.googleapis.com/v1beta/interactions",data=payload,headers={"Content-Type":"application/json","x-goog-api-key":api_key},method="POST")
    result = request_gemini(request)
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
Minden kért összefoglaló első mondatában nevezd meg, mi történt és pontosan kit vagy mit érint a változás. Ha a forrás megadja az érintett modelleket, szolgáltatásokat vagy a határidőt, írd ki őket konkrétan. A második mondatban tedd világossá a legfontosabb gyakorlati következményt. Kerüld a tartalmat nem közlő felvezetést.\nCsak a megadott forrás tényeit használd; ne adj hozzá következtetést, idézetet vagy kitalált részletet.
{topic_summary_direction(story)}Adj új címet és 3–4 mondatos, {reito_direction} átfogalmazást. Az irónia kizárólag a forrásban szereplő tények szellemes egymás mellé állításából vagy megfogalmazásából eredjen. Ne találj ki jelenetet, párbeszédet, szereplői szándékot, reakciót, tanulságot vagy lezáró poént, és ne következtess a forrásban nem szereplő eredményre. Őrizd meg a cikk lényegi részleteit és tényeit.
Ne készíts Eredeti vagy Tolkien-változatot, ne idézz vagy másolj konkrét műrészletet, és ne adj hozzá új tényt.
A válasz kizárólag JSON legyen:
{{"reito":{{"title":"...","body":"..."}}}}
Forrás: {story["source"]}
Eredeti cím: {story["title"]}
Alapanyag ({basis}):
{source_text[:18000]}"""
    payload=json.dumps({"model":"gemini-3.5-flash-lite","input":prompt,"store":False}).encode()
    request=urllib.request.Request("https://generativelanguage.googleapis.com/v1beta/interactions",data=payload,headers={"Content-Type":"application/json","x-goog-api-key":api_key},method="POST")
    result = request_gemini(request)
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
def needs_style_refresh(story):
    variants = story.get("variants", {})
    tolkien = variants.get("tolkien", {})
    reito = variants.get("reito", {})
    return (
        story.get("summaryVersion") != SUMMARY_VERSION
        or not variants.get("original", {}).get("body")
        or not tolkien.get("title") or not tolkien.get("body")
        or not reito.get("title") or not reito.get("body")
    )


previous={}
previous_edition={}
pending_current=[]
current_archive_path=None
try:
    if latest_official_path is not None:
        previous_edition=json.loads(latest_official_path.read_text(encoding="utf-8"))
    previous={record.get("url"):record for story in previous_edition.get("stories",[]) for record in all_story_records(story) if record.get("url")}
    if not previous_edition.get("testEdition"):
        issue_at=parse_published(previous_edition.get("updatedAt"))
        if issue_at:
            current_archive_path=Path("data/archive")/previous_edition.get("archiveFile", f"{issue_at:%Y-%m-%d-%H%M}.json")
        # One-off editorial handoffs for specific editions.
        slot_at=parse_published(previous_edition.get("scheduledAt")) or issue_at
        skip_backfill = issue_at and (
            issue_at.date().isoformat() == "2026-11-24"
            or (slot_at.date().isoformat() == "2026-11-26" and previous_edition.get("issueNumber") == 1)
        )
        if skip_backfill:
            print("Skipping style backfill for this issue to prepare the next edition.")
        else:
            for grouped_story in previous_edition.get("stories",[]):
              for saved_story in all_story_records(grouped_story):
                if saved_story.get("archiveDate"):continue
                if needs_style_refresh(saved_story):
                    pending_current.append(saved_story)
except Exception:pass
api_key=os.getenv("GEMINI_API_KEY","").strip()
stories=[]
due_slots = [
    (now.replace(hour=hour, minute=0, second=0, microsecond=0), number)
    for hour, number in sorted(ISSUE_HOURS.items())
    if hour <= now.hour and number not in today_issued_numbers
]
if publish_only and not due_slots:
    print("No unpublished official issue is due today.", flush=True)
    raise SystemExit(0)
scheduled_at, scheduled_issue_number = due_slots[0] if publish_only else (None, None)
cutoff = scheduled_at if publish_only else now
previous_cutoff = parse_published(previous_edition.get("contentCutoff")) or latest_official_at
collect_new_edition=manual or publish_only
prepare_in_background=bool(api_key) and background and not pending_current
next_issue = min(
    slot for day in (now, now + timedelta(days=1))
    for hour in ISSUE_HOURS
    if (slot := day.replace(hour=hour, minute=0, second=0, microsecond=0)) > now
)
vivid_styles=(scheduled_at or (now if manual else next_issue))>=VIVID_STYLE_START
# Keep items between issue runs, even when a source's RSS list rolls over.
inbox_path=Path("data/rss-pending.json")
snapshot_ref=os.getenv("NANONEWS_SNAPSHOT_REF")
snapshot_sha=None
if publish_only and snapshot_ref:
    snapshot_sha=subprocess.check_output(
        ["git", "log", "-1", f"--before={cutoff.isoformat()}", "--format=%H",
         snapshot_ref, "--", str(inbox_path)],
        text=True,
    ).strip()
    if not snapshot_sha:
        raise SystemExit(f"No saved inbox found by {cutoff.isoformat()}")
    inbox_state=json.loads(subprocess.check_output(
        ["git", "show", f"{snapshot_sha}:{inbox_path}"], text=True,
    ))
    print(f"Publishing from inbox snapshot {snapshot_sha} at {cutoff.isoformat()}")
else:
    try:
        inbox_state=json.loads(inbox_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        inbox_state={}
if isinstance(inbox_state,list):
    inbox_state={"articles":inbox_state}
inbox={story_key(record["link"]):record for record in inbox_state.get("articles",[])}
last_rss_collection=parse_published(inbox_state.get("lastRssCollection"))
# Use UTC hour slots so the repeated local hour at the end of daylight saving time still runs twice.
rss_hour=now.timestamp()//3600
collect_rss=(collect_only or manual) and (last_rss_collection is None or last_rss_collection.timestamp()//3600<rss_hour)

for key,record in list(inbox.items()):
    published=parse_published(record["published"])
    observed=parse_published(record["observed"])
    if key in published_before or (previous_cutoff and (published or observed) and (published or observed)<=previous_cutoff):
        del inbox[key]

if collect_rss:
    print("Starting RSS collection.", flush=True)
    inbox_state["lastRssCollection"]=now.isoformat()
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
                    if key in published_before or (previous_cutoff and published_at and published_at<=previous_cutoff):
                        continue
                    desc=text(item.find("description"))
                    existing=inbox.get(key)
                    record={
                        "source":source,
                        "published":published,
                        "observed":existing["observed"] if existing else now.isoformat(),
                        "title":title,
                        "link":link,
                        "description":desc,
                        "image":image_for(item,desc),
                    }
                    if existing is None or any(existing.get(field)!=value for field,value in record.items()):
                        inbox[key]=record
            except Exception as exc:
                print(f"Feed error {source} {url}: {exc}")

def save_inbox():
    inbox_path.parent.mkdir(exist_ok=True)
    inbox_state["articles"] = list(inbox.values())
    inbox_path.write_text(json.dumps(inbox_state, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")

if collect_only:
    save_inbox()
    print(f"RSS collection complete; {len(inbox)} stored articles.", flush=True)
    raise SystemExit(0)

print("Assembling official edition from saved articles." if publish_only else "Starting article and style processing.", flush=True)

def save_prepared_story(record, story):
    if all(story.get("variants", {}).get(style, {}).get("body")
           for style in ("original", "tolkien", "reito")):
        record["prepared"] = story
        record["preparedVividStyles"] = vivid_styles
        print(f"Prepared all three variants: {story['url']}")


def finish_preparation(record, story, future):
    try:
        story["variants"] = future.result()
    except Exception as exc:
        print(f"Rewrite unavailable {story['url']}: {exc}")
    save_prepared_story(record, story)


preparation_pool = ThreadPoolExecutor(max_workers=GEMINI_WORKERS) if prepare_in_background else None
preparations = deque()

unclassified_cutoff = now.timestamp() - timedelta(days=7).total_seconds()
for key, record in list(inbox.items()):
    source=record["source"]
    retention_start = parse_published(record.get("observed"))
    published_for_retention = parse_published(record.get("published"))
    # Use the earlier available time to prevent old, dated RSS items from being re-added.
    expired = any(at and at.timestamp() <= unclassified_cutoff
                  for at in (retention_start, published_for_retention))
    if background and time.monotonic() >= work_deadline:
        break
    if publish_only and retention_start and retention_start > cutoff:
        continue
    if not expired and not collect_new_edition and not prepare_in_background:
        continue
    prepared=record.get("prepared")
    if (collect_new_edition or prepare_in_background) and prepared and prepared.get("summaryVersion")==SUMMARY_VERSION and record.get("preparedVividStyles")==vivid_styles:
        if collect_new_edition:
            article_date=parse_published(prepared["published"])
            if article_date and (not previous_cutoff or previous_cutoff<article_date) and article_date<=cutoff:
                prepared["categories"] = apply_subject_categories(
                    record["title"], record["description"], prepared["categories"],
                )
                if not prepared["categories"]:
                    continue
                if not publish_only and "sourceArticleLinks" not in prepared:
                    _, _, source_links=fetch_article(prepared["url"])
                    if source_links is not None:
                        prepared["sourceArticleLinks"]=source_links
                stories.append(prepared)
        continue
    title=record["title"]
    link=record["link"]
    desc=record["description"]
    feed_published=record["published"]
    hay=(title+" "+desc+" "+link).casefold()
    cats=[key for key,terms in rules.items() if key != "tennis" and any(match_term(term,hay) for term in terms)]
    if is_tennis_story(title, desc):
        cats.append("tennis")
    football_cats=football_overrides(title,desc,link)
    if "arsenal" in cats and not football_cats["arsenal"]:cats.remove("arsenal")
    cats.extend(key for key,matched in football_cats.items() if matched and key not in cats)
    if source=="NBAnews.hu" and "nba" not in cats:cats.append("nba")
    if source=="Fűzővel kifelé!" and "nfl" not in cats:cats.append("nfl")
    cats = [key for key in cats if key != "technology"]
    if is_technology_story(title, desc) and not is_sport_related(hay, cats):
        cats.append("technology")
    if (("parliament" in cats or is_domestic_economy(hay,cats) or any(match_term(term,hay) for term in NER_MARKERS)) and not is_sport_related(hay,cats)) or is_domestic_sport_economy(hay,cats):cats.append("belfold")
    if is_foreign_political_economic(hay,cats):cats.append("foreign")
    context = title + " " + desc
    foreign_nvidia = re.search(r"nvidi[aá]", title, re.I) and re.search(r"jensen huang|árfolyam|tőzsd|vezérigazgató|vállalat élére", context, re.I)
    foreign_deal = re.search(r"franciaország|németország|olaszország|spanyolország", title, re.I) and re.search(r"autógyár|felvásárl|üzemet|gyárat|beruház", title, re.I)
    lake_environment = re.search(r"balaton|velencei-tó|fertő tó|tisza-tó", context, re.I) and re.search(r"vízállás|vízhiány|vízpótlás|vízminőség|vízszennyezés", context, re.I)
    foreign_nvidia = foreign_nvidia and not re.search(r"bemutat|új (?:chip|processzor|grafikus kártya|technológia)|fejleszt", title, re.I)
    if foreign_nvidia or foreign_deal:
        cats = [cat for cat in cats if cat not in {"belfold", "parliament", "foreign"}
                and not (foreign_nvidia and cat == "technology")]
        cats.append("foreign")
        if foreign_deal and re.search(r"magyarországi[^.!?]{0,55}(?:beruház|gyár|üzem|gyártás)|(?:szegedi|debreceni)[^.!?]{0,35}(?:beruház|gyár|üzem)", context, re.I):
            cats.append("belfold")
    cats = ["environment"] if lake_environment else apply_subject_categories(title, desc, cats)
    if not cats:
        if expired:
            del inbox[key]
        continue
    if not collect_new_edition and not prepare_in_background:
        continue
    story={"source":source,"title":title,"summary":concise_sentences(desc,3)[:500],"url":link,"published":feed_published,"categories":cats,"image":record["image"],"summaryVersion":SUMMARY_VERSION}
    article_text,article_published,source_links=("",None,None) if publish_only else fetch_article(link)
    if source_links is not None:
        story["sourceArticleLinks"]=source_links
    if not story["published"] and article_published:story["published"]=article_published
    article_date=parse_published(story["published"])
    if article_date and article_date>cutoff:continue
    if previous_cutoff and (not article_date or article_date<=previous_cutoff):
        print(f"Skipping story without a post-issue publication date: {link}")
        continue
    basis_text=article_text or story["summary"]
    story["contentBasis"]="article" if article_text else "rss"
    story["sourceHash"]=hashlib.sha256(basis_text.encode("utf-8")).hexdigest()
    cached=previous.get(link,{})
    if cached.get("summaryVersion")==SUMMARY_VERSION and cached.get("sourceHash")==story["sourceHash"] and cached.get("variants",{}).get("original",{}).get("body") and cached.get("variants",{}).get("tolkien",{}).get("body") and cached.get("variants",{}).get("reito",{}).get("body"):
        story["variants"]=cached["variants"]
    elif preparation_pool is not None:
        # The RSS inbox can contain both www and non-www URLs for a story.
        if preparations and reference_key(preparations[0][1]["url"]) == reference_key(link):
            finish_preparation(*preparations.popleft())
        future = preparation_pool.submit(
            gemini_rewrites, story, article_text, api_key, vivid_styles=vivid_styles,
        )
        preparations.append((record, story, future))
        if len(preparations) == GEMINI_WORKERS:
            finish_preparation(*preparations.popleft())
        continue
    elif not publish_only and api_key and not pending_current:
        try:
            story["variants"]=gemini_rewrites(story,article_text,api_key,vivid_styles=vivid_styles)
        except Exception as exc:print(f"Rewrite unavailable {link}: {exc}")
    if collect_new_edition:
        stories.append(story)
    else:
        save_prepared_story(record, story)

if preparation_pool is not None:
    preparation_pool.shutdown()
    for preparation in preparations:
        finish_preparation(*preparation)

if not publish_only:
    save_inbox()

def backfill_story(pending_story):
    if (background or force_backfill) and time.monotonic() >= work_deadline:
        return False
    updated = False
    current_variants=pending_story.setdefault("variants",{})
    if (pending_story.get("summaryVersion")!=SUMMARY_VERSION or
        not current_variants.get("original",{}).get("body")):
        article_text,_,_=fetch_article(pending_story.get("url",""))
        try:
            generated=gemini_rewrites(pending_story,article_text,api_key,vivid_styles=edition_uses_vivid_styles(previous_edition))
            pending_story["variants"]=generated
            pending_story["summaryVersion"]=SUMMARY_VERSION
            if article_text:
                pending_story["contentBasis"]="article"
                pending_story["sourceHash"]=hashlib.sha256(article_text.encode("utf-8")).hexdigest()
            updated=True
            print(f"Refreshed v2 summary and styles for {pending_story.get('url')}")
        except Exception as exc:
            print(f"Pending v2 summary unavailable {pending_story.get('url')}: {exc}")
        return updated
    current_tolkien=current_variants.setdefault("tolkien",{})
    current_reito=current_variants.setdefault("reito",{})
    article_text,_,_=fetch_article(pending_story.get("url",""))
    needs_tolkien = not current_tolkien.get("title") or not current_tolkien.get("body")
    needs_reito = not current_reito.get("title") or not current_reito.get("body")
    if needs_tolkien and needs_reito:
        try:
            generated = gemini_rewrites(
                pending_story, article_text, api_key,
                vivid_styles=edition_uses_vivid_styles(previous_edition), styles_only=True,
            )
            for style, current in (("tolkien", current_tolkien), ("reito", current_reito)):
                for field in ("title", "body"):
                    if not current.get(field):
                        current[field] = generated[style][field]
            updated = True
            if article_text:
                pending_story["contentBasis"] = "article"
                pending_story["sourceHash"] = hashlib.sha256(article_text.encode("utf-8")).hexdigest()
        except Exception as exc:
            print(f"Pending combined style rewrite unavailable {pending_story.get('url')}: {exc}")
        return updated
    if needs_tolkien:
        try:
            generated=gemini_tolkien_rewrite(pending_story,article_text,api_key,vivid_styles=edition_uses_vivid_styles(previous_edition))
            if not current_tolkien.get("title"):current_tolkien["title"]=generated["title"]
            if not current_tolkien.get("body"):current_tolkien["body"]=generated["body"]
            updated=True
            print(f"Completed missing Tolkien rewrite for {pending_story.get('url')}")
        except Exception as exc:print(f"Pending Tolkien rewrite unavailable {pending_story.get('url')}: {exc}")
    if not current_reito.get("title") or not current_reito.get("body"):
        try:
            generated=gemini_reito_rewrite(pending_story,article_text,api_key,vivid_styles=edition_uses_vivid_styles(previous_edition))
            if not current_reito.get("title"):current_reito["title"]=generated["title"]
            if not current_reito.get("body"):current_reito["body"]=generated["body"]
            updated=True
            print(f"Completed missing Rejto rewrite for {pending_story.get('url')}")
        except Exception as exc:print(f"Pending Rejto rewrite unavailable {pending_story.get('url')}: {exc}")
    if current_tolkien.get("title") and current_tolkien.get("body") and current_reito.get("title") and current_reito.get("body"):
        if current_variants.get("original",{}).get("body"):
            pending_story["summaryVersion"]=SUMMARY_VERSION
        if article_text:
            pending_story["contentBasis"]="article"
            pending_story["sourceHash"]=hashlib.sha256(article_text.encode("utf-8")).hexdigest()
    return updated


def backfill_group(stories):
    updated = False
    for story in stories:
        if backfill_story(story):
            updated = True
    return updated


pending_updated = False
if api_key and not publish_only and (not manual or pending_current) and pending_current:
    stories_by_article = {}
    for story in pending_current[:10]:
        stories_by_article.setdefault(reference_key(story.get("url", "")), []).append(story)
    with ThreadPoolExecutor(max_workers=GEMINI_WORKERS) as backfill_pool:
        backfill_results = list(backfill_pool.map(backfill_group, stories_by_article.values()))
    pending_updated = any(backfill_results)


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

if not stories and not publish_only:
    if not pending_updated:
        print("No new stories or missing Tolkien/Rejto rewrites; leaving the current edition and archive unchanged.")
        raise SystemExit(0)
    if pending_updated and latest_official_path is not None:
        latest_official_path.write_text(json.dumps(previous_edition,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    sync_pending_archive()
    print(f"Completed missing style rewrites in the current issue; {len(pending_current)} stories were checked.")
    raise SystemExit(0)
sync_pending_archive()
stories.sort(key=lambda s:s["published"],reverse=True)
stories=group_similar_stories(stories)
stories=attach_archived_stories(stories,archived_similarity_records.values())
issue_number=None if manual else scheduled_issue_number
edition={"updatedAt":now.isoformat(),"testEdition":manual,"issueNumber":issue_number,"stories":stories}
if publish_only:
    edition.update(scheduledAt=scheduled_at.isoformat(), contentCutoff=cutoff.isoformat())
    # Give overdue slots distinct archive names even when published in the same minute.
    if snapshot_sha:
        edition["inboxSnapshot"] = snapshot_sha
    edition["archiveFile"] = f"{scheduled_at:%Y-%m-%d-%H%M}.json"
Path("data").mkdir(exist_ok=True)
Path("data/latest.json").write_text(json.dumps(edition,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
archive=Path("data/archive");archive.mkdir(exist_ok=True)
stamp=now.strftime("%Y-%m-%d-%H%M")
(archive/edition.get("archiveFile", f"{stamp}.json")).write_text(json.dumps(edition,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
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
