"""Build a NANONews status report from the main-branch history."""
import argparse
import json
import re
import subprocess
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from textwrap import dedent
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Budapest")
REPO = "https://github.com/ngynrbrt-prog/nanonews"
SOURCES = ("Telex", "HVG", "Nemzeti Sport", "NBAnews.hu", "Fűzővel kifelé!",
           "444.hu", "Portfolio.hu", "Origo.hu", "IGN Hungary")
STYLES = ("original", "tolkien", "reito")
HEADERS = ("Forrás", "Begyűjtött cikk", "Rovatba illő cikk", "Elkészült Eredeti",
           "Elkészült Tolkien tollából", "Elkészült Rejtő Jenő", "Mindhárom elkészült",
           "Mindhárom elkészült (%)", "Éles kiadásban stílusra váró cikk")


def git(*args):
    return subprocess.check_output(("git", *args), text=True, encoding="utf-8").strip()


def load(ref, path):
    return json.loads(git("show", f"{ref}:{path}"))


def history(cutoff, path=None):
    # First-parent traversal excludes commits that were only on a side branch.
    history_args = ["--", path] if path else []
    return git("log", "--first-parent", "-1",
               f"--until={cutoff.isoformat()}", "--format=%H", "HEAD", *history_args)


def snapshot_rules(ref):
    source = git("show", f"{ref}:refresh_news.py")
    # Use the declaration block and the historical classification body without
    # executing collection, Gemini requests, or publication.
    declarations, separator, _ = source.partition("\npublished_before=set()")
    if not separator:
        raise RuntimeError("A forráscommit kiadási szabályai nem olvashatók.")
    scope = {}
    exec(compile(declarations, "refresh_news.py", "exec"), scope)
    start = source.index("    cats=[key for key,terms")
    end = re.search(r"(?m)^    if not cats:", source[start:]).start() + start
    body = dedent(source[start:end])
    exec("def classify(source, title, desc, link):\n"
         "    hay = (title + ' ' + desc + ' ' + link).casefold()\n"
         + "".join("    " + line + "\n" for line in body.splitlines())
         + "    return cats\n", scope)
    return scope


def story_records(edition, walk):
    for story in edition.get("stories", []):
        yield from walk(story)


def has_text(variants, style, field="body"):
    return bool((variants.get(style, {}).get(field) or "").strip())


