import json, re, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
TZ=ZoneInfo("Europe/Budapest")
now=datetime.now(TZ)
if now.hour not in (6,14) and __import__("os").getenv("GITHUB_EVENT_NAME") != "workflow_dispatch":
    print("Outside the two Budapest edition times; no refresh.")
    raise SystemExit(0)
feeds={
 "Telex":"https://telex.hu/rss",
 "HVG":"https://hvg.hu/rss",
 "Index":"https://index.hu/rss",
 "Nemzeti Sport":"https://www.nemzetisport.hu/publicapi/hu/rss/nso/articles",
}
topics=["Arsenal","Manchester City","Manchester City","Bayern München","Manchester United","Como","Fernando Alonso","F1","foci"]
def text(node):
    if node is None: return ""
    return re.sub(r"\\s+"," ", "".join(node.itertext())).strip()
stories=[]; seen=set()
for source,url in feeds.items():
    try:
        req=urllib.request.Request(url,headers={"User-Agent":"NANONews/1.0 (RSS reader)"})
        root=ET.fromstring(urllib.request.urlopen(req,timeout=20).read())
        for item in root.findall(".//item"):
            title=text(item.find("title")); link=text(item.find("link"))
            desc=text(item.find("description"))
            hay=(title+" "+desc).casefold()
            if not title or not link or link in seen or not any(k.casefold() in hay for k in topics): continue
            seen.add(link)
            stories.append({"source":source,"title":title,"summary":desc[:500],"url":link,"published":text(item.find("pubDate"))})
    except Exception as e:
        print(f"Feed error {source}: {e}")
stories.sort(key=lambda s:s["published"],reverse=True)
edition={"updatedAt":now.isoformat(),"stories":stories[:40]}
Path("data").mkdir(exist_ok=True)
Path("data/latest.json").write_text(json.dumps(edition,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
archive=Path("data/archive"); archive.mkdir(exist_ok=True)
stamp=now.strftime("%Y-%m-%d-%H")
(archive/f"{stamp}.json").write_text(json.dumps(edition,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(f"Saved {len(edition['stories'])} stories at {edition['updatedAt']}")
