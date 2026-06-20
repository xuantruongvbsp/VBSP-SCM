"""So sánh số liệu giữa 2 kỳ snapshot bất kỳ."""
from __future__ import annotations

import streamlit as st
import pandas as pd
from streamlit.delta_generator import DeltaGenerator

from auth import normalize_role, la_phan_he_pgd
from utils import fmt_ty, fmt_so, vn, lazy_expander as _lazy_expander
from tabs.base_tab import TabContext
from state_manager import SCMStateManager
from snapshot_service import (
    danh_sach_ky, doc_snapshot,
    danh_sach_ky_nq11, doc_nq11_snapshot,
    danh_sach_ky_gqvl, doc_gqvl_snapshot,
    danh_sach_ky_cdtotkvv, doc_cdtotkvv_snapshot,
)
from tabs.tab_so_sanh_ky._common import (
    delta_str, pct_change_str, fmt_pct_vn, tl_nqh,
    render_kpi_row, render_quality_bars_2_ky,
    render_comparison_table, render_hbar_chart,
)
from tabs.tab_so_sanh_ky._export import (
    render_export_ui, build_excel_sheets_pgd,
)
import plotly.graph_objects as go


# ─── AGGREGATE ──────────────────────────────────────────────────────────

def _agg(df: pd.DataFrame) -> dict:
    zero = {k: 0.0 for k in
            ["tong_du_no", "du_no_th", "du_no_qh", "du_no_khoanh", "so_ho", "so_ku", "gn_nam"]}
    if df is None or df.empty:
        return zero
    return {
        "tong_du_no":   float(df["tong_du_no"].sum()),
        "du_no_th":     float(df["du_no_th"].sum()),
        "du_no_qh":     float(df["du_no_qh"].sum()),
        "du_no_khoanh": float(df["du_no_khoanh"].sum()),
        "so_ho":        float(df["so_ho"].sum()),
        "so_ku":        float(df["so_ku"].sum()),
        "gn_nam":       float(df["gn_nam"].sum()),
    }


# ─── KY SELECTOR ────────────────────────────────────────────────────────

def _ky_selector(
    ds: list, ky1: str, ky2: str, prefix: str,
    label: str = "",
) -> tuple[str, str] | None:
    lbl = f"{label} " if label else ""
    available_ky1 = ky1 if ky1 in ds else (ds[min(1, len(ds) - 1)] if len(ds) > 1 else ds[0])
    available_ky2 = ky2 if ky2 in ds else ds[0]
    if available_ky1 == available_ky2:
        available_ky1 = ds[min(1, len(ds) - 1)]
        available_ky2 = ds[0]
    col_k1, col_k2 = st.columns(2)
    sel_k1 = col_k1.selectbox(
        f"📅 {lbl}— Kỳ 1", ds,
        index=ds.index(available_ky1) if available_ky1 in ds else min(1, len(ds) - 1),
        key=f"ss2k_{prefix}_ky1",
        help="Kỳ dùng làm mốc so sánh",
    )
    sel_k2 = col_k2.selectbox(
        f"📅 {lbl}— Kỳ 2", ds,
        index=ds.index(available_ky2) if available_ky2 in ds else 0,
        key=f"ss2k_{prefix}_ky2",
        help="Kỳ muốn đánh giá biến động",
    )
    if sel_k1 == sel_k2:
        st.warning("⚠️ Vui lòng chọn 2 kỳ khác nhau.")
        return None
    return sel_k1, sel_k2


# ─── SECTION 1: KPI ─────────────────────────────────────────────────────

