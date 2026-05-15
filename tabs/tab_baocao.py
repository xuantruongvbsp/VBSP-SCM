"""Tab Báo cáo."""
from __future__ import annotations

from datetime import datetime, date
from typing import TYPE_CHECKING

import streamlit as st
import pandas as pd

import db
from config import *
from utils import fmt_so, fmt_ty, vn, ten_file_xuat, hien_thi_dataframe_phan_trang, xuat_excel
from services import xuat_bao_cao, ten_file_bao_cao
from pdf_service import nut_xuat_pdf
from data import (danh_dau_khong_hd, tong_hop_khong_hd, ds_chi_tiet_khong_hd)
from tabs import tab_nq11
from auth import la_phan_he_pgd, la_phan_he_cn, normalize_role

if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator


_COLS_TIEN = {
    COT_DU_NO_TH, COT_DU_NO_QH, COT_TONG_DU_NO, COT_LAI_TON,
    "Tổng_dư_nợ", "Dư_nợ_trong_hạn", "Dư_nợ_quá_hạn",
    "Lãi_tồn_KHĐ", "Dư nợ TH", "Dư nợ QH", "Nợ khoanh", "Tổng dư nợ", "Lãi tồn",
}
_COLS_PCT = {"Tỷ_lệ_QH_%", "Tỷ_lệ_KHĐ_%", "QH%", "TL Nợ xấu %"}


def _fmt_df(df: pd.DataFrame) -> pd.DataFrame:
    """Chuyển cột tiền → fmt_ty string, cột % → chuỗi VN trước khi hiển thị."""
    d = df.copy()
    for col in d.columns:
        if col in _COLS_TIEN:
            d[col] = pd.to_numeric(d[col], errors="coerce").apply(fmt_ty)
        elif col in _COLS_PCT:
            d[col] = pd.to_numeric(d[col], errors="coerce").apply(
                lambda x: f"{x:.2f}".replace(".", ",") + "%" if pd.notna(x) else "—"
            )
    return d


def _bc_fmt_metric(x: float) -> str:
    """Format số tiền cho metric display (tỷ/triệu)."""
    try:
        x = float(x)
        if abs(x) >= 1e9:
            s = f"{x/1e9:,.3f}".replace(",","X").replace(".",",").replace("X",".")
            return f"{s.rstrip('0').rstrip(',') if ',' in s else s} tỷ"
        if abs(x) >= 1e6:
            s = f"{x/1e6:,.1f}".replace(",","X").replace(".",",").replace("X",".")
            return f"{s} triệu"
        if abs(x) > 0:
            return f"{x:,.0f}".replace(",",".")
        return "—"
    except Exception:
        return "—"


from utils import get_tab_context

