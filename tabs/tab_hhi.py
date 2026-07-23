"""
Tab Nguồn vốn địa phương — Phân hệ Chi nhánh.

Báo cáo Tỷ trọng Vốn ủy thác địa phương trên Tổng nguồn vốn:
  Tỷ lệ % = Nguồn vốn ngân sách địa phương (Tỉnh/Huyện) ủy thác / Tổng nguồn vốn tại địa phương

Phân tích theo 3 chiều: PGD, Xã, Chương trình tín dụng.
Dữ liệu từ cột "Nguồn vốn" (1=TW, 2=ĐP) trong HSTD.
"""
from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit.delta_generator import DeltaGenerator

import db
from components.delta_card import kpi_row
from config import (
    COT_MA_CHUONG_TRINH,
    COT_MA_NHA_DAU_TU,
    COT_NGUON_VON,
    COT_TEN_CT,
    COT_TEN_PGD,
    COT_TEN_XA,
    COT_TONG_DU_NO,
    DON_VI_CHI_NHANH,
    DS_PGD,
)
from logger import get_logger
from snapshot_service import danh_sach_ky, doc_snapshot_nvdp_range, ky_baseline
from tabs.base_tab import TabContext
from utils import fmt_ty, hien_thi_dataframe_phan_trang, xuat_excel, lazy_tabs

logger = get_logger(__name__)

_COLOR_TW = "#42A5F5"
_COLOR_DP = "#EF5350"
_COLOR_DP_TINH = "#26A69A"
_COLOR_DP_XA = "#FFB74D"
_CHART_LAYOUT = dict(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")


def _text_sach(value) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"nan", "none"} else text


def _ma_ct_int(value) -> int | None:
    text = _text_sach(value)
    if not text:
        return None
    try:
        number = pd.to_numeric(pd.Series([text]), errors="coerce").iloc[0]
    except Exception:
        return None
    if pd.isna(number):
        return None
    return int(number)


def _map_nguon_von(v) -> str:
    """Phân loại nguồn vốn: 'Trung ương' | 'Địa phương' | 'Khác'."""
    s = str(v).strip().upper()
    if s in ("1", "1.0", "TW", "TRUNG ƯƠNG"):
        return "Trung ương"
    if s in ("2", "2.0", "ĐP", "ĐỊA PHƯƠNG"):
        return "Địa phương"
    try:
        n = int(float(s))
        if n == 1:
            return "Trung ương"
        if n == 2:
            return "Địa phương"
    except (ValueError, TypeError):
        pass
    return "Khác"


def _rule_cap_lookup() -> tuple[dict[tuple[int, str], str], dict[str, str]]:
    """Map rule Mã CT + Mã NĐT sang cấp vốn, đọc kv_store đúng 1 lần mỗi render."""
    exact: dict[tuple[int, str], str] = {}
    fallback: dict[str, str] = {}
    for item in db.doc_ndt_dp_rule_list():
        ma_ndt = _text_sach(item.get("ma", ""))
        if not ma_ndt:
            continue
        cap = "xa" if str(item.get("cap", "tinh")).strip().lower() == "xa" else "tinh"
        ma_ct = item.get("ma_ct")
        if ma_ct is None:
            fallback[ma_ndt] = cap
            continue
        try:
            exact[(int(ma_ct), ma_ndt)] = cap
        except Exception:
            continue
    return exact, fallback


def _rules_cache_key(rules: list[dict]) -> str:
    """Fingerprint rule phân loại Mã NĐT để cache bust khi admin đổi rule."""
    parts = []
    for item in rules:
        ma = _text_sach(item.get("ma", ""))
        if not ma:
            continue
        ma_ct = item.get("ma_ct")
        cap = "xa" if str(item.get("cap", "tinh")).strip().lower() == "xa" else "tinh"
        parts.append(f"{ma_ct or 'ALL'}:{ma}:{cap}")
    return "|".join(sorted(parts))


def _cap_label_tu_ma_ndt(ma_ct, ma_ndt, exact: dict[tuple[int, str], str], fallback: dict[str, str]) -> str:
    ma = _text_sach(ma_ndt)
    ma_ct_i = _ma_ct_int(ma_ct)
    cap = "xa"
    if ma:
        cap = exact.get((ma_ct_i, ma), fallback.get(ma, "xa")) if ma_ct_i is not None else fallback.get(ma, "xa")
    return "ĐP cấp tỉnh" if cap == "tinh" else "ĐP cấp xã/khác"


def _phan_nguon_von(df: pd.DataFrame) -> pd.DataFrame:
    """Thêm nhãn nguồn vốn tổng và nhãn phân cấp ĐP từ Mã nhà đầu tư."""
    if {"_nv_label", "_nv_cap_label"}.issubset(df.columns):
        return df
    if COT_NGUON_VON not in df.columns:
        df = df.copy()
        df["_nv_label"] = "Không rõ"
        df["_nv_cap_label"] = "Không rõ"
        return df
    df = df.copy()
    if "_nv_label" not in df.columns:
        df["_nv_label"] = df[COT_NGUON_VON].map(_map_nguon_von)
    df["_nv_cap_label"] = df["_nv_label"]
    mask_dp = df["_nv_label"].eq("Địa phương")
    if mask_dp.any():
        exact, fallback = _rule_cap_lookup()
        ma_ct_s = df[COT_MA_CHUONG_TRINH] if COT_MA_CHUONG_TRINH in df.columns else pd.Series([None] * len(df), index=df.index)
        ma_ndt_s = df[COT_MA_NHA_DAU_TU] if COT_MA_NHA_DAU_TU in df.columns else pd.Series([""] * len(df), index=df.index)
        df.loc[mask_dp, "_nv_cap_label"] = [
            _cap_label_tu_ma_ndt(ma_ct, ma_ndt, exact, fallback)
            for ma_ct, ma_ndt in zip(ma_ct_s.loc[mask_dp], ma_ndt_s.loc[mask_dp])
        ]
    return df


