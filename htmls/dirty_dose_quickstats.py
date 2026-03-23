#!/usr/bin/env python3
"""
Quick dirty-dose cohort stats from voxel CSV files.

Outputs:
1) Ear-level feature table (per CSV)
2) MWU summary table (toxic vs nontoxic)
3) Console summary for fast thesis write-up
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu, spearmanr


REQUIRED_COLS = [
    "AbsVolume_cm3",
    "BeamSet FractionDose (cGy)",
    "J2 Clean dose (cGy)",
    "J2 Dirty fraction",
    "J2 Dirty dose (cGy)",
    "LETd proton (keV/um)",
]


def infer_toxic_label(path: Path) -> int | None:
    p = str(path).replace("\\", "/")
    if "/Toxic/" in p:
        return 1
    if "/Nontoxic/" in p:
        return 0
    return None


def weighted_mean(x: pd.Series, w: pd.Series) -> float:
    denom = float(w.sum())
    return float((x * w).sum() / denom) if denom > 0 else float(x.mean())


def dose_at_volume_cc(values: pd.Series, vols_cc: pd.Series, cc: float = 0.035) -> float:
    temp = pd.DataFrame({"v": values.astype(float), "cc": vols_cc.astype(float)})
    temp = temp.sort_values("v", ascending=False)
    cum = temp["cc"].cumsum()
    hit = temp.loc[cum >= cc, "v"]
    return float(hit.iloc[0]) if len(hit) else float(temp["v"].iloc[-1])


def compute_features(csv_path: Path) -> dict | None:
    toxic = infer_toxic_label(csv_path)
    if toxic is None:
        return None

    df = pd.read_csv(csv_path)
    if df.empty:
        return None
    if not all(c in df.columns for c in REQUIRED_COLS):
        return None

    w = df["AbsVolume_cm3"].astype(float)
    if float(w.sum()) <= 0:
        w = pd.Series(np.ones(len(df)), index=df.index)

    total = df["BeamSet FractionDose (cGy)"].astype(float)
    clean = df["J2 Clean dose (cGy)"].astype(float)
    dirty = df["J2 Dirty dose (cGy)"].astype(float)
    dfrac = df["J2 Dirty fraction"].astype(float)
    letd = df["LETd proton (keV/um)"].astype(float)

    return {
        "file": csv_path.name,
        "path": str(csv_path),
        "toxic": toxic,
        "nvox": int(len(df)),
        "mean_total_cGy": weighted_mean(total, w),
        "mean_clean_cGy": weighted_mean(clean, w),
        "mean_dirty_cGy": weighted_mean(dirty, w),
        "mean_dirty_frac": weighted_mean(dfrac, w),
        "mean_letd": weighted_mean(letd, w),
        "d0035_total_cGy": dose_at_volume_cc(total, w, cc=0.035),
        "d0035_dirty_cGy": dose_at_volume_cc(dirty, w, cc=0.035),
        "d0035_letd": dose_at_volume_cc(letd, w, cc=0.035),
        "v_dirtyfrac_ge_0p3": float(w[dfrac >= 0.3].sum() / w.sum()),
        "v_dirtydose_ge_300": float(w[dirty >= 300.0].sum() / w.sum()),
        "v_letd_ge_5": float(w[letd >= 5.0].sum() / w.sum()),
        "v_totaldose_ge_500": float(w[total >= 500.0].sum() / w.sum()),
    }


def dedupe_sum_files(files: Iterable[Path]) -> list[Path]:
    grouped: dict[tuple[int | None, str], Path] = {}
    for f in files:
        key = (infer_toxic_label(f), f.name)
        grouped.setdefault(key, f)
    return list(grouped.values())


def mwu_summary(df: pd.DataFrame) -> pd.DataFrame:
    features = [c for c in df.columns if c not in {"file", "path", "toxic"}]
    n_toxic = int((df["toxic"] == 1).sum())
    n_nontoxic = int((df["toxic"] == 0).sum())

    rows = []
    for feat in features:
        t = df.loc[df["toxic"] == 1, feat].astype(float)
        n = df.loc[df["toxic"] == 0, feat].astype(float)
        if len(t) == 0 or len(n) == 0:
            continue

        res = mannwhitneyu(t, n, alternative="two-sided")
        u = float(res.statistic)
        p = float(res.pvalue)
        auc = u / (n_toxic * n_nontoxic) if n_toxic and n_nontoxic else np.nan
        auc = max(auc, 1 - auc) if np.isfinite(auc) else np.nan
        rank_biserial = (2 * u / (n_toxic * n_nontoxic) - 1) if n_toxic and n_nontoxic else np.nan

        rows.append(
            {
                "feature": feat,
                "mwu_pvalue": p,
                "auc_like_effect": auc,
                "rank_biserial_signed": rank_biserial,
                "toxic_median": float(np.median(t)),
                "nontoxic_median": float(np.median(n)),
                "median_delta_toxic_minus_nontoxic": float(np.median(t) - np.median(n)),
            }
        )

    out = pd.DataFrame(rows).sort_values("mwu_pvalue", ascending=True)
    return out.reset_index(drop=True)


def run_once(files: list[Path], outdir: Path, tag: str) -> None:
    feats = [compute_features(f) for f in files]
    feats = [x for x in feats if x is not None]
    if not feats:
        print(f"[{tag}] No usable files.")
        return

    feat_df = pd.DataFrame(feats)
    stats_df = mwu_summary(feat_df)

    feat_path = outdir / f"dirty_dose_features_{tag}.csv"
    stats_path = outdir / f"dirty_dose_mwu_{tag}.csv"
    feat_df.to_csv(feat_path, index=False)
    stats_df.to_csv(stats_path, index=False)

    rho, rho_p = spearmanr(feat_df["mean_letd"], feat_df["mean_dirty_frac"])
    n_toxic = int((feat_df["toxic"] == 1).sum())
    n_nontoxic = int((feat_df["toxic"] == 0).sum())

    print(f"\n[{tag}] rows={len(feat_df)} toxic={n_toxic} nontoxic={n_nontoxic}")
    print(f"[{tag}] saved features: {feat_path}")
    print(f"[{tag}] saved MWU:      {stats_path}")
    print(f"[{tag}] Spearman(mean_letd, mean_dirty_frac): rho={rho:.4f}, p={rho_p:.4g}")
    print(f"[{tag}] Top MWU features:")
    for _, r in stats_df.head(8).iterrows():
        print(
            f"  - {r['feature']}: p={r['mwu_pvalue']:.4f}, "
            f"delta={r['median_delta_toxic_minus_nontoxic']:.4f}, auc={r['auc_like_effect']:.3f}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Dirty-dose quick stats for thesis-ready summaries.")
    parser.add_argument(
        "--csv-root",
        type=Path,
        default=Path(
            "/mnt/c/Users/sjaga/OneDrive - University of Oklahoma/OUHSC MedPhys/Research/COCHLEA/"
            "sj colossus cochlea research/ionpg cochlea data/dirty dose/csvs"
        ),
        help="Root folder containing dirty-dose CSV files.",
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=Path.cwd() / "dirty_dose_quickstats_out",
        help="Output directory for summary CSV files.",
    )
    parser.add_argument(
        "--scope",
        choices=["sum", "all"],
        default="sum",
        help="Use only SUM files (recommended) or all CSV files.",
    )
    parser.add_argument(
        "--mode",
        choices=["dedupe", "raw", "both"],
        default="both",
        help="dedupe: one row per (tox class, SUM filename), raw: every matched file, both: run both.",
    )
    args = parser.parse_args()

    if not args.csv_root.exists():
        raise FileNotFoundError(f"CSV root not found: {args.csv_root}")
    args.outdir.mkdir(parents=True, exist_ok=True)

    files = sorted(args.csv_root.rglob("*.csv"))
    if args.scope == "sum":
        files = [f for f in files if "/SUM/" in str(f).replace("\\", "/") and "__SUM__" in f.name]
    files = [f for f in files if infer_toxic_label(f) is not None]
    print(f"Discovered CSV files after filters: {len(files)}")

    if args.mode in {"dedupe", "both"}:
        run_once(dedupe_sum_files(files), args.outdir, "dedupe")
    if args.mode in {"raw", "both"}:
        run_once(files, args.outdir, "raw")


if __name__ == "__main__":
    main()
