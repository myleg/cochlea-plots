import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, unquote
import html

PLOTS_ROOT = Path(r"C:\Users\SJAGABAT\OneDrive - University of Oklahoma\Desktop\ionpg cochlea data\dirty dose\plots").resolve()
HTML_ROOT = PLOTS_ROOT / "htmls"
MANIFEST = HTML_ROOT / "manifest.json"
MASTER_INDEX = HTML_ROOT / "MULTIVIEW__MASTER_INDEX.html"
TVN_INDEX = HTML_ROOT / "toxic_htmls" / "INDEX_MULTIVIEW__TOXIC_VS_NONTOXIC.html"
CHEMO_INDEX = HTML_ROOT / "chemo_htmls" / "INDEX_MULTIVIEW__CHEMO_VS_NO_CHEMO.html"


def file_url(p: Path) -> str:
    return "file:///" + quote(p.resolve().as_posix(), safe="/:()[]@!$&'*,;=._-+")


def dtype_from_name(name: str) -> str:
    n = name.replace('.html', '')
    n = re.sub(r'^MULTIVIEW__', '', n)
    n = n.replace('__toxic_vs_nontoxic', '')
    n = n.replace('__chemo_vs_no_chemo', '')
    n = n.replace('NONTOXIC__', '')
    n = n.replace('TOXIC__', '')
    return n


def collect_pages() -> dict:
    tvn = sorted(PLOTS_ROOT.rglob("MULTIVIEW__*__toxic_vs_nontoxic.html"), key=lambda p: p.name.lower())
    tox_chemo = sorted(PLOTS_ROOT.rglob("MULTIVIEW__TOXIC__*__chemo_vs_no_chemo.html"), key=lambda p: p.name.lower())
    non_chemo = sorted(PLOTS_ROOT.rglob("MULTIVIEW__NONTOXIC__*__chemo_vs_no_chemo.html"), key=lambda p: p.name.lower())

    def pack(group: str, subgroup: str, pages: list[Path]):
        rows = []
        for p in pages:
            rows.append({
                "group": group,
                "subgroup": subgroup,
                "dtype": dtype_from_name(p.name),
                "name": p.name,
                "path": str(p),
                "rel": p.relative_to(PLOTS_ROOT).as_posix(),
                "url": file_url(p),
            })
        return rows

    all_rows = []
    all_rows += pack("toxic_vs_nontoxic", "all", tvn)
    all_rows += pack("chemo_vs_no_chemo", "toxic", tox_chemo)
    all_rows += pack("chemo_vs_no_chemo", "nontoxic", non_chemo)
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "plots_root": str(PLOTS_ROOT),
        "html_root": str(HTML_ROOT),
        "indexes": {
            "master": str(MASTER_INDEX),
            "toxic_vs_nontoxic": str(TVN_INDEX),
            "chemo_vs_no_chemo": str(CHEMO_INDEX),
        },
        "pages": all_rows,
    }


def write_manifest(data: dict):
    HTML_ROOT.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(data, indent=2), encoding="utf-8")


def li(rows: list[dict]) -> str:
    if not rows:
        return "<li class='empty'>(none)</li>"
    out = []
    for r in rows:
        out.append(
            f"<li><a href='{html.escape(r['url'])}'>{html.escape(r['dtype'].replace('_', ' '))}</a>"
            f"<span class='rel'>{html.escape(r['rel'])}</span></li>"
        )
    return "\n".join(out)


