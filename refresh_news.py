import hashlib, json, re, urllib.request, xml.etree.ElementTree as ET, os, time
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from zoneinfo import ZoneInfo

TZ=ZoneInfo("Europe/Budapest")
now=datetime.now(TZ)
manual=os.getenv("GITHUB_EVENT_NAME") == "workflow_dispatch"
if now.hour not in (6,14,20) and not manual:
    print("Outside NANONews edition times.")
    raise SystemExit(0)

feeds={
 "Telex":["https://telex.hu/rss"],
 "HVG":["https://hvg.hu/rss"],
 "Index":["https://index.hu/rss"],
 "Nemzeti Sport":["https://www.nemzetisport.hu/publicapi/hu/rss/nso/articles","https://www.nemzetisport.hu/static/rss_hirek.xml"],
}
rules={
 "arsenal":["arsenal"],"man-city":["manchester city","man city"],"bayern":["bayern münchen","bayern munchen","bayern"],
 "man-united":["manchester united","man united"],"como":["como "],
 "premier":["premier league","angol bajnokság","angol liga","premier ligában"],
 "f1":["formula-1","formula 1","forma-1","f1","fernando alonso","nagydíj","nagy díj"],
 "nba":["nba","kosárlabda"],
 "parliament":["országgyűlés","parlament","képviselő","törvényjavaslat","frakció","orszaggyules"],
 "hu-market":["bux","budapesti értéktőzsde","magyar tőzsde","otp részvény","mol részvény","richter részvény","mtelekom részvény"],
 "world-market":["nasdaq","s&p 500","dow jones","wall street","stock market","nyse","dax","nikkei","amerikai tőzsde","külföldi tőzsde","részvénypiacokon"],
 "domestic":["magyarország","magyarországon","magyarországi","budapest","debrecen","szeged","miskolc","pécs","győr","hazai","magyar kormány","miniszterelnök"],
}

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

def fetch_article(url):
    try:
        req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 (compatible; NANONews/1.0; +https://ngynrbrt-prog.github.io/nanonews/)","Accept":"text/html"})
        with urllib.request.urlopen(req,timeout=18) as response:
            raw=response.read(2_000_000)
            charset=response.headers.get_content_charset() or "utf-8"
        page=raw.decode(charset,errors="replace")
        parser=ArticleTextParser();parser.feed(page)
        paras=parser.preferred if parser.preferred else parser.fallback
        body="\n\n".join(paras)
        body=re.sub(r"\s+"," ",body).strip()
        return body[:18000] if len(body)>250 else ""
    except Exception as exc:
        print(f"Article fetch unavailable {url}: {exc}")
        return ""

def gemini_rewrites(story,article_text,api_key):
    source_text=article_text or story["summary"]
    basis="a cikk nyilvánosan elérhető törzsszövege" if article_text else "az RSS-ben elérhető kivonat"
    prompt=f"""Feladat: készíts egy magyar nyelvű, Tolkien hangulatát idéző NANONews-változatot ugyanarról a hírről.
Csak a megadott forrás tényeit használd; ne adj hozzá következtetést, idézetet vagy kitalált részletet.
Írj új, önálló címet és részletes, tömör összefoglalót. Az összefoglaló 3–5 mondatban fedje le a hír legfontosabb tényeit, szereplőit, eredményét és következményét, ha ezek szerepelnek a forrásban. Ne másold át mondatról mondatra a cikket, és ne írj az eredetinél hosszabb szöveget.
- Tolkien-hangulat: epikus, régies-krónikás hangulat, közérthető megfogalmazással. Ne adj hozzá fantasy-elemet vagy új tényt.
A válasz kizárólag JSON legyen ebben az alakban:
{{"tolkien":{{"title":"...","body":"..."}}}}
Forrás: {story["source"]}
Eredeti cím: {story["title"]}
Alapanyag ({basis}):
{source_text[:18000]}"""
    payload=json.dumps({"model":"gemini-3.5-flash-lite","input":prompt,"store":False}).encode()
    request=urllib.request.Request("https://generativelanguage.googleapis.com/v1beta/interactions",data=payload,headers={"Content-Type":"application/json","x-goog-api-key":api_key},method="POST")
    with urllib.request.urlopen(request,timeout=50) as response:
        result=json.loads(response.read().decode("utf-8"))
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
    for mode in ("tolkien",):
        value=parsed.get(mode,{})
        title=re.sub(r"\s+"," ",str(value.get("title",""))).strip()
        body=re.sub(r"\s+"," ",str(value.get("body",""))).strip()
        if not title or not body:raise ValueError(f"Missing {mode} rewrite")
        variants[mode]={"title":title[:180],"body":body[:2400]}
    return variants

# Reuse generated rewrites for unchanged stories so the free API quota is spent only on new/updated links.
previous={}
try:
    last=json.loads(Path("data/latest.json").read_text(encoding="utf-8"))
    previous={s.get("url"):s for s in last.get("stories",[]) if s.get("url")}
except Exception:pass
api_key=os.getenv("GEMINI_API_KEY","").strip()
stories=[];seen=set()
for source,urls in feeds.items():
 for url in urls:
    try:
        req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 NANONews RSS reader"})
        root=ET.fromstring(urllib.request.urlopen(req,timeout=20).read())
        for item in root.findall(".//item"):
            title=text(item.find("title"));link=text(item.find("link"));desc=text(item.find("description"))
            if not title or not link or link in seen:continue
            hay=(title+" "+desc+" "+link).casefold()
            cats=[key for key,terms in rules.items() if any(match_term(term,hay) for term in terms)]
            if not cats:continue
            seen.add(link)
            story={"source":source,"title":title,"summary":desc[:500],"url":link,"published":text(item.find("pubDate")),"categories":cats,"image":image_for(item,desc)}
            article_text=fetch_article(link)
            basis_text=article_text or story["summary"]
            story["contentBasis"]="article" if article_text else "rss"
            story["sourceHash"]=hashlib.sha256(basis_text.encode("utf-8")).hexdigest()
            cached=previous.get(link,{})
            if cached.get("sourceHash")==story["sourceHash"] and cached.get("variants"):
                story["variants"]=cached["variants"]
            elif api_key:
                try:
                    story["variants"]=gemini_rewrites(story,article_text,api_key)
                    time.sleep(4)
                except Exception as exc:print(f"Rewrite unavailable {link}: {exc}")
            stories.append(story)
    except Exception as e: print(f"Feed error {source} {url}: {e}")
stories.sort(key=lambda s:s["published"],reverse=True)
edition={"updatedAt":now.isoformat(),"testEdition":manual,"stories":stories[:80]}
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
        items.append({"file":file.name,"updatedAt":d.get("updatedAt"),"count":len(d.get("stories",[])),"testEdition":d.get("testEdition",False)})
    except Exception: pass
items.sort(key=lambda item: item.get("updatedAt") or "", reverse=True)
(archive/"index.json").write_text(json.dumps({"editions":items},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(f"Saved {len(edition['stories'])} stories, {sum(bool(s['image']) for s in edition['stories'])} images at {edition['updatedAt']}; rewrites {sum(bool(s.get('variants')) for s in edition['stories'])}")
