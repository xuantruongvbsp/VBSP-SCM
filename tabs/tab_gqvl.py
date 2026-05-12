"""Tab Theo dõi chỉ tiêu Giải quyết Việc làm (GQVL)."""
from __future__ import annotations

from io import BytesIO
from datetime import datetime
from typing import TYPE_CHECKING

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from config import (
    FILE_PATH_GQVL, TEN_FILE_GQVL,
    COT_TEN_PGD, COT_MA_KH, COT_NGAY_SL,
)
from data import (ts_file, doc_file_gqvl,
                  doc_gqvl_pgd, ds_pgd_co_gqvl, duong_dan_gqvl_pgd)
from services import luu_pgd_file
from utils import fmt, fmt_bang_ty, fmt_ty, fmt_so, vn, xuat_excel, hien_thi_dataframe_phan_trang

if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator


def _tao_column_config_gqvl() -> dict[str, st.column_config.Column]:
    """
    Tạo column_config chuẩn cho bảng GQVL.
    
    Returns:
        Dict cấu hình column cho st.dataframe
    """
    return {
        "Dư_nợ_TH": st.column_config.NumberColumn(
            "Dư nợ TH",
            format="%.0f ₫",
            help="Dư nợ trong hạn"
        ),
        "Dư_nợ_QH": st.column_config.NumberColumn(
            "Dư nợ QH",
            format="%.0f ₫",
            help="Dư nợ quá hạn"
        ),
        "Dư_nợ_khoanh": st.column_config.NumberColumn(
            "Dư nợ khoanh",
            format="%.0f ₫",
            help="Dư nợ khoanh"
        ),
        "Tổng_dư_nợ": st.column_config.NumberColumn(
            "Tổng dư nợ",
            format="%.0f ₫",
            help="Tổng dư nợ"
        ),
        "Tổng_GN": st.column_config.NumberColumn(
            "Tổng GN",
            format="%.0f ₫",
            help="Tổng giải ngân"
        ),
        "GN_năm_nay": st.column_config.NumberColumn(
            "GN năm nay",
            format="%.0f ₫",
            help="Giải ngân trong năm"
        ),
        "TL_QH_%": st.column_config.NumberColumn(
            "TL QH %",
            format="%.3f%%",
            help="Tỷ lệ quá hạn %"
        ),
        G_DU_NO_TH: st.column_config.NumberColumn(
            G_DU_NO_TH,
            format="%.0f ₫",
            help="Dư nợ trong hạn"
        ),
        G_DU_NO_QH: st.column_config.NumberColumn(
            G_DU_NO_QH,
            format="%.0f ₫",
            help="Dư nợ quá hạn"
        ),
        G_DU_NO_KH: st.column_config.NumberColumn(
            G_DU_NO_KH,
            format="%.0f ₫",
            help="Dư nợ khoanh"
        ),
        G_TONG_GN: st.column_config.NumberColumn(
            G_TONG_GN,
            format="%.0f ₫",
            help="Tổng giải ngân"
        ),
        G_GN_NAM: st.column_config.NumberColumn(
            G_GN_NAM,
            format="%.0f ₫",
            help="Giải ngân năm"
        ),
    }


def _tao_column_config_nganh() -> dict[str, st.column_config.Column]:
    """Tạo column_config cho bảng theo ngành SXKD."""
    return {
        "Dư_nợ": st.column_config.NumberColumn(
            "Dư nợ",
            format="%.0f ₫",
            help="Dư nợ"
        ),
        "NQH": st.column_config.NumberColumn(
            "NQH",
            format="%.0f ₫",
            help="Nợ quá hạn"
        ),
        "GN_năm": st.column_config.NumberColumn(
            "GN năm",
            format="%.0f ₫",
            help="Giải ngân năm"
        ),
        "Số_món": st.column_config.NumberColumn(
            "Số món",
            format="%d",
            help="Số món vay"
        ),
    }


