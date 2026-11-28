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
        if "range_label" in data and (not isinstance(data["range_label"], str) or not data["range_label"].strip()):
            raise ValueError(f"Invalid optional field 'range_label': {path}")
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
    topics = sorted({g["skill"] for g in guides})
    options = "\n".join(f'            <option value="{escape(topic)}">{escape(topic)}</option>' for topic in topics)
    cards = []
    for g in guides:
        title = escape(g["title"])
        artifact = escape(g["artifact"])
        updated = date.fromisoformat(g["updated_on"]).isoformat()
        level_range = g.get("range_label", f"Levels {g['level_start']}–{g['level_end']}")
        search = " ".join([g["title"], g["skill"], level_range, g["summary"], *g.get("tags", [])])
        cards.append(f'''      <article class="card" data-topic="{escape(g['skill'])}" data-search="{escape(search)}">
        <header>
          <h2>{title}</h2>
          <p class="range">{escape(level_range)}</p>
        </header>
        <p class="summary">{escape(g['summary'])}</p>
        <footer class="card-footer">
          <p class="meta">Updated on <time datetime="{updated}">{updated}</time> · {statuses[g['status']]}</p>
          <div class="links">
            <a class="guide-link" href="{artifact}" aria-label="Open guide: {title}">Open guide</a>
            <a href="{escape(g['calculations'])}" aria-label="View calculations for {title} (JSON)">View calculations</a>
          </div>
        </footer>
      </article>''')
    count = f"{len(guides)} {'guide' if len(guides) == 1 else 'guides'} available"
    empty_attributes = ' hidden' if guides else ''
    empty_message = 'Try a different search term or choose another topic.' if guides else 'No guides are available yet.'
    return '''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Route library · Melvor Idle 2</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #10161c;
      --panel: #19232c;
      --field: #151e25;
      --line: #34444f;
      --control-line: #5c7380;
      --text: #e6edf0;
      --muted: #acbdc7;
      --accent: #93dfb3;
      --accent-hover: #b5edca;
      --accent-pressed: #7fc89e;
      --on-accent: #12271d;
    }
    *, *::before, *::after { box-sizing: border-box; }
    [hidden] { display: none !important; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font: 1rem/1.6 system-ui, sans-serif;
      overflow-wrap: anywhere;
    }
    ::selection { color: var(--on-accent); background: var(--accent); }
    main {
      max-width: 70rem;
      margin-inline: auto;
      padding: clamp(2rem, 6vw, 5rem) clamp(1.125rem, 4vw, 2.5rem) 2.5rem;
    }
    h1, h2, p { margin: 0; }
    h1 {
      font-size: clamp(2.5rem, 6vw, 4.5rem);
      font-weight: 750;
      line-height: 1.06;
      letter-spacing: -0.035em;
    }
    h2 {
      font-size: clamp(1.25rem, 2.4vw, 1.5rem);
      line-height: 1.25;
      letter-spacing: -0.02em;
      text-wrap: pretty;
    }
    a { color: var(--accent); text-underline-offset: 0.22em; }
    a:hover { color: var(--accent-hover); }
    :focus-visible { outline: 2px solid var(--accent); outline-offset: 4px; }
    .intro, .summary, .meta { color: var(--muted); }
    .intro { max-width: 66ch; margin-top: 1rem; }
    .library {
      border-top: 1px solid var(--line);
      margin-top: clamp(1.5rem, 4vw, 2.5rem);
      padding-top: clamp(1.25rem, 3vw, 1.75rem);
    }
    .filters {
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(10rem, 15rem);
      gap: 1rem;
    }
    .filters label {
      display: grid;
      gap: 0.375rem;
      font-size: 0.875rem;
      font-weight: 600;
    }
    input, select {
      width: 100%;
      min-width: 0;
      min-height: 3rem;
      border: 1px solid var(--control-line);
      border-radius: 0.5rem;
      padding: 0.625rem 0.75rem;
      background: var(--field);
      color: var(--text);
      font: 400 1rem/1.4 system-ui, sans-serif;
    }
    input { caret-color: var(--accent); }
    input::placeholder { color: var(--muted); opacity: 1; }
    select { cursor: pointer; }
    input:hover, select:hover { border-color: var(--muted); }
    .meta { font-size: 0.875rem; }
    .filter-status {
      display: flex;
      align-items: center;
      flex-wrap: wrap;
      justify-content: space-between;
      gap: 0 0.75rem;
      min-height: 2.75rem;
      margin-block: 0.375rem 0.5rem;
    }
    #count { font-variant-numeric: tabular-nums; }
    #clear-filters {
      min-height: 2.75rem;
      padding: 0;
      border: 0;
      background: transparent;
      color: var(--accent);
      font: 600 0.875rem/1.4 system-ui, sans-serif;
      text-decoration: underline;
      text-underline-offset: 0.22em;
      cursor: pointer;
    }
    #clear-filters:hover { color: var(--accent-hover); }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(min(100%, 21rem), 1fr));
      gap: clamp(0.875rem, 2vw, 1.25rem);
    }
    .card {
      display: flex;
      flex-direction: column;
      gap: 0.75rem;
      min-width: 0;
      padding: clamp(1rem, 2.5vw, 1.75rem);
      border: 1px solid var(--line);
      border-radius: 0.875rem;
      background: var(--panel);
    }
    .range { margin-top: 0.375rem; color: var(--accent); font-size: 0.875rem; font-weight: 650; }
    .summary { font-size: 0.975rem; }
    .card-footer { margin-top: auto; padding-top: 0.5rem; }
    .card-footer .meta {
      border-top: 1px solid var(--line);
      padding-top: 0.875rem;
      margin-bottom: 0.75rem;
    }
    time { font-variant-numeric: tabular-nums; }
    .links {
      display: flex;
      align-items: center;
      flex-wrap: wrap;
      gap: 0.375rem 1rem;
      font-size: 0.875rem;
    }
    .links a {
      display: inline-flex;
      align-items: center;
      min-height: 2.75rem;
    }
    .guide-link {
      border-radius: 0.5rem;
      padding: 0.5rem 0.875rem;
      background: var(--accent);
      color: var(--on-accent);
      font-weight: 700;
      text-decoration: none;
    }
    .guide-link:hover { background: var(--accent-hover); color: var(--on-accent); }
    .guide-link:active { background: var(--accent-pressed); }
    #empty {
      border: 1px solid var(--line);
      border-radius: 0.875rem;
      padding: 1.25rem;
      background: var(--panel);
      color: var(--muted);
    }
    .page-footer {
      border-top: 1px solid var(--line);
      margin-top: 1rem;
      padding-top: 1rem;
    }
    .page-footer p { max-width: 74ch; }
    @media (max-width: 33rem) {
      .filters { grid-template-columns: 1fr; gap: 0.75rem; }
    }
    @media print {
      :root {
        color-scheme: light;
        --bg: #fff;
        --panel: #fff;
        --field: #f3f5f4;
        --text: #17221c;
        --muted: #45564b;
        --line: #ccd3cf;
        --accent: #17653e;
      }
      main { padding: 0; }
      .filters, #clear-filters { display: none; }
      .card { break-inside: avoid; }
      .links a { min-height: auto; }
      .guide-link { padding: 0; background: transparent; color: var(--accent); text-decoration: underline; }
    }
  </style>
</head>
<body>
  <main>
    <header>
      <h1>Route library</h1>
      <p class="intro">Find Melvor Idle 2 guides for leveling skills or earning GP. See what each route requires and how its estimates were calculated.</p>
    </header>
    <section class="library" aria-label="Browse guides">
      <div class="filters" role="search" aria-label="Filter guides" hidden>
        <label for="search">Search by name, material, or term
          <input id="search" type="search" placeholder="Fletching, feathers, base rates">
        </label>
        <label for="topic">Topic
          <select id="topic">
            <option value="">All topics</option>
''' + options + '''
          </select>
        </label>
      </div>
      <div class="filter-status">
        <p id="count" class="meta" role="status">''' + count + '''</p>
        <button id="clear-filters" type="button" hidden>Clear filters</button>
      </div>
      <div class="grid">
''' + "\n".join(cards) + '''
      </div>
      <p id="empty"''' + empty_attributes + '''>''' + empty_message + '''</p>
    </section>
    <footer class="page-footer meta">
      <p>Guides work offline. External sources need a connection. <a href="catalog.json">View guide catalog (JSON)</a></p>
    </footer>
  </main>
  <script>
    const search = document.getElementById('search');
    const topic = document.getElementById('topic');
    const clearFilters = document.getElementById('clear-filters');
    const count = document.getElementById('count');
    const empty = document.getElementById('empty');
    const normalize = text => text.normalize('NFD')
      .replace(/[\\u0300-\\u036f]/g, '')
      .toLowerCase()
      .replace(/\\p{P}+/gu, ' ');
    const cards = Array.from(document.querySelectorAll('.card'), card => ({
      element: card,
      topic: card.dataset.topic,
      text: normalize(card.dataset.search),
    }));

    function filter() {
      const terms = normalize(search.value).trim().split(/\\s+/).filter(Boolean);
      const selectedTopic = topic.value;
      let matches = 0;
      for (const card of cards) {
        const matchesTopic = !selectedTopic || card.topic === selectedTopic;
        const visible = matchesTopic && terms.every(term => card.text.includes(term));
        card.element.hidden = !visible;
        if (visible) matches++;
      }
      const noun = matches === 1 ? 'guide' : 'guides';
      const state = selectedTopic || terms.length ? 'found' : 'available';
      count.textContent = `${matches} ${noun} ${state}`;
      empty.hidden = matches !== 0;
      clearFilters.hidden = !selectedTopic && !search.value;
    }

    if (cards.length > 0) {
      search.addEventListener('input', filter);
      topic.addEventListener('change', filter);
      clearFilters.addEventListener('click', () => {
        search.value = '';
        topic.value = '';
        search.focus();
        filter();
      });
      window.addEventListener('pageshow', filter);
      document.querySelector('.filters').hidden = false;
    }
  </script>
</body>
</html>
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
