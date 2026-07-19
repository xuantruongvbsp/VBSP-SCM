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
    COT_SO_KU, COT_DVUT, COT_TEN_TO_TRUONG, COT_TEN_TO,
    COT_DU_NO_QH, COT_DU_NO_KHOANH,
)
from data.den_han import tinh_den_han_df, canh_bao_tap_trung
from data.hstd import danh_dau_khong_hd_cached
from pdf_service import xuat_pdf_group_header
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


# ══════════════════════════════════════════════════════════════════════════════
# EXPORT HELPERS — Excel & PDF
# ══════════════════════════════════════════════════════════════════════════════


def _fmt_trieu(x) -> str:
    """Format số triệu đồng kiểu VN."""
    try:
        v = float(x)
        return f"{v:,.0f}".replace(",", ".")
    except (ValueError, TypeError):
        return str(x)


def _build_thang_stats(df_loc: pd.DataFrame) -> pd.DataFrame:
    """Xây dựng bảng thống kê theo tháng (12 tháng tới) cho export."""
    if df_loc.empty or "Ngày đến hạn" not in df_loc.columns:
        return pd.DataFrame()
    df_n = df_loc.copy()
    df_n["_ngay_dh"] = pd.to_datetime(df_n["Ngày đến hạn"], errors="coerce")
    df_n["_thang_label"] = df_n["_ngay_dh"].dt.strftime("%m/%Y")
    df_n["_sort_key"] = df_n["_ngay_dh"].dt.to_period("M")
    df_n = df_n.dropna(subset=["_thang_label"])

    stats = (
        df_n.groupby(["_sort_key", "_thang_label"], sort=True)
        .agg(**{"Số khoản": (COT_TONG_DU_NO, "count"), "Dư nợ (VND)": (COT_TONG_DU_NO, "sum")})
        .reset_index()
        .sort_values("_sort_key")
    )
    tong_dn = pd.to_numeric(stats["Dư nợ (VND)"], errors="coerce").sum()
    stats["Dư nợ (triệu đồng)"] = (stats["Dư nợ (VND)"] / 1e6).round(0)
    stats["Tỷ trọng %"] = (
        (stats["Dư nợ (VND)"] / tong_dn * 100) if tong_dn > 0 else 0
    ).round(1)
    # Format hiển thị
    out = pd.DataFrame({
        "Tháng": stats["_thang_label"].values,
        "Số khoản": stats["Số khoản"].apply(fmt_so).values,
        "Dư nợ (triệu đồng)": stats["Dư nợ (triệu đồng)"].apply(_fmt_trieu).values,
        "Tỷ trọng %": stats["Tỷ trọng %"].apply(lambda x: f"{x:.1f}".replace(".", ",") + "%").values,
    })
    return out


def _build_nhom_stats(df_loc: pd.DataFrame, cot_nhom: str, ten_nhom: str) -> pd.DataFrame:
    """Xây dựng bảng thống kê theo nhóm (PGD/Xã/Hội/Tổ)."""
    if df_loc.empty or cot_nhom not in df_loc.columns:
        return pd.DataFrame()
    agg = (
        df_loc.groupby(cot_nhom, sort=False)
        .agg(**{
            "Số khoản": (COT_MA_KH if COT_MA_KH in df_loc.columns else cot_nhom, "count"),
            "_du_no": (COT_TONG_DU_NO, "sum"),
        })
        .reset_index()
        .sort_values("_du_no", ascending=False)
    )
    out = pd.DataFrame({
        ten_nhom: agg[cot_nhom].values,
        "Số khoản": agg["Số khoản"].apply(fmt_so).values,
        "Dư nợ (triệu đồng)": (agg["_du_no"] / 1e6).round(0).apply(_fmt_trieu).values,
    })
    return out


def _build_chi_tiet_sheet(df_loc: pd.DataFrame) -> pd.DataFrame:
    """Xây dựng sheet chi tiết cho Excel."""
    cols = [c for c in [
        COT_TEN_PGD, COT_TEN_KH, COT_TEN_CT, COT_SO_KU,
        COT_TONG_DU_NO, "Ngày đến hạn", "Số tháng có thể gia hạn",
    ] if c in df_loc.columns]
    df = df_loc[cols].copy()
    if "Ngày đến hạn" in df.columns:
        df["Ngày đến hạn"] = pd.to_datetime(
            df["Ngày đến hạn"], errors="coerce"
        ).dt.strftime("%d/%m/%Y").fillna("")
    if COT_TONG_DU_NO in df.columns:
        df[COT_TONG_DU_NO] = pd.to_numeric(
            df[COT_TONG_DU_NO], errors="coerce"
        ).apply(fmt_ty)
    return df.sort_values("Ngày đến hạn" if "Ngày đến hạn" in df.columns else cols[0]).reset_index(drop=True)