def _render_kpi(agg1: dict, agg2: dict, ky1: str, ky2: str) -> None:
    tl1 = tl_nqh(agg1["du_no_qh"], agg1["tong_du_no"])
    tl2 = tl_nqh(agg2["du_no_qh"], agg2["tong_du_no"])

    def _ty(x): return vn(x / 1e9, 3) + " tỷ"

    render_kpi_row([
        {"label": "💰 Tổng dư nợ", "value": _ty(agg2["tong_du_no"]),
         "delta": agg2["tong_du_no"] - agg1["tong_du_no"], "unit": "ty",
         "help": f"Kỳ {ky1}: {_ty(agg1['tong_du_no'])}"},
        {"label": "⚠️ Dư nợ quá hạn", "value": _ty(agg2["du_no_qh"]),
         "delta": agg2["du_no_qh"] - agg1["du_no_qh"], "unit": "ty", "inverse": True,
         "help": f"Kỳ {ky1}: {_ty(agg1['du_no_qh'])}"},
        {"label": "🔒 Dư nợ khoanh", "value": _ty(agg2["du_no_khoanh"]),
         "delta": agg2["du_no_khoanh"] - agg1["du_no_khoanh"], "unit": "ty", "inverse": True,
         "help": f"Kỳ {ky1}: {_ty(agg1['du_no_khoanh'])}"},
        {"label": "📊 Tỷ lệ NQH", "value": fmt_pct_vn(tl2),
         "delta": tl2 - tl1, "unit": "pct", "inverse": True,
         "help": f"Kỳ {ky1}: {fmt_pct_vn(tl1)}"},
    ])

    # Hàng 2 — số lượng
    render_kpi_row([
        {"label": "👥 Số hộ vay", "value": fmt_so(int(agg2["so_ho"])),
         "delta": agg2["so_ho"] - agg1["so_ho"], "unit": "so",
         "help": f"Kỳ {ky1}: {fmt_so(int(agg1['so_ho']))}"},
        {"label": "📋 Số khế ước", "value": fmt_so(int(agg2["so_ku"])),
         "delta": agg2["so_ku"] - agg1["so_ku"], "unit": "so",
         "help": f"Kỳ {ky1}: {fmt_so(int(agg1['so_ku']))}"},
        {"label": "💵 Giải ngân trong năm", "value": _ty(agg2["gn_nam"]),
         "delta": agg2["gn_nam"] - agg1["gn_nam"], "unit": "ty",
         "help": f"Kỳ {ky1}: {_ty(agg1['gn_nam'])}"},
        {"label": "", "value": "", "delta": None},
    ])

    # Quality bars
    render_quality_bars_2_ky(
        f"Kỳ {ky1}", agg1["tong_du_no"], agg1["du_no_th"],
        agg1["du_no_qh"], agg1["du_no_khoanh"],
        f"Kỳ {ky2}", agg2["tong_du_no"], agg2["du_no_th"],
        agg2["du_no_qh"], agg2["du_no_khoanh"],
    )


# ─── SECTION 2: CHI TIET ────────────────────────────────────────────────

def _render_bang_chi_tiet(agg1: dict, agg2: dict, ky1: str, ky2: str) -> None:
    tl1 = tl_nqh(agg1["du_no_qh"], agg1["tong_du_no"])
    tl2 = tl_nqh(agg2["du_no_qh"], agg2["tong_du_no"])
    rows = [
        ("Tổng dư nợ (triệu đồng)",      agg1["tong_du_no"],   agg2["tong_du_no"],   False, "tien"),
        ("Dư nợ trong hạn (triệu đồng)", agg1["du_no_th"],     agg2["du_no_th"],     False, "tien"),
        ("Dư nợ quá hạn (triệu đồng)",   agg1["du_no_qh"],     agg2["du_no_qh"],     True,  "tien"),
        ("Dư nợ khoanh (triệu đồng)",    agg1["du_no_khoanh"], agg2["du_no_khoanh"], True,  "tien"),
        ("Tỷ lệ NQH (%)",                tl1,                  tl2,                  True,  "pct"),
        ("Số hộ vay",                    agg1["so_ho"],        agg2["so_ho"],        False, "so"),
        ("Số khế ước",                   agg1["so_ku"],        agg2["so_ku"],        False, "so"),
        ("Giải ngân trong năm (triệu đồng)", agg1["gn_nam"],       agg2["gn_nam"],       False, "tien"),
    ]
    render_comparison_table(rows, ky1, ky2, title="Chỉ tiêu")


# ─── PGD TABLE ──────────────────────────────────────────────────────────

