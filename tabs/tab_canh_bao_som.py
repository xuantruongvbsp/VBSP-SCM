"""Nợ đến hạn có nguy cơ — khoản vay sắp đến hạn + KH không hoạt động > 90 ngày.

Ported từ VSPPRO Npl.tsx (dueSoonDormant / chuyenNQHThang).
Hoạt động ở cả phân hệ Chi nhánh (CN) lẫn PGD.
"""
from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st
from streamlit.delta_generator import DeltaGenerator

from auth import la_phan_he_cn, normalize_role
from state_manager import SCMStateManager
from config import (
    COT_DU_NO_QH,
    COT_DU_NO_TH,
    COT_LAI_TON,
    COT_MA_KH,
    COT_NGAY_DH,
    COT_SO_KU,
    COT_TEN_CT,
    COT_TEN_KH,
    COT_TEN_PGD,
    COT_TEN_XA,
    COT_TONG_DU_NO,
    DS_PGD,
)
from data.hstd import danh_dau_khong_hd_cached
from utils import fmt_so, fmt_ty, hien_thi_dataframe_phan_trang, xuat_excel


# ─── Helpers tính toán ────────────────────────────────────────────────────────

def _parse_ngay_dh(df: pd.DataFrame) -> pd.Series:
    """Parse cột Ngày ĐH theo Gia hạn thành Timestamp."""
    if COT_NGAY_DH not in df.columns:
        return pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns]")
    return pd.to_datetime(df[COT_NGAY_DH], errors="coerce", dayfirst=True)


def _quy_cua(month: int) -> int:
    """Trả về số quý (1–4) từ tháng."""
    return (month - 1) // 3 + 1


def tinh_du_soon_dormant(
    df_kh: pd.DataFrame,
    ref_date: datetime,
    scope: str,
) -> pd.DataFrame:
    """
    Khoản vay sắp đến hạn + KH không hoạt động > 90 ngày.

    Args:
        df_kh   : DataFrame đã có cột is_3m_inactive (từ danh_dau_khong_hd_cached).
        ref_date: Ngày tham chiếu (thường là hôm nay).
        scope   : "thang" | "quy" | "nam" — phạm vi thời gian.

    Returns:
        Subset của df_kh kèm cột _ngay_dh (datetime) đã parse.
    """
    if "is_3m_inactive" not in df_kh.columns:
        return pd.DataFrame()

    ngay_dh = _parse_ngay_dh(df_kh)
    ref_ts = pd.Timestamp(ref_date)

    # Chỉ lấy khoản chưa đến hạn (ngày ĐH > hôm nay)
    mask_tuong_lai = ngay_dh > ref_ts

    # KH không hoạt động > 90 ngày
    mask_khong_hd = df_kh["is_3m_inactive"].fillna(False).astype(bool)

    # Lọc theo phạm vi
    if scope == "thang":
        mask_scope = (
            (ngay_dh.dt.year == ref_date.year)
            & (ngay_dh.dt.month == ref_date.month)
        )
    elif scope == "quy":
        quy_ht = _quy_cua(ref_date.month)
        mask_scope = (
            (ngay_dh.dt.year == ref_date.year)
            & (ngay_dh.dt.month.apply(_quy_cua) == quy_ht)
        )
    else:  # nam
        mask_scope = ngay_dh.dt.year == ref_date.year

    mask = mask_tuong_lai & mask_khong_hd & mask_scope
    result = df_kh[mask].copy()
    result["_ngay_dh"] = ngay_dh[mask].values
    return result


def tinh_chuyen_nqh_thang(
    df_kh: pd.DataFrame,
    ref_date: datetime,
) -> pd.DataFrame:
    """
    Khoản vay chuyển NQH trong tháng hiện tại.

    Điều kiện:
        - Dư nợ QH > 0
        - Ngày ĐH cùng tháng/năm với hôm nay AND ngày ≤ hôm nay
          (tức là đã đến hạn nhưng chưa trả, phát sinh QH trong tháng này)
    """
    ngay_dh = _parse_ngay_dh(df_kh)
    du_qh = pd.to_numeric(
        df_kh[COT_DU_NO_QH] if COT_DU_NO_QH in df_kh.columns else pd.Series(0, index=df_kh.index),
        errors="coerce",
    ).fillna(0)

    mask_qh = du_qh > 0
    mask_thang = (
        (ngay_dh.dt.year == ref_date.year)
        & (ngay_dh.dt.month == ref_date.month)
        & (ngay_dh.dt.day <= ref_date.day)
    )

    result = df_kh[mask_qh & mask_thang].copy()
    result["_ngay_dh"] = ngay_dh[mask_qh & mask_thang].values
    return result


