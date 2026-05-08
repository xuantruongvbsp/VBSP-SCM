"""Tab Báo cáo"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO
from datetime import datetime, date

from config import *
from utils import (
    fmt_tien,
    vn,
    fmt_ty,
    fmt_cl,
    fmt_pct,
    xuat_excel,
    ten_file_xuat,
    hien_thi_dataframe_phan_trang,
)
from data import (ts_file, danh_dau_khong_hd, tong_hop_khong_hd,
                  ds_chi_tiet_khong_hd)
from auth import la_phan_he_pgd


def render(tab, **kwargs):
    df       = kwargs.get("df")
    df_full  = kwargs.get("df_full", df)
    role     = kwargs.get("role")
    pgd_user = kwargs.get("pgd_user")
    username = kwargs.get("username")
    df_nq11  = kwargs.get("df_nq11")

    with tab:
        st.subheader("📈 Báo cáo")

        def bc_fmt(x):
            try:
                x = float(x)
                if abs(x) >= 1e9:
                    s = f"{x/1e9:,.3f}".replace(",","X").replace(".",",").replace("X",".")
                    return f"{s.rstrip('0').rstrip(',') if ',' in s else s} tỷ"
                if abs(x) >= 1e6:
                    s = f"{x/1e6:,.1f}".replace(",","X").replace(".",",").replace("X",".")
                    return f"{s} triệu"
                if abs(x) > 0: return f"{x:,.0f}".replace(",",".")
                return "—"
            except: return "—"

        COLS_TIEN = [COT_MUC_VAY, COT_DU_NO_TH, COT_DU_NO_QH, COT_TONG_DU_NO,
                     "Tổng giải ngân","Giải ngân trong tháng","Giải ngân Năm"]

        def fmt_df(d):
            d2 = d.copy()
            for c in COLS_TIEN:
                if c in d2.columns: d2[c] = d2[c].apply(bc_fmt)
            for c in ["Số_KH","Số_món_vay","Số_hồ_sơ"]:
                if c in d2.columns:
                    d2[c] = d2[c].apply(lambda x: f"{int(x):,}".replace(",","."))
            return d2

        COL_CHUNG = [c for c in [
            COT_TEN_PGD,"Tên xã","Tên thôn","Tên ĐVUT","Tên tổ",
            COT_MA_KH, COT_TEN_KH,"Số điện thoại","Địa chỉ",
            COT_SO_KU, COT_NGAY_VAY, COT_NGAY_DH, COT_THOI_HAN,
            COT_LAI_SUAT, COT_MUC_VAY, COT_DU_NO_TH, COT_DU_NO_QH,
            COT_TONG_DU_NO, COT_TEN_CT,"Nguồn vốn","Tên cấp QLV",
            COT_TINH_TRANG
        ] if c in df.columns]

        # ── Chọn mảng ──
        mang = st.radio("Loại báo cáo",
            ["📊 Tổng hợp theo PGD", "📋 Báo cáo chi tiết"],
            horizontal=True, key="bc_mang")

        st.divider()

        # Bộ lọc PGD dùng chung
        if role in ("admin","manager","admin_cn","manager_cn") and COT_TEN_PGD in df.columns:
            loc_pgd_bc = st.selectbox("📍 PGD",
                ["Tất cả"]+sorted(df[COT_TEN_PGD].dropna().unique().tolist()),
                key="bc_pgd_chung")
        else:
            loc_pgd_bc = pgd_user or "Tất cả"
            st.markdown(f"📍 PGD: **{loc_pgd_bc}**")

        df_base = df.copy()
        if role in ("admin","manager","admin_cn","manager_cn") and loc_pgd_bc != "Tất cả":
            df_base = df_base[df_base[COT_TEN_PGD] == loc_pgd_bc]
        elif la_phan_he_pgd(role) and pgd_user:
            df_base = df_base[df_base[COT_TEN_PGD] == loc_pgd_bc] if loc_pgd_bc != "Tất cả" else df_base

        # ══════════════════════════════
        # MẢNG 1: TỔNG HỢP
        # ══════════════════════════════
        if mang == "📊 Tổng hợp theo PGD":

            loai_th = st.radio("Tổng hợp theo",
                ["🏘️ Theo xã/thôn",
                 "🤝 Theo hội đoàn thể (ĐVUT)",
                 "📌 Theo chương trình vay",
                 "👤 Theo CBTD (sẽ bổ sung)"],
                horizontal=True, key="bc_loai_th")

            dbc_raw = None

            # ── Xã / thôn ──
            if loai_th == "🏘️ Theo xã/thôn":
                cap_xa = st.radio("Cấp", ["Theo xã","Theo thôn/ấp"], horizontal=True, key="bc_cap_xa")
                nhom = "Tên xã" if cap_xa == "Theo xã" else "Tên thôn"
                if nhom in df_base.columns:
                    dbc_raw = df_base.groupby(nhom).agg(
                        Số_KH          =(COT_MA_KH,"nunique"),
                        Số_món_vay     =(COT_SO_KU,"nunique"),
                        Tổng_mức_vay   =(COT_MUC_VAY,"sum"),
                        Tổng_dư_nợ     =(COT_TONG_DU_NO,"sum"),
                        Dư_nợ_trong_hạn=(COT_DU_NO_TH,"sum"),
                        Dư_nợ_quá_hạn  =(COT_DU_NO_QH,"sum"),
                    ).sort_values("Tổng_dư_nợ",ascending=False).reset_index()
                    dbc_raw["Tỷ_lệ_QH_%"] = (dbc_raw["Dư_nợ_quá_hạn"]/dbc_raw["Tổng_dư_nợ"]*100).round(2)
                    st.info(f"**{len(dbc_raw):,}** {nhom.lower()}")
                    hien_thi_dataframe_phan_trang(
                        fmt_df(dbc_raw),
                        key="baocao_bak_th_xa_thon",
                    )

            # ── ĐVUT ──
            elif loai_th == "🤝 Theo hội đoàn thể (ĐVUT)":
                if "Tên ĐVUT" in df_base.columns:
                    # Đánh dấu 3 tháng không hoạt động
                    df_kh = danh_dau_khong_hd(df_base)

                    dbc_raw = df_kh.groupby("Tên ĐVUT").agg(
                        Số_KH          =(COT_MA_KH,    "nunique"),
                        Số_món_vay     =(COT_SO_KU,    "nunique"),
                        Tổng_mức_vay   =(COT_MUC_VAY,  "sum"),
                        Tổng_dư_nợ     =(COT_TONG_DU_NO,"sum"),
                        Dư_nợ_trong_hạn=(COT_DU_NO_TH, "sum"),
                        Dư_nợ_quá_hạn  =(COT_DU_NO_QH, "sum"),
                    ).sort_values("Tổng_dư_nợ", ascending=False).reset_index()
                    dbc_raw["Tỷ_lệ_QH_%"] = (
                        dbc_raw["Dư_nợ_quá_hạn"] / dbc_raw["Tổng_dư_nợ"] * 100
                    ).round(2)

                    # Tổng hợp 3 tháng không hoạt động theo ĐVUT
                    khd = tong_hop_khong_hd(df_kh, nhom_theo="Tên ĐVUT")
                    if not khd.empty:
                        dbc_raw = dbc_raw.merge(
                            khd[["Tên ĐVUT", "Món_3m_KHĐ",
                                 "Lãi_tồn_KHĐ", "Tỷ_lệ_KHĐ_%"]],
                            on="Tên ĐVUT", how="left"
                        ).fillna(0)
                        dbc_raw["Món_3m_KHĐ"] = dbc_raw["Món_3m_KHĐ"].astype(int)

                    st.info(f"**{len(dbc_raw):,}** hội đoàn thể")
                    hien_thi_dataframe_phan_trang(
                        fmt_df(dbc_raw),
                        key="baocao_bak_th_dvut",
                    )

                    # ── Xuất danh sách chi tiết để đôn đốc ───────────────
                    st.markdown("**📋 Danh sách hộ cần đôn đốc (3 tháng không hoạt động)**")
                    col_dvut, col_xuat = st.columns([2, 1])
                    with col_dvut:
                        ds_dvut = sorted(df_kh["Tên ĐVUT"].dropna().unique().tolist())
                        chon_dvut = st.selectbox(
                            "Lọc theo Hội đoàn thể",
                            ["Tất cả"] + ds_dvut,
                            key="bc_dvut_khd",
                        )
                    with col_xuat:
                        st.markdown("<br>", unsafe_allow_html=True)
                        gia_tri = None if chon_dvut == "Tất cả" else chon_dvut
                        df_dondoc = ds_chi_tiet_khong_hd(
                            df_kh, nhom_theo="Tên ĐVUT", gia_tri_nhom=gia_tri)

                        if not df_dondoc.empty:
                            buf = xuat_excel({"Đôn đốc 3m KHĐ": df_dondoc})
                            st.download_button(
                                label=f"⬇️ Xuất Excel ({len(df_dondoc)} hộ)",
                                data=buf,
                                file_name=f"DonDoc_3m_{chon_dvut}_{datetime.now().strftime('%Y%m%d')}.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                key="bc_xuat_khd",
                                type="primary",
                            )

                    if not df_dondoc.empty:
                        hien_thi_dataframe_phan_trang(
                            df_dondoc,
                            key="baocao_bak_dondoc",
                            height=340,
                        )
                        tong_lai = df_dondoc[COT_LAI_TON].sum() \
                                   if COT_LAI_TON in df_dondoc.columns else 0
                        st.caption(
                            f"Tổng **{len(df_dondoc):,}** món · "
                            f"Lãi tồn: **{tong_lai/1e6:,.1f}** triệu đồng"
                        )
                    else:
                        st.success("✅ Không có món vay nào quá 3 tháng không hoạt động.")

            # ── Chương trình ──
            elif loai_th == "📌 Theo chương trình vay":
                # Lọc thêm nguồn vốn
                col_f1, col_f2 = st.columns(2)
                with col_f1:
                    loc_nv = st.selectbox("Nguồn vốn",
                        ["Tất cả","1 - Trung ương (TW)","2 - Địa phương (ĐP)"],
                        key="bc_th_nv")
                with col_f2:
                    loc_ct_th = st.selectbox("Chương trình",
                        ["Tất cả"]+sorted(df_base[COT_TEN_CT].dropna().unique().tolist()),
                        key="bc_th_ct") if COT_TEN_CT in df_base.columns else "Tất cả"

                df_ct_th = df_base.copy()
                if loc_nv == "1 - Trung ương (TW)" and "Nguồn vốn" in df_ct_th.columns:
                    df_ct_th = df_ct_th[df_ct_th["Nguồn vốn"] == 1]
                elif loc_nv == "2 - Địa phương (ĐP)" and "Nguồn vốn" in df_ct_th.columns:
                    df_ct_th = df_ct_th[df_ct_th["Nguồn vốn"] == 2]
                if loc_ct_th != "Tất cả" and COT_TEN_CT in df_ct_th.columns:
                    df_ct_th = df_ct_th[df_ct_th[COT_TEN_CT] == loc_ct_th]

                dbc_raw = df_ct_th.groupby(COT_TEN_CT).agg(
                    Số_KH          =(COT_MA_KH,"nunique"),
                    Số_món_vay     =(COT_SO_KU,"nunique"),
                    Tổng_mức_vay   =(COT_MUC_VAY,"sum"),
                    Tổng_giải_ngân  =("Tổng giải ngân","sum"),
                    Tổng_dư_nợ     =(COT_TONG_DU_NO,"sum"),
                    Dư_nợ_trong_hạn=(COT_DU_NO_TH,"sum"),
                    Dư_nợ_quá_hạn  =(COT_DU_NO_QH,"sum"),
                ).sort_values("Tổng_dư_nợ",ascending=False).reset_index() if COT_TEN_CT in df_ct_th.columns else None
                if dbc_raw is not None:
                    dbc_raw["Tỷ_lệ_QH_%"] = (dbc_raw["Dư_nợ_quá_hạn"]/dbc_raw["Tổng_dư_nợ"]*100).round(2)
                    st.info(f"**{len(dbc_raw):,}** chương trình · {len(df_ct_th):,} hồ sơ")
                    hien_thi_dataframe_phan_trang(
                        fmt_df(dbc_raw),
                        key="baocao_bak_th_ct",
                    )

            # ── CBTD (chờ bổ sung) ──
            elif loai_th == "👤 Theo CBTD (sẽ bổ sung)":
                st.info("📋 Chức năng này sẽ bổ sung sau khi có dữ liệu CBTD phụ trách.")
                st.caption("Nhân viên sẽ nhập danh sách CBTD và gán hồ sơ trong phần Kế hoạch PGD.")

            # Xuất tổng hợp
            if dbc_raw is not None:
                st.divider()
                if st.button("📥 Xuất tổng hợp Excel", key="btn_xuat_th"):
                    buf = BytesIO()
                    with pd.ExcelWriter(buf, engine="openpyxl") as w:
                        dbc_raw.to_excel(w, index=False, sheet_name="Tổng hợp")
                    st.download_button("⬇ Tải Excel", data=buf.getvalue(),
                        file_name=f"BC_TH_{datetime.today().strftime('%d%m%Y')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="dl_bc_th")

        # ══════════════════════════════
        # MẢNG 2: CHI TIẾT
        # ══════════════════════════════
        else:
            loai_ct = st.radio("Loại chi tiết",
                ["📋 Danh sách theo tiêu chí lọc",
                 "⏰ Hồ sơ đến hạn / quá hạn",
                 "📌 Theo chương trình vay cụ thể",
                 "🏦 Theo nguồn vốn"],
                horizontal=True, key="bc_loai_ct")

            # Bộ lọc chi tiết
            with st.expander("🔧 Bộ lọc nâng cao", expanded=True):
                d1, d2, d3 = st.columns(3)
                with d1:
                    loc_xa_ct = st.selectbox("Xã",
                        ["Tất cả"]+sorted(df_base["Tên xã"].dropna().unique().tolist())
                        if "Tên xã" in df_base.columns else ["Tất cả"],
                        key="bc_ct_xa")
                with d2:
                    loc_dvut_ct = st.selectbox("Hội đoàn thể",
                        ["Tất cả"]+sorted(df_base["Tên ĐVUT"].dropna().unique().tolist())
                        if "Tên ĐVUT" in df_base.columns else ["Tất cả"],
                        key="bc_ct_dvut")
                with d3:
                    loc_tt_ct = st.selectbox("Tình trạng",
                        ["Tất cả"]+sorted(df_base[COT_TINH_TRANG].dropna().unique().tolist())
                        if COT_TINH_TRANG in df_base.columns else ["Tất cả"],
                        key="bc_ct_tt")

            df_ct = df_base.copy()
            if loc_xa_ct   != "Tất cả" and "Tên xã"       in df_ct.columns: df_ct = df_ct[df_ct["Tên xã"]       == loc_xa_ct]
            if loc_dvut_ct != "Tất cả" and "Tên ĐVUT"     in df_ct.columns: df_ct = df_ct[df_ct["Tên ĐVUT"]     == loc_dvut_ct]
            if loc_tt_ct   != "Tất cả" and COT_TINH_TRANG in df_ct.columns: df_ct = df_ct[df_ct[COT_TINH_TRANG] == loc_tt_ct]

            m1,m2,m3 = st.columns(3)
            m1.metric("Số hồ sơ",   f"{len(df_ct):,}".replace(",","."))
            m2.metric("Tổng dư nợ", bc_fmt(df_ct[COT_TONG_DU_NO].sum()) if COT_TONG_DU_NO in df_ct.columns else "—")
            m3.metric("Dư nợ QH",   bc_fmt(df_ct[COT_DU_NO_QH].sum()) if COT_DU_NO_QH in df_ct.columns else "—")

            export_df = None

            # ── Danh sách theo tiêu chí ──
            if loai_ct == "📋 Danh sách theo tiêu chí lọc":
                export_df = df_ct[COL_CHUNG].copy()
                hien_thi_dataframe_phan_trang(
                    fmt_df(export_df).reset_index(drop=True),
                    key="baocao_bak_ct_loc",
                    height=420,
                )

            # ── Đến hạn / quá hạn ──
            elif loai_ct == "⏰ Hồ sơ đến hạn / quá hạn":
                loai_dh = st.radio("Loại",
                    ["Đến hạn 30 ngày","Đến hạn 60 ngày","Quá hạn"],
                    horizontal=True, key="bc_dh_loai")
                try:
                    df_tmp = df_ct.copy()
                    df_tmp[COT_NGAY_DH] = pd.to_datetime(df_tmp[COT_NGAY_DH], dayfirst=True, errors="coerce")
                    hn = pd.Timestamp.today()
                    if loai_dh == "Quá hạn":
                        df_tmp = df_tmp[df_tmp[COT_DU_NO_QH] > 0] if COT_DU_NO_QH in df_tmp.columns else df_tmp
                        st.warning(f"⚠️ **{len(df_tmp):,}** hồ sơ quá hạn")
                    else:
                        ngay = 30 if "30" in loai_dh else 60
                        df_tmp = df_tmp[(df_tmp[COT_NGAY_DH]>=hn)&(df_tmp[COT_NGAY_DH]<=hn+pd.Timedelta(days=ngay))]
                        st.info(f"📅 **{len(df_tmp):,}** hồ sơ đến hạn trong {ngay} ngày tới")
                    export_df = df_tmp[COL_CHUNG].sort_values(COT_NGAY_DH)
                    hien_thi_dataframe_phan_trang(
                        fmt_df(export_df).reset_index(drop=True),
                        key="baocao_bak_ct_dh",
                        height=400,
                    )
                except: st.error("Không thể tính hồ sơ đến hạn.")

            # ── Theo chương trình cụ thể ──
            elif loai_ct == "📌 Theo chương trình vay cụ thể":
                if COT_TEN_CT in df_ct.columns:
                    ds_ct2 = sorted(df_ct[COT_TEN_CT].dropna().unique().tolist())
                    chon_ct2 = st.selectbox("Chọn chương trình", ds_ct2, key="bc_ct2_sel")
                    df_ct2 = df_ct[df_ct[COT_TEN_CT] == chon_ct2]

                    c1,c2,c3,c4 = st.columns(4)
                    c1.metric("Số hồ sơ",    f"{len(df_ct2):,}".replace(",","."))
                    c2.metric("Tổng dư nợ",  bc_fmt(df_ct2[COT_TONG_DU_NO].sum()))
                    c3.metric("Dư nợ QH",    bc_fmt(df_ct2[COT_DU_NO_QH].sum()))
                    c4.metric("Tỷ lệ QH",
                        f"{df_ct2[COT_DU_NO_QH].sum()/df_ct2[COT_TONG_DU_NO].sum()*100:.2f}%"
                        if df_ct2[COT_TONG_DU_NO].sum() > 0 else "—")

                    # Tổng hợp theo xã
                    if "Tên xã" in df_ct2.columns:
                        st.markdown("**Tổng hợp theo xã**")
                        t_xa = df_ct2.groupby("Tên xã").agg(
                            Số_hồ_sơ=(COT_MA_KH,"count"),
                            Tổng_dư_nợ=(COT_TONG_DU_NO,"sum"),
                            Dư_nợ_QH=(COT_DU_NO_QH,"sum")
                        ).sort_values("Tổng_dư_nợ",ascending=False).reset_index()
                        t_xa["Tổng_dư_nợ"] = t_xa["Tổng_dư_nợ"].apply(bc_fmt)
                        t_xa["Dư_nợ_QH"]   = t_xa["Dư_nợ_QH"].apply(bc_fmt)
                        hien_thi_dataframe_phan_trang(
                            t_xa,
                            key="baocao_bak_ct2_xa",
                        )

                    export_df = df_ct2[COL_CHUNG].copy()
                    st.markdown("**Danh sách hồ sơ**")
                    hien_thi_dataframe_phan_trang(
                        fmt_df(export_df).reset_index(drop=True),
                        key="baocao_bak_ct2_ds",
                        height=350,
                    )

            # ── Theo nguồn vốn ──
            elif loai_ct == "🏦 Theo nguồn vốn":
                if "Nguồn vốn" in df_ct.columns:
                    chon_nv = st.radio("Nguồn vốn",
                        ["Tổng hợp cả 2","1 - Trung ương (TW)","2 - Địa phương (ĐP)"],
                        horizontal=True, key="bc_nv_chon")

                    # Tổng hợp so sánh TW vs ĐP
                    st.markdown("**Tổng hợp so sánh nguồn vốn**")
                    t_nv = df_ct.groupby("Nguồn vốn").agg(
                        Số_KH          =(COT_MA_KH,"nunique"),
                        Số_món_vay     =(COT_SO_KU,"nunique"),
                        Tổng_mức_vay   =(COT_MUC_VAY,"sum"),
                        Tổng_dư_nợ     =(COT_TONG_DU_NO,"sum"),
                        Dư_nợ_trong_hạn=(COT_DU_NO_TH,"sum"),
                        Dư_nợ_quá_hạn  =(COT_DU_NO_QH,"sum"),
                    ).reset_index()
                    t_nv["Nguồn vốn"] = t_nv["Nguồn vốn"].map({1:"1 - TW",2:"2 - ĐP"}).fillna(t_nv["Nguồn vốn"].astype(str))
                    t_nv["Tỷ_lệ_QH_%"] = (t_nv["Dư_nợ_quá_hạn"]/t_nv["Tổng_dư_nợ"]*100).round(2)
                    hien_thi_dataframe_phan_trang(
                        fmt_df(t_nv),
                        key="baocao_bak_nv_tong",
                    )

                    # Lọc và hiển thị chi tiết
                    if chon_nv != "Tổng hợp cả 2":
                        nv_val = 1 if "TW" in chon_nv else 2
                        df_nv = df_ct[df_ct["Nguồn vốn"] == nv_val]
                        st.divider()

                        # Tổng hợp theo chương trình
                        st.markdown(f"**Theo chương trình — {'TW' if nv_val==1 else 'ĐP'}**")
                        t_ct_nv = df_nv.groupby(COT_TEN_CT).agg(
                            Số_hồ_sơ   =(COT_MA_KH,"count"),
                            Tổng_dư_nợ =(COT_TONG_DU_NO,"sum"),
                            Dư_nợ_QH   =(COT_DU_NO_QH,"sum"),
                        ).sort_values("Tổng_dư_nợ",ascending=False).reset_index() if COT_TEN_CT in df_nv.columns else None
                        if t_ct_nv is not None:
                            t_ct_nv["Tổng_dư_nợ"] = t_ct_nv["Tổng_dư_nợ"].apply(bc_fmt)
                            t_ct_nv["Dư_nợ_QH"]   = t_ct_nv["Dư_nợ_QH"].apply(bc_fmt)
                            hien_thi_dataframe_phan_trang(
                                t_ct_nv,
                                key="baocao_bak_nv_ct",
                            )

                        export_df = df_nv[COL_CHUNG].copy()
                        st.markdown("**Danh sách hồ sơ**")
                        hien_thi_dataframe_phan_trang(
                            fmt_df(export_df).reset_index(drop=True),
                            key="baocao_bak_nv_ds",
                            height=350,
                        )
                    else:
                        export_df = df_ct[COL_CHUNG].copy()

            # Xuất Excel
            if export_df is not None:
                st.divider()
                if st.button("📥 Xuất báo cáo chi tiết", type="primary", key="btn_xuat_ct"):
                    buf = BytesIO()
                    with pd.ExcelWriter(buf, engine="openpyxl") as w:
                        export_df.to_excel(w, index=False, sheet_name="Chi tiết")
                        if role in ("admin","manager","admin_cn","manager_cn") and COT_TEN_PGD in df.columns:
                            df.groupby(COT_TEN_PGD).agg(
                                Số_hồ_sơ=(COT_MA_KH,"count"),
                                Tổng_dư_nợ=(COT_TONG_DU_NO,"sum"),
                                Dư_nợ_QH=(COT_DU_NO_QH,"sum")
                            ).reset_index().to_excel(w, index=False, sheet_name="Tổng hợp PGD")
                    st.download_button("⬇ Tải Excel", data=buf.getvalue(),
                        file_name=f"BC_CT_{loai_ct[2:12].strip().replace(' ','_')}_{datetime.today().strftime('%d%m%Y')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="dl_bc_ct")