@st.cache_data(show_spinner=False)
def _nhan_nv_numeric(_df: pd.DataFrame, cache_key: str) -> tuple[pd.DataFrame, "pd.Series"]:
    """Pre-label + pre-convert dư nợ → (df_labeled, dn_series). Cache theo cache_key."""
    df_labeled = _phan_nguon_von(_df)
    dn = pd.to_numeric(df_labeled[COT_TONG_DU_NO], errors="coerce").fillna(0.0)
    return df_labeled, dn


def _bang_theo_nv(
    df: pd.DataFrame,
    nhom_col: str,
    extra_cols: list[str] | None = None,
    df_labeled: pd.DataFrame | None = None,
    them_dong_tong: bool = False,
) -> pd.DataFrame:
    """Bảng tổng hợp theo nhóm: TW dư nợ | ĐP dư nợ | Tỷ trọng ĐP%.

    Args:
        df_labeled: Pre-labeled df (tránh gọi lại _phan_nguon_von).
    """
    if nhom_col not in df.columns or COT_TONG_DU_NO not in df.columns:
        return pd.DataFrame()

    if df_labeled is not None and "_nv_label" in df_labeled.columns:
        df_work = df_labeled
    else:
        df_work = _phan_nguon_von(df)

    idx_cols = [nhom_col] + [c for c in (extra_cols or []) if c in df_work.columns]

    # Vectorized: group by nhom + cap_label, sum dư nợ, unstack cap_label thành cột
    df_agg = df_work[idx_cols + ["_nv_cap_label"]].copy()
    df_agg["_dn"] = pd.to_numeric(df_work[COT_TONG_DU_NO], errors="coerce").fillna(0.0).values

    pivot = (
        df_agg.groupby(idx_cols + ["_nv_cap_label"])["_dn"]
        .sum()
        .unstack("_nv_cap_label", fill_value=0.0)
        .reset_index()
    )
    pivot.columns.name = None

    for col in ("Trung ương", "ĐP cấp tỉnh", "ĐP cấp xã/khác"):
        if col not in pivot.columns:
            pivot[col] = 0.0

    pivot["Địa phương"] = pivot["ĐP cấp tỉnh"] + pivot["ĐP cấp xã/khác"]
    pivot["_tong"] = pivot["Trung ương"] + pivot["Địa phương"]

    result = pivot.sort_values("_tong", ascending=False).reset_index(drop=True)
    if result.empty:
        return result

    result["Tỷ trọng ĐP (%)"] = result.apply(
        lambda r: r["Địa phương"] / r["_tong"] * 100
        if r["_tong"] > 0 else 0.0,
        axis=1,
    )
    result = result.sort_values("_tong", ascending=False).reset_index(drop=True)
    if them_dong_tong:
        tong_row = {col: "" for col in idx_cols}
        tong_row[idx_cols[0]] = "Tổng cộng"
        for col in ["Trung ương", "ĐP cấp tỉnh", "ĐP cấp xã/khác", "Địa phương", "_tong"]:
            tong_row[col] = result[col].sum()
        tong_row["Tỷ trọng ĐP (%)"] = (
            tong_row["Địa phương"] / tong_row["_tong"] * 100
            if tong_row["_tong"] > 0 else 0.0
        )
        result = pd.concat([result, pd.DataFrame([tong_row])], ignore_index=True)

    result["TW (triệu đồng)"] = result["Trung ương"].apply(fmt_ty)
    result["ĐP cấp tỉnh (triệu đồng)"] = result["ĐP cấp tỉnh"].apply(fmt_ty)
    result["ĐP cấp xã/khác (triệu đồng)"] = result["ĐP cấp xã/khác"].apply(fmt_ty)
    result["ĐP (triệu đồng)"] = result["Địa phương"].apply(fmt_ty)
    result["Tổng (triệu đồng)"] = result["_tong"].apply(fmt_ty)
    result["Tỷ trọng ĐP (%)"] = result["Tỷ trọng ĐP (%)"].apply(
        lambda x: f"{x:.1f}".replace(".", ",") + "%"
    )

    display_cols = idx_cols + [
        "TW (triệu đồng)",
        "ĐP cấp tỉnh (triệu đồng)", "ĐP cấp xã/khác (triệu đồng)",
        "ĐP (triệu đồng)",
        "Tổng (triệu đồng)", "Tỷ trọng ĐP (%)",
    ]
    return result[[c for c in display_cols if c in result.columns]]


def _ten_don_vi_ngan(value) -> str:
    text = _text_sach(value)
    if text == DON_VI_CHI_NHANH:
        return "Hội sở tỉnh"
    if text.startswith("PGD "):
        return text[4:].strip()
    return text


