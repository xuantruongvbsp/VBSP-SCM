"""
Tab Cảnh báo Khoản vay Đến hạn & Nợ đến hạn có nguy cơ.
Phân tích dư nợ đến hạn trong N tháng tới + phát hiện khoản có nguy cơ chuyển NQH.
"""
from __future__ import annotations

import os
from datetime import datetime

import pandas as pd
import streamlit as st

from auth import la_phan_he_pgd
from logger import get_logger

logger = get_logger(__name__)

from config import (
    CACHE_HSTD, COT_TEN_PGD, COT_TEN_KH, COT_TEN_CT,
    COT_TONG_DU_NO, COT_NGAY_DEN_HAN, COT_MA_KH, COT_TEN_XA,
    COT_SO_KU, COT_DVUT, COT_TEN_TO_TRUONG,
)
from data.den_han import tinh_den_han_df, canh_bao_tap_trung
from data.hstd import danh_dau_khong_hd_cached
from pdf_service import xuat_pdf_group_header, nut_xuat_pdf
from utils import fmt_ty, fmt_so, xuat_excel, ten_file_xuat, hien_thi_dataframe_phan_trang
from state_manager import SCMStateManager


@st.cache_data(show_spinner=False)
def _doc_va_tinh_den_han(pgd_user: str | None, mtime: float) -> pd.DataFrame:
    """Đọc parquet + tính toán den_han; cache theo (pgd_user, mtime file)."""
    try:
        df = pd.read_parquet(CACHE_HSTD)
    except Exception:
        return pd.DataFrame()
    if pgd_user and COT_TEN_PGD in df.columns:
        df = df[df[COT_TEN_PGD] == pgd_user]
    return tinh_den_han_df(df)


def _loc_thang(df_tinh: pd.DataFrame, tu_thang: int, den_thang: int) -> pd.DataFrame:
    col = "Tháng đến hạn còn lại"
    mask = (
        df_tinh[col].notna()
        & (df_tinh[col] >= tu_thang)
        & (df_tinh[col] <= den_thang)
    )
    return df_tinh[mask].copy()


def _selectbox_safe(label: str, options: list, key: str):
    if not options:
        options = ["Tất cả"]
    prev = st.session_state.get(key)
    index = 0 if prev not in options else int(options.index(prev))
    return st.selectbox(label, options=options, index=index, key=key)


