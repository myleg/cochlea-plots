#!/usr/bin/env python3
"""
Simple, thesis-friendly Streamlit multiview generator.

This app generates side-by-side galleries directly from the PNG folder structure
under `plots/`, without needing the long custom HTML/index generation pipeline.

Quick use:
1) Interactive Streamlit viewer:
   streamlit run streamlit_multiview_simple.py
2) One-off static HTML export:
   python streamlit_multiview_simple.py --export-html
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

SCRIPT_DIR = Path(__file__).resolve().parent
PLOTS_ROOT = SCRIPT_DIR.parent
MODE_LABELS = {
    "Toxic vs Nontoxic": "toxic_vs_nontoxic",
    "Chemo vs No Chemo (Toxic only)": "chemo_vs_no_chemo_toxic",
    "Chemo vs No Chemo (Nontoxic only)": "chemo_vs_no_chemo_nontoxic",
}
ROOTS = {
    "toxic_vs_nontoxic": (("toxic",), ("nontoxic",), "Toxic", "Nontoxic"),
    "chemo_vs_no_chemo_toxic": (("toxic", "chemo"), ("toxic", "no chemo"), "Chemo", "No Chemo"),
    "chemo_vs_no_chemo_nontoxic": (("nontoxic", "chemo"), ("nontoxic", "no chemo"), "Chemo", "No Chemo"),
}

CSS = """body{font-family:Segoe UI,Arial,sans-serif;margin:12px;background:#0b0f14;color:#e8eef6}
h1{font-size:20px;margin:0 0 8px 0} .meta{color:#9fb0c3;font-size:12px;margin-bottom:10px}
a{color:#9ecbff}.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;align-items:start}
.pane{background:#111824;border:1px solid #2a3546;border-radius:10px;padding:10px}.pane h2{font-size:16px;margin:0 0 8px 0}
.tiles{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:8px}
.card{margin:0;border:1px solid #2a3546;background:#0f1520;border-radius:8px;overflow:hidden}
.card img{width:100%;height:auto;display:block;cursor:zoom-in}.card figcaption{padding:6px 8px;font-size:12px;word-break:break-word;color:#d6e2ef}
.empty{color:#e07a7a;font-weight:700;padding:14px;border:1px solid #3b2028;background:#221317;border-radius:8px}
@media (max-width:1000px){.grid{grid-template-columns:1fr;}}
.img-modal{position:fixed;inset:0;background:rgba(0,0,0,.88);display:none;z-index:99999;align-items:center;justify-content:center;padding:20px}
.img-modal.open{display:flex}.img-modal-img{max-width:96vw;max-height:90vh;width:auto;height:auto;display:block;box-shadow:0 16px 40px rgba(0,0,0,.55);border:1px solid rgba(255,255,255,.18);background:#0b0f14}
.img-modal-close{position:absolute;top:12px;right:16px;border:1px solid rgba(255,255,255,.35);background:rgba(20,20,20,.65);color:#fff;font-size:28px;line-height:1;padding:2px 10px;border-radius:8px;cursor:pointer}
.img-modal-cap{position:absolute;left:20px;right:20px;bottom:10px;color:#e8eef6;font-size:13px;text-align:center;text-shadow:0 1px 2px rgba(0,0,0,.8);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}"""

JS = """(function(){
  const modal=document.getElementById('imgModal'),img=document.getElementById('imgModalImg'),cap=document.getElementById('imgModalCap'),btn=document.getElementById('imgModalClose');
  if(!modal||!img||!btn)return;
  const close=()=>{modal.classList.remove('open');modal.setAttribute('aria-hidden','true');img.removeAttribute('src');cap.textContent='';};
  const open=(src,alt)=>{if(!src)return;img.src=src;img.alt=alt||'Expanded plot';cap.textContent=alt||'';modal.classList.add('open');modal.setAttribute('aria-hidden','false');};
  document.querySelectorAll('.card img').forEach((el)=>el.addEventListener('click',(e)=>{e.preventDefault();e.stopPropagation();open(el.getAttribute('src')||'',el.getAttribute('alt')||'');}));
  btn.addEventListener('click',close);modal.addEventListener('click',(e)=>{if(e.target===modal)close();});window.addEventListener('keydown',(e)=>{if(e.key==='Escape')close();});
})();"""


def pngs(folder: Path) -> list[Path]:
    return sorted((p for p in folder.iterdir() if p.is_file() and p.suffix.lower() == ".png"), key=lambda p: p.name.lower()) if folder.exists() else []


def roots(mode: str, base: Path) -> tuple[Path, Path, str, str]:
    lparts, rparts, llabel, rlabel = ROOTS[mode]
    return base.joinpath(*lparts), base.joinpath(*rparts), llabel, rlabel


def common_dtypes(left: Path, right: Path) -> list[str]:
    lset = {p.name for p in left.iterdir() if p.is_dir()} if left.exists() else set()
    rset = {p.name for p in right.iterdir() if p.is_dir()} if right.exists() else set()
    return sorted(lset & rset)


def file_url(path: Path) -> str:
    s = path.resolve().as_posix()
    if s.startswith("/mnt/") and len(s) > 6 and s[5].isalpha() and s[6] == "/":
        s = f"{s[5].upper()}:{s[6:]}"
    return "file:///" + quote(s, safe="/:()[]@!$&'*,;=._-+")


def sha(paths: list[Path]) -> str:
    h = hashlib.sha256()
    for p in paths:
        st = p.stat()
        h.update(f"{p.name}|{st.st_size}|{int(st.st_mtime)}".encode("utf-8"))
    return h.hexdigest()


def summary(mode: str, dtype: str, left_label: str, right_label: str, left: list[Path], right: list[Path]) -> dict:
    return {
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "mode": mode,
        "dtype": dtype,
        "left_label": left_label,
        "right_label": right_label,
        "left_count": len(left),
        "right_count": len(right),
        "left_fingerprint_sha256": sha(left),
        "right_fingerprint_sha256": sha(right),
        "left_folder": str(left[0].parent) if left else "",
        "right_folder": str(right[0].parent) if right else "",
    }


def legacy_titles(mode: str, dtype: str) -> tuple[str, str]:
    if mode == "chemo_vs_no_chemo_nontoxic":
        return f"Nontoxic Chemo vs No Chemo {dtype}", f"Nontoxic Chemo vs No Chemo: {dtype}"
    if mode == "chemo_vs_no_chemo_toxic":
        return f"Toxic Chemo vs No Chemo {dtype}", f"Toxic Chemo vs No Chemo: {dtype}"
    return f"Toxic vs Nontoxic {dtype}", f"Toxic vs Nontoxic: {dtype}"


def cards(images: list[Path]) -> str:
    if not images:
        return "<div class='empty'>No images found.</div>"
    return "\n".join(
        f"<figure class='card'><img src='{html.escape(file_url(p))}' alt='{html.escape(p.name)}'><figcaption>{html.escape(p.name)}</figcaption></figure>"
        for p in images
    )


def write_html(mode: str, dtype: str, left_label: str, right_label: str, left: list[Path], right: list[Path], plots_root: Path, out_path: Path) -> None:
    title_tag, heading = legacy_titles(mode, dtype)
    back = file_url(plots_root / "toxic_htmls" / "MULTIVIEW__TOXIC_VS_NONTOXIC__INDEX.html")
    toc = file_url(plots_root / "htmls" / "MULTIVIEW__MASTER_INDEX.html")
    out = f"""<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>{html.escape(title_tag)}</title><style>{CSS}</style></head><body>
<h1>{html.escape(heading)}</h1>
<div class='meta'>{html.escape(left_label)}={len(left)} | {html.escape(right_label)}={len(right)}</div>
<div class='meta'><a href='{html.escape(back)}'>Back to index</a> | <a href='{html.escape(toc)}'>TOC</a></div>
<div class='grid'><section class='pane'><h2>{html.escape(left_label)}</h2><div class='tiles'>{cards(left)}</div></section>
<section class='pane'><h2>{html.escape(right_label)}</h2><div class='tiles'>{cards(right)}</div></section></div>
<div id='imgModal' class='img-modal' aria-hidden='true'><button type='button' id='imgModalClose' class='img-modal-close' aria-label='Close'>&times;</button>
<img id='imgModalImg' class='img-modal-img' alt='Expanded plot'><div id='imgModalCap' class='img-modal-cap'></div></div>
<script>{JS}</script></body></html>"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(out, encoding="utf-8")


def run_self_test(plots_root: Path) -> int:
    mode = "toxic_vs_nontoxic"
    left_root, right_root, left_label, right_label = roots(mode, plots_root)
    dtypes = common_dtypes(left_root, right_root)
    if not dtypes:
        print("No common dtypes found.")
        return 1
    left, right = pngs(left_root / dtypes[0]), pngs(right_root / dtypes[0])
    print(json.dumps(summary(mode, dtypes[0], left_label, right_label, left, right), indent=2))
    return 0


def run_streamlit(plots_root: Path) -> None:
    import streamlit as st

    st.set_page_config(page_title="Simple Cochlea Multiview", layout="wide")
    st.title("Simple Cochlea Multiview (Streamlit)")
    st.caption("Lightweight reproducible generator from PNG folders.")
    mode_name = st.sidebar.selectbox("Comparison", list(MODE_LABELS.keys()))
    mode = MODE_LABELS[mode_name]
    left_root, right_root, left_label, right_label = roots(mode, plots_root)
    dtypes = common_dtypes(left_root, right_root)
    if not dtypes:
        st.error(f"No shared plot types found between:\n- {left_root}\n- {right_root}")
        st.stop()
    dtype = st.sidebar.selectbox("Plot type", dtypes)
    left, right = pngs(left_root / dtype), pngs(right_root / dtype)
    st.subheader(dtype.replace("_", " "))
    st.write(f"{left_label}: **{len(left)}** images | {right_label}: **{len(right)}** images")
    c1, c2 = st.columns(2)
    for col, label, items in ((c1, left_label, left), (c2, right_label, right)):
        with col:
            st.markdown(f"### {label}")
            cols = st.columns(3)
            for i, p in enumerate(items):
                with cols[i % 3]:
                    st.image(str(p), caption=p.name, use_container_width=True)
    meta = summary(mode, dtype, left_label, right_label, left, right)
    st.markdown("---")
    st.markdown("#### Reproducibility Summary")
    st.json(meta, expanded=False)
    st.download_button("Download summary JSON", data=json.dumps(meta, indent=2), file_name=f"simple_streamlit_summary__{mode}__{dtype}.json", mime="application/json")


def export_html(mode: str, dtype: str, plots_root: Path, out_html: Path) -> int:
    left_root, right_root, left_label, right_label = roots(mode, plots_root)
    left, right = pngs(left_root / dtype), pngs(right_root / dtype)
    write_html(mode, dtype, left_label, right_label, left, right, plots_root, out_html)
    print(json.dumps(summary(mode, dtype, left_label, right_label, left, right), indent=2))
    print(f"Wrote HTML: {out_html}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--self-test", action="store_true")
    p.add_argument("--export-html", action="store_true")
    p.add_argument("--mode", default="chemo_vs_no_chemo_nontoxic")
    p.add_argument("--dtype", default="Clean_Dose_minus_Dirty_Dose_vs_Total_Dose")
    p.add_argument("--plots-root", type=Path, default=PLOTS_ROOT)
    p.add_argument("--out-html", type=Path, default=SCRIPT_DIR / "sample_multiview_from_simple_streamlit.html")
    a = p.parse_args()
    plots_root = a.plots_root.resolve()
    if a.self_test:
        return run_self_test(plots_root)
    if a.export_html:
        return export_html(a.mode, a.dtype, plots_root, a.out_html.resolve())
    run_streamlit(plots_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