def write_indexes(data: dict):
    pages = data["pages"]
    tvn = [r for r in pages if r["group"] == "toxic_vs_nontoxic"]
    chemo_t = [r for r in pages if r["group"] == "chemo_vs_no_chemo" and r["subgroup"] == "toxic"]
    chemo_n = [r for r in pages if r["group"] == "chemo_vs_no_chemo" and r["subgroup"] == "nontoxic"]

    css = (
        "body{font-family:Segoe UI,Arial,sans-serif;margin:20px;background:#0b0f14;color:#e8eef6;}"
        "a{color:#9ecbff;text-decoration:none;}a:hover{text-decoration:underline;}"
        ".card{background:#111824;border:1px solid #2a3546;border-radius:10px;padding:14px;margin-bottom:14px;}"
        ".small{color:#9fb0c3;font-size:12px}.rel{display:block;color:#90a0b3;font-size:11px;word-break:break-all}"
        ".grid2{display:grid;grid-template-columns:1fr 1fr;gap:12px}.empty{color:#e07a7a}"
        "@media(max-width:1000px){.grid2{grid-template-columns:1fr}}"
    )

    MASTER_INDEX.write_text(
        f"""<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Multiview Master Index</title><style>{css}</style></head><body>
<div class='card'><h1>Multiview Master Index</h1></div>
<div class='card'><h2>Toxic vs Nontoxic</h2><ul>{li(tvn)}</ul></div>
<div class='card'><h2>Chemo vs No Chemo</h2><div class='grid2'><div><h3>Toxic</h3><ul>{li(chemo_t)}</ul></div><div><h3>Nontoxic</h3><ul>{li(chemo_n)}</ul></div></div></div>
</body></html>""",
        encoding='utf-8'
    )

    TVN_INDEX.parent.mkdir(parents=True, exist_ok=True)
    TVN_INDEX.write_text(
        f"""<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Toxic vs Nontoxic Index</title><style>{css}</style></head><body>
<div class='card'><h1>Toxic vs Nontoxic Index</h1><p><a href='{html.escape(file_url(MASTER_INDEX))}'>Open Master Index</a></p><ul>{li(tvn)}</ul></div>
</body></html>""",
        encoding='utf-8'
    )

    CHEMO_INDEX.parent.mkdir(parents=True, exist_ok=True)
    CHEMO_INDEX.write_text(
        f"""<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Chemo vs No Chemo Index</title><style>{css}</style></head><body>
<div class='card'><h1>Chemo vs No Chemo Index</h1><p><a href='{html.escape(file_url(MASTER_INDEX))}'>Open Master Index</a></p>
<div class='grid2'><div><h3>Toxic</h3><ul>{li(chemo_t)}</ul></div><div><h3>Nontoxic</h3><ul>{li(chemo_n)}</ul></div></div>
</div></body></html>""",
        encoding='utf-8'
    )


def rewrite_relative_links_to_absolute():
    all_files = [p.resolve() for p in PLOTS_ROOT.rglob('*') if p.is_file()]
    by_name = {}
    for p in all_files:
        by_name.setdefault(p.name.lower(), []).append(p)

    def fallback(base_name: str):
        b = base_name.lower()
        if "table_of_contents" in b:
            return MASTER_INDEX if MASTER_INDEX.exists() else None
        if "master_index" in b:
            return MASTER_INDEX if MASTER_INDEX.exists() else None
        if "toxic_vs_nontoxic" in b and "index" in b:
            return TVN_INDEX if TVN_INDEX.exists() else None
        if "chemo" in b and "index" in b:
            return CHEMO_INDEX if CHEMO_INDEX.exists() else None
        return None

    def resolve(cur: Path, raw: str):
        v = html.unescape(raw).strip()
        if not v:
            return None
        lv = v.lower()
        if lv.startswith(('file:///', 'http://', 'https://', 'data:', 'javascript:', '#')):
            return None
        base = unquote(v.split('#', 1)[0].split('?', 1)[0])

        c1 = (cur.parent / base).resolve()
        if c1.exists():
            return c1
        c2 = (PLOTS_ROOT / base).resolve()
        if c2.exists():
            return c2

        name = Path(base).name.lower()
        cands = by_name.get(name, [])
        if len(cands) == 1:
            return cands[0]

        fb = fallback(name)
        if fb is not None and fb.exists():
            return fb
        return None

    rx = re.compile(r"\b(src|href)\s*=\s*(['\"])(.*?)\2", re.IGNORECASE)
    changed_files = 0
    changed_links = 0

    for h in PLOTS_ROOT.rglob('*.html'):
        txt = h.read_text(encoding='utf-8', errors='replace')
        c = [0]

        def sub(m):
            attr, q, val = m.group(1), m.group(2), m.group(3)
            t = resolve(h, val)
            if t is None:
                return m.group(0)
            c[0] += 1
            return f"{attr}={q}{file_url(t)}{q}"

        out = rx.sub(sub, txt)
        if out != txt:
            h.write_text(out, encoding='utf-8', errors='replace')
            changed_files += 1
            changed_links += c[0]
    return changed_files, changed_links


def main():
    data = collect_pages()
    write_manifest(data)
    write_indexes(data)
    changed_files, changed_links = rewrite_relative_links_to_absolute()

    print(f"Manifest: {MANIFEST}")
    print(f"Pages indexed: {len(data['pages'])}")
    print(f"TVN pages: {sum(1 for p in data['pages'] if p['group']=='toxic_vs_nontoxic')}")
    print(f"Chemo toxic pages: {sum(1 for p in data['pages'] if p['group']=='chemo_vs_no_chemo' and p['subgroup']=='toxic')}")
    print(f"Chemo nontoxic pages: {sum(1 for p in data['pages'] if p['group']=='chemo_vs_no_chemo' and p['subgroup']=='nontoxic')}")
    print(f"Links rewritten absolute: files={changed_files}, links={changed_links}")


if __name__ == "__main__":
    main()