def render(tab: DeltaGenerator, **kwargs: dict) -> None:
    """
    Render tab Báo cáo.
    
    Args:
        tab: Streamlit DeltaGenerator cho tab này
        **kwargs: Chứa df, df_full, role, pgd_user, username, df_nq11
    """
    df = kwargs.get("df")
    df_full = kwargs.get("df_full", df)
    role_raw = str(kwargs.get("role", "user") or "user")
    role = normalize_role(role_raw)
    pgd_user = kwargs.get("pgd_user")
    username = kwargs.get("username")
    df_nq11 = kwargs.get("df_nq11")

    import streamlit as _st
    _tab_ctx = tab if tab is not None else _st.container()
    with _tab_ctx:
        st.subheader("📈 Báo cáo")

        COL_CHUNG = [c for c in [
            COT_TEN_PGD,"Tên xã","Tên thôn","Tên ĐVUT","Tên tổ",
            COT_MA_KH, COT_TEN_KH,"Số điện thoại","Địa chỉ",
            COT_SO_KU, COT_NGAY_VAY, COT_NGAY_DH, COT_THOI_HAN,
            COT_LAI_SUAT, COT_DU_NO_TH, COT_DU_NO_QH,
            COT_TONG_DU_NO, COT_TEN_CT,"Nguồn vốn","Tên cấp QLV",
            COT_TINH_TRANG
        ] if c in df.columns]

        # ── Chọn mảng ──
        mang = st.radio("Loại báo cáo",
            ["📊 Tổng hợp theo PGD", "📋 Báo cáo chi tiết"],
            horizontal=True, key="bc_mang")

        st.divider()

        if mang == "📊 Tổng hợp theo PGD":
            col_f1, col_f2, col_f3 = st.columns(3)

            with col_f1:
                if la_phan_he_pgd(role) and pgd_user:
                    loc_pgd = pgd_user
                    st.markdown(f"📍 PGD: **{loc_pgd}**")
                else:
                    ds_pgd = (
                        sorted(df[COT_TEN_PGD].dropna().unique())
                        if COT_TEN_PGD in df.columns
                        else []
                    )
                    loc_pgd = st.selectbox(
                        "📍 PGD",
                        ["Tất cả"] + ds_pgd,
                        key="bc_pc_pgd",
                    )

            with col_f2:
                if loc_pgd != "Tất cả":
                    ds_xa = (
                        sorted(df[df[COT_TEN_PGD] == loc_pgd][COT_TEN_XA].dropna().unique())
                        if COT_TEN_XA in df.columns and COT_TEN_PGD in df.columns
                        else []
                    )
                else:
                    ds_xa = (
                        sorted(df[COT_TEN_XA].dropna().unique())
                        if COT_TEN_XA in df.columns
                        else []
                    )
                loc_xa = st.selectbox("🏘️ Xã", ["Tất cả"] + ds_xa, key="bc_pc_xa")

            with col_f3:
                ds_ct = []
                if loc_pgd != "Tất cả":
                    from data.pgd import pgd_slug

                    ds_ct = db.doc_kv(f"ct_registry_{pgd_slug(loc_pgd)}") or []
                if not ds_ct:
                    ds_ct = (
                        sorted(df[COT_TEN_CT].dropna().unique())
                        if COT_TEN_CT in df.columns
                        else []
                    )
                loc_ct = st.selectbox("📌 Chương trình", ["Tất cả"] + ds_ct, key="bc_pc_ct")

            df_filtered = df.copy()
            if loc_pgd != "Tất cả" and COT_TEN_PGD in df_filtered.columns:
                df_filtered = df_filtered[df_filtered[COT_TEN_PGD] == loc_pgd]
            if loc_xa != "Tất cả" and COT_TEN_XA in df_filtered.columns:
                df_filtered = df_filtered[df_filtered[COT_TEN_XA] == loc_xa]
            if loc_ct != "Tất cả" and COT_TEN_CT in df_filtered.columns:
                df_filtered = df_filtered[df_filtered[COT_TEN_CT] == loc_ct]

            df_base = df_filtered
            if COT_TONG_DU_NO in df_base.columns:
                df_base = df_base[df_base[COT_TONG_DU_NO] > 0]

            COT_DU_NO_KHOANH = "Dư nợ khoanh"

            _required_cols = [
                COT_TEN_PGD,
                COT_TEN_XA,
                COT_TEN_CT,
                COT_MA_KH,
                COT_SO_KU,
                COT_DU_NO_TH,
                COT_DU_NO_QH,
                COT_TONG_DU_NO,
                COT_LAI_TON,
            ]
            _missing_cols = [c for c in _required_cols if c not in df_base.columns]
            df_pdf = pd.DataFrame()
            if not _missing_cols:
                df_pdf_src = df_base.copy()
                if COT_DU_NO_KHOANH not in df_pdf_src.columns:
                    df_pdf_src[COT_DU_NO_KHOANH] = 0

                df_pdf = (
                    df_pdf_src.groupby([COT_TEN_PGD, COT_TEN_XA, COT_TEN_CT])
                    .agg(
                        **{
                            "Số KH": (COT_MA_KH, "nunique"),
                            "Số món": (COT_SO_KU, "nunique"),
                            "Dư nợ TH": (COT_DU_NO_TH, "sum"),
                            "Dư nợ QH": (COT_DU_NO_QH, "sum"),
                            "Nợ khoanh": (COT_DU_NO_KHOANH, "sum"),
                            "Tổng dư nợ": (COT_TONG_DU_NO, "sum"),
                            "Lãi tồn": (COT_LAI_TON, "sum"),
                        }
                    )
                    .reset_index()
                )

                df_pdf["TL Nợ xấu %"] = (
                    (df_pdf["Dư nợ QH"] + df_pdf["Nợ khoanh"])
                    / df_pdf["Tổng dư nợ"].replace(0, float("nan"))
                    * 100
                ).round(2).fillna(0)


                COLS_PDF = [
                    COT_TEN_PGD,
                    COT_TEN_XA,
                    COT_TEN_CT,
                    "Số KH",
                    "Số món",
                    "Dư nợ TH",
                    "Dư nợ QH",
                    "Nợ khoanh",
                    "Tổng dư nợ",
                    "Lãi tồn",
                    "TL Nợ xấu %",
                ]
                COLS_PDF = [c for c in COLS_PDF if c in df_pdf.columns]
                df_pdf = df_pdf[COLS_PDF].sort_values([COT_TEN_PGD, COT_TEN_XA, COT_TEN_CT])

            _ss_pdf = "_pdf_bytes_baocao_phancap"
            _ssf_pdf = "_pdf_file_baocao_phancap"

            if st.button("📄 Xuất PDF phân cấp", key="btn_pdf_bc_phancap", type="secondary"):
                if _missing_cols:
                    st.warning(f"⚠️ Thiếu cột dữ liệu để xuất PDF: {', '.join(_missing_cols)}")
                elif df_pdf.empty:
                    st.warning("⚠️ Không có dữ liệu để xuất.")
                else:
                    try:
                        from pdf_service import xuat_pdf_group_header

                        _phu = []
                        if loc_pgd != "Tất cả":
                            _phu.append(f"PGD: {loc_pgd}")
                        if loc_xa != "Tất cả":
                            _phu.append(f"Xã: {loc_xa}")
                        if loc_ct != "Tất cả":
                            _phu.append(f"CT: {loc_ct}")
                        tieu_de_phu = "  |  ".join(_phu) if _phu else "Toàn Chi nhánh"

                        with st.spinner("⏳ Đang tạo PDF..."):
                            pdf_bytes = xuat_pdf_group_header(
                                df=df_pdf,
                                tieu_de="Báo cáo Tổng hợp Tín dụng — Phân cấp PGD > Xã > Chương trình",
                                nhom_theo=COT_TEN_PGD,
                                nguoi_xuat=username or "unknown",
                                cols_tien=[
                                    "Dư nợ TH",
                                    "Dư nợ QH",
                                    "Nợ khoanh",
                                    "Tổng dư nợ",
                                    "Lãi tồn",
                                ],
                                tieu_de_phu=tieu_de_phu,
                            )
                        st.session_state[_ss_pdf] = pdf_bytes
                        st.session_state[_ssf_pdf] = ten_file_xuat("BC_PhanCap_PGD_Xa_CT")
                        db.ghi_audit(
                            username or "unknown",
                            "xuat_pdf_bao_cao",
                            f"PDF phân cấp — {tieu_de_phu}",
                        )
                    except Exception as _e:
                        import traceback

                        st.error(f"❌ Lỗi tạo PDF: {_e}")
                        st.code(traceback.format_exc())

            if st.session_state.get(_ss_pdf):
                st.download_button(
                    "⬇ Tải PDF phân cấp",
                    data=st.session_state[_ss_pdf],
                    file_name=st.session_state.get(_ssf_pdf, "BC_PhanCap.pdf"),
                    mime="application/pdf",
                    key="btn_pdf_bc_phancap_dl",
                )
        else:
            if (la_phan_he_cn(role) and role != "executive") and COT_TEN_PGD in df.columns:
                loc_pgd_bc = st.selectbox(
                    "📍 PGD",
                    ["Tất cả"] + sorted(df[COT_TEN_PGD].dropna().unique().tolist()),
                    key="bc_pgd_chung",
                )
            else:
                loc_pgd_bc = pgd_user or "Tất cả"
                st.markdown(f"📍 PGD: **{loc_pgd_bc}**")

            df_base = df.copy()
            if (la_phan_he_cn(role) and role != "executive") and loc_pgd_bc != "Tất cả":
                df_base = df_base[df_base[COT_TEN_PGD] == loc_pgd_bc]
            elif la_phan_he_pgd(role) and pgd_user:
                df_base = df_base[df_base[COT_TEN_PGD] == loc_pgd_bc] if loc_pgd_bc != "Tất cả" else df_base
            if COT_TONG_DU_NO in df_base.columns:
                df_base = df_base[df_base[COT_TONG_DU_NO] > 0]

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
                        Tổng_dư_nợ     =(COT_TONG_DU_NO,"sum"),
                        Dư_nợ_trong_hạn=(COT_DU_NO_TH,"sum"),
                        Dư_nợ_quá_hạn  =(COT_DU_NO_QH,"sum"),
                    ).sort_values("Tổng_dư_nợ",ascending=False).reset_index()
                    dbc_raw["Tỷ_lệ_QH_%"] = (
                        dbc_raw["Dư_nợ_quá_hạn"]
                        / dbc_raw["Tổng_dư_nợ"].replace(0, float("nan"))
                        * 100
                    ).round(2).fillna(0)
                    st.info(f"**{fmt_so(len(dbc_raw))}** {nhom.lower()}")
                    hien_thi_dataframe_phan_trang(
                        _fmt_df(dbc_raw),
                        key="baocao_th_xa_thon",
                    )

            # ── ĐVUT ──
            elif loai_th == "🤝 Theo hội đoàn thể (ĐVUT)":
                if "Tên ĐVUT" in df_base.columns:
                    # Đánh dấu 3 tháng không hoạt động
                    df_kh = danh_dau_khong_hd(df_base)

                    dbc_raw = df_kh.groupby("Tên ĐVUT").agg(
                        Số_KH          =(COT_MA_KH,    "nunique"),
                        Số_món_vay     =(COT_SO_KU,    "nunique"),
                        Tổng_dư_nợ     =(COT_TONG_DU_NO,"sum"),
                        Dư_nợ_trong_hạn=(COT_DU_NO_TH, "sum"),
                        Dư_nợ_quá_hạn  =(COT_DU_NO_QH, "sum"),
                    ).sort_values("Tổng_dư_nợ", ascending=False).reset_index()
                    dbc_raw["Tỷ_lệ_QH_%"] = (
                        dbc_raw["Dư_nợ_quá_hạn"]
                        / dbc_raw["Tổng_dư_nợ"].replace(0, float("nan"))
                        * 100
                    ).round(2).fillna(0)

                    # Tổng hợp 3 tháng không hoạt động theo ĐVUT
                    khd = tong_hop_khong_hd(df_kh, nhom_theo="Tên ĐVUT")
                    if not khd.empty:
                        dbc_raw = dbc_raw.merge(
                            khd[["Tên ĐVUT", "Món_3m_KHĐ",
                                 "Lãi_tồn_KHĐ", "Tỷ_lệ_KHĐ_%"]],
                            on="Tên ĐVUT", how="left"
                        ).fillna(0)
                        dbc_raw["Món_3m_KHĐ"] = dbc_raw["Món_3m_KHĐ"].astype(int)

                    st.info(f"**{fmt_so(len(dbc_raw))}** hội đoàn thể")
                    hien_thi_dataframe_phan_trang(
                        _fmt_df(dbc_raw),
                        key="baocao_th_dvut",
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
                            key="baocao_dondoc_dvut",
                            height=340,
                        )
                        tong_lai = df_dondoc[COT_LAI_TON].sum() \
                                   if COT_LAI_TON in df_dondoc.columns else 0
                        st.caption(
                            f"Tổng **{fmt_so(len(df_dondoc))}** món · "
                            f"Lãi tồn: **{vn(tong_lai/1e6,1)}** triệu đồng"
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

                try:
                    agg_dict = {
                        "Số_KH":          (COT_MA_KH, "nunique"),
                        "Số_món_vay":     (COT_SO_KU, "nunique"),
                        "Tổng_dư_nợ":     (COT_TONG_DU_NO, "sum"),
                        "Dư_nợ_trong_hạn":(COT_DU_NO_TH, "sum"),
                        "Dư_nợ_quá_hạn":  (COT_DU_NO_QH, "sum"),
                    }
                    if COT_LAI_TON in df_ct_th.columns:
                        agg_dict["Lãi_tồn_KHĐ"] = (COT_LAI_TON, "sum")

                    dbc_raw = (
                        df_ct_th.groupby(COT_TEN_CT)
                        .agg(**agg_dict)
                        .sort_values("Tổng_dư_nợ", ascending=False)
                        .reset_index()
                    ) if COT_TEN_CT in df_ct_th.columns else None

                    if dbc_raw is not None:
                        dbc_raw["Tỷ_lệ_QH_%"] = (
                            dbc_raw["Dư_nợ_quá_hạn"]
                            / dbc_raw["Tổng_dư_nợ"].replace(0, float("nan"))
                            * 100
                        ).round(2).fillna(0)
                        st.info(f"**{fmt_so(len(dbc_raw))}** chương trình · {fmt_so(len(df_ct_th))} hồ sơ")
                        hien_thi_dataframe_phan_trang(
                            _fmt_df(dbc_raw),
                            key="baocao_th_chuong_trinh",
                        )
                except Exception as e:
                    st.error(f"Lỗi khi nhóm theo chương trình vay: {e}")
                    dbc_raw = None

            # ── CBTD (chờ bổ sung) ──
            elif loai_th == "👤 Theo CBTD (sẽ bổ sung)":
                st.info("📋 Chức năng này sẽ bổ sung sau khi có dữ liệu CBTD phụ trách.")
                st.caption("Nhân viên sẽ nhập danh sách CBTD và gán hồ sơ trong phần Kế hoạch PGD.")

            # Xuất tổng hợp
            if dbc_raw is not None:
                st.divider()
                if st.button("📥 Xuất tổng hợp Excel", key="btn_xuat_th"):
                    data_excel = xuat_bao_cao(
                        sheets={"Tổng hợp": dbc_raw},
                        tieu_de="Báo cáo tổng hợp",
                        nguoi_xuat=username or "Người dùng",
                    )
                    st.session_state["_bytes_bc_th"] = data_excel
                    st.session_state["_file_bc_th"] = ten_file_bao_cao("BC_TH")

                if st.session_state.get("_bytes_bc_th"):
                    st.download_button("⬇ Tải Excel",
                        data=st.session_state["_bytes_bc_th"],
                        file_name=st.session_state["_file_bc_th"],
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="dl_bc_th")

        # ══════════════════════════════
        # MẢNG 2: CHI TIẾT
        # ══════════════════════════════
        else:
            sub_bc, sub_nq11 = st.tabs(["📋 Báo cáo chi tiết", "📑 NQ11"])

            with sub_nq11:
                tab_nq11.render(sub_nq11, **kwargs)

            with sub_bc:
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
                m1.metric("Số hồ sơ", fmt_so(len(df_ct)))
                m2.metric("Tổng dư nợ", _bc_fmt_metric(df_ct[COT_TONG_DU_NO].sum()) if COT_TONG_DU_NO in df_ct.columns else "—")
                m3.metric("Dư nợ QH", _bc_fmt_metric(df_ct[COT_DU_NO_QH].sum()) if COT_DU_NO_QH in df_ct.columns else "—")

                export_df = None

                # ── Danh sách theo tiêu chí ──
                if loai_ct == "📋 Danh sách theo tiêu chí lọc":
                    export_df = df_ct[COL_CHUNG].copy()
                    hien_thi_dataframe_phan_trang(
                        _fmt_df(export_df.reset_index(drop=True)),
                        key="baocao_ct_loc",
                        column_config=_tao_column_config_baocao(export_df),
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
                            st.warning(f"⚠️ **{fmt_so(len(df_tmp))}** hồ sơ quá hạn")
                        else:
                            ngay = 30 if "30" in loai_dh else 60
                            df_tmp = df_tmp[(df_tmp[COT_NGAY_DH]>=hn)&(df_tmp[COT_NGAY_DH]<=hn+pd.Timedelta(days=ngay))]
                            st.info(f"📅 **{fmt_so(len(df_tmp))}** hồ sơ đến hạn trong {ngay} ngày tới")
                        export_df = df_tmp[COL_CHUNG].sort_values(COT_NGAY_DH)
                        hien_thi_dataframe_phan_trang(
                            _fmt_df(export_df.reset_index(drop=True)),
                            key="baocao_ct_den_han",
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
                        c1.metric("Số hồ sơ", fmt_so(len(df_ct2)))
                        c2.metric("Tổng dư nợ", _bc_fmt_metric(df_ct2[COT_TONG_DU_NO].sum()))
                        c3.metric("Dư nợ QH", _bc_fmt_metric(df_ct2[COT_DU_NO_QH].sum()))
                        c4.metric("Tỷ lệ QH",
                            f"{df_ct2[COT_DU_NO_QH].sum()/df_ct2[COT_TONG_DU_NO].sum()*100:.2f}%"
                            if df_ct2[COT_TONG_DU_NO].sum() > 0 else "—")

                        # Tổng hợp theo xã
                        if "Tên xã" in df_ct2.columns:
                            st.markdown("**Tổng hợp theo xã**")
                            t_xa = df_ct2.groupby("Tên xã").agg(
                                Số_hồ_sơ=(COT_MA_KH, "nunique"),
                                Tổng_dư_nợ=(COT_TONG_DU_NO, "sum"),
                                Dư_nợ_QH=(COT_DU_NO_QH, "sum"),
                            ).sort_values("Tổng_dư_nợ", ascending=False).reset_index()
                            t_xa["Tỷ_lệ_QH_%"] = (
                                t_xa["Dư_nợ_QH"]
                                / t_xa["Tổng_dư_nợ"].replace(0, float("nan"))
                                * 100
                            ).round(2).fillna(0)
                            hien_thi_dataframe_phan_trang(
                                _fmt_df(t_xa),
                                key="baocao_ct_ct2_xa",
                            )

                        export_df = df_ct2[COL_CHUNG].copy()
                        st.markdown("**Danh sách hồ sơ**")
                        hien_thi_dataframe_phan_trang(
                            _fmt_df(export_df.reset_index(drop=True)),
                            key="baocao_ct_ct2_ds",
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
                            Tổng_dư_nợ     =(COT_TONG_DU_NO,"sum"),
                            Dư_nợ_trong_hạn=(COT_DU_NO_TH,"sum"),
                            Dư_nợ_quá_hạn  =(COT_DU_NO_QH,"sum"),
                        ).reset_index()
                        t_nv["Nguồn vốn"] = t_nv["Nguồn vốn"].map({1:"1 - TW",2:"2 - ĐP"}).fillna(t_nv["Nguồn vốn"].astype(str))
                        t_nv["Tỷ_lệ_QH_%"] = (
                            t_nv["Dư_nợ_quá_hạn"]
                            / t_nv["Tổng_dư_nợ"].replace(0, float("nan"))
                            * 100
                        ).round(2).fillna(0)
                        hien_thi_dataframe_phan_trang(
                            _fmt_df(t_nv),
                            key="baocao_ct_nv_tong",
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
                                t_ct_nv["Tỷ_lệ_QH_%"] = (
                                    t_ct_nv["Dư_nợ_QH"]
                                    / t_ct_nv["Tổng_dư_nợ"].replace(0, float("nan"))
                                    * 100
                                ).round(2).fillna(0)
                                hien_thi_dataframe_phan_trang(
                                    _fmt_df(t_ct_nv),
                                    key="baocao_ct_nv_ct",
                                )

                            export_df = df_nv[COL_CHUNG].copy()
                            st.markdown("**Danh sách hồ sơ**")
                            hien_thi_dataframe_phan_trang(
                                _fmt_df(export_df.reset_index(drop=True)),
                                key="baocao_ct_nv_ds",
                                    height=350,
                            )
                        else:
                            export_df = df_ct[COL_CHUNG].copy()

                # Xuất Excel
                if export_df is not None:
                    st.divider()
                    col_xl, col_pdf = st.columns([1, 1])
                    with col_xl:
                        if st.button("📥 Xuất báo cáo chi tiết", type="primary", key="btn_xuat_ct"):
                            sheets = {"Chi tiết": export_df}
                            if la_phan_he_cn(role) and COT_TEN_PGD in df.columns:
                                sheets["Tổng hợp PGD"] = df.groupby(COT_TEN_PGD).agg(
                                    Số_hồ_sơ=(COT_MA_KH, "count"),
                                    Tổng_dư_nợ=(COT_TONG_DU_NO, "sum"),
                                    Dư_nợ_QH=(COT_DU_NO_QH, "sum"),
                                ).reset_index()

                            tieu_de_xuat = f"Báo cáo chi tiết — {loai_ct[2:].strip()}"
                            ten_file = ten_file_bao_cao(
                                f"BC_CT_{loai_ct[2:12].strip().replace(' ','_')}"
                            )
                            file_bytes = xuat_bao_cao(sheets, tieu_de_xuat, username or "unknown")
                            st.session_state["_bytes_bc_ct"] = file_bytes
                            st.session_state["_file_bc_ct"] = ten_file

                        if st.session_state.get("_bytes_bc_ct"):
                            st.download_button(
                                "⬇ Tải Excel",
                                data=st.session_state["_bytes_bc_ct"],
                                file_name=st.session_state["_file_bc_ct"],
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                key="dl_bc_ct",
                            )
                    with col_pdf:
                        nut_xuat_pdf(
                            df=export_df,
                            tieu_de=f"Báo cáo — {loai_ct[2:].strip()}",
                            username=username or "unknown",
                            cols_tien=[c for c in [COT_DU_NO_TH, COT_DU_NO_QH, COT_TONG_DU_NO]
                                       if c in export_df.columns],
                            prefix_file="BC_CT",
                            key="pdf_bc_ct",
                        )
