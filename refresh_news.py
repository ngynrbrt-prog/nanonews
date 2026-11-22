import json, re, urllib.request, xml.etree.ElementTree as ET, os
from datetime import datetime
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
 "foci":["labdarúgás","labdarugas","futball","foci","football","soccer","nb i","gól","gólt"],
}
def text(node):
    if node is None:return ""
    return re.sub(r"\s+"," "," ".join(node.itertext())).strip()
def image_for(item,desc):
    for node in item.iter():
        tag=node.tag.lower()
        if tag.endswith("thumbnail") or tag.endswith("content") or tag.endswith("enclosure"):
            url=node.attrib.get("url","")
            if url.startswith("http") and any(x in url.lower() for x in (".jpg",".jpeg",".png",".webp","image")):
                return url
    m=re.search(r'<img[^>]+src=["\\'](https?://[^"\\']+)',desc,re.I)
    return m.group(1) if m else ""
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
            cats=[key for key,terms in rules.items() if any(term in hay for term in terms)]
            if not cats:continue
            seen.add(link)
            stories.append({"source":source,"title":title,"summary":desc[:500],"url":link,"published":text(item.find("pubDate")),"categories":cats,"image":image_for(item,desc)})
    except Exception as e: print(f"Feed error {source} {url}: {e}")
stories.sort(key=lambda s:s["published"],reverse=True)
edition={"updatedAt":now.isoformat(),"testEdition":manual,"stories":stories[:80]}
Path("data").mkdir(exist_ok=True)
Path("data/latest.json").write_text(json.dumps(edition,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
archive=Path("data/archive");archive.mkdir(exist_ok=True)
stamp=now.strftime("%Y-%m-%d-%H%M")
(archive/f"{stamp}.json").write_text(json.dumps(edition,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
items=[]
for file in sorted(archive.glob("*.json"),reverse=True):
    try:
        d=json.loads(file.read_text(encoding="utf-8"))
        items.append({"file":file.name,"updatedAt":d.get("updatedAt"),"count":len(d.get("stories",[])),"testEdition":d.get("testEdition",False)})
    except Exception: pass
(archive/"index.json").write_text(json.dumps({"editions":items},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(f"Saved {len(edition['stories'])} stories, {sum(bool(s['image']) for s in edition['stories'])} images at {edition['updatedAt']}")