def _xay_dung_sheets_excel(
    df_loc: pd.DataFrame,
    den_thang: int,
    _co_db: bool = False,
) -> dict[str, pd.DataFrame]:
    """Xây dựng dict sheets đầy đủ cho export Excel."""
    sheets: dict[str, pd.DataFrame] = {}

    # 1. Tổng hợp
    tong_khoan = len(df_loc)
    tong_tien = pd.to_numeric(df_loc[COT_TONG_DU_NO], errors="coerce").sum()
    so_pgd = df_loc[COT_TEN_PGD].nunique() if COT_TEN_PGD in df_loc.columns else 0
    so_xa = df_loc[COT_TEN_XA].nunique() if COT_TEN_XA in df_loc.columns else 0
    so_to = df_loc[COT_TEN_TO].nunique() if COT_TEN_TO in df_loc.columns else 0

    th_data = {
        "Chỉ tiêu": [
            "Khoảng thời gian", "Số khoản đến hạn", "Dư nợ đến hạn (triệu đồng)",
            "Số PGD", "Số Xã/Phường", "Số Tổ TK&VV",
        ],
        "Giá trị": [
            f"{den_thang} tháng", fmt_so(tong_khoan), fmt_ty(tong_tien),
            fmt_so(so_pgd), fmt_so(so_xa), fmt_so(so_to),
        ],
    }
    sheets["Tổng hợp"] = pd.DataFrame(th_data)

    # 2. Theo tháng
    th_thang = _build_thang_stats(df_loc)
    if not th_thang.empty:
        sheets["Theo tháng"] = th_thang

    # 3. Theo PGD
    th_pgd = _build_nhom_stats(df_loc, COT_TEN_PGD, "PGD")
    if not th_pgd.empty:
        sheets["Theo PGD"] = th_pgd

    # 4. Theo Xã
    th_xa = _build_nhom_stats(df_loc, COT_TEN_XA, "Xã/Phường")
    if not th_xa.empty:
        sheets["Theo Xã"] = th_xa

    # 5. Theo Hội đoàn thể
    th_hoi = _build_nhom_stats(df_loc, COT_DVUT, "Hội đoàn thể")
    if not th_hoi.empty:
        sheets["Theo Hội"] = th_hoi

    # 6. Theo Tổ TK&VV
    th_to = _build_nhom_stats(df_loc, COT_TEN_TO, "Tổ TK&VV")
    if not th_to.empty:
        sheets["Theo Tổ"] = th_to

    # 7. Chi tiết
    sheets["Chi tiết"] = _build_chi_tiet_sheet(df_loc)

    # 8. NQ11 (nếu có)
    if _co_db and "_ct_db" in df_loc.columns:
        df_nq11 = df_loc[df_loc["_ct_db"].str.contains("NQ11")]
        if not df_nq11.empty:
            cols_nq11 = [c for c in [
                COT_TEN_PGD, COT_TEN_KH, COT_SO_KU, COT_TEN_CT,
                COT_TONG_DU_NO, "Ngày đến hạn",
            ] if c in df_nq11.columns]
            df_nq11_xuat = df_nq11[cols_nq11].copy()
            if "Ngày đến hạn" in df_nq11_xuat.columns:
                df_nq11_xuat["Ngày đến hạn"] = pd.to_datetime(
                    df_nq11_xuat["Ngày đến hạn"], errors="coerce"
                ).dt.strftime("%d/%m/%Y").fillna("")
            if COT_TONG_DU_NO in df_nq11_xuat.columns:
                df_nq11_xuat[COT_TONG_DU_NO] = pd.to_numeric(
                    df_nq11_xuat[COT_TONG_DU_NO], errors="coerce"
                ).apply(fmt_ty)
            sheets["NQ11"] = df_nq11_xuat

    return sheets