def _render_bang_pgd(df1: pd.DataFrame, df2: pd.DataFrame,
                     ky1: str, ky2: str) -> None:
    m1 = df1[["ten_pgd", "tong_du_no", "du_no_qh", "so_ho"]].rename(columns={
        "tong_du_no": "dn1", "du_no_qh": "nqh1", "so_ho": "ho1",
    })
    m2 = df2[["ten_pgd", "tong_du_no", "du_no_qh", "so_ho"]].rename(columns={
        "tong_du_no": "dn2", "du_no_qh": "nqh2", "so_ho": "ho2",
    })
    jn = pd.merge(m1, m2, on="ten_pgd", how="outer").fillna(0)
    for col in ["dn1", "dn2", "nqh1", "nqh2", "ho1", "ho2"]:
        if col in jn.columns:
            jn[col] = pd.to_numeric(jn[col], errors="coerce").fillna(0)
    jn["delta_dn"]  = jn["dn2"]  - jn["dn1"]
    jn["delta_nqh"] = jn["nqh2"] - jn["nqh1"]
    jn["delta_ho"]  = jn["ho2"]  - jn["ho1"]
    jn["tl_nqh1"] = (jn["nqh1"] / jn["dn1"].replace(0, float("nan")) * 100).fillna(0.0)
    jn["tl_nqh2"] = (jn["nqh2"] / jn["dn2"].replace(0, float("nan")) * 100).fillna(0.0)

    tong = {
        "ten_pgd": "⬛ Tổng Chi nhánh",
        "dn1": jn["dn1"].sum(), "dn2": jn["dn2"].sum(),
        "delta_dn": jn["delta_dn"].sum(),
        "nqh1": jn["nqh1"].sum(), "nqh2": jn["nqh2"].sum(),
        "delta_nqh": jn["delta_nqh"].sum(),
        "ho1": jn["ho1"].sum(), "ho2": jn["ho2"].sum(),
        "delta_ho": jn["delta_ho"].sum(),
        "tl_nqh1": jn["nqh1"].sum() / jn["dn1"].sum() * 100 if jn["dn1"].sum() else 0,
        "tl_nqh2": jn["nqh2"].sum() / jn["dn2"].sum() * 100 if jn["dn2"].sum() else 0,
    }
    jn = pd.concat([jn.sort_values("delta_dn", ascending=False),
                    pd.DataFrame([tong])], ignore_index=True)

    def _row_to_html(r):
        is_tong = str(r["ten_pgd"]).startswith("⬛")
        bold = "font-weight:700;" if is_tong else ""
        bg = "var(--surface-hi,rgba(46,125,50,0.08))" if is_tong else ""
        cl_dn = f"class='delta-pos'" if r["delta_dn"] >= 0 else f"class='delta-neg'"
        cl_nqh = f"class='delta-pos'" if r["tl_nqh2"] - r["tl_nqh1"] <= 0 else f"class='delta-neg'"
        return (
            f"<tr style='border-bottom:1px solid var(--border,#e5e7eb);background:{bg}'>"
            f"<td style='padding:7px 10px;{bold}'>{r['ten_pgd']}</td>"
            f"<td style='padding:7px 10px;text-align:right'>{fmt_ty(r['dn1'])}</td>"
            f"<td style='padding:7px 10px;text-align:right;{bold}'>{fmt_ty(r['dn2'])}</td>"
            f"<td style='padding:7px 10px;text-align:right' {cl_dn}><strong>{delta_str(r['delta_dn'],'tien')}</strong></td>"
            f"<td style='padding:7px 10px;text-align:right;{bold}'>{fmt_pct_vn(r['tl_nqh1'])}</td>"
            f"<td style='padding:7px 10px;text-align:right;{bold}'>{fmt_pct_vn(r['tl_nqh2'])}</td>"
            f"<td style='padding:7px 10px;text-align:right' {cl_nqh}><strong>{delta_str(r['tl_nqh2']-r['tl_nqh1'],'pct')}</strong></td>"
            f"<td style='padding:7px 10px;text-align:right'>{fmt_so(int(r['ho2']))}</td>"
            f"<td style='padding:7px 10px;text-align:right' {cl_dn}>{delta_str(r['delta_ho'],'so')}</td>"
            f"</tr>"
        )

    rows_html = "".join(jn.apply(_row_to_html, axis=1))
    st.markdown(
        f"""<div style="overflow-x:auto;border-radius:8px;border:1px solid var(--border,#e5e7eb)">
        <table style="width:100%;border-collapse:collapse;font-size:0.85rem">
          <thead>
            <tr style="background:var(--surface-hi,#1e3a5f);color:var(--text-head,white)">
              <th style="padding:9px 10px;text-align:left">Đơn vị</th>
              <th style="padding:9px 10px;text-align:right">DN kỳ {ky1}</th>
              <th style="padding:9px 10px;text-align:right">DN kỳ {ky2}</th>
              <th style="padding:9px 10px;text-align:right">Δ Dư nợ</th>
              <th style="padding:9px 10px;text-align:right">NQH% {ky1}</th>
              <th style="padding:9px 10px;text-align:right">NQH% {ky2}</th>
              <th style="padding:9px 10px;text-align:right">Δ NQH%</th>
              <th style="padding:9px 10px;text-align:right">Số hộ {ky2}</th>
              <th style="padding:9px 10px;text-align:right">Δ Hộ</th>
            </tr>
          </thead>
          <tbody>{rows_html}</tbody>
        </table></div>""",
        unsafe_allow_html=True,
    )


# ─── CHART ──────────────────────────────────────────────────────────────