def render(tab=None, role: str = None, **kwargs) -> None:
    state = SCMStateManager()
    st.subheader("⏰ Cảnh báo Khoản vay Đến hạn & Nợ đến hạn có nguy cơ")
    st.caption(
        "Phân tích dư nợ đến hạn trong N tháng tới + "
        "phát hiện khoản vay sắp đến hạn có khách hàng không giao dịch > 90 ngày."
    )

    pgd_user = kwargs.get("pgd_user")
    pgd_filter = kwargs.get("pgd_filter")
    _pgd_filter = pgd_user or pgd_filter

    # ── Chế độ xem ──────────────────────────────────────────────────
    key_prefix = kwargs.get("key_prefix", "dh_")

    mode = st.radio(
        "Chế độ xem",
        ["📊 Phân tích Đến hạn", "🚨 Nợ đến hạn có nguy cơ"],
        horizontal=True,
        key=f"{key_prefix}den_han_mode",
    )

    # ── Mode 2: Nợ đến hạn có nguy cơ ───────────────────────────────
    if mode == "🚨 Nợ đến hạn có nguy cơ":
        df_kh = kwargs.get("df_kh")
        ds_pgd_all = list(kwargs.get("ds_pgd_all", []) or [])
        la_cn = kwargs.get("la_cn", False)
        key_prefix = kwargs.get("key_prefix", "dh_")

        if df_kh is None:
            try:
                _mtime = os.path.getmtime(CACHE_HSTD)
                df_full = pd.read_parquet(CACHE_HSTD)
                if _pgd_filter and COT_TEN_PGD in df_full.columns:
                    df_full = df_full[df_full[COT_TEN_PGD] == _pgd_filter]
                df_kh = danh_dau_khong_hd_cached(df_full)
            except Exception:
                st.warning("⚠️ Chưa có dữ liệu HSTD.")
                return

        from tabs.tab_canh_bao_som import _render_canh_bao
        _render_canh_bao(df_kh, ds_pgd_all, key_prefix, la_cn)
        return

    # ── Mode 1: Phân tích Đến hạn ──────────────────────────────────
    try:
        _mtime = os.path.getmtime(CACHE_HSTD)
    except FileNotFoundError:
        st.warning("⚠️ Chưa có dữ liệu HSTD. Vui lòng upload file trước.")
        return

    df_tinh = _doc_va_tinh_den_han(_pgd_filter, _mtime)
    if df_tinh.empty:
        st.warning("⚠️ Chưa có dữ liệu HSTD.")
        return
    if COT_NGAY_DEN_HAN not in df_tinh.columns:
        st.error(f"❌ File HSTD thiếu cột '{COT_NGAY_DEN_HAN}'. Kiểm tra lại file upload.")
        return

    # ── Filters ──────────────────────────────────────────────────────
    _den_thang_map = {"1 tháng": 1, "3 tháng": 3, "6 tháng": 6, "12 tháng": 12}
    den_thang = _den_thang_map[st.radio(
        "Xem trước",
        options=list(_den_thang_map.keys()),
        index=2,
        horizontal=True,
        key=f"{key_prefix}den_han_radio",
    )]

    col_f2, col_f3, col_f4, col_f5, col_f6 = st.columns(5)
    with col_f2:
        if _pgd_filter:
            loc_pgd = "Tất cả"
        elif not la_phan_he_pgd(role) and COT_TEN_PGD in df_tinh.columns:
            ds_pgd_f = sorted(df_tinh[COT_TEN_PGD].dropna().unique().tolist())
            loc_pgd = _selectbox_safe("Lọc PGD", ["Tất cả"] + ds_pgd_f, key=f"{key_prefix}den_han_loc_pgd")
        else:
            loc_pgd = "Tất cả"
            st.caption("Lọc PGD (CN)")

    df_tinh_filtered = df_tinh.copy()
    if loc_pgd != "Tất cả" and COT_TEN_PGD in df_tinh_filtered.columns:
        df_tinh_filtered = df_tinh_filtered[df_tinh_filtered[COT_TEN_PGD] == loc_pgd]

    with col_f3:
        if COT_TEN_XA in df_tinh_filtered.columns:
            ds_xa = sorted(df_tinh_filtered[COT_TEN_XA].dropna().astype(str).unique().tolist())
            loc_xa = _selectbox_safe("Lọc Xã", ["Tất cả"] + ds_xa, key=f"{key_prefix}den_han_loc_xa")
        else:
            loc_xa = "Tất cả"
            st.caption("Không có cột Xã")

    if loc_xa != "Tất cả" and COT_TEN_XA in df_tinh_filtered.columns:
        df_tinh_filtered = df_tinh_filtered[df_tinh_filtered[COT_TEN_XA] == loc_xa]

    with col_f4:
        if COT_TEN_TO_TRUONG in df_tinh_filtered.columns:
            ds_to = sorted(df_tinh_filtered[COT_TEN_TO_TRUONG].dropna().astype(str).unique().tolist())
            loc_to = _selectbox_safe(
                "Lọc Tổ trưởng", ["Tất cả"] + ds_to, key=f"{key_prefix}den_han_loc_to_truong"
            )
        else:
            loc_to = "Tất cả"
            st.caption("Không có cột Tổ trưởng")

    if loc_to != "Tất cả" and COT_TEN_TO_TRUONG in df_tinh_filtered.columns:
        df_tinh_filtered = df_tinh_filtered[df_tinh_filtered[COT_TEN_TO_TRUONG] == loc_to]

    with col_f5:
        if COT_TEN_CT in df_tinh_filtered.columns:
            ds_ct_f = sorted(df_tinh_filtered[COT_TEN_CT].dropna().unique().tolist())
            loc_ct = _selectbox_safe(
                "Lọc Chương trình", ["Tất cả"] + ds_ct_f, key=f"{key_prefix}den_han_loc_ct"
            )
        else:
            loc_ct = "Tất cả"
    with col_f6:
        if COT_DVUT in df_tinh_filtered.columns:
            ds_dvut_f = sorted(df_tinh_filtered[COT_DVUT].dropna().unique().tolist())
            loc_dvut = _selectbox_safe(
                "Lọc Hội đoàn thể", ["Tất cả"] + ds_dvut_f, key=f"{key_prefix}den_han_loc_dvut"
            )
        else:
            loc_dvut = "Tất cả"
    if loc_ct != "Tất cả" and COT_TEN_CT in df_tinh_filtered.columns:
        df_tinh_filtered = df_tinh_filtered[df_tinh_filtered[COT_TEN_CT] == loc_ct]
    if loc_dvut != "Tất cả" and COT_DVUT in df_tinh_filtered.columns:
        df_tinh_filtered = df_tinh_filtered[df_tinh_filtered[COT_DVUT] == loc_dvut]


    df_loc = _loc_thang(df_tinh_filtered, 0, den_thang)
    df_loc = df_loc[pd.to_numeric(df_loc[COT_TONG_DU_NO], errors="coerce").fillna(0) > 0]

    # ── 4 Metrics ────────────────────────────────────────────────────
    tong_khoan = len(df_loc)
    tong_tien = pd.to_numeric(df_loc[COT_TONG_DU_NO], errors="coerce").sum() if tong_khoan > 0 else 0
    so_pgd = df_loc[COT_TEN_PGD].nunique() if tong_khoan > 0 and COT_TEN_PGD in df_loc.columns else 0
    tong_dn_full = pd.to_numeric(df_tinh[COT_TONG_DU_NO], errors="coerce").sum()
    ty_le = tong_tien / tong_dn_full * 100 if tong_dn_full else 0

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Số khoản đến hạn", fmt_so(tong_khoan))
    m2.metric("Dư nợ đến hạn (triệu đ)", fmt_ty(tong_tien))
    m3.metric("Số PGD liên quan", so_pgd)
    m4.metric("Tỷ lệ dư nợ/tổng", f"{ty_le:.2f}".replace(".", ",") + "%")

    # ── Cảnh báo tập trung ───────────────────────────────────────────
    if not df_loc.empty:
        try:
            for cb in canh_bao_tap_trung(df_tinh_filtered, den_thang=den_thang)[:5]:
                ty_le_cb = f"{cb['ty_le'] * 100:.1f}".replace(".", ",") + "%"
                st.warning(
                    f"⚠️ **{cb['pgd']}**: {ty_le_cb} dư nợ đến hạn trong {cb['thang']} "
                    f"— {fmt_ty(cb['tong_den_han'])} / {fmt_ty(cb['tong_pgd'])} triệu đ"
                )
        except Exception as _e:
            logger.error("canh_bao_tap_trung lỗi: %s", _e)

    # ── 3 Tabs ───────────────────────────────────────────────────────
    if not df_loc.empty:
        tab_thang, tab_nhom, tab_ds = st.tabs(["📅 Theo tháng", "🏢 Theo nhóm", "📋 Danh sách"])

        with tab_thang:
            df_nam = _loc_thang(df_tinh, 0, 12)
            df_nam = df_nam[pd.to_numeric(df_nam[COT_TONG_DU_NO], errors="coerce").fillna(0) > 0]
            if loc_pgd != "Tất cả" and COT_TEN_PGD in df_nam.columns:
                df_nam = df_nam[df_nam[COT_TEN_PGD] == loc_pgd]
            if loc_xa != "Tất cả" and COT_TEN_XA in df_nam.columns:
                df_nam = df_nam[df_nam[COT_TEN_XA] == loc_xa]
            if loc_to != "Tất cả" and COT_TEN_TO_TRUONG in df_nam.columns:
                df_nam = df_nam[df_nam[COT_TEN_TO_TRUONG] == loc_to]
            if loc_ct != "Tất cả" and COT_TEN_CT in df_nam.columns:
                df_nam = df_nam[df_nam[COT_TEN_CT] == loc_ct]
            if loc_dvut != "Tất cả" and COT_DVUT in df_nam.columns:
                df_nam = df_nam[df_nam[COT_DVUT] == loc_dvut]

            if df_nam.empty:
                st.info("Không có khoản vay đến hạn trong 12 tháng tới.")
            else:
                df_nam = df_nam.copy()
                df_nam["_ngay_dh"] = pd.to_datetime(df_nam["Ngày đến hạn"], errors="coerce")
                df_nam["_thang_label"] = df_nam["_ngay_dh"].dt.strftime("%m/%Y")
                df_nam["_sort_key"] = df_nam["_ngay_dh"].dt.to_period("M")

                df_th_stats = (
                    df_nam.dropna(subset=["_thang_label"])
                    .groupby(["_sort_key", "_thang_label"], sort=True)
                    .agg(so_khoan=(COT_TONG_DU_NO, "count"), du_no=(COT_TONG_DU_NO, "sum"))
                    .reset_index()
                    .sort_values("_sort_key")
                )
                _today_period = pd.Period(pd.Timestamp.today().strftime("%Y-%m"), freq="M")
                df_th_stats["_thang_so"] = df_th_stats["_sort_key"].apply(
                    lambda p: max(0, (p - _today_period).n)
                )

                if not df_th_stats.empty:
                    tong_du_no_nam = df_th_stats["du_no"].sum()
                    df_th_stats["pct"] = (
                        df_th_stats["du_no"] / tong_du_no_nam * 100
                        if tong_du_no_nam > 0 else 0
                    ).round(1)
                    df_bang = df_th_stats[["_thang_label", "so_khoan", "du_no", "pct"]].copy()
                    df_bang.columns = ["Tháng", "Số khoản", "Dư nợ (triệu đồng)", "Tỷ trọng %"]
                    df_bang["Số khoản"] = df_bang["Số khoản"].apply(fmt_so)
                    df_bang["Dư nợ (triệu đồng)"] = (
                        df_th_stats["du_no"] / 1e6
                    ).round(0).apply(lambda x: f"{x:,.0f}".replace(",", "."))
                    df_bang["Tỷ trọng %"] = df_th_stats["pct"].apply(
                        lambda x: f"{x:.1f}".replace(".", ",") + "%"
                    )
                    st.dataframe(df_bang, use_container_width=True, hide_index=True)

                    try:
                        import plotly.graph_objects as go

                        def _mau_urgency(n: int) -> str:
                            if n <= 2: return "#EF5350"
                            if n <= 4: return "#FF7043"
                            if n <= 6: return "#FFA726"
                            return "#66BB6A"

                        du_no_trieu = (df_th_stats["du_no"] / 1e6).round(0)
                        colors_bar = [_mau_urgency(int(t)) for t in df_th_stats["_thang_so"]]
                        fig = go.Figure(go.Bar(
                            x=df_th_stats["_thang_label"],
                            y=du_no_trieu,
                            text=du_no_trieu.apply(
                                lambda x: f"{x:,.0f}".replace(",", ".")
                            ),
                            textposition="outside",
                            marker_color=colors_bar,
                            customdata=df_th_stats["so_khoan"],
                            hovertemplate=(
                                "<b>%{x}</b><br>"
                                "Dư nợ: %{y:,.0f} triệu<br>"
                                "Số khoản: %{customdata}<extra></extra>"
                            ),
                        ))
                        fig.update_layout(
                            xaxis_title="Tháng đến hạn",
                            yaxis_title="Dư nợ (triệu đồng)",
                            height=380,
                            margin=dict(t=30, b=40, l=10, r=10),
                            showlegend=False,
                            paper_bgcolor="rgba(0,0,0,0)",
                            plot_bgcolor="rgba(0,0,0,0)",
                        )
                        st.plotly_chart(fig, use_container_width=True, key="dh_chart_thang")
                        st.caption(
                            "🔴 Khẩn ≤ 2 tháng &nbsp;·&nbsp; "
                            "🟠 3–4 tháng &nbsp;·&nbsp; "
                            "🟡 5–6 tháng &nbsp;·&nbsp; "
                            "🟢 7–12 tháng"
                        )
                    except Exception as _e:
                        logger.error("Không thể vẽ đồ thị đến hạn: %s", _e, exc_info=True)
                        st.warning(f"Không thể vẽ đồ thị: {_e}")

        with tab_nhom:
            nhom_theo = st.radio(
                "Nhóm theo", ["PGD", "Xã", "Hội đoàn thể"],
                horizontal=True, key="den_han_nhom")
            NHOM_COT_MAP = {"PGD": COT_TEN_PGD, "Xã": COT_TEN_XA, "Hội đoàn thể": COT_DVUT}
            cot_nhom_th = NHOM_COT_MAP[nhom_theo]
            nhom_key = "pgd" if nhom_theo == "PGD" else ("dvut" if nhom_theo == "Hội đoàn thể" else "xa")

            if cot_nhom_th not in df_loc.columns:
                st.info(f"Dữ liệu không có cột nhóm theo {nhom_theo}.")
            else:
                _th_agg = (
                    df_loc.groupby(cot_nhom_th, sort=False)
                    .agg(**{
                        "Số khoản": (COT_MA_KH if COT_MA_KH in df_loc.columns else cot_nhom_th, "count"),
                        "_du_no": (COT_TONG_DU_NO, "sum"),
                    })
                    .reset_index()
                    .sort_values("_du_no", ascending=False)
                    .rename(columns={cot_nhom_th: nhom_theo})
                )
                _th_agg["Số khoản"] = _th_agg["Số khoản"].apply(fmt_so)
                _th_agg["Dư nợ (triệu đồng)"] = (
                    _th_agg["_du_no"] / 1e6
                ).round(0).apply(lambda x: f"{x:,.0f}".replace(",", "."))
                st.dataframe(
                    _th_agg[[nhom_theo, "Số khoản", "Dư nợ (triệu đồng)"]],
                    use_container_width=True, hide_index=True,
                )
                try:
                    import plotly.express as _px
                    _top = _th_agg.nlargest(min(20, len(_th_agg)), "_du_no").sort_values("_du_no")
                    _fig = _px.bar(
                        _top,
                        x="_du_no", y=nhom_theo, orientation="h",
                        color="_du_no",
                        color_continuous_scale=[[0.0, "#C8E6C9"], [0.5, "#43A047"], [1.0, "#1B5E20"]],
                        text="Dư nợ (triệu đồng)",
                        labels={"_du_no": "Dư nợ", nhom_theo: nhom_theo},
                        height=max(300, len(_top) * 36),
                    )
                    _fig.update_traces(textposition="outside",
                                       hovertemplate="<b>%{y}</b><br>Dư nợ: %{text}<extra></extra>")
                    _fig.update_layout(
                        coloraxis_showscale=False,
                        xaxis=dict(showticklabels=False, title=""),
                        yaxis_title="",
                        margin=dict(l=10, r=130, t=20, b=10),
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                    )
                    st.plotly_chart(_fig, use_container_width=True, key=f"dh_bar_nhom_{nhom_key}")
                except Exception as _e:
                    logger.error("Không thể vẽ biểu đồ nhóm: %s", _e, exc_info=True)
                    st.caption(f"Không thể vẽ biểu đồ: {_e}")

        with tab_ds:
            cols_ct_ds = [c for c in [
                COT_TEN_PGD, COT_TEN_KH, COT_TEN_CT, COT_TONG_DU_NO,
                "Ngày đến hạn", "Số tháng có thể gia hạn",
            ] if c in df_loc.columns]
            df_ct = df_loc[cols_ct_ds].copy()
            if "Ngày đến hạn" in df_ct.columns:
                df_ct = df_ct.sort_values("Ngày đến hạn")
                df_ct["Ngày đến hạn"] = pd.to_datetime(
                    df_ct["Ngày đến hạn"], errors="coerce"
                ).dt.strftime("%d/%m/%Y").fillna("")
            df_ct = df_ct.reset_index(drop=True)

            hien_thi_dataframe_phan_trang(df_ct, key="dh_tbl_ds", height=420)

            if COT_TEN_PGD in df_loc.columns:
                df_th_pgd = (
                    df_loc.groupby(COT_TEN_PGD)
                    .agg(**{
                        "Số khoản": (COT_TONG_DU_NO, "count"),
                        "Dư nợ (VND)": (COT_TONG_DU_NO, "sum"),
                    })
                    .reset_index()
                    .sort_values("Dư nợ (VND)", ascending=False)
                )
                df_th_pgd["Dư nợ (VND)"] = df_th_pgd["Dư nợ (VND)"].apply(fmt_so)
                sheets_xuat = {"TH_PGD": df_th_pgd, "Chi tiết": df_ct}
            else:
                sheets_xuat = {"Chi tiết": df_ct}

            col_ex, col_pdf_tab = st.columns(2)
            with col_ex:
                st.download_button(
                    "📥 Xuất Excel",
                    data=xuat_excel(sheets_xuat),
                    file_name=ten_file_xuat(f"DenHan_{den_thang}thang"),
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="btn_xuat_den_han_excel",
                    use_container_width=True,
                )
            with col_pdf_tab:
                nut_xuat_pdf(
                    df=df_ct,
                    tieu_de=f"Hồ sơ đến hạn trong {den_thang} tháng",
                    username=kwargs.get("username", ""),
                    cols_tien=[COT_TONG_DU_NO],
                    prefix_file=f"DenHan_{den_thang}thang",
                    key="btn_pdf_den_han",
                )
    else:
        st.info("Không có khoản vay đến hạn trong khoảng thời gian đã chọn.")

    # ── Xuất PDF Group Header ─────────────────────────────────────────────────
    st.divider()
    st.markdown("#### 📄 Xuất PDF Báo cáo Đến hạn")

    col_g1, col_g2, col_g3 = st.columns(3)
    with col_g1:
        nhom_pdf = st.radio(
            "Nhóm theo (PDF)",
            options=["Chương trình", "PGD", "Xã"],
            horizontal=True,
            key="den_han_nhom_pdf",
        )
    with col_g2:
        loc_pgd_pdf = ""
        if not _pgd_filter and not la_phan_he_pgd(role) and COT_TEN_PGD in df_loc.columns:
            ds_pgd_pdf = sorted(df_loc[COT_TEN_PGD].dropna().unique().tolist())
            loc_pgd_pdf = st.selectbox(
                "Lọc PGD", [""] + ds_pgd_pdf,
                format_func=lambda x: "(Tất cả)" if x == "" else x,
                key="den_han_loc_pgd_pdf",
            )
    with col_g3:
        loc_ct_pdf = ""
        if COT_TEN_CT in df_loc.columns:
            ds_ct_pdf = sorted(df_loc[COT_TEN_CT].dropna().unique().tolist())
            loc_ct_pdf = st.selectbox(
                "Lọc Chương trình", [""] + ds_ct_pdf,
                format_func=lambda x: "(Tất cả)" if x == "" else x,
                key="den_han_loc_ct_pdf",
            )

    df_pdf = df_loc.copy()
    if "Ngày đến hạn" in df_pdf.columns:
        df_pdf["Ngày đến hạn"] = pd.to_datetime(
            df_pdf["Ngày đến hạn"], errors="coerce"
        ).dt.strftime("%d/%m/%Y").fillna("")
    if loc_pgd_pdf and COT_TEN_PGD in df_pdf.columns:
        df_pdf = df_pdf[df_pdf[COT_TEN_PGD] == loc_pgd_pdf]
    if loc_ct_pdf and COT_TEN_CT in df_pdf.columns:
        df_pdf = df_pdf[df_pdf[COT_TEN_CT] == loc_ct_pdf]

    _nhom_col_map_pdf = {"Chương trình": COT_TEN_CT, "PGD": COT_TEN_PGD, "Xã": COT_TEN_XA}
    nhom_col_pdf = _nhom_col_map_pdf[nhom_pdf]
    _detail_pdf_cols = [c for c in [
        COT_MA_KH, COT_TEN_KH, COT_SO_KU,
        "Ngày đến hạn", "Số tháng có thể gia hạn",
        COT_TONG_DU_NO,
    ] if c in df_pdf.columns]
    if nhom_col_pdf not in _detail_pdf_cols:
        _detail_pdf_cols = [nhom_col_pdf] + _detail_pdf_cols
    else:
        _detail_pdf_cols = [nhom_col_pdf] + [c for c in _detail_pdf_cols if c != nhom_col_pdf]

    if st.button("📄 Xuất PDF Group Header", key="btn_pdf_den_han_group", type="primary"):
        if df_pdf.empty:
            st.warning("⚠️ Không có dữ liệu sau khi lọc để xuất PDF.")
        else:
            username = st.session_state.get("username", "VBSP-SCM")
            _tieu_de_phu_parts = []
            if loc_pgd_pdf:
                _tieu_de_phu_parts.append(f"PGD: {loc_pgd_pdf}")
            if loc_ct_pdf:
                _tieu_de_phu_parts.append(f"CT: {loc_ct_pdf}")
            _tieu_de_phu = "  |  ".join(_tieu_de_phu_parts) if _tieu_de_phu_parts else ""
            try:
                with st.spinner("⏳ Đang tạo PDF, vui lòng chờ..."):
                    pdf_bytes = xuat_pdf_group_header(
                        df=df_pdf[_detail_pdf_cols].sort_values(
                            [nhom_col_pdf, "Ngày đến hạn"]
                            if "Ngày đến hạn" in df_pdf.columns
                            else [nhom_col_pdf]
                        ),
                        tieu_de=f"Báo cáo Khoản vay Đến hạn trong {den_thang} tháng",
                        nhom_theo=nhom_col_pdf,
                        nguoi_xuat=username,
                        cols_tien=[COT_TONG_DU_NO],
                        tieu_de_phu=_tieu_de_phu,
                        loc_pgd=loc_pgd_pdf,
                        loc_ct=loc_ct_pdf,
                        loc_xa="",
                    )
                state.downloads.set(
                    "den_han_group_pdf",
                    pdf_bytes,
                    f"DenHan_{den_thang}thang_{datetime.now().strftime('%d%m%Y_%H%M')}.pdf",
                )
            except Exception as _e:
                logger.error("Lỗi tạo PDF đến hạn: %s", _e, exc_info=True)
                state.downloads.clear("den_han_group_pdf")
                st.error(f"❌ Lỗi tạo PDF: {_e}")

    if state.downloads.has("den_han_group_pdf"):
        if st.download_button(
            label="⬇ Tải file PDF",
            data=state.downloads.get_bytes("den_han_group_pdf"),
            file_name=state.downloads.get_filename("den_han_group_pdf") or f"DenHan_{den_thang}thang_{datetime.now().strftime('%d%m%Y_%H%M')}.pdf",
            mime="application/pdf",
            key="btn_pdf_den_han_group_dl",
        ):
            state.downloads.clear("den_han_group_pdf")