# ── Hằng số cột GQVL (sau khi rename) ────────────────────────────────────────
G_MA_KH      = "Mã KH"
G_TEN_KH     = "Tên KH"
G_SO_KU      = "Số khế ước"
G_TEN_XA     = "Tên xã"
G_TEN_THON   = "Tên thôn"
G_TEN_TO     = "Tên tổ trưởng"
G_NGAY_VAY   = "Ngày vay"
G_NGAY_DH    = "Ngày ĐH sau cùng"
G_THOI_HAN   = "Thời hạn vay"
G_DU_NO_TH   = "Dư nợ trong hạn"
G_DU_NO_QH   = "Dư nợ quá hạn"
G_DU_NO_KH   = "Dư nợ khoanh"
G_NGUON_VON  = "Nguồn vốn"
G_MA_NHA_DAU_TU = "Mã nhà đầu tư"
G_TEN_NGANH  = "Tên ngành SXKD"
G_TONG_GN    = "Tổng giải ngân"
G_GN_NAM     = "Giải ngân trong năm"
G_DU_TK      = "Dư tài khoản"
G_NQ11       = "NQ11"

def render(tab: DeltaGenerator, **kwargs: dict) -> None:
    """
    Render tab Theo dõi chỉ tiêu GQVL.
    
    Args:
        tab: Streamlit DeltaGenerator cho tab này
        **kwargs: Chứa role, pgd_user, df_full
    """
    role = kwargs.get("role")
    pgd_user = kwargs.get("pgd_user")
    df_full = kwargs.get("df_full")

    _tab_ctx = tab if tab is not None else __import__('streamlit').container()
    with _tab_ctx:
        st.subheader("💼 Theo dõi chỉ tiêu Giải quyết Việc làm (GQVL)")

        # ── Upload file ───────────────────────────────────────────────────
        # ── Upload file GQVL theo PGD ─────────────────────────────────────
        with st.expander("📤 Upload file GQVL theo PGD", expanded=True):
            st.caption("Mỗi PGD lưu file riêng — không ghi đè nhau")
            upc1, upc2 = st.columns([2,1])
            with upc1:
                f_up = st.file_uploader(
                    "Chọn file sao kê GQVL (.xlsx)",
                    type=["xlsx","xls"], key="up_gqvl"
                )
            with upc2:
                # Chọn PGD để lưu
                if role in ("admin","manager","admin_cn","manager_cn") and COT_TEN_PGD in kwargs.get("df_full", pd.DataFrame()).columns:
                    ds_pgd_all = sorted(kwargs["df_full"][COT_TEN_PGD].dropna().unique().tolist())
                    pgd_up = st.selectbox("Lưu cho PGD", ds_pgd_all, key="gqvl_pgd_up")
                else:
                    pgd_up = pgd_user or "Chung"
                    st.markdown(f"**PGD:** {pgd_up}")

            if f_up and pgd_up:
                kq = luu_pgd_file(pgd_up, "gqvl", f_up.read())
                kq.hien_thi()
                if kq.thanh_cong:
                    st.rerun()

            # Danh sách PGD đã có file
            pgd_da_up = ds_pgd_co_gqvl()
            if pgd_da_up:
                st.caption(f"✅ Đã có file: {' · '.join(pgd_da_up)}")
            else:
                st.caption("⚠️ Chưa có PGD nào upload file GQVL")

        # ── Chọn PGD để xem ───────────────────────────────────────────────
        pgd_da_up = ds_pgd_co_gqvl()
        if not pgd_da_up:
            st.info("👆 Upload file GQVL của PGD bên trên để xem số liệu.")
            return

        if role in ("admin","manager","admin_cn","manager_cn"):
            pgd_xem = st.selectbox("📍 Xem PGD", ["Tất cả"] + pgd_da_up, key="gqvl_pgd_xem")
        else:
            pgd_xem = pgd_user or pgd_da_up[0]
            st.markdown(f"📍 PGD: **{pgd_xem}**")

        # ── Load dữ liệu ──────────────────────────────────────────────────
        try:
            if pgd_xem == "Tất cả":
                from data import doc_gqvl_toan_cn
                df = doc_gqvl_toan_cn()
                if df is None:
                    st.warning("Chưa có file GQVL nào.")
                    return
            else:
                _ts = ts_file(duong_dan_gqvl_pgd(pgd_xem))
                df  = doc_gqvl_pgd(pgd_xem, _ts)
                if df is None:
                    st.info(f"Chưa có file GQVL cho **{pgd_xem}**.")
                    return
        except Exception as e:
            st.error(f"Lỗi đọc file GQVL: {e}")
            return

        ngay_file = datetime.fromtimestamp(ts_file(FILE_PATH_GQVL)).strftime("%d/%m/%Y")
        st.caption(f"📅 File ngày: **{ngay_file}** · {fmt_so(len(df))} món vay GQVL")

        st.divider()

        # ── KPI tổng quan ─────────────────────────────────────────────────
        tong_dn   = (df[G_DU_NO_TH].sum() if G_DU_NO_TH in df.columns else 0) + \
                    (df[G_DU_NO_QH].sum() if G_DU_NO_QH in df.columns else 0) + \
                    (df[G_DU_NO_KH].sum() if G_DU_NO_KH in df.columns else 0)
        du_no_th  = df[G_DU_NO_TH].sum()  if G_DU_NO_TH in df.columns else 0
        du_no_qh  = df[G_DU_NO_QH].sum()  if G_DU_NO_QH in df.columns else 0
        du_no_kh  = df[G_DU_NO_KH].sum()  if G_DU_NO_KH in df.columns else 0
        tong_gn   = df[G_TONG_GN].sum()   if G_TONG_GN  in df.columns else 0
        gn_nam    = df[G_GN_NAM].sum()    if G_GN_NAM   in df.columns else 0
        n_kh      = df[G_MA_KH].nunique() if G_MA_KH     in df.columns else 0
        tl_qh     = du_no_qh / tong_dn * 100 if tong_dn > 0 else 0

        k1,k2,k3,k4,k5,k6 = st.columns(6)
        k1.metric("Số khách hàng",      fmt_so(n_kh))
        k2.metric("Tổng dư nợ",         fmt(tong_dn))
        k3.metric("Dư nợ trong hạn",    fmt(du_no_th))
        k4.metric("Dư nợ quá hạn",      fmt(du_no_qh),
                  delta=f"{tl_qh:.3f}%",
                  delta_color="inverse" if tl_qh > 0 else "normal")
        k5.metric("Tổng giải ngân",     fmt(tong_gn))
        k6.metric("Giải ngân năm nay",  fmt(gn_nam))

        st.divider()

        # ── Tabs nội dung ─────────────────────────────────────────────────
        tb1, tb2, tb3, tb4 = st.tabs([
            "📍 Theo địa bàn", "🏭 Theo ngành SXKD",
            "⚠️ Nợ quá hạn", "📋 Danh sách chi tiết"
        ])

        # ── Tab 1: Theo địa bàn ───────────────────────────────────────────
        with tb1:
            cap = st.radio("Cấp xem", ["Theo xã", "Theo thôn/ấp"],
                           horizontal=True, key="gqvl_cap")
            nhom = G_TEN_XA if cap == "Theo xã" else G_TEN_THON

            if nhom in df.columns:
                t_db = df.groupby(nhom).agg(
                    Số_KH       =(G_MA_KH,    "nunique"),
                    Dư_nợ_TH   =(G_DU_NO_TH, "sum"),
                    Dư_nợ_QH   =(G_DU_NO_QH, "sum"),
                    Dư_nợ_khoanh=(G_DU_NO_KH, "sum"),
                    Tổng_GN    =(G_TONG_GN,  "sum"),
                    GN_năm_nay =(G_GN_NAM,   "sum"),
                ).reset_index().sort_values("Dư_nợ_TH", ascending=False)

                t_db["Tổng_dư_nợ"] = t_db["Dư_nợ_TH"] + t_db["Dư_nợ_QH"] + t_db["Dư_nợ_khoanh"]
                t_db["TL_QH_%"]    = (t_db["Dư_nợ_QH"] / t_db["Tổng_dư_nợ"] * 100).round(3).fillna(0)

                # Biểu đồ
                fig = go.Figure()
                fig.add_bar(name="Dư nợ trong hạn", x=t_db[nhom],
                            y=t_db["Dư_nợ_TH"]/1e9, marker_color="#1565C0")
                fig.add_bar(name="Dư nợ quá hạn",   x=t_db[nhom],
                            y=t_db["Dư_nợ_QH"]/1e9, marker_color="#C62828")
                fig.update_layout(
                    barmode="stack", height=320,
                    margin=dict(l=0,r=0,t=10,b=60),
                    yaxis_title="Tỷ đồng", xaxis_tickangle=-30,
                    legend=dict(orientation="h", y=1.08),
                    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                )
                st.plotly_chart(fig, use_container_width=True)

                # Bảng - dùng column_config thay vì apply format
                hien_thi_dataframe_phan_trang(
                    t_db,
                    key="gqvl_th_dia_ban",
                    column_config=_tao_column_config_gqvl(),
                )

        # ── Tab 2: Theo ngành SXKD ────────────────────────────────────────
        with tb2:
            if G_TEN_NGANH in df.columns:
                t_ng = df.groupby(G_TEN_NGANH).agg(
                    Số_món  =(G_SO_KU,    "count"),
                    Dư_nợ  =(G_DU_NO_TH, "sum"),
                    NQH    =(G_DU_NO_QH, "sum"),
                    GN_năm =(G_GN_NAM,   "sum"),
                ).reset_index().sort_values("Dư_nợ", ascending=False)

                # Rút gọn tên ngành
                t_ng["Tên rút gọn"] = t_ng[G_TEN_NGANH].apply(
                    lambda x: str(x)[:40]+"…" if len(str(x)) > 40 else str(x))

                fig2 = px.bar(t_ng.head(15), x="Dư_nợ", y="Tên rút gọn",
                              orientation="h",
                              color="Dư_nợ", color_continuous_scale="Blues",
                              hover_data={G_TEN_NGANH: True, "Số_món": True})
                fig2.update_layout(
                    height=480, margin=dict(l=0,r=40,t=10,b=10),
                    xaxis_title="Dư nợ (đồng)",
                    yaxis=dict(title="", autorange="reversed"),
                    coloraxis_showscale=False,
                    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                )
                st.plotly_chart(fig2, use_container_width=True)

                hien_thi_dataframe_phan_trang(
                    t_ng[[G_TEN_NGANH, "Số_món", "Dư_nợ", "NQH", "GN_năm"]],
                    key="gqvl_th_nganh",
                    column_config=_tao_column_config_nganh(),
                )

        # ── Tab 3: Nợ quá hạn ────────────────────────────────────────────
        with tb3:
            if G_DU_NO_QH in df.columns:
                df_qh = df[df[G_DU_NO_QH].fillna(0) > 0].copy()

                if df_qh.empty:
                    st.success("✅ Không có món vay GQVL nào quá hạn!")
                else:
                    st.error(f"⚠️ Có **{fmt_so(len(df_qh))}** món vay quá hạn · Tổng NQH: **{fmt(df_qh[G_DU_NO_QH].sum())}**")

                    # Tổng hợp NQH theo xã
                    if G_TEN_XA in df_qh.columns:
                        st.markdown("**NQH theo xã**")
                        t_qh_xa = df_qh.groupby(G_TEN_XA).agg(
                            Số_món=(G_SO_KU,"count"),
                            NQH=(G_DU_NO_QH,"sum"),
                        ).sort_values("NQH", ascending=False).reset_index()
                        fig3 = px.bar(t_qh_xa, x="NQH", y=G_TEN_XA,
                                      orientation="h", color="NQH",
                                      color_continuous_scale="Reds")
                        fig3.update_traces(textposition="outside")
                        fig3.update_layout(height=320,
                            margin=dict(l=0,r=80,t=10,b=10),
                            yaxis=dict(title="",autorange="reversed"),
                            xaxis_title="", coloraxis_showscale=False,
                            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
                        st.plotly_chart(fig3, use_container_width=True)

                    # Danh sách chi tiết NQH
                    cols_qh = [c for c in [G_TEN_XA, G_TEN_THON, G_TEN_TO,
                                           G_MA_KH, G_TEN_KH, G_SO_KU,
                                           G_NGAY_VAY, G_NGAY_DH,
                                           G_DU_NO_TH, G_DU_NO_QH, G_TEN_NGANH]
                               if c in df_qh.columns]
                    df_qh_hien = df_qh[cols_qh].copy()

                    hien_thi_dataframe_phan_trang(
                        df_qh_hien.reset_index(drop=True),
                        key="gqvl_nqh_ds_chitiet",
                        column_config=_tao_column_config_gqvl(),
                        height=380,
                    )

                    # Xuất Excel NQH
                    if st.button("📥 Xuất danh sách NQH", key="xuat_gqvl_qh"):
                        buf = BytesIO()
                        with pd.ExcelWriter(buf, engine="openpyxl") as w:
                            df_qh[cols_qh].to_excel(w, index=False, sheet_name="NQH_GQVL")
                        st.session_state["_bytes_gqvl_qh"] = buf.getvalue()
                        st.session_state["_file_gqvl_qh"] = f"NQH_GQVL_{datetime.today().strftime('%d%m%Y')}.xlsx"

                    if st.session_state.get("_bytes_gqvl_qh"):
                        st.download_button("⬇ Tải Excel NQH GQVL",
                            data=st.session_state["_bytes_gqvl_qh"],
                            file_name=st.session_state["_file_gqvl_qh"],
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key="dl_gqvl_qh")

        # ── Tab 4: Danh sách chi tiết ─────────────────────────────────────
        with tb4:
            # Bộ lọc
            fl1, fl2, fl3 = st.columns(3)
            with fl1:
                ds_xa = ["Tất cả"] + (sorted(df[G_TEN_XA].dropna().unique().tolist())
                                       if G_TEN_XA in df.columns else [])
                loc_xa = st.selectbox("Xã", ds_xa, key="gqvl_loc_xa")
            with fl2:
                loc_nv = st.selectbox("Nguồn vốn",
                    ["Tất cả","TW","ĐP"], key="gqvl_loc_nv")
            with fl3:
                loc_qh = st.checkbox("⚠️ Chỉ hiện quá hạn", key="gqvl_loc_qh")

            df_loc = df.copy()
            if loc_xa != "Tất cả" and G_TEN_XA in df_loc.columns:
                df_loc = df_loc[df_loc[G_TEN_XA] == loc_xa]
            if loc_nv != "Tất cả" and G_NGUON_VON in df_loc.columns:
                df_loc = df_loc[df_loc[G_NGUON_VON] == loc_nv]
            if loc_qh and G_DU_NO_QH in df_loc.columns:
                df_loc = df_loc[df_loc[G_DU_NO_QH].fillna(0) > 0]

            m1, m2, m3 = st.columns(3)
            m1.metric("Số món", fmt_so(len(df_loc)))
            m2.metric("Tổng dư nợ",
                fmt((df_loc[G_DU_NO_TH].sum() if G_DU_NO_TH in df_loc.columns else 0)
                   + (df_loc[G_DU_NO_QH].sum() if G_DU_NO_QH in df_loc.columns else 0)))
            m3.metric("NQH", fmt(df_loc[G_DU_NO_QH].sum() if G_DU_NO_QH in df_loc.columns else 0))

            cols_hien = [c for c in [
                G_TEN_XA, G_TEN_THON, G_MA_KH, G_TEN_KH,
                G_SO_KU, G_NGAY_VAY, G_NGAY_DH, G_THOI_HAN,
                G_DU_NO_TH, G_DU_NO_QH, G_DU_NO_KH,
                G_NGUON_VON, G_MA_NHA_DAU_TU, G_TEN_NGANH,
                G_TONG_GN, G_GN_NAM, G_NQ11,
            ] if c in df_loc.columns]

            df_hien = df_loc[cols_hien].copy()

            hien_thi_dataframe_phan_trang(
                df_hien.reset_index(drop=True),
                key="gqvl_ds_chinh",
                column_config=_tao_column_config_gqvl(),
                height=420,
            )

            # Xuất Excel toàn bộ
            st.divider()
            if st.button("📥 Xuất danh sách đang lọc", key="xuat_gqvl_ds"):
                buf = BytesIO()
                with pd.ExcelWriter(buf, engine="openpyxl") as w:
                    df_loc[cols_hien].to_excel(w, index=False, sheet_name="GQVL")
                st.session_state["_bytes_gqvl_ds"] = buf.getvalue()
                st.session_state["_file_gqvl_ds"] = f"GQVL_{datetime.today().strftime('%d%m%Y')}.xlsx"

            if st.session_state.get("_bytes_gqvl_ds"):
                st.download_button("⬇ Tải Excel",
                    data=st.session_state["_bytes_gqvl_ds"],
                    file_name=st.session_state["_file_gqvl_ds"],
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="dl_gqvl_ds")