def _xuat_pdf_den_han(
    df_loc: pd.DataFrame,
    den_thang: int,
    username: str,
) -> bytes:
    """Xuất PDF hoàn chỉnh: biểu đồ phân bổ theo tháng + bảng chi tiết."""
    from components.export_pdf import xuat_pdf_co_chart

    # Build biểu đồ phân bổ theo tháng
    figs = []
    th_thang = _build_thang_stats(df_loc)
    if not th_thang.empty:
        try:
            import plotly.graph_objects as go

            # Đọc lại số thô cho chart
            df_chart = df_loc.copy()
            df_chart["_ngay_dh"] = pd.to_datetime(df_chart["Ngày đến hạn"], errors="coerce")
            df_chart["_thang_label"] = df_chart["_ngay_dh"].dt.strftime("%m/%Y")
            df_chart["_sort_key"] = df_chart["_ngay_dh"].dt.to_period("M")
            df_chart = df_chart.dropna(subset=["_thang_label"])

            stats = (
                df_chart.groupby(["_sort_key", "_thang_label"], sort=True)
                .agg(du_no=(COT_TONG_DU_NO, "sum"), so_khoan=(COT_TONG_DU_NO, "count"))
                .reset_index()
                .sort_values("_sort_key")
            )
            _today_period = pd.Period(pd.Timestamp.today().strftime("%Y-%m"), freq="M")
            stats["_thang_so"] = stats["_sort_key"].apply(
                lambda p: max(0, (p - _today_period).n)
            )

            def _mau(n: int) -> str:
                if n <= 2: return "#EF5350"
                if n <= 4: return "#FF7043"
                if n <= 6: return "#FFA726"
                return "#66BB6A"

            du_no_tr = (stats["du_no"] / 1e6).round(0)
            colors_bar = [_mau(int(t)) for t in stats["_thang_so"]]

            fig = go.Figure(go.Bar(
                x=stats["_thang_label"],
                y=du_no_tr,
                text=du_no_tr.apply(lambda x: f"{x:,.0f}".replace(",", ".")),
                textposition="outside",
                marker_color=colors_bar,
                customdata=stats["so_khoan"],
                hovertemplate=(
                    "<b>%{x}</b><br>Dư nợ: %{y:,.0f} triệu<br>"
                    "Số khoản: %{customdata}<extra></extra>"
                ),
            ))
            fig.update_layout(
                title=f"Phân bổ dư nợ đến hạn theo tháng (trong {den_thang} tháng)",
                xaxis_title="Tháng đến hạn",
                yaxis_title="Dư nợ (triệu đồng)",
                height=400,
                margin=dict(t=50, b=40, l=10, r=10),
                showlegend=False,
            )
            figs.append((fig, f"Phân bổ dư nợ đến hạn {den_thang} tháng tới"))
        except Exception as _e:
            logger.error("_xuat_pdf_den_han chart: %s", _e, exc_info=True)

    # Build bảng chi tiết
    df_pdf = _build_chi_tiet_sheet(df_loc)

    return xuat_pdf_co_chart(
        df=df_pdf,
        tieu_de=f"Báo cáo Khoản vay Đến hạn trong {den_thang} tháng",
        nguoi_xuat=username,
        figs=figs if figs else None,
        cols_tien=[COT_TONG_DU_NO],
        don_vi_tien="triệu đồng",
        prefix_file=f"DenHan_{den_thang}thang",
        them_dong_tong=False,
        them_ngay_xuat=True,
    )