def _bang_hien_thi(df: pd.DataFrame) -> pd.DataFrame:
    """Chuẩn hóa DataFrame để hiển thị — format tiền tệ, tên cột thân thiện."""
    cols = [
        COT_TEN_PGD, COT_TEN_XA, COT_TEN_KH, COT_SO_KU,
        COT_TEN_CT, "_ngay_dh", COT_TONG_DU_NO, COT_DU_NO_QH,
        COT_LAI_TON, "so_thang_khong_hd",
    ]
    cols_co = [c for c in cols if c in df.columns]
    out = df[cols_co].copy()

    # Ngày ĐH → chuỗi dễ đọc
    if "_ngay_dh" in out.columns:
        out["_ngay_dh"] = pd.to_datetime(out["_ngay_dh"], errors="coerce").dt.strftime("%d/%m/%Y")
        out = out.rename(columns={"_ngay_dh": "Ngày ĐH"})

    # Số tháng KHĐ
    if "so_thang_khong_hd" in out.columns:
        out = out.rename(columns={"so_thang_khong_hd": "Tháng KHĐ"})

    # Format tiền → tỷ đồng
    for col in [COT_TONG_DU_NO, COT_DU_NO_QH, COT_LAI_TON]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").apply(
                lambda x: fmt_ty(x) if pd.notna(x) else "—"
            )

    return out


# ─── Biểu đồ heatmap tháng ────────────────────────────────────────────────────

def _heatmap_thang(df_soon: pd.DataFrame, key_prefix: str) -> None:
    """Bar chart: số khoản sắp đến hạn theo tháng (tối đa 18 tháng tới)."""
    if df_soon.empty or "_ngay_dh" not in df_soon.columns:
        return

    try:
        import plotly.graph_objects as go
    except ImportError:
        return

    ngay_dh = pd.to_datetime(df_soon["_ngay_dh"], errors="coerce")
    df_plot = df_soon.copy()
    df_plot["_ym"] = ngay_dh.dt.to_period("M").astype(str)

    agg: dict = {"so_mon": ("_ym", "count")}
    if COT_TONG_DU_NO in df_plot.columns:
        agg["tong_dn"] = (COT_TONG_DU_NO, "sum")

    nhom = df_plot.groupby("_ym").agg(**agg).reset_index().sort_values("_ym")
    if nhom.empty:
        return

    hover_text = nhom["so_mon"].astype(str) + " món"
    if "tong_dn" in nhom.columns:
        hover_text = hover_text + "<br>" + nhom["tong_dn"].apply(
            lambda x: fmt_ty(x) if pd.notna(x) else ""
        )

    fig = go.Figure(go.Bar(
        x=nhom["_ym"],
        y=nhom["so_mon"],
        marker_color="#ef5350",
        text=nhom["so_mon"].astype(str),
        textposition="outside",
        hovertext=hover_text,
        hoverinfo="x+text",
    ))
    fig.update_layout(
        xaxis_title="Tháng đáo hạn",
        yaxis_title="Số khoản",
        height=280,
        margin=dict(t=20, b=30, l=40, r=20),
    )
    st.markdown("**📅 Phân bổ theo tháng đáo hạn**")
    st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}som_hm_bar")


# ─── Render core ──────────────────────────────────────────────────────────────

