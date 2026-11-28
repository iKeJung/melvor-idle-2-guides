"""Package the validated guide library for GitHub Pages."""

import argparse
import json
import re
import shutil
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit, urlunsplit


ROOT = Path(__file__).resolve().parents[1]
GUIDES = ROOT / "guides"
LINK = re.compile(r'''(?P<prefix>\bhref\s*=\s*(?P<quote>["']))(?P<url>.*?)(?P=quote)''', re.IGNORECASE)


def link_to_repository(html, source, source_url, published):
    def replace(match):
        link = urlsplit(match["url"])
        if not link.path or link.scheme or link.netloc or link.path.startswith("/"):
            return match[0]

        target = (source.parent / unquote(link.path)).resolve()
        if target in published:
            return match[0]
        if target.is_relative_to(GUIDES) or not target.is_relative_to(ROOT) or not target.is_file():
            raise ValueError(f"Broken link in {source.relative_to(ROOT)}: {match['url']}")

        path = quote(target.relative_to(ROOT).as_posix())
        base = urlsplit(f"{source_url}/{path}")
        url = urlunsplit((base.scheme, base.netloc, base.path, link.query, link.fragment))
        return f'{match["prefix"]}{url}{match["quote"]}'

    return LINK.sub(replace, html)


def build(output, source_url):
    catalog = json.loads((GUIDES / "catalog.json").read_text(encoding="utf-8"))
    paths = ["index.html", "catalog.json"]
    paths.extend(guide[field] for guide in catalog["guides"] for field in ("artifact", "calculations", "metadata"))
    published = {GUIDES / path for path in paths}

    output.mkdir(parents=True)
    for source in sorted(published):
        if not source.resolve().is_relative_to(GUIDES) or source.resolve() != source or not source.is_file():
            raise ValueError(f"Invalid public guide file: {source}")
        destination = output / source.relative_to(GUIDES)
        destination.parent.mkdir(parents=True, exist_ok=True)

        if source.suffix == ".html":
            html = link_to_repository(source.read_text(encoding="utf-8"), source, source_url, published)
            destination.write_text(html, encoding="utf-8", newline="\n")
        elif source.name == "calculations.json":
            calculations = json.loads(source.read_text(encoding="utf-8"))
            if "snapshot" in calculations:
                raise ValueError(f"Character snapshot in public calculations: {source}")
            calculations.pop("personalization", None)
            content = json.dumps(calculations, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
            destination.write_text(content, encoding="utf-8", newline="\n")
        else:
            shutil.copyfile(source, destination)

    print(f"Built the public site with {len(catalog['guides'])} guide(s) at {output}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="New directory for the Pages artifact")
    parser.add_argument("--source-url", required=True, help="GitHub blob URL for this revision, without a file path")
    args = parser.parse_args()
    try:
        build(args.output, args.source_url.rstrip("/"))
    except (OSError, ValueError) as error:
        parser.exit(1, f"Could not build Pages site: {error}\n")


if __name__ == "__main__":
    main()