def _render_to_tkv(
    df_loc: pd.DataFrame,
    df_full: pd.DataFrame | None,
    key_prefix: str = "dh_",
) -> None:
    """Phân tích Tổ TK&VV: đến hạn theo tổ + tổ có NQH/khoanh > 0."""
    _dh_sub_labels = ["📅 Đến hạn theo Tổ", "🔴 Tổ có NQH / Nợ khoanh"]
    _dh_sub_sel = st.radio("", range(len(_dh_sub_labels)), format_func=lambda i: _dh_sub_labels[i],
                           horizontal=True, key=f"{key_prefix}sub_to_tab", label_visibility="collapsed")
    st.divider()

    # ── Phần 1: Đến hạn theo Tổ ─────────────────────────────────────────
    if _dh_sub_sel == 0:
        if COT_TEN_TO not in df_loc.columns:
            st.info("Dữ liệu không có cột Tên tổ.")
        elif df_loc.empty:
            st.info("Không có khoản vay đến hạn trong khoảng thời gian đã chọn.")
        else:
            _agg_to: dict = {
                "Số khoản": (COT_MA_KH if COT_MA_KH in df_loc.columns else COT_TEN_TO, "count"),
                "_du_no": (COT_TONG_DU_NO, "sum"),
            }
            _to_dh = (
                df_loc.groupby(COT_TEN_TO, sort=False)
                .agg(**_agg_to)
                .reset_index()
                .sort_values("_du_no", ascending=False)
            )
            _to_dh["Dư nợ đến hạn (triệu đ)"] = (
                _to_dh["_du_no"] / 1e6
            ).round(0).apply(lambda x: f"{x:,.0f}".replace(",", "."))
            _to_dh["Số khoản"] = _to_dh["Số khoản"].apply(fmt_so)

            col_to_truong = COT_TEN_TO_TRUONG if COT_TEN_TO_TRUONG in df_loc.columns else None
            if col_to_truong:
                _truong_map = (
                    df_loc.dropna(subset=[COT_TEN_TO, COT_TEN_TO_TRUONG])
                    .groupby(COT_TEN_TO)[COT_TEN_TO_TRUONG]
                    .agg(lambda s: s.mode().iloc[0] if len(s) else "")
                    .to_dict()
                )
                _to_dh["Tổ trưởng"] = _to_dh[COT_TEN_TO].map(_truong_map).fillna("")

            # Đếm NQ11/GQVL per tổ nếu đã được gắn nhãn
            if "_ct_db" in df_loc.columns:
                _nq11_per_to = (
                    df_loc[df_loc["_ct_db"].str.contains("NQ11")]
                    .groupby(COT_TEN_TO).size().rename("NQ11")
                )
                _gqvl_per_to = (
                    df_loc[df_loc["_ct_db"].str.contains("GQVL")]
                    .groupby(COT_TEN_TO).size().rename("GQVL")
                )
                _to_dh = _to_dh.join(_nq11_per_to, on=COT_TEN_TO, how="left")
                _to_dh = _to_dh.join(_gqvl_per_to, on=COT_TEN_TO, how="left")
                for _c in ["NQ11", "GQVL"]:
                    if _c in _to_dh.columns:
                        _to_dh[_c] = _to_dh[_c].fillna(0).astype(int).apply(
                            lambda x: str(x) if x > 0 else "—"
                        )

            cols_show = [COT_TEN_TO]
            if col_to_truong:
                cols_show.append("Tổ trưởng")
            cols_show += ["Số khoản", "Dư nợ đến hạn (triệu đ)"]
            for _c in ["NQ11", "GQVL"]:
                if _c in _to_dh.columns:
                    cols_show.append(_c)
            _to_dh_show = _to_dh[[c for c in cols_show if c in _to_dh.columns]]
            st.caption(f"Tổng: **{len(_to_dh_show)}** tổ có khoản đến hạn")
            st.dataframe(_to_dh_show, use_container_width=True, hide_index=True)

            try:
                import plotly.express as _px
                _top_to = _to_dh.nlargest(min(20, len(_to_dh)), "_du_no").sort_values("_du_no")
                _fig_to = _px.bar(
                    _top_to,
                    x="_du_no", y=COT_TEN_TO, orientation="h",
                    color="_du_no",
                    color_continuous_scale=[[0.0, "#FFF9C4"], [0.5, "#F9A825"], [1.0, "#E65100"]],
                    text="Dư nợ đến hạn (triệu đ)",
                    labels={"_du_no": "Dư nợ", COT_TEN_TO: "Tổ"},
                    height=max(300, len(_top_to) * 34),
                )
                _fig_to.update_traces(textposition="outside",
                                      hovertemplate="<b>%{y}</b><br>Dư nợ: %{text}<extra></extra>")
                _fig_to.update_layout(
                    coloraxis_showscale=False,
                    xaxis=dict(showticklabels=False, title=""),
                    yaxis_title="",
                    margin=dict(l=10, r=140, t=20, b=10),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                )
                st.plotly_chart(_fig_to, use_container_width=True, key=f"{key_prefix}bar_to_dh")
            except Exception as _e:
                logger.error("_render_to_tkv chart: %s", _e, exc_info=True)

    # ── Phần 2: Tổ có NQH / Nợ khoanh > 0 ──────────────────────────────
    elif _dh_sub_sel == 1:
        df_src = df_full if df_full is not None and not df_full.empty else df_loc
        if COT_TEN_TO not in df_src.columns:
            st.info("Dữ liệu không có cột Tên tổ.")
            return

        _has_qh = COT_DU_NO_QH in df_src.columns
        _has_kh = COT_DU_NO_KHOANH in df_src.columns
        if not _has_qh and not _has_kh:
            st.info("Dữ liệu không có cột NQH / Nợ khoanh.")
            return

        _agg_spec: dict = {
            "Số khoản": (COT_MA_KH if COT_MA_KH in df_src.columns else COT_TEN_TO, "count"),
            "_dn": (COT_TONG_DU_NO, "sum"),
        }
        if _has_qh:
            _agg_spec["_nqh"] = (COT_DU_NO_QH, "sum")
        if _has_kh:
            _agg_spec["_khoanh"] = (COT_DU_NO_KHOANH, "sum")

        _to_nqh = (
            df_src.groupby(COT_TEN_TO, sort=False)
            .agg(**_agg_spec)
            .reset_index()
        )

        # Chỉ giữ tổ có NQH > 0 hoặc khoanh > 0
        _mask_nqh = (_to_nqh.get("_nqh", pd.Series(0, index=_to_nqh.index)) > 0) | \
                    (_to_nqh.get("_khoanh", pd.Series(0, index=_to_nqh.index)) > 0)
        _to_nqh_co = _to_nqh[_mask_nqh].copy()

        if _to_nqh_co.empty:
            st.success("✅ Không có tổ nào có NQH hoặc nợ khoanh.")
            return

        st.warning(f"⚠️ **{len(_to_nqh_co)}** tổ có NQH hoặc nợ khoanh > 0")

        # Tổ trưởng
        if COT_TEN_TO_TRUONG in df_src.columns:
            _truong_map2 = (
                df_src.dropna(subset=[COT_TEN_TO, COT_TEN_TO_TRUONG])
                .groupby(COT_TEN_TO)[COT_TEN_TO_TRUONG]
                .agg(lambda s: s.mode().iloc[0] if len(s) else "")
                .to_dict()
            )
            _to_nqh_co["Tổ trưởng"] = _to_nqh_co[COT_TEN_TO].map(_truong_map2).fillna("")

        # Tỷ lệ NQH
        if _has_qh:
            _to_nqh_co["Tỷ lệ NQH"] = (
                _to_nqh_co["_nqh"] / _to_nqh_co["_dn"].replace(0, float("nan")) * 100
            ).round(2).apply(lambda x: f"{x:.2f}".replace(".", ",") + "%" if pd.notna(x) else "")
            _to_nqh_co["NQH (triệu đ)"] = (_to_nqh_co["_nqh"] / 1e6).round(0).apply(
                lambda x: f"{x:,.0f}".replace(",", "."))

        if _has_kh:
            _to_nqh_co["Khoanh (triệu đ)"] = (_to_nqh_co["_khoanh"] / 1e6).round(0).apply(
                lambda x: f"{x:,.0f}".replace(",", "."))

        _out_cols = [c for c in [
            COT_TEN_TO, "Tổ trưởng", "Số khoản",
            "NQH (triệu đ)", "Tỷ lệ NQH", "Khoanh (triệu đ)",
        ] if c in _to_nqh_co.columns]
        _to_nqh_co["Số khoản"] = _to_nqh_co["Số khoản"].apply(fmt_so)
        _to_show = _to_nqh_co[_out_cols].sort_values(
            "NQH (triệu đ)" if "NQH (triệu đ)" in _out_cols else _out_cols[0],
            ascending=False,
        )
        st.dataframe(_to_show, use_container_width=True, hide_index=True)

        # Bar chart NQH
        if _has_qh:
            try:
                import plotly.express as _px2
                _top_nqh = _to_nqh_co.nlargest(min(20, len(_to_nqh_co)), "_nqh").sort_values("_nqh")
                _fig_nqh = _px2.bar(
                    _top_nqh,
                    x="_nqh", y=COT_TEN_TO, orientation="h",
                    color="_nqh",
                    color_continuous_scale=[[0.0, "#FFCDD2"], [0.5, "#E53935"], [1.0, "#B71C1C"]],
                    text="NQH (triệu đ)" if "NQH (triệu đ)" in _top_nqh.columns else "_nqh",
                    labels={"_nqh": "NQH", COT_TEN_TO: "Tổ"},
                    height=max(300, len(_top_nqh) * 34),
                )
                _fig_nqh.update_traces(textposition="outside",
                                       hovertemplate="<b>%{y}</b><br>NQH: %{text}<extra></extra>")
                _fig_nqh.update_layout(
                    coloraxis_showscale=False,
                    xaxis=dict(showticklabels=False, title=""),
                    yaxis_title="",
                    margin=dict(l=10, r=140, t=20, b=10),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                )
                st.plotly_chart(_fig_nqh, use_container_width=True, key=f"{key_prefix}bar_to_nqh")
            except Exception as _e:
                logger.error("_render_to_tkv nqh chart: %s", _e, exc_info=True)