def _ordered_units(values: pd.Series) -> list[str]:
    existing = [_text_sach(v) for v in values.dropna().tolist()]
    existing_set = {v for v in existing if v}
    preferred = [DON_VI_CHI_NHANH] + list(DS_PGD)
    ordered = [v for v in preferred if v in existing_set]
    ordered.extend(sorted(existing_set - set(ordered)))
    return ordered


def _bang_nguon_von_xa_02_ct(
    df: pd.DataFrame,
    df_labeled: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Bảng đối chiếu GQVL/NSVSMT dùng nguồn ngân sách cấp xã nhận ủy thác."""
    required = {COT_TEN_PGD, COT_MA_CHUONG_TRINH, COT_TONG_DU_NO}
    if df is None or df.empty or not required.issubset(df.columns):
        return pd.DataFrame()

    if df_labeled is not None and {"_nv_label", "_nv_cap_label"}.issubset(df_labeled.columns):
        df_work = df_labeled.copy()
    else:
        df_work = _phan_nguon_von(df)

    ma_ct = df_work[COT_MA_CHUONG_TRINH].map(_ma_ct_int)
    dn = pd.to_numeric(df_work[COT_TONG_DU_NO], errors="coerce").fillna(0.0)
    mask = (
        df_work["_nv_label"].eq("Địa phương")
        & df_work["_nv_cap_label"].eq("ĐP cấp xã/khác")
        & ma_ct.isin([3, 6])
    )

    rows = df_work.loc[mask, [COT_TEN_PGD]].copy()
    rows["_ma_ct"] = ma_ct.loc[mask].astype(int)
    rows["_dn"] = dn.loc[mask].values

    units = _ordered_units(df_work[COT_TEN_PGD])
    if not units:
        return pd.DataFrame()

    if rows.empty:
        pivot = pd.DataFrame(0.0, index=units, columns=[3, 6])
    else:
        pivot = (
            rows.groupby([COT_TEN_PGD, "_ma_ct"])["_dn"]
            .sum()
            .unstack("_ma_ct", fill_value=0.0)
            .reindex(units, fill_value=0.0)
        )
        for col in (3, 6):
            if col not in pivot.columns:
                pivot[col] = 0.0
        pivot = pivot[[3, 6]]

    out = pd.DataFrame(
        {
            "STT": range(1, len(pivot) + 1),
            "Đơn vị": [_ten_don_vi_ngan(v) for v in pivot.index],
            "GQVL nguồn vốn xã": pivot[3].astype(float).values,
            "NS&VSMTNT nguồn vốn xã": pivot[6].astype(float).values,
        }
    )
    out["Tổng cộng"] = out["GQVL nguồn vốn xã"] + out["NS&VSMTNT nguồn vốn xã"]

    total = {
        "STT": "",
        "Đơn vị": "Tổng cộng",
        "GQVL nguồn vốn xã": out["GQVL nguồn vốn xã"].sum(),
        "NS&VSMTNT nguồn vốn xã": out["NS&VSMTNT nguồn vốn xã"].sum(),
        "Tổng cộng": out["Tổng cộng"].sum(),
    }
    out = pd.concat([out, pd.DataFrame([total])], ignore_index=True)

    for col in ["GQVL nguồn vốn xã", "NS&VSMTNT nguồn vốn xã", "Tổng cộng"]:
        out[col] = out[col].apply(fmt_ty)
    return out


def _ve_bieu_do_ngang(df_table: pd.DataFrame, label_col: str, tieu_de: str, key: str) -> None:
    """Vẽ biểu đồ cột ngang tỷ trọng ĐP — dark-mode compatible."""
    df_chart = df_table.copy()
    pct_col = "Tỷ trọng ĐP (%)"
    df_chart["_pct"] = df_chart[pct_col].str.replace(",", ".").str.rstrip("%").astype(float)
    df_chart = df_chart.sort_values("_pct", ascending=True)

    colors = ["#E53935" if v > 50 else ("#FFA000" if v > 30 else "#43A047") for v in df_chart["_pct"]]

    fig = go.Figure(go.Bar(
        y=df_chart[label_col],
        x=df_chart["_pct"],
        orientation="h",
        marker_color=colors,
        text=df_chart[pct_col],
        textposition="outside",
    ))
    fig.update_layout(
        title=tieu_de,
        xaxis_title="Tỷ trọng ĐP (%)",
        yaxis=dict(autorange="reversed"),
        height=max(400, len(df_chart) * 30 + 100),
        margin=dict(l=20, r=80, t=50, b=30),
        **_CHART_LAYOUT,
    )
    st.plotly_chart(fig, use_container_width=True, key=key)


def _ve_treemap_pgd(df_labeled: pd.DataFrame, dn: pd.Series) -> None:
    """Treemap TW vs ĐP cấp tỉnh/cấp xã phân theo PGD."""
    nguon = df_labeled["_nv_label"]
    nguon_cap = df_labeled["_nv_cap_label"]
    pgds = df_labeled[COT_TEN_PGD]
    tw_by_pgd = dn[nguon.eq("Trung ương")].groupby(pgds).sum()
    dp_tinh_by_pgd = dn[nguon_cap.eq("ĐP cấp tỉnh")].groupby(pgds).sum()
    dp_xa_by_pgd = dn[nguon_cap.eq("ĐP cấp xã/khác")].groupby(pgds).sum()
    all_pgd = sorted(set(tw_by_pgd.index) | set(dp_tinh_by_pgd.index) | set(dp_xa_by_pgd.index))
    ids, labels, parents, values = [], [], [], []
    for pgd in all_pgd:
        tw_val = float(tw_by_pgd.get(pgd, 0))
        dp_tinh_val = float(dp_tinh_by_pgd.get(pgd, 0))
        dp_xa_val = float(dp_xa_by_pgd.get(pgd, 0))
        if tw_val + dp_tinh_val + dp_xa_val == 0:
            continue
        pid = f"pgd_{pgd}"
        ids.append(pid); labels.append(pgd); parents.append(""); values.append(tw_val + dp_tinh_val + dp_xa_val)
        if tw_val:
            ids.append(f"tw_{pgd}"); labels.append("TW"); parents.append(pid); values.append(tw_val)
        if dp_tinh_val:
            ids.append(f"dp_tinh_{pgd}"); labels.append("ĐP tỉnh"); parents.append(pid); values.append(dp_tinh_val)
        if dp_xa_val:
            ids.append(f"dp_xa_{pgd}"); labels.append("ĐP xã"); parents.append(pid); values.append(dp_xa_val)
    if not ids:
        return
    colors = [
        _COLOR_TW if lb == "TW" else _COLOR_DP_TINH if lb == "ĐP tỉnh" else _COLOR_DP_XA if lb == "ĐP xã" else "#BDBDBD"
        for lb in labels
    ]
    fig = go.Figure(go.Treemap(
        ids=ids, labels=labels, parents=parents, values=values,
        branchvalues="total", marker_colors=colors,
        textinfo="label+value+percent parent",
    ))
    fig.update_layout(title="TW vs ĐP theo PGD", height=300,
                      margin=dict(l=10, r=10, t=40, b=10), **_CHART_LAYOUT)
    st.plotly_chart(fig, use_container_width=True, key="nvdp_treemap_pgd")


def _ve_treemap_ct(df_labeled: pd.DataFrame, dn: pd.Series) -> None:
    """Treemap TW vs ĐP cấp tỉnh/cấp xã phân theo Chương trình tín dụng."""
    nguon = df_labeled["_nv_label"]
    nguon_cap = df_labeled["_nv_cap_label"]
    cts = df_labeled[COT_TEN_CT]
    tw_by_ct = dn[nguon.eq("Trung ương")].groupby(cts).sum()
    dp_tinh_by_ct = dn[nguon_cap.eq("ĐP cấp tỉnh")].groupby(cts).sum()
    dp_xa_by_ct = dn[nguon_cap.eq("ĐP cấp xã/khác")].groupby(cts).sum()
    all_ct = sorted(set(tw_by_ct.index) | set(dp_tinh_by_ct.index) | set(dp_xa_by_ct.index))
    ids, labels, parents, values = [], [], [], []
    for ct in all_ct:
        tw_val = float(tw_by_ct.get(ct, 0))
        dp_tinh_val = float(dp_tinh_by_ct.get(ct, 0))
        dp_xa_val = float(dp_xa_by_ct.get(ct, 0))
        if tw_val + dp_tinh_val + dp_xa_val == 0:
            continue
        pid = f"ct_{ct}"
        short = ct[:25] if len(ct) > 25 else ct
        ids.append(pid); labels.append(short); parents.append(""); values.append(tw_val + dp_tinh_val + dp_xa_val)
        if tw_val:
            ids.append(f"tw_{ct}"); labels.append("TW"); parents.append(pid); values.append(tw_val)
        if dp_tinh_val:
            ids.append(f"dp_tinh_{ct}"); labels.append("ĐP tỉnh"); parents.append(pid); values.append(dp_tinh_val)
        if dp_xa_val:
            ids.append(f"dp_xa_{ct}"); labels.append("ĐP xã"); parents.append(pid); values.append(dp_xa_val)
    if not ids:
        return
    colors = [
        _COLOR_TW if lb == "TW" else _COLOR_DP_TINH if lb == "ĐP tỉnh" else _COLOR_DP_XA if lb == "ĐP xã" else "#BDBDBD"
        for lb in labels
    ]
    fig = go.Figure(go.Treemap(
        ids=ids, labels=labels, parents=parents, values=values,
        branchvalues="total", marker_colors=colors,
        textinfo="label+value+percent parent",
    ))
    fig.update_layout(title="TW vs ĐP theo Chương trình", height=300,
                      margin=dict(l=10, r=10, t=40, b=10), **_CHART_LAYOUT)
    st.plotly_chart(fig, use_container_width=True, key="nvdp_treemap_ct")


def _render_top_contributors(df_labeled: pd.DataFrame, dn: pd.Series, mask_dp: pd.Series) -> None:
    """Top 5 đơn vị có tỷ trọng ĐP cao nhất."""
    cap = df_labeled["_nv_cap_label"]
    if COT_TEN_PGD in df_labeled.columns:
        dp_grp = dn[mask_dp].groupby(df_labeled[COT_TEN_PGD]).sum()
        dp_tinh_grp = dn[cap.eq("ĐP cấp tỉnh")].groupby(df_labeled[COT_TEN_PGD]).sum()
        dp_xa_grp = dn[cap.eq("ĐP cấp xã/khác")].groupby(df_labeled[COT_TEN_PGD]).sum()
        total_grp = dn.groupby(df_labeled[COT_TEN_PGD]).sum()
        pct = (dp_grp / total_grp.replace(0, 1) * 100).sort_values(ascending=False).head(5)
        items = [
            (
                f"- **{k}**: {v:.1f}% ({fmt_ty(dp_grp.get(k, 0))} tr; "
                f"tỉnh {fmt_ty(dp_tinh_grp.get(k, 0))} tr, xã {fmt_ty(dp_xa_grp.get(k, 0))} tr)"
            )
            for k, v in pct.items()
        ]
        st.markdown("**Top PGD tỷ trọng ĐP:**\n" + "\n".join(items))
    elif COT_TEN_CT in df_labeled.columns:
        dp_grp = dn[mask_dp].groupby(df_labeled[COT_TEN_CT]).sum()
        dp_tinh_grp = dn[cap.eq("ĐP cấp tỉnh")].groupby(df_labeled[COT_TEN_CT]).sum()
        dp_xa_grp = dn[cap.eq("ĐP cấp xã/khác")].groupby(df_labeled[COT_TEN_CT]).sum()
        total_grp = dn.groupby(df_labeled[COT_TEN_CT]).sum()
        pct = (dp_grp / total_grp.replace(0, 1) * 100).sort_values(ascending=False).head(5)
        items = [
            (
                f"- **{k[:30] if len(k) > 30 else k}**: {v:.1f}% ({fmt_ty(dp_grp.get(k, 0))} tr; "
                f"tỉnh {fmt_ty(dp_tinh_grp.get(k, 0))} tr, xã {fmt_ty(dp_xa_grp.get(k, 0))} tr)"
            )
            for k, v in pct.items()
        ]
        st.markdown("**Top CT tỷ trọng ĐP:**\n" + "\n".join(items))


def _render_sub_pgd(df: pd.DataFrame, df_labeled: pd.DataFrame | None = None) -> None:
    df_pgd_hien = _bang_theo_nv(df, COT_TEN_PGD, df_labeled=df_labeled, them_dong_tong=True)
    if df_pgd_hien.empty:
        st.warning("Không có dữ liệu PGD.")
        return
    df_pgd = df_pgd_hien.iloc[:-1]  # exclude "Tổng cộng" row for chart
    _ve_bieu_do_ngang(df_pgd, COT_TEN_PGD, "Tỷ trọng vốn Địa phương theo PGD", "nvdp_pgd_chart")
    st.markdown("**Bảng chi tiết theo PGD**")
    hien_thi_dataframe_phan_trang(df_pgd_hien, key="nvdp_pgd_table", height=480)


def _render_sub_xa(df: pd.DataFrame, kp: str = "", df_labeled: pd.DataFrame | None = None) -> None:
    df_xa = _bang_theo_nv(df, COT_TEN_XA, extra_cols=[COT_TEN_PGD], df_labeled=df_labeled)
    if df_xa.empty:
        st.warning("Không có dữ liệu Xã.")
        return
    df_top = df_xa.copy()
    df_top["_pct"] = df_top["Tỷ trọng ĐP (%)"].str.replace(",", ".").str.rstrip("%").astype(float)
    df_top = df_top.sort_values("_pct", ascending=False).head(20)
    _ve_bieu_do_ngang(df_top, COT_TEN_XA, "Top 20 Xã — Tỷ trọng vốn Địa phương cao nhất", f"{kp}nvdp_xa_chart")
    st.markdown("**Bảng chi tiết theo Xã**")
    hien_thi_dataframe_phan_trang(df_xa, key=f"{kp}nvdp_xa_table", height=480)


def _render_sub_ct(df: pd.DataFrame, kp: str = "", df_labeled: pd.DataFrame | None = None) -> None:
    df_ct = _bang_theo_nv(df, COT_TEN_CT, df_labeled=df_labeled)
    if df_ct.empty:
        st.warning("Không có dữ liệu Chương trình.")
        return
    _ve_bieu_do_ngang(df_ct, COT_TEN_CT, "Tỷ trọng vốn Địa phương theo Chương trình tín dụng", f"{kp}nvdp_ct_chart")
    st.markdown("**Bảng chi tiết theo Chương trình**")
    hien_thi_dataframe_phan_trang(df_ct, key=f"{kp}nvdp_ct_table", height=480)


def _render_trend(ky_list: list[str], cache_key: str) -> None:
    """Biểu đồ xu hướng TW vs ĐP qua các kỳ snapshot."""
    if len(ky_list) < 2:
        return
    df_trend = _cached_snapshot_range(ky_list[-1], ky_list[0], cache_key)
    if df_trend.empty:
        return

    df_tw = df_trend[df_trend["nguon_von"] == "1"].set_index("ky")["tong_du_no"]
    df_dp = df_trend[df_trend["nguon_von"] == "2"].set_index("ky")["tong_du_no"]
    ky_vals = sorted(df_trend["ky"].unique())

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=ky_vals,
        y=[df_tw.get(k, 0) / 1e9 for k in ky_vals],
        name="Trung ương",
        marker_color=_COLOR_TW,
    ))
    fig.add_trace(go.Bar(
        x=ky_vals,
        y=[df_dp.get(k, 0) / 1e9 for k in ky_vals],
        name="Địa phương",
        marker_color=_COLOR_DP,
    ))
    fig.update_layout(
        barmode="stack",
        title="Xu hướng dư nợ TW vs ĐP theo kỳ",
        yaxis_title="Tỷ đồng",
        height=350,
        margin=dict(l=20, r=20, t=50, b=30),
        legend=dict(orientation="h", y=1.08),
        **_CHART_LAYOUT,
    )
    st.plotly_chart(fig, use_container_width=True, key="nvdp_trend_chart")


# ── Cache snapshot context ────────────────────────────────────────────────────
@st.cache_data(show_spinner=False, ttl=600)
def _load_snapshot_context(cache_key: str) -> dict:
    """Cache snapshot context: ky_list, df_prev, prev_label. TTL 10 phút."""
    ky_list = danh_sach_ky()
    ctx: dict = {"ky_list": ky_list, "df_prev": pd.DataFrame(), "prev_label": "so với kỳ trước"}

    if not ky_list:
        return ctx

    prev_ky = ky_baseline(ky_list, ky_list[0]) or (ky_list[1] if len(ky_list) > 1 else None)
    if prev_ky and prev_ky != ky_list[0]:
        ky_parts = prev_ky.split("-")
        ctx["prev_label"] = f"so baseline T{ky_parts[1]}/{ky_parts[0]}"
        ctx["df_prev"] = doc_snapshot_nvdp_range(prev_ky, prev_ky)

    return ctx


@st.cache_data(show_spinner=False)
def _cached_snapshot_range(tu_ky: str, den_ky: str, cache_key: str) -> pd.DataFrame:
    """Cache doc_snapshot_nvdp_range — dùng cho trend chart."""
    return doc_snapshot_nvdp_range(tu_ky, den_ky)


# ── Cache Excel export ────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def _cached_excel_sheets(
    _df_labeled: pd.DataFrame,
    is_pgd_view: bool,
    extra_cols: tuple[str, ...],
    view_key: str = "cn",
    ts: float = 0.0,
    rules_key: str = "",
) -> bytes:
    """Cache Excel export — tránh tính lại bảng mỗi lần tải."""
    _ = (view_key, ts, rules_key)
    sheets: dict[str, pd.DataFrame] = {
        "Nguồn xã 02 CT": _bang_nguon_von_xa_02_ct(_df_labeled, df_labeled=_df_labeled),
        "Theo Chương trình": _bang_theo_nv(_df_labeled, COT_TEN_CT, df_labeled=_df_labeled),
        "Theo Xã": _bang_theo_nv(_df_labeled, COT_TEN_XA, extra_cols=list(extra_cols), df_labeled=_df_labeled),
    }
    if not is_pgd_view:
        sheets["Theo PGD"] = _bang_theo_nv(_df_labeled, COT_TEN_PGD, df_labeled=_df_labeled, them_dong_tong=True)
    return xuat_excel(sheets)


# ── Entry point ───────────────────────────────────────────────────────────────

def render(tab: DeltaGenerator = None, **kwargs) -> None:
    df_full = kwargs.get("df_full")
    pgd_user = kwargs.get("pgd_user", "")
    ts_hstd = float(kwargs.get("ts_hstd", 0.0))

    ctx = TabContext(tab, **kwargs)
    with ctx:
        st.subheader("🏦 Nguồn vốn địa phương")
        if pgd_user:
            st.caption(
                f"Báo cáo Tỷ trọng Vốn ủy thác địa phương tại **{pgd_user}** — "
                "phân tích theo Xã và Chương trình tín dụng."
            )
        else:
            st.caption(
                "Báo cáo Tỷ trọng Vốn ủy thác địa phương trên Tổng nguồn vốn "
                "— phân tích theo PGD, Xã và Chương trình tín dụng."
            )

        if df_full is None or df_full.empty:
            st.warning("⚠️ Chưa có dữ liệu. Vui lòng upload và merge HSTD.")
            return

        if pgd_user and COT_TEN_PGD in df_full.columns:
            df_full = df_full[df_full[COT_TEN_PGD] == pgd_user].copy()
            if df_full.empty:
                st.warning(f"⚠️ Không có dữ liệu cho PGD **{pgd_user}**.")
                return

        if COT_NGUON_VON not in df_full.columns:
            st.warning(
                "⚠️ Dữ liệu HSTD không có cột 'Nguồn vốn'. "
                "Vui lòng kiểm tra lại file HSTD gốc."
            )
            return

        selected_pgd = None
        if not pgd_user and COT_TEN_PGD in df_full.columns:
            pgds = sorted(df_full[COT_TEN_PGD].dropna().unique().tolist())
            sel = st.selectbox(
                "🔍 Lọc theo PGD (tùy chọn)",
                ["Tất cả"] + pgds,
                key="nvdp_filter_pgd",
            )
            if sel != "Tất cả":
                selected_pgd = sel
                df_display = df_full[df_full[COT_TEN_PGD] == sel].copy()
            else:
                df_display = df_full
        else:
            df_display = df_full

        # ── PRE-COMPUTE (1 lần duy nhất cho toàn bộ render) ──────────────────
        rules_key = _rules_cache_key(db.doc_ndt_dp_rule_list())
        nv_cache_key = f"{'pgd' if pgd_user else 'cn'}_{selected_pgd or 'all'}_{ts_hstd}_{rules_key}"
        df_labeled, dn_series = _nhan_nv_numeric(df_display, nv_cache_key)
        mask_tw = df_labeled["_nv_label"] == "Trung ương"
        mask_dp = df_labeled["_nv_label"] == "Địa phương"
        mask_dp_tinh = df_labeled["_nv_cap_label"] == "ĐP cấp tỉnh"
        mask_dp_xa = df_labeled["_nv_cap_label"] == "ĐP cấp xã/khác"
        tong_du_no = float(dn_series.sum())
        dn_tw = float(dn_series[mask_tw].sum())
        dn_dp = float(dn_series[mask_dp].sum())
        dn_dp_tinh = float(dn_series[mask_dp_tinh].sum())
        dn_dp_xa = float(dn_series[mask_dp_xa].sum())
        tl_dp = dn_dp / tong_du_no * 100 if tong_du_no > 0 else 0.0

        # Delta từ snapshot — chỉ khi xem toàn CN (không filter PGD)
        delta_tong = delta_tw = delta_dp = delta_tl = None
        prev_label = "so với kỳ trước"
        ky_list: list[str] = []

        if not pgd_user and selected_pgd is None:
            snap_ctx = _load_snapshot_context(f"nvdp_{ts_hstd}")
            ky_list = snap_ctx["ky_list"]
            prev_label = snap_ctx["prev_label"]
            df_prev = snap_ctx["df_prev"]
            if not df_prev.empty:
                p_tw = float(df_prev[df_prev["nguon_von"] == "1"]["tong_du_no"].sum())
                p_dp = float(df_prev[df_prev["nguon_von"] == "2"]["tong_du_no"].sum())
                p_tong = p_tw + p_dp
                p_tl = p_dp / p_tong * 100 if p_tong > 0 else 0.0
                delta_tong = (tong_du_no - p_tong) / p_tong * 100 if p_tong > 0 else None
                delta_tw = (dn_tw - p_tw) / p_tw * 100 if p_tw > 0 else None
                delta_dp = (dn_dp - p_dp) / p_dp * 100 if p_dp > 0 else None
                delta_tl = tl_dp - p_tl

        kpi_row(
            [
                {
                    "label": "Tổng dư nợ",
                    "value": fmt_ty(tong_du_no),
                    "suffix": "tr.đ",
                    "delta": delta_tong,
                    "delta_label": prev_label,
                    "icon": "💰",
                    "precision": 1,
                },
                {
                    "label": "Dư nợ Trung ương",
                    "value": fmt_ty(dn_tw),
                    "suffix": "tr.đ",
                    "delta": delta_tw,
                    "delta_label": prev_label,
                    "icon": "🏛️",
                    "precision": 1,
                },
                {
                    "label": "Dư nợ Địa phương",
                    "value": fmt_ty(dn_dp),
                    "suffix": "tr.đ",
                    "delta": delta_dp,
                    "delta_label": prev_label,
                    "icon": "🏘️",
                    "precision": 1,
                },
                {
                    "label": "ĐP cấp tỉnh",
                    "value": fmt_ty(dn_dp_tinh),
                    "suffix": "tr.đ",
                    "help": "Dư nợ nguồn ĐP có Mã nhà đầu tư được rule phân loại cấp tỉnh.",
                    "icon": "🏛️",
                },
                {
                    "label": "ĐP cấp xã/khác",
                    "value": fmt_ty(dn_dp_xa),
                    "suffix": "tr.đ",
                    "help": "Dư nợ nguồn ĐP có Mã nhà đầu tư thuộc cấp xã/khác hoặc chưa có rule cấp tỉnh.",
                    "icon": "🏘️",
                },
                {
                    "label": "Tỷ trọng vốn ĐP",
                    "value": f"{tl_dp:.1f}".replace(".", ",") + "%",
                    "delta": delta_tl,
                    "delta_label": prev_label,
                    "delta_color": "inverse" if tl_dp > 50 else "normal",
                    "icon": "📊",
                    "precision": 1,
                },
            ],
            num_columns=3,
        )

        # ── Pie + Treemap + công thức ───────────────────────────────────────────
        col_pie, col_treemap, col_info = st.columns([1.2, 1.2, 2])
        with col_pie:
            fig_pie = go.Figure(go.Pie(
                labels=["Trung ương", "ĐP cấp tỉnh", "ĐP cấp xã/khác"],
                values=[dn_tw, dn_dp_tinh, dn_dp_xa],
                marker_colors=[_COLOR_TW, _COLOR_DP_TINH, _COLOR_DP_XA],
                hole=0.4,
                textinfo="label+percent",
            ))
            fig_pie.update_layout(
                title="Cơ cấu nguồn vốn",
                height=300,
                margin=dict(l=10, r=10, t=40, b=10),
                **_CHART_LAYOUT,
            )
            st.plotly_chart(fig_pie, use_container_width=True, key="nvdp_pie")

        with col_treemap:
            if COT_TEN_PGD in df_labeled.columns and not pgd_user and not selected_pgd:
                _ve_treemap_pgd(df_labeled, dn_series)
            elif COT_TEN_CT in df_labeled.columns:
                _ve_treemap_ct(df_labeled, dn_series)
            else:
                st.info("Chưa có cột chương trình để vẽ treemap nguồn vốn.")

        with col_info:
            st.markdown("##### 📐 Cách đo lường")
            st.latex(
                r"\text{Tỷ lệ \%} = "
                r"\frac{\text{Nguồn vốn ngân sách địa phương (Tỉnh/Huyện) ủy thác}}"
                r"{\text{Tổng nguồn vốn tại địa phương}}"
            )
            st.info(
                "Nguồn vốn được xác định từ cột **Nguồn vốn** trong HSTD: "
                "**1 = Trung ương**, **2 = Địa phương**. "
                "Riêng nguồn ĐP được tách tiếp theo rule **Mã CT + Mã nhà đầu tư** "
                "đã cấu hình ở tab Mã NĐT địa phương."
            )
            st.markdown("##### 🔝 Đơn vị nổi bật")
            _render_top_contributors(df_labeled, dn_series, mask_dp)

        # ── Trend chart (chỉ khi xem toàn CN, có ít nhất 2 kỳ) ──────────────
        if len(ky_list) >= 2:
            st.divider()
            st.markdown("**📈 Xu hướng theo kỳ snapshot**")
            _render_trend(ky_list, f"nvdp_trend_{ts_hstd}")

        st.divider()

        is_pgd_view = bool(pgd_user or selected_pgd)
        view_key = selected_pgd or pgd_user or "cn"
        kp = f"pgd_" if is_pgd_view else ""
        extra_cols_tuple = (COT_TEN_PGD,) if COT_TEN_PGD in df_display.columns else ()

        df_xa_02_ct = _bang_nguon_von_xa_02_ct(df_display, df_labeled=df_labeled)
        if not df_xa_02_ct.empty:
            st.markdown("**🏘️ Đối chiếu nguồn vốn ngân sách cấp xã nhận ủy thác**")
            st.caption(
                "Đơn vị: triệu đồng · Chỉ gồm 02 chương trình GQVL và NS&VSMTNT, "
                "lọc `Nguồn vốn = Địa phương` và phân loại Mã NĐT là `ĐP cấp xã/khác`."
            )
            hien_thi_dataframe_phan_trang(df_xa_02_ct, key=f"{kp}nvdp_xa_02_ct_table", height=480)
            st.divider()

        # ── Sub-tabs phân tích ────────────────────────────────────────────────
        if is_pgd_view:
            lazy_tabs(
                ["🗺️ Theo Xã", "📌 Theo Chương trình"],
                [
                    lambda: (
                        st.warning("Không tìm thấy cột Tên Xã trong dữ liệu.")
                        if COT_TEN_XA not in df_display.columns
                        else _render_sub_xa(df_display, kp, df_labeled=df_labeled)
                    ),
                    lambda: (
                        st.warning("Không tìm thấy cột Tên chương trình trong dữ liệu.")
                        if COT_TEN_CT not in df_display.columns
                        else _render_sub_ct(df_display, kp, df_labeled=df_labeled)
                    ),
                ],
                key="nvdp_sub_pgd",
            )
        else:
            lazy_tabs(
                ["🏢 Theo PGD", "🗺️ Theo Xã", "📌 Theo Chương trình"],
                [
                    lambda: (
                        st.warning("Không tìm thấy cột Tên PGD trong dữ liệu.")
                        if COT_TEN_PGD not in df_display.columns
                        else _render_sub_pgd(df_display, df_labeled=df_labeled)
                    ),
                    lambda: (
                        st.warning("Không tìm thấy cột Tên Xã trong dữ liệu.")
                        if COT_TEN_XA not in df_display.columns
                        else _render_sub_xa(df_display, kp, df_labeled=df_labeled)
                    ),
                    lambda: (
                        st.warning("Không tìm thấy cột Tên chương trình trong dữ liệu.")
                        if COT_TEN_CT not in df_display.columns
                        else _render_sub_ct(df_display, kp, df_labeled=df_labeled)
                    ),
                ],
                key="nvdp_sub_cn",
            )

        # ── Xuất Excel ────────────────────────────────────────────────────────
        st.divider()
        st.markdown("**📥 Xuất Excel — Báo cáo Nguồn vốn địa phương**")
        today_str = date.today().strftime("%d/%m/%Y")
        today_file = date.today().strftime("%Y%m%d")
        try:
            buf = _cached_excel_sheets(df_labeled, is_pgd_view, extra_cols_tuple, view_key, ts_hstd, rules_key)
        except Exception as e:
            logger.error("tab_hhi export excel: %s", e, exc_info=True)
            st.warning(f"Không thể tạo đầy đủ file Excel nguồn vốn địa phương: {e}")
            buf = xuat_excel({"Lỗi xuất file": pd.DataFrame({"Lỗi": [str(e)]})})
        st.download_button(
            label=f"⬇️ Tải Excel Nguồn vốn ĐP ({today_str})",
            data=buf,
            file_name=f"NguonVonDiaPhuong_{today_file}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="nvdp_xuat_excel",
        )