def _render_bieu_do(df1: pd.DataFrame, df2: pd.DataFrame,
                    ky1: str, ky2: str) -> None:
    m1 = df1[["ten_pgd", "tong_du_no"]].rename(columns={"tong_du_no": "dn1"})
    m2 = df2[["ten_pgd", "tong_du_no"]].rename(columns={"tong_du_no": "dn2"})
    jn = pd.merge(m1, m2, on="ten_pgd", how="outer").fillna(0)
    for _c in ["dn1", "dn2"]:
        if _c in jn.columns:
            jn[_c] = pd.to_numeric(jn[_c], errors="coerce").fillna(0)
    jn["delta"] = jn["dn2"] - jn["dn1"]
    jn = jn[~jn["ten_pgd"].str.startswith("__")].sort_values("delta")

    if jn.empty:
        return
    render_hbar_chart(
        labels=jn["ten_pgd"].astype(str).tolist(),
        values=jn["delta"].tolist(),
        title=f"Biến động dư nợ: {ky1} → {ky2}",
        key="ss2k_chart_dn",
    )


# ─── NQ11 SECTION ──────────────────────────────────────────────────────

def _render_nq11_section(ky1: str, ky2: str, pgd_mode: bool, pgd_user: str | None) -> None:
    ds = danh_sach_ky_nq11()
    if len(ds) < 2:
        st.info("ℹ️ Chưa có đủ 2 kỳ NQ11 snapshot.")
        return

    ky_sel = _ky_selector(ds, ky1, ky2, "nq11", label="NQ11")
    if ky_sel is None:
        return
    sel_k1, sel_k2 = ky_sel

    df1 = doc_nq11_snapshot(sel_k1)
    df2 = doc_nq11_snapshot(sel_k2)
    if df1.empty or df2.empty:
        st.warning("⚠️ Một trong hai kỳ NQ11 chưa có dữ liệu snapshot.")
        return

    if pgd_mode and pgd_user:
        df1 = df1[df1["ten_pgd"] == pgd_user].reset_index(drop=True)
        df2 = df2[df2["ten_pgd"] == pgd_user].reset_index(drop=True)
    else:
        df1 = df1[df1["ten_pgd"] == "__CN__"].reset_index(drop=True)
        df2 = df2[df2["ten_pgd"] == "__CN__"].reset_index(drop=True)
    if df1.empty or df2.empty:
        st.info("ℹ️ Không có dữ liệu NQ11 tổng hợp cho kỳ đã chọn.")
        return

    a1 = df1.iloc[0].to_dict()
    a2 = df2.iloc[0].to_dict()

    def _ty(x): return vn(float(x) / 1e9, 3) + " tỷ"
    render_kpi_row([
        {"label": "Tổng dư nợ NQ11", "value": _ty(a2.get("tong_du_no", 0)),
         "delta": float(a2.get("tong_du_no", 0)) - float(a1.get("tong_du_no", 0)), "unit": "ty",
         "help": f"Kỳ {sel_k1}: {_ty(a1.get('tong_du_no', 0))}"},
        {"label": "Nợ quá hạn NQ11", "value": _ty(a2.get("no_qh", 0)),
         "delta": float(a2.get("no_qh", 0)) - float(a1.get("no_qh", 0)), "unit": "ty", "inverse": True,
         "help": f"Kỳ {sel_k1}: {_ty(a1.get('no_qh', 0))}"},
        {"label": "Số khách hàng NQ11", "value": fmt_so(int(a2.get("so_kh", 0))),
         "delta": float(a2.get("so_kh", 0)) - float(a1.get("so_kh", 0)), "unit": "so",
         "help": f"Kỳ {sel_k1}: {fmt_so(int(a1.get('so_kh', 0)))}"},
        {"label": "", "value": "", "delta": None},
    ])

    rows_nq11 = [
        ("Tổng dư nợ NQ11 (triệu đồng)", float(a1.get("tong_du_no", 0)), float(a2.get("tong_du_no", 0)), False, "tien"),
        ("Nợ trong hạn NQ11 (triệu đồng)", float(a1.get("no_th", 0)), float(a2.get("no_th", 0)), False, "tien"),
        ("Nợ quá hạn NQ11 (triệu đồng)", float(a1.get("no_qh", 0)), float(a2.get("no_qh", 0)), True, "tien"),
        ("Giải ngân NQ11 trong năm (triệu đồng)", float(a1.get("gn_nam", 0)), float(a2.get("gn_nam", 0)), False, "tien"),
        ("Số khách hàng NQ11", float(a1.get("so_kh", 0)), float(a2.get("so_kh", 0)), False, "so"),
    ]
    render_comparison_table(rows_nq11, sel_k1, sel_k2, title="Chỉ tiêu NQ11")


# ─── GQVL SECTION ──────────────────────────────────────────────────────

