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
    library = (root / "guias").resolve()
    if not library.is_dir():
        raise ValueError(f"Biblioteca não encontrada: {library}")
    guides = []
    seen = set()
    for path in sorted(library.rglob("metadados.json")):
        if not path.resolve().is_relative_to(library):
            raise ValueError(f"Metadados fora da biblioteca: {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or type(data.get("schema_version")) is not int or data["schema_version"] != 1:
            raise ValueError(f"Schema inválido: {path}")
        for field in ("id", "game", "skill", "slug", "title", "summary", "updated_on", "status", "artifact", "calculations"):
            if not isinstance(data.get(field), str) or not data[field].strip():
                raise ValueError(f"Campo obrigatório inválido '{field}': {path}")
        if data["game"] != "Melvor Idle 2":
            raise ValueError(f"Jogo diferente do escopo da biblioteca: {path}")
        slug = data["slug"]
        start, end = data.get("level_start"), data.get("level_end")
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
            raise ValueError(f"Slug inválido: {path}")
        if type(start) is not int or type(end) is not int or not 1 <= start < end:
            raise ValueError(f"Intervalo de níveis inválido: {path}")
        expected_id = f"{slug}-{start}-{end}"
        expected_dir = library / slug / f"{start}-{end}"
        if path.parent != expected_dir or data["id"] != expected_id:
            raise ValueError(f"ID ou diretório não corresponde à habilidade/faixa: {path}")
        if expected_id in seen:
            raise ValueError(f"Guia duplicado: {expected_id}")
        seen.add(expected_id)
        if data["status"] not in {"referencia", "validado", "parcial"}:
            raise ValueError(f"Status inválido: {path}")
        if date.fromisoformat(data["updated_on"]).isoformat() != data["updated_on"]:
            raise ValueError(f"Data inválida: {path}")
        tags = data.get("tags", [])
        if not isinstance(tags, list) or any(not isinstance(t, str) or not t.strip() for t in tags):
            raise ValueError(f"Tags inválidas: {path}")
        for field, name in (("artifact", "guia.html"), ("calculations", "calculos.json")):
            target = path.parent / name
            if data[field] != name or not target.is_file() or not target.resolve().is_relative_to(library):
                raise ValueError(f"Arquivo obrigatório ausente ou inválido: {target}")
        calculations = json.loads((path.parent / "calculos.json").read_text(encoding="utf-8"))
        if not isinstance(calculations, dict) or not calculations:
            raise ValueError(f"Cálculos devem ser um objeto JSON não vazio: {path}")
        if calculations.get("guide_id") != expected_id:
            raise ValueError(f"Cálculos pertencem a outro guia ou não têm guide_id: {path}")
        html = GuideHTML()
        html.feed((path.parent / "guia.html").read_text(encoding="utf-8"))
        if not html.has_title or len(html.ids) != len(set(html.ids)) or set(html.anchors) - set(html.ids):
            raise ValueError(f"Título ou navegação interna inválidos: {path}")
        record = dict(data)
        record["artifact"] = (path.parent / "guia.html").relative_to(library).as_posix()
        record["calculations"] = (path.parent / "calculos.json").relative_to(library).as_posix()
        record["metadata"] = path.relative_to(library).as_posix()
        guides.append(record)
    registered_dirs = {library / g["slug"] / f"{g['level_start']}-{g['level_end']}" for g in guides}
    for artifact in library.rglob("guia.html"):
        if artifact.parent not in registered_dirs:
            raise ValueError(f"Guia sem metadados no catálogo: {artifact}")
    return sorted(guides, key=lambda g: (g["skill"].casefold(), g["level_start"], g["level_end"]))


def render_index(guides):
    statuses = {"referencia": "Referência calculada", "validado": "Validado no personagem", "parcial": "Análise parcial"}
    options = "".join(f'<option value="{escape(s, quote=True)}">{escape(s)}</option>' for s in sorted({g["skill"] for g in guides}))
    cards = []
    for g in guides:
        tags = "".join(f'<span class="tag">{escape(t)}</span>' for t in g.get("tags", []))
        search = " ".join([g["title"], g["skill"], g["summary"], *g.get("tags", [])])
        cards.append(f'''<article class="card" data-skill="{escape(g['skill'], quote=True)}" data-search="{escape(search, quote=True)}">
  <div class="label">{escape(g['skill'])} · níveis {g['level_start']}–{g['level_end']}</div>
  <h2><a href="{escape(g['artifact'], quote=True)}">{escape(g['title'])}</a></h2>
  <p>{escape(g['summary'])}</p><div class="tags">{tags}</div>
  <p class="meta">Revisado em {date.fromisoformat(g['updated_on']).strftime('%d/%m/%Y')} · {statuses[g['status']]}</p>
  <div class="links"><a href="{escape(g['artifact'], quote=True)}">Abrir guia →</a><a href="{escape(g['calculations'], quote=True)}">Cálculos JSON</a></div>
</article>''')
    return '''<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Biblioteca de rotas · Melvor Idle 2</title>
<style>
:root{color-scheme:dark;--bg:#10161c;--panel:#19232c;--line:#34444f;--text:#e6edf0;--muted:#acbdc7;--accent:#93dfb3}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:16px/1.6 system-ui,sans-serif}main{max-width:1080px;margin:auto;padding:48px 24px}h1{font-size:clamp(2rem,5vw,3.2rem);line-height:1.15;margin:12px 0 20px}h2{font-size:1.35rem;line-height:1.3}a{color:var(--accent);text-underline-offset:3px}.eyebrow,.label{color:var(--accent);font-size:.8rem;font-weight:700;letter-spacing:.08em}.intro,.meta{color:var(--muted)}.intro{max-width:760px}.filters{display:flex;gap:16px;flex-wrap:wrap;margin:30px 0 10px}.filters label{display:flex;flex-direction:column;gap:6px;flex:1;min-width:200px;font-size:.85rem}input,select{background:var(--panel);color:var(--text);border:1px solid var(--line);border-radius:8px;padding:12px;font:inherit}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,320px),1fr));gap:18px;margin:24px 0}.card{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:24px}.card h2 a{text-decoration:none}.card p{font-size:.95rem}.tags,.links{display:flex;gap:10px;flex-wrap:wrap}.tag{font-size:.75rem;border:1px solid var(--line);padding:3px 8px;border-radius:20px}.card .meta{font-size:.8rem;margin-top:22px}.links{justify-content:space-between;font-size:.88rem}.how{border-top:1px solid var(--line);padding-top:22px;margin-top:36px}code{color:var(--accent)}[hidden]{display:none!important}:focus-visible{outline:3px solid var(--accent);outline-offset:3px}@media(max-width:600px){main{padding:28px 18px}.card{padding:18px}}@media print{:root{color-scheme:light;--bg:white;--panel:#f3f5f4;--text:#17221c;--muted:#45564b;--line:#ccd3cf;--accent:#17653e}.filters{display:none}.card{break-inside:avoid}}
</style></head><body><main>
<header><div class="eyebrow">MELVOR IDLE 2 · GUIAS DO PROJETO</div><h1>Biblioteca de rotas</h1>
<p class="intro">Consulte guias por habilidade e faixa de níveis. Cada rota explica materiais, tempo de preparação, hipóteses e fontes; os cálculos ficam ao lado do artefato.</p></header>
<div class="filters"><label>Buscar por nome, material ou termo<input id="search" type="search" placeholder="Ex.: Fletching, coleta, taxas base"></label>
<label>Habilidade<select id="skill"><option value="">Todas as habilidades</option>''' + options + '''</select></label></div>
<p id="count" class="meta" role="status">''' + str(len(guides)) + ''' guia(s) disponível(is)</p>
<div class="grid">''' + "\n".join(cards) + '''</div><p id="empty" hidden>Nenhum guia encontrado. Tente outro termo ou habilidade.</p>
<section class="how"><h2>Criar um novo guia</h2><p>Peça <code>Use $rota</code>: informe a habilidade e os níveis inicial e final quando solicitado. Você também pode pedir diretamente <code>Crie uma rota de Woodcutting do 10 ao 50</code>.</p>
<p class="intro">O guia é salvo em <code>guias/&lt;habilidade&gt;/&lt;inicio&gt;-&lt;fim&gt;/</code> e adicionado a este índice. Novas análises da mesma faixa atualizam o guia existente.</p>
<p><a href="../.agents/skills/rota/SKILL.md">Instruções da skill rota</a> · <a href="catalogo.json">Catálogo JSON</a></p></section>
<footer class="meta"><p>Consulta offline, sem servidor. As fontes externas exigem conexão. Índice gerado dos arquivos metadados.json; edite os registros e execute o gerador para atualizar.</p></footer>
</main><script>
const search=document.getElementById('search'),skill=document.getElementById('skill'),cards=Array.from(document.querySelectorAll('.card'));
const normalize=text=>text.normalize('NFD').replace(/[\\u0300-\\u036f]/g,'').toLowerCase();
function filter(){const terms=normalize(search.value).trim().split(/\\s+/).filter(Boolean);let count=0;for(const card of cards){const text=normalize(card.dataset.search);const visible=(!skill.value||card.dataset.skill===skill.value)&&terms.every(term=>text.includes(term));card.hidden=!visible;if(visible)count++;}document.getElementById('count').textContent=count+' guia(s) encontrado(s)';document.getElementById('empty').hidden=count!==0;}
search.addEventListener('input',filter);skill.addEventListener('change',filter);
</script></body></html>
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[4], help="Raiz do projeto")
    parser.add_argument("--check", action="store_true", help="Valida sem escrever; falha se o índice estiver desatualizado")
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        guides = read_guides(root)
        outputs = {
            root / "guias" / "catalogo.json": json.dumps({"schema_version": 1, "guides": guides}, ensure_ascii=False, indent=2) + "\n",
            root / "guias" / "index.html": render_index(guides),
        }
        for path in outputs:
            if path.is_symlink() or not path.resolve().is_relative_to((root / "guias").resolve()):
                raise ValueError(f"Destino inválido: {path}")
        if args.check:
            stale = [str(p) for p, content in outputs.items() if not p.is_file() or p.read_text(encoding="utf-8") != content]
            if stale:
                raise ValueError("Índice ausente ou desatualizado: " + ", ".join(stale))
        else:
            for path, content in outputs.items():
                path.write_text(content, encoding="utf-8", newline="\n")
        print(f"OK: {len(guides)} guia(s); biblioteca {'validada' if args.check else 'atualizada'} em {root / 'guias'}")
        return 0
    except (ValueError, OSError) as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
