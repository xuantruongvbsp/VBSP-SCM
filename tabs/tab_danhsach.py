"""Tab Danh sách & Lọc."""
from __future__ import annotations

from io import BytesIO
from datetime import datetime, date
from typing import TYPE_CHECKING

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from config import *
from utils import (
    fmt_so,
    fmt_tien,
    vn,
    xuat_excel,
    ten_file_xuat,
    hien_thi_dataframe_phan_trang,
)
from auth import la_phan_he_pgd
if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator


@st.cache_data(show_spinner=False)
def _cache_kpi_danhsach(
    _dl: pd.DataFrame,
    ts: float,
    pgd_user: str,
    cot_ma_kh: str,
    cot_tdn: str,
    cot_dqh: str,
    filter_sig: str,
) -> dict:
    _ = (ts, pgd_user, filter_sig)  # cache key; filter_sig = trạng thái bộ lọc (không hash _dl)
    n_kh = _dl[cot_ma_kh].nunique() if cot_ma_kh in _dl.columns else len(_dl)
    if cot_ma_kh in _dl.columns and cot_tdn in _dl.columns:
        _mask = _dl[cot_tdn].fillna(0) > 0
        n_kh_dn = _dl.loc[_mask, cot_ma_kh].nunique()
    else:
        n_kh_dn = n_kh
    tong_dn = _dl[cot_tdn].sum() if cot_tdn in _dl.columns else 0
    tong_dqh = _dl[cot_dqh].sum() if cot_dqh in _dl.columns else 0
    tong_khoanh = _dl["Dư nợ khoanh"].sum() if "Dư nợ khoanh" in _dl.columns else 0
    if len(_dl) <= 100_000:
        from data import danh_dau_khong_hd

        dl_kh = danh_dau_khong_hd(_dl)
        n_3m = int(dl_kh["is_3m_inactive"].sum()) if "is_3m_inactive" in dl_kh.columns else 0
    else:
        n_3m = 0
    return dict(
        n_kh=n_kh,
        n_kh_dn=n_kh_dn,
        tong_dn=tong_dn,
        tong_dqh=tong_dqh,
        tong_khoanh=tong_khoanh,
        n_3m=n_3m,
    )


def _tao_column_config_danh_sach(df: pd.DataFrame) -> dict[str, st.column_config.Column]:
    """
    Tạo column_config cho bảng danh sách hồ sơ.
    
    Args:
        df: DataFrame chứa dữ liệu cần hiển thị
    
    Returns:
        Dict cấu hình column cho st.dataframe
    """
    config: dict[str, st.column_config.Column] = {}
    
    if COT_MUC_VAY in df.columns:
        config[COT_MUC_VAY] = st.column_config.NumberColumn(
            "Mức vay",
            format="%.0f ₫",
            help="Mức vay ban đầu"
        )
    
    if COT_DU_NO_TH in df.columns:
        config[COT_DU_NO_TH] = st.column_config.NumberColumn(
            "Dư nợ trong hạn",
            format="%.0f ₫",
            help="Dư nợ chưa đến hạn thanh toán"
        )
    
    if COT_DU_NO_QH in df.columns:
        config[COT_DU_NO_QH] = st.column_config.NumberColumn(
            "Dư nợ quá hạn",
            format="%.0f ₫",
            help="Dư nợ quá hạn cần thu hồi"
        )
    
    if COT_TONG_DU_NO in df.columns:
        config[COT_TONG_DU_NO] = st.column_config.NumberColumn(
            "Tổng dư nợ",
            format="%.0f ₫",
            help="Tổng dư nợ hiện tại"
        )
    
    if COT_LAI_SUAT in df.columns:
        config[COT_LAI_SUAT] = st.column_config.NumberColumn(
            "Lãi suất",
            format="%.2f%%",
            help="Lãi suất vay"
        )
    
    return config