def _render_gqvl_section(ky1: str, ky2: str, pgd_mode: bool, pgd_user: str | None) -> None:
    ds = danh_sach_ky_gqvl()
    if len(ds) < 2:
        st.info("ℹ️ Chưa có đủ 2 kỳ GQVL snapshot.")
        return

    ky_sel = _ky_selector(ds, ky1, ky2, "gqvl", label="GQVL")
    if ky_sel is None:
        return
    sel_k1, sel_k2 = ky_sel

    df1 = doc_gqvl_snapshot(sel_k1)
    df2 = doc_gqvl_snapshot(sel_k2)
    if df1.empty or df2.empty:
        st.warning("⚠️ Một trong hai kỳ GQVL chưa có dữ liệu snapshot.")
        return

    if pgd_mode and pgd_user:
        df1 = df1[df1["ten_pgd"] == pgd_user].reset_index(drop=True)
        df2 = df2[df2["ten_pgd"] == pgd_user].reset_index(drop=True)
    else:
        df1 = df1[df1["ten_pgd"] == "__CN__"].reset_index(drop=True)
        df2 = df2[df2["ten_pgd"] == "__CN__"].reset_index(drop=True)
    if df1.empty or df2.empty:
        st.info("ℹ️ Không có dữ liệu GQVL tổng hợp cho kỳ đã chọn.")
        return

    a1 = df1.iloc[0].to_dict()
    a2 = df2.iloc[0].to_dict()

    def _ty(x): return vn(float(x) / 1e9, 3) + " tỷ"
    render_kpi_row([
        {"label": "DN trong hạn GQVL", "value": _ty(a2.get("dn_th", 0)),
         "delta": float(a2.get("dn_th", 0)) - float(a1.get("dn_th", 0)), "unit": "ty",
         "help": f"Kỳ {sel_k1}: {_ty(a1.get('dn_th', 0))}"},
        {"label": "DN quá hạn GQVL", "value": _ty(a2.get("dn_qh", 0)),
         "delta": float(a2.get("dn_qh", 0)) - float(a1.get("dn_qh", 0)), "unit": "ty", "inverse": True,
         "help": f"Kỳ {sel_k1}: {_ty(a1.get('dn_qh', 0))}"},
        {"label": "DN khoanh GQVL", "value": _ty(a2.get("dn_khoanh", 0)),
         "delta": float(a2.get("dn_khoanh", 0)) - float(a1.get("dn_khoanh", 0)), "unit": "ty", "inverse": True,
         "help": f"Kỳ {sel_k1}: {_ty(a1.get('dn_khoanh', 0))}"},
        {"label": "Giải ngân GQVL", "value": _ty(a2.get("gn_nam", 0)),
         "delta": float(a2.get("gn_nam", 0)) - float(a1.get("gn_nam", 0)), "unit": "ty",
         "help": f"Kỳ {sel_k1}: {_ty(a1.get('gn_nam', 0))}"},
    ])

    rows_gqvl = [
        ("Dư nợ trong hạn (triệu đồng)", float(a1.get("dn_th", 0)), float(a2.get("dn_th", 0)), False, "tien"),
        ("Dư nợ quá hạn (triệu đồng)", float(a1.get("dn_qh", 0)), float(a2.get("dn_qh", 0)), True, "tien"),
        ("Dư nợ khoanh (triệu đồng)", float(a1.get("dn_khoanh", 0)), float(a2.get("dn_khoanh", 0)), True, "tien"),
        ("Giải ngân trong năm (triệu đồng)", float(a1.get("gn_nam", 0)), float(a2.get("gn_nam", 0)), False, "tien"),
        ("Số khách hàng GQVL", float(a1.get("so_kh", 0)), float(a2.get("so_kh", 0)), False, "so"),
    ]
    render_comparison_table(rows_gqvl, sel_k1, sel_k2, title="Chỉ tiêu GQVL")


# ─── CDTOTKVV SECTION ──────────────────────────────────────────────────