def _tinh_diem_rui_ro(row: pd.Series) -> int:
    """Tính điểm rủi ro 0–100 cho 1 hồ sơ."""
    score = 0
    # NQH > 0 → +40
    if COT_DU_NO_QH in row.index:
        nqh = pd.to_numeric(row[COT_DU_NO_QH], errors="coerce")
        if pd.notna(nqh) and nqh > 0:
            score += 40
    # Lãi tồn > 3 tháng → +20
    if COT_LAI_TON in row.index:
        lai = pd.to_numeric(row[COT_LAI_TON], errors="coerce")
        if pd.notna(lai) and lai > 0:
            score += 20
    # KHĐ > 90 ngày → +15
    if "is_3m_inactive" in row.index:
        if row.get("is_3m_inactive", False):
            score += 15
    # Gia hạn → +15
    if "Số tháng có thể gia hạn" in row.index:
        gh = pd.to_numeric(row["Số tháng có thể gia hạn"], errors="coerce")
        if pd.notna(gh) and gh > 0:
            score += 15
    return min(score, 100)


def _badge_rui_ro(score: int) -> str:
    if score >= 60: return "🔴 Cao"
    if score >= 30: return "🟡 Trung bình"
    return "🟢 Thấp"


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


    # Xóa cache Excel khi filter thay đổi để tránh tải file cũ
    _fp = f"{den_thang}|{loc_pgd}|{loc_xa}|{loc_to}|{loc_ct}|{loc_dvut}"
    if st.session_state.get(f"{key_prefix}_dh_fp") != _fp:
        st.session_state.pop("_xls_den_han", None)
        st.session_state[f"{key_prefix}_dh_fp"] = _fp

    df_loc = _loc_thang(df_tinh_filtered, 0, den_thang)
    df_loc = df_loc[pd.to_numeric(df_loc[COT_TONG_DU_NO], errors="coerce").fillna(0) > 0]

    # ── Gắn nhãn NQ11 / GQVL ─────────────────────────────────────────
    # Ưu tiên dùng cột __is_nq11/__is_gqvl từ _enrich_hstd() trong app.py
    df_loc = df_loc.copy()
    if "__is_nq11" in df_loc.columns or "__is_gqvl" in df_loc.columns:
        _is_nq = df_loc.get("__is_nq11", pd.Series(False, index=df_loc.index)).fillna(False).astype(bool)
        _is_gq = df_loc.get("__is_gqvl", pd.Series(False, index=df_loc.index)).fillna(False).astype(bool)
        df_loc["_ct_db"] = "—"
        df_loc.loc[_is_nq & ~_is_gq, "_ct_db"] = "NQ11"
        df_loc.loc[~_is_nq & _is_gq, "_ct_db"] = "GQVL"
        df_loc.loc[_is_nq & _is_gq, "_ct_db"] = "NQ11+GQVL"
    else:
        # Fallback: set-lookup khi chưa enrich (backward compat)
        _df_nq11 = kwargs.get("df_nq11")
        _df_gqvl = kwargs.get("df_sk_gqvl") or kwargs.get("df_gqvl")
        _set_nq11: set[str] = set()
        _set_gqvl: set[str] = set()
        if _df_nq11 is not None and not _df_nq11.empty:
            _ku_col_nq11 = next(
                (c for c in ["Số khế ước", COT_SO_KU] if c in _df_nq11.columns), None)
            if _ku_col_nq11:
                _set_nq11 = set(_df_nq11[_ku_col_nq11].dropna().astype(str).str.strip())
        if _df_gqvl is not None and not _df_gqvl.empty:
            _ku_col_gqvl = next(
                (c for c in ["Số khế ước", COT_SO_KU] if c in _df_gqvl.columns), None)
            if _ku_col_gqvl:
                _set_gqvl = set(_df_gqvl[_ku_col_gqvl].dropna().astype(str).str.strip())
        if (_set_nq11 or _set_gqvl) and COT_SO_KU in df_loc.columns:
            _ku = df_loc[COT_SO_KU].astype(str).str.strip()
            df_loc["_ct_db"] = "—"
            df_loc.loc[_ku.isin(_set_nq11) & ~_ku.isin(_set_gqvl), "_ct_db"] = "NQ11"
            df_loc.loc[~_ku.isin(_set_nq11) & _ku.isin(_set_gqvl), "_ct_db"] = "GQVL"
            df_loc.loc[_ku.isin(_set_nq11) & _ku.isin(_set_gqvl), "_ct_db"] = "NQ11+GQVL"
        else:
            df_loc["_ct_db"] = "—"

    # ── 4 Metrics ────────────────────────────────────────────────────
    tong_khoan = len(df_loc)
    tong_tien = pd.to_numeric(df_loc[COT_TONG_DU_NO], errors="coerce").sum() if tong_khoan > 0 else 0
    so_pgd = df_loc[COT_TEN_PGD].nunique() if tong_khoan > 0 and COT_TEN_PGD in df_loc.columns else 0
    tong_dn_full = pd.to_numeric(df_tinh[COT_TONG_DU_NO], errors="coerce").sum()
    ty_le = tong_tien / tong_dn_full * 100 if tong_dn_full else 0

    _so_nq11 = int((df_loc["_ct_db"].str.contains("NQ11")).sum()) if not df_loc.empty else 0
    _so_gqvl = int((df_loc["_ct_db"].str.contains("GQVL")).sum()) if not df_loc.empty else 0
    _co_db = _so_nq11 > 0 or _so_gqvl > 0

    if _co_db:
        m1, m2, m3, m4, m5 = st.columns(5)
    else:
        m1, m2, m3, m4 = st.columns(4)
    m1.metric("Số khoản đến hạn", fmt_so(tong_khoan))
    m2.metric("Dư nợ đến hạn (triệu đ)", fmt_ty(tong_tien))
    m3.metric("Số PGD liên quan", so_pgd)
    m4.metric("Tỷ lệ dư nợ/tổng", f"{ty_le:.2f}".replace(".", ",") + "%")
    if _co_db:
        _db_parts = []
        if _so_nq11:
            _db_parts.append(f"NQ11: {fmt_so(_so_nq11)}")
        if _so_gqvl:
            _db_parts.append(f"GQVL: {fmt_so(_so_gqvl)}")
        m5.metric("Chương trình ĐB", " · ".join(_db_parts),
                  help="Khoản vay thuộc Nghị Quyết 11 và/hoặc Giải quyết Việc làm")

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
        _dh_labels = ["📅 Theo tháng", "🏢 Theo nhóm", "🏘️ Tổ TK&VV", "📋 Danh sách"]
        _dh_sel = st.radio("", range(len(_dh_labels)), format_func=lambda i: _dh_labels[i],
                           horizontal=True, key=f"{key_prefix}main_sub_tab", label_visibility="collapsed")
        st.divider()

        if _dh_sel == 0:
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

        elif _dh_sel == 1:
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

        elif _dh_sel == 2:
            _render_to_tkv(df_loc, kwargs.get("df"), key_prefix)

        elif _dh_sel == 3:
            # Filter nhanh NQ11 / GQVL
            _df_loc_ds = df_loc
            _co_db_ds = _co_db and "_ct_db" in df_loc.columns
            if _co_db_ds:
                _opts_db = ["Tất cả"]
                if _so_nq11:
                    _opts_db.append("Chỉ NQ11")
                if _so_gqvl:
                    _opts_db.append("Chỉ GQVL")
                if _so_nq11 and _so_gqvl:
                    _opts_db.append("NQ11 hoặc GQVL")
                _loc_db = st.radio(
                    "Lọc chương trình đặc biệt",
                    _opts_db, horizontal=True,
                    key=f"{key_prefix}den_han_loc_db",
                )
                if _loc_db == "Chỉ NQ11":
                    _df_loc_ds = df_loc[df_loc["_ct_db"].str.contains("NQ11")]
                elif _loc_db == "Chỉ GQVL":
                    _df_loc_ds = df_loc[df_loc["_ct_db"].str.contains("GQVL")]
                elif _loc_db == "NQ11 hoặc GQVL":
                    _df_loc_ds = df_loc[df_loc["_ct_db"] != "—"]

            cols_ct_ds = [c for c in [
                COT_TEN_PGD, COT_TEN_KH, COT_TEN_CT, COT_SO_KU, COT_TONG_DU_NO,
                "Ngày đến hạn", "Số tháng có thể gia hạn",
            ] if c in _df_loc_ds.columns]
            df_ct = _df_loc_ds[cols_ct_ds].copy()
            # Gắn nhãn CT đặc biệt nếu có dữ liệu NQ11/GQVL
            if _co_db_ds:
                df_ct.insert(
                    df_ct.columns.get_loc(COT_TEN_CT) + 1 if COT_TEN_CT in df_ct.columns else len(df_ct.columns),
                    "CT Đặc biệt",
                    _df_loc_ds["_ct_db"].values,
                )
            # ── P3.2: Cột điểm rủi ro ──
            df_ct["🎯 Rủi ro"] = _df_loc_ds.apply(_tinh_diem_rui_ro, axis=1).apply(_badge_rui_ro)
            if "Ngày đến hạn" in df_ct.columns:
                df_ct = df_ct.sort_values("Ngày đến hạn")
                df_ct["Ngày đến hạn"] = pd.to_datetime(
                    df_ct["Ngày đến hạn"], errors="coerce"
                ).dt.strftime("%d/%m/%Y").fillna("")
            df_ct[COT_TONG_DU_NO] = pd.to_numeric(
                df_ct[COT_TONG_DU_NO], errors="coerce"
            ).apply(fmt_ty)
            df_ct = df_ct.reset_index(drop=True)

            hien_thi_dataframe_phan_trang(df_ct, key="dh_tbl_ds", height=420)

            # ── Nút xuất báo cáo Excel + PDF ───────────────────────────
            col_ex, col_pdf_tab = st.columns(2)
            with col_ex:
                if st.button("📥 Tạo Excel", key="btn_gen_den_han_excel",
                             use_container_width=True):
                    try:
                        sheets_xuat = _xay_dung_sheets_excel(df_loc, den_thang, _co_db)
                        st.session_state["_xls_den_han"] = xuat_excel(sheets_xuat)
                    except Exception as e:
                        logger.error("tab_den_han xuat_excel: %s", e, exc_info=True)
                        st.error(f"❌ Lỗi xuất Excel: {e}")
                if st.session_state.get("_xls_den_han"):
                    st.download_button(
                        "📥 Tải Excel",
                        data=st.session_state["_xls_den_han"],
                        file_name=ten_file_xuat(f"DenHan_{den_thang}thang"),
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetsml.sheet",
                        key="btn_xuat_den_han_excel",
                        use_container_width=True,
                    )
            with col_pdf_tab:
                if st.button("📄 Tạo PDF", key="btn_gen_pdf_den_han",
                             use_container_width=True):
                    try:
                        username = kwargs.get("username", st.session_state.get("username", "VBSP-SCM"))
                        pdf_bytes = _xuat_pdf_den_han(df_loc, den_thang, username)
                        state.downloads.set(
                            "den_han_full_pdf",
                            pdf_bytes,
                            f"DenHan_{den_thang}thang_{datetime.now().strftime('%d%m%Y_%H%M')}.pdf",
                        )
                    except Exception as e:
                        logger.error("tab_den_han _xuat_pdf_den_han: %s", e, exc_info=True)
                        st.error(f"❌ Lỗi xuất PDF: {e}")
                if state.downloads.has("den_han_full_pdf"):
                    if st.download_button(
                        "� Tải PDF",
                        data=state.downloads.get_bytes("den_han_full_pdf"),
                        file_name=state.downloads.get_filename("den_han_full_pdf")
                            or f"DenHan_{den_thang}thang_{datetime.now().strftime('%d%m%Y_%H%M')}.pdf",
                        mime="application/pdf",
                        key="btn_dl_pdf_den_han",
                        use_container_width=True,
                    ):
                        state.downloads.clear("den_han_full_pdf")
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