def render(tab: DeltaGenerator, **kwargs: dict) -> None:
    """
    Render tab Danh sách & Lọc.
    
    Args:
        tab: Streamlit DeltaGenerator cho tab này
        **kwargs: Chứa df, df_full, role, pgd_user, username, df_nq11
    """
    df       = kwargs.get("df")
    df_full  = kwargs.get("df_full", df)
    role     = kwargs.get("role")
    pgd_user = kwargs.get("pgd_user")
    username = kwargs.get("username")
    df_nq11  = kwargs.get("df_nq11")

    with tab:
        st.subheader("Danh sách hồ sơ & Bộ lọc")
        with st.expander("🔧 Bộ lọc", expanded=True):
            f1, f2, f3, f4 = st.columns(4)
            with f1:
                ds_xa = ["Tất cả"] + sorted(df[COT_TEN_XA].dropna().unique().tolist()) \
                        if COT_TEN_XA in df.columns else ["Tất cả"]
                cxa = st.selectbox("Xã", ds_xa, key="loc_xa")
            with f2:
                ds_dvut = ["Tất cả"] + sorted(df["Tên ĐVUT"].dropna().unique().tolist()) \
                          if "Tên ĐVUT" in df.columns else ["Tất cả"]
                cdvut = st.selectbox("Hội đoàn thể", ds_dvut, key="loc_dvut")
            with f3:
                ds_to = ["Tất cả"] + sorted(df[COT_TEN_TO].dropna().unique().tolist()) \
                        if COT_TEN_TO in df.columns else ["Tất cả"]
                cto = st.selectbox("Tổ TK&VV", ds_to, key="loc_to")
            with f4:
                ds_ct = ["Tất cả"] + sorted(df[COT_TEN_CT].dropna().unique().tolist()) \
                        if COT_TEN_CT in df.columns else ["Tất cả"]
                cct = st.selectbox("Chương trình", ds_ct, key="loc_ct")

        # Filter sau expander — dùng boolean mask, không copy toàn bộ df
        _masks = []
        if la_phan_he_pgd(role) and pgd_user:
            _masks.append(df[COT_TEN_PGD] == pgd_user)
        if cxa   != "Tất cả" and COT_TEN_XA  in df.columns:
            _masks.append(df[COT_TEN_XA]  == cxa)
        if cdvut != "Tất cả" and "Tên ĐVUT" in df.columns:
            _masks.append(df["Tên ĐVUT"]  == cdvut)
        if cto   != "Tất cả" and COT_TEN_TO  in df.columns:
            _masks.append(df[COT_TEN_TO]  == cto)
        if cct   != "Tất cả" and COT_TEN_CT  in df.columns:
            _masks.append(df[COT_TEN_CT]  == cct)

        if _masks:
            import functools, operator
            _final_mask = functools.reduce(operator.and_, _masks)
            dl = df.loc[_final_mask].reset_index(drop=True)
            del _masks, _final_mask
        else:
            dl = df  # không filter → dùng thẳng, không copy

        ts = kwargs.get("ts_hstd", 0.0)
        pgd_user = kwargs.get("pgd_user", "")
        _filter_sig = f"{cxa}|{cdvut}|{cto}|{cct}"
        _kpi = _cache_kpi_danhsach(
            dl,
            ts,
            pgd_user,
            COT_MA_KH,
            COT_TONG_DU_NO,
            COT_DU_NO_QH,
            _filter_sig,
        )
        n_kh = _kpi["n_kh"]
        n_kh_dn = _kpi["n_kh_dn"]
        tong_dn = _kpi["tong_dn"]
        tong_dqh = _kpi["tong_dqh"]
        tong_khoanh = _kpi["tong_khoanh"]
        n_3m = _kpi["n_3m"]

        def _metric_card(label: str, value: str, color: str, icon: str) -> str:
            return f"""
            <div style="
                background: {color};
                border-radius: 12px;
                padding: 16px 20px;
                text-align: center;
                box-shadow: 0 2px 8px rgba(0,0,0,0.12);
            ">
                <div style="font-size:28px">{icon}</div>
                <div style="font-size:22px; font-weight:700;
                            color:#fff; margin:6px 0 4px;">{value}</div>
                <div style="font-size:13px; color:rgba(255,255,255,0.85);
                            font-weight:500; line-height:1.3">{label}</div>
            </div>"""

        cols = st.columns(5)
        cards = [
            ("Khách hàng có dư nợ", fmt_so(n_kh_dn), "#1976D2", "👤"),
            ("Tổng dư nợ", fmt_tien(tong_dn), "#388E3C", "💰"),
            ("Dư nợ quá hạn", fmt_tien(tong_dqh), "#D32F2F", "⚠️"),
            ("Dư nợ khoanh", fmt_tien(tong_khoanh), "#7B1FA2", "🔒"),
            ("3 tháng không HĐ", f"{fmt_so(n_3m)} món", "#F57C00", "🔴"),
        ]
        for col, (label, value, color, icon) in zip(cols, cards):
            col.markdown(_metric_card(label, value, color, icon), unsafe_allow_html=True)

        # Thêm khoảng cách sau card
        st.markdown("<div style='margin-top:16px'></div>", unsafe_allow_html=True)
        sc1, sc2 = st.columns([5, 1])
        with sc1:
            tu_khoa = st.text_input(
                "🔍",
                placeholder="Tìm theo họ tên, mã KH, CCCD hoặc SĐT...",
                key="search_kh",
                label_visibility="collapsed",
            )
        with sc2:
            st.markdown('<div class="vbsp-btn">', unsafe_allow_html=True)
            if st.button("✕ Xóa", key="clear_search", use_container_width=True):
                st.session_state["search_kh"] = ""
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

        if tu_khoa.strip():
            dieu_kien_tim = pd.Series(False, index=dl.index)
            for cot in [COT_MA_KH, COT_TEN_KH, COT_SO_KU, COT_SDT]:
                if cot in dl.columns:
                    dieu_kien_tim = dieu_kien_tim | dl[cot].astype(str).str.contains(
                        tu_khoa, case=False, na=False
                    )
            dl = dl[dieu_kien_tim].copy()
        if tu_khoa.strip():
            st.caption(f"🔎 Tìm thấy **{fmt_so(len(dl))}** hồ sơ khớp · `{tu_khoa.strip()}`")
        else:
            st.caption(f"📋 **{fmt_so(len(dl))}** hồ sơ — dùng ô tìm kiếm để lọc nhanh")

        ch = [c for c in [COT_TEN_PGD,COT_MA_KH,COT_TEN_KH,COT_SO_KU,COT_NGAY_VAY,
                           COT_NGAY_DH,COT_THOI_HAN,COT_LAI_SUAT,COT_MUC_VAY,
                           COT_DU_NO_TH,COT_DU_NO_QH,COT_TONG_DU_NO,
                           COT_TINH_TRANG,COT_TEN_CT,COT_SDT] if c in dl.columns]
        hien_thi_dataframe_phan_trang(
            dl[ch].reset_index(drop=True),
            key="danhsach_loc",
            column_config=_tao_column_config_danh_sach(dl[ch]),
            height=400,
        )
        st.divider()
        if st.button("📥 Xuất danh sách đang lọc"):
            buf = BytesIO()
            with pd.ExcelWriter(buf, engine="openpyxl") as w:
                dl[ch].to_excel(w, index=False, sheet_name="Danh sách")
            st.download_button("⬇ Tải file Excel", data=buf.getvalue(),
                file_name=f"danh_sach_{datetime.today().strftime('%d%m%Y')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        # ══════════════════════════════════════════════════════════════════════
        # SECTION: NỢ ĐẾN HẠN
        # ══════════════════════════════════════════════════════════════════════
        st.divider()
        st.subheader("📅 Nợ đến hạn")

        # ──────────────────────────────────────────────────────────────────────
        # THAY ĐỔI 1: Bộ lọc xã và chương trình dùng chung
        # ──────────────────────────────────────────────────────────────────────
        c_xa_dh, c_ct_dh = st.columns([2, 3])
        with c_xa_dh:
            ds_xa_dh = ["Tất cả (cả PGD)"]
            if COT_TEN_XA in dl.columns:
                ds_xa_dh += sorted(dl[COT_TEN_XA].dropna().unique().tolist())
            chon_xa_dh = st.selectbox(
                "📍 Lọc theo xã",
                ds_xa_dh,
                key="dh_xa_chung",
                help="Không chọn = hiện toàn PGD; chọn xã = chỉ hiện xã đó",
            )
        with c_ct_dh:
            ds_ct_dh = ["Tất cả"]
            if COT_TEN_CT in dl.columns:
                ds_ct_dh += sorted(dl[COT_TEN_CT].dropna().unique().tolist())
            chon_ct_dh = st.selectbox("📌 Lọc chương trình", ds_ct_dh, key="dh_ct_chung")

        # Áp lọc vào df_dh (dùng cho cả 3 mốc và cả 2 biểu đồ)
        df_dh = dl.copy()
        if chon_xa_dh != "Tất cả (cả PGD)" and COT_TEN_XA in df_dh.columns:
            df_dh = df_dh[df_dh[COT_TEN_XA] == chon_xa_dh]
        if chon_ct_dh != "Tất cả" and COT_TEN_CT in df_dh.columns:
            df_dh = df_dh[df_dh[COT_TEN_CT] == chon_ct_dh]

        # Tạo tên phạm vi cho title và caption
        ten_pham_vi = chon_xa_dh if chon_xa_dh != "Tất cả (cả PGD)" else "Toàn PGD"

        # Parse ngày — wrap trong try/except
        try:
            df_dh = df_dh.copy()
            df_dh[COT_NGAY_DH] = pd.to_datetime(df_dh[COT_NGAY_DH], dayfirst=True, errors="coerce")
        except Exception:
            st.warning("⚠️ Không thể parse cột ngày đến hạn.")
            st.stop()

        today     = pd.Timestamp.today().normalize()
        cuoi_thang = (today + pd.offsets.MonthEnd(1)).normalize()
        moc_3thang = today + pd.Timedelta(days=90)
        cuoi_nam   = pd.Timestamp(today.year, 12, 31)

        def _loc_moc(df_in, den_ngay):
            """Lọc hồ sơ có COT_NGAY_DH trong [today, den_ngay], chưa quá hạn."""
            mask = (df_in[COT_NGAY_DH] >= today) & (df_in[COT_NGAY_DH] <= den_ngay)
            return df_in[mask].copy()

        df_thang   = _loc_moc(df_dh, cuoi_thang)
        df_3thang  = _loc_moc(df_dh, moc_3thang)
        df_nam     = _loc_moc(df_dh, cuoi_nam)

        # ──────────────────────────────────────────────────────────────────────
        # 3 Sub-tab: Trong tháng / 3 tháng / Trong năm
        # ──────────────────────────────────────────────────────────────────────
        tab_thang, tab_3thang, tab_nam = st.tabs([
            f"📆 Trong tháng ({fmt_so(len(df_thang))} món)",
            f"📆 3 tháng tới ({fmt_so(len(df_3thang))} món)",
            f"📆 Trong năm ({fmt_so(len(df_nam))} món)",
        ])

        # Cột hiển thị chung cho 3 tab
        ch_dh = [c for c in [COT_TEN_PGD, COT_MA_KH, COT_TEN_KH, COT_SO_KU,
                              COT_NGAY_VAY, COT_NGAY_DH, COT_THOI_HAN,
                              COT_TONG_DU_NO, COT_TEN_CT, COT_TEN_XA]
                 if c in df_dh.columns]

        with tab_thang:
            st.caption(f"Hồ sơ đến hạn từ hôm nay đến {cuoi_thang.strftime('%d/%m/%Y')}")
            st.metric("Tổng dư nợ trong tháng",
                      f"{df_thang[COT_TONG_DU_NO].sum()/1e6:.1f} triệu đ" if COT_TONG_DU_NO in df_thang.columns else "—")
            hien_thi_dataframe_phan_trang(
                df_thang[ch_dh].reset_index(drop=True),
                key="danhsach_dh_thang",
                column_config=_tao_column_config_danh_sach(df_thang[ch_dh]),
                height=300,
            )

        with tab_3thang:
            st.caption(f"Hồ sơ đến hạn từ hôm nay đến {moc_3thang.strftime('%d/%m/%Y')}")
            st.metric("Tổng dư nợ 3 tháng",
                      f"{df_3thang[COT_TONG_DU_NO].sum()/1e6:.1f} triệu đ" if COT_TONG_DU_NO in df_3thang.columns else "—")
            hien_thi_dataframe_phan_trang(
                df_3thang[ch_dh].reset_index(drop=True),
                key="danhsach_dh_3thang",
                column_config=_tao_column_config_danh_sach(df_3thang[ch_dh]),
                height=300,
            )

        with tab_nam:
            st.caption(f"Hồ sơ đến hạn từ hôm nay đến {cuoi_nam.strftime('%d/%m/%Y')}")
            st.metric("Tổng dư nợ trong năm",
                      f"{df_nam[COT_TONG_DU_NO].sum()/1e6:.1f} triệu đ" if COT_TONG_DU_NO in df_nam.columns else "—")
            hien_thi_dataframe_phan_trang(
                df_nam[ch_dh].reset_index(drop=True),
                key="danhsach_dh_nam",
                column_config=_tao_column_config_danh_sach(df_nam[ch_dh]),
                height=300,
            )

        # ──────────────────────────────────────────────────────────────────────
        # THAY ĐỔI 2: Biểu đồ lịch nhiệt (heatmap theo tháng trong năm)
        # ──────────────────────────────────────────────────────────────────────
        st.divider()
        st.markdown("### 🗓️ Lịch đến hạn theo tháng trong năm")
        st.caption("Tháng có dư nợ cao hơn bình quân → màu đỏ đậm dần")

        # Dùng toàn bộ hồ sơ trong năm hiện tại (kể cả đã qua hạn) để thấy bức tranh đầy đủ
        df_ca_nam = df_dh[
            (df_dh[COT_NGAY_DH].dt.year == today.year) &
            df_dh[COT_NGAY_DH].notna()
        ].copy()
        df_ca_nam["_thang"] = df_ca_nam[COT_NGAY_DH].dt.month

        # Tổng hợp theo tháng
        tong_thang = (
            df_ca_nam.groupby("_thang")
            .agg(
                so_mon =(COT_SO_KU,      "nunique"),
                du_no  =(COT_TONG_DU_NO, "sum"),
            )
            .reindex(range(1, 13), fill_value=0)
            .reset_index()
            .rename(columns={"_thang": "Tháng"})
        )
        tong_thang["du_no_trieu"] = tong_thang["du_no"] / 1_000_000

        binh_quan_mon = tong_thang["so_mon"].mean()
        binh_quan_no  = tong_thang["du_no_trieu"].mean()
        THANG_VI = ["T1","T2","T3","T4","T5","T6","T7","T8","T9","T10","T11","T12"]

        def _mau_nhiet(values, binh_quan):
            """
            Trả về list màu hex cho từng cột:
            - Dưới bình quân: xanh lá nhạt (#a8d5a2 → #2d8a4e)
            - Trên bình quân: cam nhạt → đỏ đậm (#f5c6a0 → #c0392b)
            Cường độ tỷ lệ thuận với khoảng cách so với bình quân.
            """
            colors = []
            max_val = max(values) if max(values) > 0 else 1
            for v in values:
                if v <= binh_quan:
                    # xanh lá: nhạt → đậm tỷ lệ v/binh_quan
                    t = v / binh_quan if binh_quan > 0 else 0
                    r = int(168 - t * (168 - 45))
                    g = int(213 - t * (213 - 138))
                    b = int(162 - t * (162 - 78))
                else:
                    # đỏ: cam nhạt → đỏ đậm tỷ lệ (v-binh_quan)/(max-binh_quan)
                    t = (v - binh_quan) / (max_val - binh_quan) if max_val > binh_quan else 0
                    r = int(245 - t * (245 - 192))
                    g = int(198 - t * (198 - 57))
                    b = int(160 - t * (160 - 43))
                colors.append(f"rgb({r},{g},{b})")
            return colors

        bieu_do_tab1, bieu_do_tab2 = st.tabs([
            "📊 Số món đến hạn theo tháng",
            "💰 Dư nợ đến hạn theo tháng",
        ])

        with bieu_do_tab1:
            mau_mon = _mau_nhiet(tong_thang["so_mon"].tolist(), binh_quan_mon)
            fig1 = go.Figure(go.Bar(
                x=THANG_VI,
                y=tong_thang["so_mon"],
                marker_color=mau_mon,
                text=tong_thang["so_mon"].apply(
                    lambda x: fmt_so(int(x)) if x > 0 else ""
                ),
                textposition="outside",
                hovertemplate="<b>%{x}</b><br>Số món: %{y}<extra></extra>",
            ))
            # Đường bình quân
            fig1.add_hline(
                y=binh_quan_mon,
                line_dash="dash",
                line_color="gray",
                annotation_text=f"Bình quân: {binh_quan_mon:.0f} món",
                annotation_position="right",
            )
            # Highlight tháng hiện tại
            fig1.add_vrect(
                x0=today.month - 1 - 0.4,
                x1=today.month - 1 + 0.4,
                fillcolor="rgba(255,215,0,0.15)",
                line_width=0,
                annotation_text="Tháng này",
                annotation_position="top left",
            )
            fig1.update_layout(
                title=f"Số món đến hạn — {ten_pham_vi} — năm {today.year}",
                xaxis_title="Tháng",
                yaxis_title="Số món",
                showlegend=False,
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                height=350,
                margin=dict(t=50, b=30, l=40, r=80),
            )
            st.plotly_chart(fig1, use_container_width=True)
            st.caption(
                f"📍 Phạm vi: **{ten_pham_vi}**  ·  "
                f"🟢 Dưới bình quân ({binh_quan_mon:.0f} món)  "
                f"🔴 Trên bình quân — màu càng đậm càng xa bình quân"
            )

        with bieu_do_tab2:
            mau_no = _mau_nhiet(tong_thang["du_no_trieu"].tolist(), binh_quan_no)
            fig2 = go.Figure(go.Bar(
                x=THANG_VI,
                y=tong_thang["du_no_trieu"].round(1),
                marker_color=mau_no,
                text=tong_thang["du_no_trieu"].apply(
                    lambda x: vn(x, 1) if x > 0 else ""
                ),
                textposition="outside",
                hovertemplate="<b>%{x}</b><br>Dư nợ: %{y:.1f} triệu đ<extra></extra>",
            ))
            fig2.add_hline(
                y=binh_quan_no,
                line_dash="dash",
                line_color="gray",
                annotation_text=f"Bình quân: {fmt_so(round(binh_quan_no, 0))} tr.đ",
                annotation_position="right",
            )
            fig2.add_vrect(
                x0=today.month - 1 - 0.4,
                x1=today.month - 1 + 0.4,
                fillcolor="rgba(255,215,0,0.15)",
                line_width=0,
                annotation_text="Tháng này",
                annotation_position="top left",
            )
            fig2.update_layout(
                title=f"Dư nợ đến hạn — {ten_pham_vi} — năm {today.year} (triệu đồng)",
                xaxis_title="Tháng",
                yaxis_title="Triệu đồng",
                showlegend=False,
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                height=350,
                margin=dict(t=50, b=30, l=40, r=100),
            )
            st.plotly_chart(fig2, use_container_width=True)
            st.caption(
                f"📍 Phạm vi: **{ten_pham_vi}**  ·  "
                f"🟢 Dưới bình quân ({fmt_so(round(binh_quan_no, 0))} tr.đ)  "
                f"🔴 Trên bình quân — màu càng đậm càng lớn hơn bình quân"
            )