def _render_cdtotkvv_section(ky1: str, ky2: str, pgd_mode: bool, pgd_user: str | None) -> None:
    ds = danh_sach_ky_cdtotkvv()
    if len(ds) < 2:
        st.info("ℹ️ Chưa có đủ 2 kỳ Chấm điểm tổ snapshot.")
        return

    ky_sel = _ky_selector(ds, ky1, ky2, "cdt", label="CDTOTKVV")
    if ky_sel is None:
        return
    sel_k1, sel_k2 = ky_sel

    df1 = doc_cdtotkvv_snapshot(sel_k1)
    df2 = doc_cdtotkvv_snapshot(sel_k2)
    if df1.empty or df2.empty:
        st.warning("⚠️ Một trong hai kỳ CDTOTKVV chưa có dữ liệu snapshot.")
        return

    if pgd_mode and pgd_user:
        df1_f = df1[df1["ten_pgd"] == pgd_user].reset_index(drop=True)
        df2_f = df2[df2["ten_pgd"] == pgd_user].reset_index(drop=True)
        if df1_f.empty or df2_f.empty:
            df1_f = df1[df1["ten_pgd"] == "__CN__"].reset_index(drop=True)
            df2_f = df2[df2["ten_pgd"] == "__CN__"].reset_index(drop=True)
        df1, df2 = df1_f, df2_f
    else:
        df1 = df1[df1["ten_pgd"] == "__CN__"].reset_index(drop=True)
        df2 = df2[df2["ten_pgd"] == "__CN__"].reset_index(drop=True)
    if df1.empty or df2.empty:
        st.info("ℹ️ Không có dữ liệu CDTOTKVV tổng hợp cho kỳ đã chọn.")
        return

    a1 = df1.iloc[0].to_dict()
    a2 = df2.iloc[0].to_dict()

    # Row 1: 5 metrics — đầy đủ Tốt / Khá / TB / Yếu
    render_kpi_row([
        {"label": "Tổng số tổ", "value": fmt_so(int(a2.get("so_to", 0))),
         "delta": float(a2.get("so_to", 0)) - float(a1.get("so_to", 0)), "unit": "so"},
        {"label": "Tổ Tốt", "value": fmt_so(int(a2.get("so_tot", 0))),
         "delta": float(a2.get("so_tot", 0)) - float(a1.get("so_tot", 0)), "unit": "so",
         "help": f"Kỳ {sel_k1}: {fmt_so(int(a1.get('so_tot', 0)))}"},
        {"label": "Tổ Khá", "value": fmt_so(int(a2.get("so_kha", 0))),
         "delta": float(a2.get("so_kha", 0)) - float(a1.get("so_kha", 0)), "unit": "so",
         "help": f"Kỳ {sel_k1}: {fmt_so(int(a1.get('so_kha', 0)))}"},
        {"label": "Tổ Trung bình", "value": fmt_so(int(a2.get("so_tb", 0))),
         "delta": float(a2.get("so_tb", 0)) - float(a1.get("so_tb", 0)), "unit": "so", "inverse": True,
         "help": f"Kỳ {sel_k1}: {fmt_so(int(a1.get('so_tb', 0)))}"},
        {"label": "Tổ Yếu", "value": fmt_so(int(a2.get("so_yeu", 0))),
         "delta": float(a2.get("so_yeu", 0)) - float(a1.get("so_yeu", 0)), "unit": "so", "inverse": True,
         "help": f"Kỳ {sel_k1}: {fmt_so(int(a1.get('so_yeu', 0)))}"},
    ])
    # Row 2: Điểm TB — căn giữa
    st.markdown("")  # spacer
    _metric_col = st.columns([1, 2, 1])[1]  # center column
    with _metric_col:
        st.metric(
            "📊 Điểm TB toàn CN / PGD",
            f"{float(a2.get('diem_tb', 0)):.2f}",
            delta=delta_str(float(a2.get("diem_tb", 0)) - float(a1.get("diem_tb", 0)), "pct"),
            help=f"Kỳ {sel_k1}: {float(a1.get('diem_tb', 0)):.2f} điểm",
        )

    cat_rows = [
        ("Tổng số tổ",      float(a1.get("so_to",  0)), float(a2.get("so_to",  0)), False, "so"),
        ("Tổ xếp loại Tốt", float(a1.get("so_tot", 0)), float(a2.get("so_tot", 0)), False, "so"),
        ("Tổ xếp loại Khá", float(a1.get("so_kha", 0)), float(a2.get("so_kha", 0)), False, "so"),
        ("Tổ Trung bình",   float(a1.get("so_tb",  0)), float(a2.get("so_tb",  0)), True,  "so"),
        ("Tổ xếp loại Yếu", float(a1.get("so_yeu", 0)), float(a2.get("so_yeu", 0)), True,  "so"),
        ("Điểm TB",         float(a1.get("diem_tb",0)), float(a2.get("diem_tb",0)), False, "pct"),
    ]
    render_comparison_table(cat_rows, sel_k1, sel_k2, title="Chỉ tiêu chất lượng tổ")

    st.divider()

    # Pie charts cơ cấu xếp loại — chỉ hiện khi xem toàn Chi nhánh (không PGD)
    if not pgd_mode:
        st.markdown("**📊 Cơ cấu xếp loại theo từng kỳ**")
        try:
            col_pie1, col_pie2 = st.columns(2)
            labels_pie  = ["Tốt", "Khá", "Trung bình", "Yếu"]
            colors_pie  = ["#16a34a", "#2563eb", "#f59e0b", "#dc2626"]
            vals1 = [float(a1.get("so_tot", 0)), float(a1.get("so_kha", 0)),
                     float(a1.get("so_tb",  0)), float(a1.get("so_yeu", 0))]
            vals2 = [float(a2.get("so_tot", 0)), float(a2.get("so_kha", 0)),
                     float(a2.get("so_tb",  0)), float(a2.get("so_yeu", 0))]
            for col_pie, vals, lbl in [(col_pie1, vals1, sel_k1), (col_pie2, vals2, sel_k2)]:
                fig_pie = go.Figure(go.Pie(
                    labels=labels_pie, values=vals,
                    marker_colors=colors_pie,
                    hole=0.35,
                    textinfo="label+percent",
                ))
                fig_pie.update_layout(
                    title=dict(text=f"Cơ cấu xếp loại kỳ {lbl}", font_size=13),
                    height=300,
                    margin=dict(t=40, b=10, l=10, r=10),
                    showlegend=False,
                )
                col_pie.plotly_chart(fig_pie, use_container_width=True,
                                     key=f"ss2k_pie_cdt_{lbl.replace('-', '_')}")
        except Exception:
            pass