def report(cutoff):
    head = history(cutoff)
    rss_ref = history(cutoff, "data/rss-pending.json")
    if not head or not rss_ref:
        raise RuntimeError("A mérési határhoz nem érhető el GitHub-pillanatkép.")
    rules = snapshot_rules(rss_ref)
    parse = rules["parse_published"]
    story_key = rules["story_key"]
    archive = git("ls-tree", "-r", "--name-only", head, "data/archive").splitlines()
    editions = []
    for path in ["data/latest.json", *archive]:
        if not path.endswith(".json") or path.endswith("/index.json"):
            continue
        issue = load(head, path)
        at = parse(issue.get("updatedAt"))
        if at and at < cutoff and not issue.get("testEdition"):
            editions.append((at, issue))
    if not editions:
        raise RuntimeError("A mérési határ előtt nem található hivatalos kiadás.")
    start, live = max(editions, key=lambda item: item[0])
    walk = rules["all_story_records"]
    prior = {story_key(item["url"]) for _, issue in editions
             for item in story_records(issue, walk) if item.get("url")}
    live_rules = snapshot_rules(head)
    next_issue = min(
        datetime.combine(cutoff.date() + timedelta(days=day), time(hour), TZ)
        for day in (0, 1) for hour in live_rules.get("ISSUE_HOURS", (6, 17))
        if datetime.combine(cutoff.date() + timedelta(days=day), time(hour), TZ) > cutoff
    )
    vivid = next_issue >= rules["VIVID_STYLE_START"]
    pending = load(rss_ref, "data/rss-pending.json")
    rows = {name: [0] * 7 for name in SOURCES}
    missing_observed = missing_published = 0
    records = {story_key(x["link"]): x for x in
               (pending if isinstance(pending, list) else pending.get("articles", []))}
    for key, item in records.items():
        if item["source"] not in rows:
            continue
        prepared = item.get("prepared") or {}
        observed = parse(item.get("observed"))
        published = parse(item.get("published")) or parse(prepared.get("published"))
        if not observed:
            missing_observed += 1
            continue
        if not start < observed <= cutoff or (published and not start < published <= cutoff):
            continue
        row = rows[item["source"]]
        row[0] += 1
        if key in prior or not rules["classify"](item["source"], item["title"],
                                                item.get("description", ""), item["link"]):
            continue
        if published is None:
            missing_published += 1
            continue
        row[1] += 1
        prepared_at = parse(prepared.get("published"))
        if (prepared.get("summaryVersion") != rules["SUMMARY_VERSION"]
                or item.get("preparedVividStyles") != vivid
                or not prepared_at or not start < prepared_at <= cutoff):
            continue
        ready = [has_text(prepared.get("variants") or {}, style) for style in STYLES]
        for index, done in enumerate(ready, 2):
            row[index] += done
        row[5] += all(ready)
    seen = set()
    for item in story_records(live, walk):
        if item.get("archiveDate") or not item.get("url") or item.get("source") not in rows:
            continue
        key = story_key(item["url"])
        if key in seen:
            continue
        seen.add(key)
        variants = item.get("variants") or {}
        if (item.get("summaryVersion") != live_rules["SUMMARY_VERSION"]
                or not all(has_text(variants, style) for style in STYLES)
                or not all(has_text(variants, style, "title") for style in STYLES[1:])):
            rows[item["source"]][6] += 1

    rows["Összesen"] = list(map(sum, zip(*rows.values())))
    lines = ["| " + " | ".join(HEADERS) + " |", "|---|" + "---:|" * 8]
    for name, (collected, eligible, original, tolkien, reito, ready, waiting) in rows.items():
        ratio = f"{100 * ready / eligible:.1f}%".replace(".", ",") if eligible else "—"
        values = (name, collected, eligible, original, tolkien, reito, ready, ratio, waiting)
        lines.append("| " + " | ".join(map(str, values)) + " |")
    rss_at = parse(git("show", "-s", "--format=%cI", rss_ref))
    return (
        f"A mérési időszak budapesti idő szerint {start:%Y-%m-%d %H:%M:%S} és "
        f"{cutoff:%Y-%m-%d %H:%M} között tartott. "
        f"A következő kiadás tervezett ideje {next_issue:%Y-%m-%d %H:%M}.\n\n"
        + "\n".join(lines)
        + f"\n\nAz RSS-adatok utolsó elérhető mentése {rss_at:%Y-%m-%d %H:%M:%S}. "
        "Az ezután esetleg begyűjtött vagy elkészült, még nem rögzített adatok ismeretlenek. "
        f"Hiányzó észlelési idő {missing_observed} rekordnál, igazolatlan megjelenési idő "
        f"{missing_published} témába illő rekordnál fordult elő. "
        f"[RSS-forráscommit]({REPO}/commit/{rss_ref}) · [Kiadás állapota]({REPO}/commit/{head})\n\n"
        f"Mentés indítása budapesti idő szerint {datetime.now(TZ):%Y-%m-%d %H:%M:%S}.\n"
    )


def save(folder, cutoff, section):
    date = cutoff.date().isoformat()
    path = folder / f"NANONews-allapotjelentes-{date}.md"
    heading = f"## {cutoff:%H:%M}"
    existing = path.read_text(encoding="utf-8") if path.exists() else f"# NANONews állapotjelentés – {date}\n"
    replacement = f"{heading}\n\n{section.strip()}\n"
    pattern = rf"(?ms)^{re.escape(heading)}[ \t]*\n.*?(?=^## |\Z)"
    if re.search(pattern, existing):
        output = re.sub(pattern, lambda _: replacement + "\n", existing).rstrip() + "\n"
    else:
        output = existing.rstrip() + "\n\n" + replacement
    folder.mkdir(parents=True, exist_ok=True)
    path.write_text(output, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cutoff", help="Kézi mérés helyi idővel, YYYY-MM-DDTHH:MM formában.")
    parser.add_argument("--schedule", default="")
    parser.add_argument("--output-dir", type=Path, default=Path("Dokumentumok/állapotjelentések"))
    args = parser.parse_args()
    if args.cutoff:
        cutoff = datetime.fromisoformat(args.cutoff)
        cutoff = cutoff.astimezone(TZ) if cutoff.tzinfo else cutoff.replace(tzinfo=TZ)
    else:
        utc_hour = int(args.schedule.split()[1])
        utc_now = datetime.now(timezone.utc)
        nominal = datetime.combine(utc_now.date(), time(utc_hour), timezone.utc)
        if nominal > utc_now:
            nominal -= timedelta(days=1)
        cutoff = nominal.astimezone(TZ)
        if cutoff.hour not in (3, 15, 21):
            return
    if cutoff.hour not in (3, 5, 15, 21) or cutoff.minute or cutoff.second or cutoff > datetime.now(TZ):
        parser.error("A mérési határ múltbeli vagy aktuális 03:00, 05:00 (korábbi reggeli mérés), 15:00 vagy 21:00 legyen.")
    save(args.output_dir, cutoff, report(cutoff))


if __name__ == "__main__":
    main()