def _render_canh_bao(
    df_kh: pd.DataFrame,
    ds_pgd_all: list[str],
    key_prefix: str,
    la_cn: bool,
) -> None:
    """Core render — dùng chung cho CN và PGD."""
    today = datetime.now()

    # ── Scope toggle ──────────────────────────────────────────────
    scope_label = st.radio(
        "🔭 Phạm vi cảnh báo",
        ["Tháng này", "Quý này", "Năm nay"],
        horizontal=True,
        key=f"{key_prefix}som_scope",
    )
    scope_map = {"Tháng này": "thang", "Quý này": "quy", "Năm nay": "nam"}
    scope_code = scope_map[scope_label]

    # ── Tính toán ────────────────────────────────────────────────
    df_soon = tinh_du_soon_dormant(df_kh, today, scope_code)
    so_mon_soon = len(df_soon)
    tong_dn_soon = (
        pd.to_numeric(df_soon[COT_TONG_DU_NO], errors="coerce").sum()
        if not df_soon.empty and COT_TONG_DU_NO in df_soon.columns
        else 0
    )

    # ── KPI Cards ────────────────────────────────────────────────
    k1 = st.columns(1)[0]
    label_scope = scope_label.lower().replace(" ", " ")
    k1.metric(
        f"⚠️ Sắp đến hạn + KH không HĐ ({scope_label})",
        fmt_so(so_mon_soon),
        delta=fmt_ty(tong_dn_soon) if tong_dn_soon > 0 else None,
        delta_color="inverse" if so_mon_soon > 0 else "off",
    )

    # ── Heatmap tháng ─────────────────────────────────────────────
    if not df_soon.empty:
        _heatmap_thang(df_soon, key_prefix)

    # ── Thông tin COT_NGAY_DH ────────────────────────────────────
    if COT_NGAY_DH not in df_kh.columns:
        st.warning(
            f"⚠️ Không tìm thấy cột '{COT_NGAY_DH}' trong dữ liệu. "
            "Nợ đến hạn có nguy cơ cần cột ngày đến hạn để hoạt động."
        )
        return

    # ── Chi tiết ─────────────────────────────────────────
    st.markdown(f"**⚠️ Sắp đến hạn + KH không HĐ ({fmt_so(so_mon_soon)} món)**")

    if df_soon.empty:
        st.success(
            f"✅ Không có khoản vay nào sắp đến hạn trong {scope_label.lower()} "
            "mà khách hàng đang không hoạt động."
        )
    else:
        df_filter_soon = df_soon.copy()
        if la_cn and ds_pgd_all:
            state = SCMStateManager()
            _key_pgd = f"{key_prefix}som_pgd_soon"
            _desired_pgd = state.filter_pgd or "Tất cả"
            if _key_pgd not in st.session_state:
                st.session_state[_key_pgd] = _desired_pgd if _desired_pgd in (["Tất cả"] + ds_pgd_all) else "Tất cả"
            loc_pgd = st.selectbox(
                "Lọc PGD", ["Tất cả"] + ds_pgd_all,
                key=_key_pgd,
            )
            if loc_pgd != "Tất cả" and COT_TEN_PGD in df_filter_soon.columns:
                df_filter_soon = df_filter_soon[df_filter_soon[COT_TEN_PGD] == loc_pgd]
                state.filter_pgd = loc_pgd
            else:
                state.filter_pgd = None

        df_hien = _bang_hien_thi(df_filter_soon)
        hien_thi_dataframe_phan_trang(df_hien, key=f"{key_prefix}som_tbl_soon", height=380)

        if st.button(
            f"📥 Xuất Excel ({len(df_filter_soon)} món)",
            key=f"{key_prefix}som_xuat_soon",
        ):
            state = SCMStateManager()
            _dl_key = f"{key_prefix}som_excel_soon"
            state.downloads.set(
                _dl_key,
                xuat_excel({"Sắp đến hạn KHĐ": df_hien}),
                f"CanhBaoSom_{scope_label.replace(' ', '_')}_{today.strftime('%Y%m%d')}.xlsx",
            )
        state = SCMStateManager()
        _dl_key = f"{key_prefix}som_excel_soon"
        if state.downloads.has(_dl_key):
            if st.download_button(
                "⬇️ Tải về",
                data=state.downloads.get_bytes(_dl_key) or b"",
                file_name=state.downloads.get_filename(_dl_key) or f"CanhBaoSom_{scope_label.replace(' ', '_')}_{today.strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"{key_prefix}som_dl_soon",
            ):
                state.downloads.clear(_dl_key)



# ─── Public render ────────────────────────────────────────────────────────────

def render(tab: DeltaGenerator = None, **kwargs) -> None:
    """
    Render tab Nợ đến hạn có nguy cơ.

    Dùng được ở cả CN (truyền df_full) và PGD (truyền df đã lọc theo PGD).
    """
    df       = kwargs.get("df")
    df_full  = kwargs.get("df_full", df)
    role_raw = str(kwargs.get("role", "user") or "user")
    role     = normalize_role(role_raw)
    pgd_user = kwargs.get("pgd_user")
    ds_pgd_all = list(kwargs.get("ds_pgd_all", DS_PGD) or DS_PGD)

    ctx = tab if tab is not None else st.container()
    with ctx:
        st.subheader("🚨 Nợ đến hạn có nguy cơ")
        st.caption(
            "Phát hiện khoản vay **sắp đến hạn** + khách hàng "
            "**không giao dịch > 90 ngày** — can thiệp trước khi phát sinh nợ quá hạn."
        )

        use_df = df_full if la_phan_he_cn(role) else df
        if use_df is None or use_df.empty:
            st.warning("⚠️ Chưa có dữ liệu HSTD.")
            return

        df_kh = danh_dau_khong_hd_cached(use_df)

        if la_phan_he_cn(role):
            key_prefix = "cn_"
            _render_canh_bao(df_kh, ds_pgd_all, key_prefix, la_cn=True)
        else:
            from data.pgd import pgd_slug
            slug = pgd_slug(pgd_user) if pgd_user else "pgd"
            key_prefix = f"pgd_{slug}_"
            _render_canh_bao(df_kh, [], key_prefix, la_cn=False)