# ─── RENDER CHÍNH ──────────────────────────────────────────────────────

def _render_cached(role: str, username: str, pgd_user: str | None, pgd_mode: bool) -> None:
    st.subheader("🔄 So sánh 2 kỳ")

    ds_ky = danh_sach_ky()
    if len(ds_ky) < 2:
        st.warning("⚠️ Cần ít nhất **2 kỳ snapshot** để so sánh.")
        return

    ky_sel = _ky_selector(ds_ky, ds_ky[min(1, len(ds_ky)-1)], ds_ky[0], "", label="")
    if ky_sel is None:
        return
    ky1, ky2 = ky_sel

    df1 = doc_snapshot(ky1)
    df2 = doc_snapshot(ky2)
    if df1.empty or df2.empty:
        st.warning("⚠️ Một hoặc cả hai kỳ chưa có dữ liệu snapshot.")
        return

    pgd_data_list = sorted(set(
        p for p in list(df1["ten_pgd"].unique()) + list(df2["ten_pgd"].unique())
        if not str(p).startswith("__")
    ))
    _loc_pgd = None
    if not pgd_mode and pgd_data_list:
        state = SCMStateManager()
        _opts = ["🏢 Tất cả Chi nhánh"] + pgd_data_list
        _desired = state.filter_pgd or "🏢 Tất cả Chi nhánh"
        if "ss2k_pgd_filter" not in st.session_state:
            st.session_state["ss2k_pgd_filter"] = _desired if _desired in _opts else "🏢 Tất cả Chi nhánh"
        elif st.session_state.get("ss2k_pgd_filter") not in _opts:
            st.session_state["ss2k_pgd_filter"] = "🏢 Tất cả Chi nhánh"
        _loc_pgd = st.selectbox("📍 Lọc PGD", _opts, key="ss2k_pgd_filter")
        if _loc_pgd and _loc_pgd != "🏢 Tất cả Chi nhánh":
            state.filter_pgd = _loc_pgd
            df1 = df1[df1["ten_pgd"] == _loc_pgd].reset_index(drop=True)
            df2 = df2[df2["ten_pgd"] == _loc_pgd].reset_index(drop=True)
        else:
            state.filter_pgd = None

    if pgd_mode and pgd_user:
        df1 = df1[df1["ten_pgd"] == pgd_user].reset_index(drop=True)
        df2 = df2[df2["ten_pgd"] == pgd_user].reset_index(drop=True)
        if df1.empty or df2.empty:
            st.warning(f"⚠️ Chưa có dữ liệu snapshot cho **{pgd_user}**.")
            return

    agg1 = _agg(df1)
    agg2 = _agg(df2)

    _ten_hien_thi = _loc_pgd if _loc_pgd and _loc_pgd != "🏢 Tất cả Chi nhánh" else (
        pgd_user if pgd_mode and pgd_user else "Toàn Chi nhánh"
    )
    st.caption(f"So sánh **{ky1}** → **{ky2}** · {_ten_hien_thi}")
    st.divider()

    # ── SECTION 1: KPI + Quality bars ──
    _render_kpi(agg1, agg2, ky1, ky2)
    st.divider()

    # ── SECTION 2: Bảng chi tiết ──
    st.markdown("**📊 Bảng so sánh chi tiết**")
    _render_bang_chi_tiet(agg1, agg2, ky1, ky2)

    # ── PGD table + chart ──
    if not pgd_mode and (not _loc_pgd or _loc_pgd == "🏢 Tất cả Chi nhánh"):
        st.divider()
        if _lazy_expander("🏢 Biến động theo đơn vị", "bang_pgd_2ky"):
            _render_bang_pgd(df1, df2, ky1, ky2)
            st.divider()
            _render_bieu_do(df1, df2, ky1, ky2)

    # ── SECTION 3: Export ──
    st.divider()
    tl1 = tl_nqh(agg1["du_no_qh"], agg1["tong_du_no"])
    tl2 = tl_nqh(agg2["du_no_qh"], agg2["tong_du_no"])
    rows_data = [
        ("Tổng dư nợ (triệu đồng)",      fmt_ty(agg1["tong_du_no"]),   fmt_ty(agg2["tong_du_no"]),
         delta_str(agg2["tong_du_no"] - agg1["tong_du_no"], "tien"),
         pct_change_str(agg1["tong_du_no"], agg2["tong_du_no"])),
        ("Dư nợ trong hạn (triệu đồng)", fmt_ty(agg1["du_no_th"]),     fmt_ty(agg2["du_no_th"]),
         delta_str(agg2["du_no_th"] - agg1["du_no_th"], "tien"),
         pct_change_str(agg1["du_no_th"], agg2["du_no_th"])),
        ("Dư nợ quá hạn (triệu đồng)",   fmt_ty(agg1["du_no_qh"]),     fmt_ty(agg2["du_no_qh"]),
         delta_str(agg2["du_no_qh"] - agg1["du_no_qh"], "tien"),
         pct_change_str(agg1["du_no_qh"], agg2["du_no_qh"])),
        ("Dư nợ khoanh (triệu đồng)",    fmt_ty(agg1["du_no_khoanh"]), fmt_ty(agg2["du_no_khoanh"]),
         delta_str(agg2["du_no_khoanh"] - agg1["du_no_khoanh"], "tien"),
         pct_change_str(agg1["du_no_khoanh"], agg2["du_no_khoanh"])),
        ("Tỷ lệ NQH (%)",                fmt_pct_vn(tl1),              fmt_pct_vn(tl2),
         delta_str(tl2 - tl1, "pct"), "—"),
        ("Số hộ vay",                    fmt_so(int(agg1["so_ho"])),   fmt_so(int(agg2["so_ho"])),
         delta_str(agg2["so_ho"] - agg1["so_ho"], "so"),
         pct_change_str(agg1["so_ho"], agg2["so_ho"])),
        ("Số khế ước",                   fmt_so(int(agg1["so_ku"])),   fmt_so(int(agg2["so_ku"])),
         delta_str(agg2["so_ku"] - agg1["so_ku"], "so"),
         pct_change_str(agg1["so_ku"], agg2["so_ku"])),
        ("Giải ngân trong năm (triệu đồng)", fmt_ty(agg1["gn_nam"]), fmt_ty(agg2["gn_nam"]),
         delta_str(agg2["gn_nam"] - agg1["gn_nam"], "tien"),
         pct_change_str(agg1["gn_nam"], agg2["gn_nam"])),
    ]
    sheets_extra = None
    if not pgd_mode and not df1.empty and not df2.empty:
        sheets_extra = build_excel_sheets_pgd(df1, df2, ky1, ky2)
    render_export_ui(rows_data, ky1, ky2, username, sheets_extra,
                     action="xuat_bieu_cn", key_prefix="2ky")

    # ── Lazy sections ──
    st.divider()
    if _lazy_expander("📋 So sánh NQ11 (Nghị quyết 11)", "nq11"):
        _render_nq11_section(ky1, ky2, pgd_mode, pgd_user)
    if _lazy_expander("💼 So sánh GQVL (Giải quyết việc làm)", "gqvl"):
        _render_gqvl_section(ky1, ky2, pgd_mode, pgd_user)
    if _lazy_expander("🏆 So sánh chất lượng Tổ TK&VV", "cdtotkvv"):
        _render_cdtotkvv_section(ky1, ky2, pgd_mode, pgd_user)


def render_2_ky(tab: DeltaGenerator = None, **kwargs) -> None:
    ctx = TabContext(tab, **kwargs)
    role     = normalize_role(str(kwargs.get("role", "user")))
    username = kwargs.get("username", "unknown")
    pgd_user = kwargs.get("pgd_user")
    pgd_mode = bool(kwargs.get("pgd_mode", False)) or (
        pgd_user is not None and la_phan_he_pgd(role)
    )

    with ctx:
        _render_cached(role, username, pgd_user, pgd_mode)
