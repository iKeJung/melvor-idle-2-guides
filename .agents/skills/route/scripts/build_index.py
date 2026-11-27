#!/usr/bin/env python3
"""Build the offline guide index from validated local metadata. Standard library only."""
import argparse
import json
import re
import sys
from datetime import date
from html import escape
from html.parser import HTMLParser
from pathlib import Path


class GuideHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.anchors = []
        self.has_title = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.has_title |= tag == "title"
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if tag == "a" and attrs.get("href", "").startswith("#"):
            self.anchors.append(attrs["href"][1:])


def read_guides(root):
    library = (root / "guides").resolve()
    if not library.is_dir():
        raise ValueError(f"Library not found: {library}")
    guides = []
    seen = set()
    for path in sorted(library.rglob("metadata.json")):
        if not path.resolve().is_relative_to(library):
            raise ValueError(f"Metadata outside the library: {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or type(data.get("schema_version")) is not int or data["schema_version"] != 2:
            raise ValueError(f"Invalid schema: {path}")
        for field in ("id", "game", "skill", "slug", "title", "summary", "updated_on", "status", "artifact", "calculations"):
            if not isinstance(data.get(field), str) or not data[field].strip():
                raise ValueError(f"Invalid required field '{field}': {path}")
        if data["game"] != "Melvor Idle 2":
            raise ValueError(f"Game is outside the library scope: {path}")
        slug = data["slug"]
        start, end = data.get("level_start"), data.get("level_end")
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
            raise ValueError(f"Invalid slug: {path}")
        if type(start) is not int or type(end) is not int or not 1 <= start < end:
            raise ValueError(f"Invalid level range: {path}")
        expected_id = f"{slug}-{start}-{end}"
        expected_dir = library / slug / f"{start}-{end}"
        if path.parent != expected_dir or data["id"] != expected_id:
            raise ValueError(f"ID or directory does not match skill/range: {path}")
        if expected_id in seen:
            raise ValueError(f"Duplicate guide: {expected_id}")
        seen.add(expected_id)
        if data["status"] not in {"reference", "validated", "partial"}:
            raise ValueError(f"Invalid status: {path}")
        if date.fromisoformat(data["updated_on"]).isoformat() != data["updated_on"]:
            raise ValueError(f"Invalid date: {path}")
        tags = data.get("tags", [])
        if not isinstance(tags, list) or any(not isinstance(t, str) or not t.strip() for t in tags):
            raise ValueError(f"Invalid tags: {path}")
        for field, name in (("artifact", "guide.html"), ("calculations", "calculations.json")):
            target = path.parent / name
            if data[field] != name or not target.is_file() or not target.resolve().is_relative_to(library):
                raise ValueError(f"Missing or invalid required file: {target}")
        calculations = json.loads((path.parent / "calculations.json").read_text(encoding="utf-8"))
        if not isinstance(calculations, dict) or not calculations:
            raise ValueError(f"Calculations must be a nonempty JSON object: {path}")
        if calculations.get("guide_id") != expected_id:
            raise ValueError(f"Calculations belong to another guide or have no guide_id: {path}")
        html = GuideHTML()
        html.feed((path.parent / "guide.html").read_text(encoding="utf-8"))
        if not html.has_title or len(html.ids) != len(set(html.ids)) or set(html.anchors) - set(html.ids):
            raise ValueError(f"Invalid title or internal navigation: {path}")
        record = dict(data)
        record["artifact"] = (path.parent / "guide.html").relative_to(library).as_posix()
        record["calculations"] = (path.parent / "calculations.json").relative_to(library).as_posix()
        record["metadata"] = path.relative_to(library).as_posix()
        guides.append(record)
    registered_dirs = {library / g["slug"] / f"{g['level_start']}-{g['level_end']}" for g in guides}
    for artifact in library.rglob("guide.html"):
        if artifact.parent not in registered_dirs:
            raise ValueError(f"Guide has no catalog metadata: {artifact}")
    return sorted(guides, key=lambda g: (g["skill"].casefold(), g["level_start"], g["level_end"]))


def render_index(guides):
    statuses = {"reference": "Calculated reference", "validated": "Validated on a character", "partial": "Partial analysis"}
    options = "".join(f'<option value="{escape(s, quote=True)}">{escape(s)}</option>' for s in sorted({g["skill"] for g in guides}))
    cards = []
    for g in guides:
        tags = "".join(f'<span class="tag">{escape(t)}</span>' for t in g.get("tags", []))
        search = " ".join([g["title"], g["skill"], g["summary"], *g.get("tags", [])])
        cards.append(f'''<article class="card" data-skill="{escape(g['skill'], quote=True)}" data-search="{escape(search, quote=True)}">
  <div class="label">{escape(g['skill'])} · levels {g['level_start']}–{g['level_end']}</div>
  <h2><a href="{escape(g['artifact'], quote=True)}">{escape(g['title'])}</a></h2>
  <p>{escape(g['summary'])}</p><div class="tags">{tags}</div>
  <p class="meta">Updated on {date.fromisoformat(g['updated_on']).isoformat()} · {statuses[g['status']]}</p>
  <div class="links"><a href="{escape(g['artifact'], quote=True)}">Open guide →</a><a href="{escape(g['calculations'], quote=True)}">Calculations JSON</a></div>
</article>''')
    return '''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Route library · Melvor Idle 2</title>
<style>
:root{color-scheme:dark;--bg:#10161c;--panel:#19232c;--line:#34444f;--text:#e6edf0;--muted:#acbdc7;--accent:#93dfb3}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:16px/1.6 system-ui,sans-serif}main{max-width:1080px;margin:auto;padding:48px 24px}h1{font-size:clamp(2rem,5vw,3.2rem);line-height:1.15;margin:12px 0 20px}h2{font-size:1.35rem;line-height:1.3}a{color:var(--accent);text-underline-offset:3px}.eyebrow,.label{color:var(--accent);font-size:.8rem;font-weight:700;letter-spacing:.08em}.intro,.meta{color:var(--muted)}.intro{max-width:760px}.filters{display:flex;gap:16px;flex-wrap:wrap;margin:30px 0 10px}.filters label{display:flex;flex-direction:column;gap:6px;flex:1;min-width:200px;font-size:.85rem}input,select{background:var(--panel);color:var(--text);border:1px solid var(--line);border-radius:8px;padding:12px;font:inherit}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,320px),1fr));gap:18px;margin:24px 0}.card{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:24px}.card h2 a{text-decoration:none}.card p{font-size:.95rem}.tags,.links{display:flex;gap:10px;flex-wrap:wrap}.tag{font-size:.75rem;border:1px solid var(--line);padding:3px 8px;border-radius:20px}.card .meta{font-size:.8rem;margin-top:22px}.links{justify-content:space-between;font-size:.88rem}.how{border-top:1px solid var(--line);padding-top:22px;margin-top:36px}code{color:var(--accent)}[hidden]{display:none!important}:focus-visible{outline:3px solid var(--accent);outline-offset:3px}@media(max-width:600px){main{padding:28px 18px}.card{padding:18px}}@media print{:root{color-scheme:light;--bg:white;--panel:#f3f5f4;--text:#17221c;--muted:#45564b;--line:#ccd3cf;--accent:#17653e}.filters{display:none}.card{break-inside:avoid}}
</style></head><body><main>
<header><div class="eyebrow">MELVOR IDLE 2 · PROJECT GUIDES</div><h1>Route library</h1>
<p class="intro">Browse guides by skill and level range. Each route explains materials, preparation time, assumptions, and sources; calculations are stored alongside the guide.</p></header>
<div class="filters"><label>Search by name, material, or term<input id="search" type="search" placeholder="E.g. Fletching, gathering, base rates"></label>
<label>Skill<select id="skill"><option value="">All skills</option>''' + options + '''</select></label></div>
<p id="count" class="meta" role="status">''' + str(len(guides)) + ''' guide(s) available</p>
<div class="grid">''' + "\n".join(cards) + '''</div><p id="empty" hidden>No guides found. Try another term or skill.</p>
<section class="how"><h2>Create a new guide</h2><p>Ask <code>Use $route</code>: provide the skill and starting/target levels when prompted. You can also ask directly: <code>Create a Woodcutting route from level 10 to 50</code>.</p>
<p class="intro">The guide is saved in <code>guides/&lt;skill&gt;/&lt;start&gt;-&lt;end&gt;/</code> and added to this index. New analyses of the same range update the existing guide.</p>
<p><a href="../.agents/skills/route/SKILL.md">Route skill instructions</a> · <a href="catalog.json">Catalog JSON</a></p></section>
<footer class="meta"><p>Offline reference, no server required. External sources need a connection. Index generated from metadata.json files; edit the records and run the builder to update it.</p></footer>
</main><script>
const search=document.getElementById('search'),skill=document.getElementById('skill'),cards=Array.from(document.querySelectorAll('.card'));
const normalize=text=>text.normalize('NFD').replace(/[\\u0300-\\u036f]/g,'').toLowerCase();
function filter(){const terms=normalize(search.value).trim().split(/\\s+/).filter(Boolean);let count=0;for(const card of cards){const text=normalize(card.dataset.search);const visible=(!skill.value||card.dataset.skill===skill.value)&&terms.every(term=>text.includes(term));card.hidden=!visible;if(visible)count++;}document.getElementById('count').textContent=count+' guide(s) found';document.getElementById('empty').hidden=count!==0;}
search.addEventListener('input',filter);skill.addEventListener('change',filter);
</script></body></html>
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[4], help="Project root")
    parser.add_argument("--check", action="store_true", help="Validate without writing; fail if the index is out of date")
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        guides = read_guides(root)
        outputs = {
            root / "guides" / "catalog.json": json.dumps({"schema_version": 2, "guides": guides}, ensure_ascii=False, indent=2) + "\n",
            root / "guides" / "index.html": render_index(guides),
        }
        for path in outputs:
            if path.is_symlink() or not path.resolve().is_relative_to((root / "guides").resolve()):
                raise ValueError(f"Invalid destination: {path}")
        if args.check:
            stale = [str(p) for p, content in outputs.items() if not p.is_file() or p.read_text(encoding="utf-8") != content]
            if stale:
                raise ValueError("Missing or outdated index: " + ", ".join(stale))
        else:
            for path, content in outputs.items():
                path.write_text(content, encoding="utf-8", newline="\n")
        print(f"OK: {len(guides)} guide(s); library {'validated' if args.check else 'updated'} at {root / 'guides'}")
        return 0
    except (ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
