"""
Không gian Điều hành (Management View)
───────────────────────────────────────
Dành cho Lãnh đạo phòng KH-NV — Giám sát NQH theo địa bàn,
quản lý chỉ tiêu, cân đối nguồn vốn.
"""
import os
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from config import (
    COT_TEN_PGD, COT_MA_KH, COT_SO_KU, COT_TEN_KH,
    COT_DU_NO_QH, COT_TONG_DU_NO, COT_DU_NO_TH, COT_TEN_CT,
    COT_NGAY_DH, COT_TINH_TRANG, COT_SDT,
    COT_LAI_TON, COT_LAI_THANG, COT_DVUT, COT_MUC_VAY,
    COT_NGAY_VAY, COT_THOI_HAN, COT_LAI_SUAT,
    TEMPLATES_DIR, TAG_MAP,
)
from auth import is_cn_role, is_pgd_role, get_permissions, normalize_role, la_phan_he_cn
from data import (
    danh_dau_khong_hd, danh_dau_khong_hd_cached,
    tong_hop_khong_hd, tong_hop_khong_hd_cached,
    ds_chi_tiet_khong_hd, canh_bao_migration, canh_bao_migration_cached,
)
from utils import (
    fmt,
    fmt_so,
    fmt_ty,
    vn,
    xuat_excel,
    quet_templates,
    auto_fill_klgb,
    auto_fill_document,
    hien_thi_dataframe_phan_trang,
)
from services.excel_service import xuat_excel_chuyen_nghiep, ten_file_xuat as excel_ten_file
from pdf_service import render_huong_dan
from components.delta_card import delta_card, kpi_row
from components.loan_drawer import loan_detail_drawer
from components.filter_bar import filter_bar, apply_filters
from components.export_pdf import download_pdf_button, xuat_pdf_co_chart

from tabs import (
    tab_tongquan, tab_baocao,
    tab_candoi, tab_cbtd, tab_khtd, tab_kehoach,
    tab_nhiem_vu, tab_khtd_giao_dc, tab_kiem_soat,
    tab_ban_dai_dien, tab_uy_thac,
    tab_tien_do, tab_tien_do_nop,
)
from tabs import tab_checklist_bc
from tabs import tab_xlrr_tong_hop
from tabs import tab_upload_khnv
from tabs import tab_audit_log
from tabs import tab_trang_thai_nguon
from tabs import tab_so_sanh_ky
from tabs import tab_hhi
from tabs import tab_no_khoanh


def _render_canh_bao(df: pd.DataFrame, ds_pgd_all: list):
    """
    Tab Cảnh báo sớm — Migration & 3 tháng không hoạt động.
    Hiển thị bảng Top đơn vị cần chấn chỉnh + xuất KL giao ban.
    """
    from tabs.tab_den_han import render as render_den_han

    st.subheader("🚨 Cảnh báo sớm — Phân loại nợ & 3 tháng không HĐ")

    if df is None or df.empty:
        st.warning("Chưa có dữ liệu HSTD."); return

    # Đánh dấu 3 tháng không hoạt động
    df_kh = danh_dau_khong_hd_cached(df)

    # ── KPI nhanh ──────────────────────────────────────────────────────────
    tong_mon    = len(df_kh)
    khd_tong    = int(df_kh["is_3m_inactive"].sum()) if "is_3m_inactive" in df_kh.columns else 0
    df_amber    = canh_bao_migration_cached(df_kh)
    amber_tong  = len(df_amber)
    tl_khd      = khd_tong / tong_mon * 100 if tong_mon > 0 else 0

    kpi_row([
        {"label": "Tổng món vay", "value": tong_mon, "icon": "📊", "suffix": "", "precision": 0,
         "help": "Tổng số món vay toàn chi nhánh"},
        {"label": "3 tháng KHĐ", "value": khd_tong, "icon": "🔴", "suffix": "", "precision": 0,
         "delta": tl_khd, "delta_label": "% tổng món", "delta_color": "inverse" if tl_khd > 2 else "off",
         "help": "Số món 3 tháng không hoạt động"},
        {"label": "Sắp chuyển KHĐ", "value": amber_tong, "icon": "⚠️", "suffix": "", "precision": 0,
         "delta_color": "off", "help": "Lãi tồn 2-3 tháng, cần đôn đốc ngay"},
        {"label": "Lãi tồn KHĐ", "value": tong_lai_khd, "icon": "💰", "suffix": "đồng", "precision": 0,
          "help": "Tổng lãi tồn các món 3 tháng KHĐ"},
     ], num_columns=4)

    st.divider()

    # ── Bảng Top đơn vị cần chấn chỉnh ───────────────────────────────────
    st.markdown("**📋 Tổng hợp theo PGD**")
    nhom_pgd = tong_hop_khong_hd_cached(df_kh, nhom_theo=COT_TEN_PGD)
    if not nhom_pgd.empty:
        hien_thi_dataframe_phan_trang(
            nhom_pgd,
            key="mgmt_khd_nhom_pgd",
            height=300,
        )

    st.markdown("**📋 Tổng hợp theo Hội đoàn thể (ĐVUT)**")
    nhom_dvut = tong_hop_khong_hd_cached(df_kh, nhom_theo="Tên ĐVUT")
    if not nhom_dvut.empty:
        hien_thi_dataframe_phan_trang(
            nhom_dvut,
            key="mgmt_khd_nhom_dvut",
            height=220,
        )

    st.divider()

    # ── Vùng Amber — cảnh báo sớm migration ──────────────────────────────
    st.markdown("**⚠️ Danh sách sắp chuyển 03 tháng không hoạt động — Đang tồn lãi 2–3 tháng (cần đôn đốc ngay)**")
    if not df_amber.empty:
        col_amber_loc, col_amber_xuat = st.columns([2, 1])
        with col_amber_loc:
            loc_pgd_a = st.selectbox(
                "Lọc PGD", ["Tất cả"] + ds_pgd_all, key="cb_amber_pgd")
        with col_amber_xuat:
            st.markdown("<br>", unsafe_allow_html=True)
            df_amber_loc = df_amber if loc_pgd_a == "Tất cả" \
                           else df_amber[df_amber[COT_TEN_PGD] == loc_pgd_a]
            buf_a = xuat_excel({"SapChuyen3mKHD": df_amber_loc})
            st.download_button(
                f"⬇️ Xuất Excel Amber ({len(df_amber_loc)} món)",
                data=buf_a,
                file_name=f"SapChuyen3mKHD_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="cb_xuat_amber",
            )
        cols_hien = [c for c in [
            COT_TEN_PGD, "Tên xã", COT_DVUT, COT_TEN_KH,
            COT_SO_KU, COT_TEN_CT, COT_LAI_TON, COT_LAI_THANG,
            "so_thang_ton_uoc", "muc_canh_bao",
        ] if c in df_amber_loc.columns]
        hien_thi_dataframe_phan_trang(
            df_amber_loc[cols_hien],
            key="mgmt_amber_ds",
            height=320,
        )
    else:
        st.success("✅ Không có món vay nào sắp chuyển 03 tháng không hoạt động.")

    st.divider()

    # ── Xuất KL giao ban tự động ──────────────────────────────────────────
    st.markdown("**📄 Xuất Thông báo KL Giao ban (Bảng II tự động điền)**")
    templates = quet_templates(TEMPLATES_DIR)
    mau_klgb  = [(t, p) for t, p in templates
                 if "giao" in t.lower() or "kl" in t.lower() or "thong bao" in t.lower()]

    if not mau_klgb:
        st.info("⚠️ Chưa có mẫu KL giao ban trong thư mục `templates/`. "
                "Đặt file `.docx` vào thư mục đó và reload.")
    else:
        col_pgd_kl, col_mau_kl = st.columns(2)
        with col_pgd_kl:
            pgd_kl = st.selectbox("Chọn PGD", ["Toàn CN"] + ds_pgd_all, key="kl_pgd")
        with col_mau_kl:
            ten_mau_kl = st.selectbox(
                "Mẫu biểu", [t[0] for t in mau_klgb], key="kl_mau")

        if st.button("🖨️ Tạo KL giao ban", type="primary", key="kl_btn"):
            try:
                df_kl = df_kh if pgd_kl == "Toàn CN" \
                        else df_kh[df_kh[COT_TEN_PGD] == pgd_kl]
                idx_mau = [t[0] for t in mau_klgb].index(ten_mau_kl)
                path_mau = mau_klgb[idx_mau][1]
                ten_pgd_str = "" if pgd_kl == "Toàn CN" else pgd_kl
                data = auto_fill_klgb(df_kl, str(path_mau), ten_pgd_str)
                fname = f"KL_GiaoBan_{pgd_kl}_{datetime.now().strftime('%d%m%Y')}.docx"
                st.session_state["_bytes_kl"] = data
                st.session_state["_file_kl"] = fname
                st.success("✅ Đã tạo xong — nhấn nút bên dưới để tải về.")
            except Exception as e:
                st.error(f"Lỗi tạo KL giao ban: {e}")

        if st.session_state.get("_bytes_kl"):
            st.download_button(
                f"⬇️ Tải KL giao ban — {st.session_state['_file_kl']}",
                data=st.session_state["_bytes_kl"],
                file_name=st.session_state["_file_kl"],
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                key="kl_dl",
            )


def _render_canh_bao_no(df_full: pd.DataFrame, ds_pgd_all: list, role: str, username: str):
    """Cảnh báo nợ — 5 sub-tab: Đến hạn, 3 tháng KHĐ, Migration, Nợ QH phát sinh, Cảnh báo sớm."""
    from tabs.tab_den_han import render as render_den_han
    from tabs import tab_canh_bao_som

    sub1, sub2, sub3, sub4, sub5 = st.tabs([
        "⏰ Đến hạn",
        "🔴 3 tháng KHĐ",
        "🚨 Migration (đủ chuẩn → NQH)",
        "📋 Nợ QH phát sinh",
        "⚡ Cảnh báo sớm",
    ])

    with sub1:
        render_den_han(role=role)

    if df_full is None or df_full.empty:
        for tab in [sub2, sub3, sub4, sub5]:
            with tab:
                st.warning("Chưa có dữ liệu HSTD.")
        return

    df_kh = danh_dau_khong_hd_cached(df_full)

    with sub2:
        _hien_thi_khd_tab(df_kh, ds_pgd_all)

    with sub3:
        _hien_thi_migration_tab(df_kh, ds_pgd_all)

    with sub4:
        _hien_thi_nqh_tab(df_kh, username)

    with sub5:
        tab_canh_bao_som._render_canh_bao(
            df_kh, ds_pgd_all, key_prefix="cn_", la_cn=True
        )


def _hien_thi_khd_tab(df_kh: pd.DataFrame, ds_pgd_all: list):
    """Sub-tab: 3 tháng không hoạt động."""
    khd_tong = int(df_kh["is_3m_inactive"].sum()) if "is_3m_inactive" in df_kh.columns else 0
    tong_mon = len(df_kh)
    tl_khd = khd_tong / tong_mon * 100 if tong_mon > 0 else 0

    k1, k2, k3 = st.columns(3)
    k1.metric("Tổng món vay", fmt_so(tong_mon))
    k2.metric("3 tháng không HĐ 🔴", fmt_so(khd_tong),
              delta=f"{tl_khd:.1f}%", delta_color="inverse" if tl_khd > 2 else "off")
    tong_lai = df_kh[df_kh.get("is_3m_inactive", False)][COT_LAI_TON].sum() \
               if COT_LAI_TON in df_kh.columns else 0
    k3.metric("Lãi tồn (triệu đồng)", vn(tong_lai / 1e6, 0))

    st.markdown("**📋 Tổng hợp theo PGD**")
    nhom_pgd = tong_hop_khong_hd_cached(df_kh, nhom_theo=COT_TEN_PGD)
    if not nhom_pgd.empty:
        hien_thi_dataframe_phan_trang(nhom_pgd, key="khd_pgd", height=280)

    st.markdown("**📋 Tổng hợp theo Hội đoàn thể**")
    nhom_dvut = tong_hop_khong_hd_cached(df_kh, nhom_theo="Tên ĐVUT")
    if not nhom_dvut.empty:
        hien_thi_dataframe_phan_trang(nhom_dvut, key="khd_dvut", height=220)

    ds_chi = ds_chi_tiet_khong_hd(df_kh)
    if not ds_chi.empty:
        col_loc, col_xuat = st.columns([2, 1])
        with col_loc:
            loc_pgd = st.selectbox("Lọc PGD", ["Tất cả"] + ds_pgd_all, key="khd_loc_pgd")
        df_chi_loc = ds_chi if loc_pgd == "Tất cả" else ds_chi[ds_chi[COT_TEN_PGD] == loc_pgd]
        with col_xuat:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button(f"📥 Tạo Excel ({len(df_chi_loc)} món)", key="khd_xuat_btn"):
                st.session_state["_khd_xuat_buf"] = xuat_excel({"3mKHD": df_chi_loc})
            if st.session_state.get("_khd_xuat_buf"):
                st.download_button(
                    "⬇️ Tải về Excel", data=st.session_state["_khd_xuat_buf"],
                    file_name=f"3mKHD_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="khd_xuat",
                )
        hien_thi_dataframe_phan_trang(df_chi_loc, key="khd_chi", height=320)


def _hien_thi_migration_tab(df_kh: pd.DataFrame, ds_pgd_all: list):
    """Sub-tab: Migration — món vay đủ chuẩn có nguy cơ chuyển NQH."""
    df_amber = canh_bao_migration_cached(df_kh)
    amber_tong = len(df_amber)

    if amber_tong == 0:
        st.success("✅ Không có món vay nào có dấu hiệu rủi ro chuyển NQH.")
        return

    k1, k2 = st.columns(2)
    k1.metric("⚠️ Số món cần theo dõi", fmt_so(amber_tong))
    tong_lai = df_amber[COT_LAI_TON].sum() if COT_LAI_TON in df_amber.columns else 0
    k2.metric("Tổng lãi tồn (triệu đồng)", vn(tong_lai/1e6, 0))

    col_loc, col_xuat = st.columns([2, 1])
    with col_loc:
        loc_pgd = st.selectbox("Lọc PGD", ["Tất cả"] + ds_pgd_all, key="mg_loc_pgd")
    df_loc = df_amber if loc_pgd == "Tất cả" else df_amber[df_amber[COT_TEN_PGD] == loc_pgd]
    with col_xuat:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button(f"📥 Tạo Excel ({len(df_loc)} món)", key="mg_xuat_btn"):
            st.session_state["_mg_xuat_buf"] = xuat_excel({"Migration": df_loc})
        if st.session_state.get("_mg_xuat_buf"):
            st.download_button(
                "⬇️ Tải về Excel", data=st.session_state["_mg_xuat_buf"],
                file_name=f"Migration_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="mg_xuat",
            )
    cols_hien = [c for c in [
        COT_TEN_PGD, "Tên xã", COT_DVUT, COT_TEN_KH, COT_SO_KU,
        COT_TEN_CT, COT_LAI_TON, COT_LAI_THANG, "so_thang_ton_uoc", "muc_canh_bao",
    ] if c in df_loc.columns]
    hien_thi_dataframe_phan_trang(df_loc[cols_hien], key="mg_chi", height=360)


def _tim_cot(df: pd.DataFrame, *cac_ten: str) -> str | None:
    """Tim cot trong DataFrame voi fuzzy matching (Unicode NFC/NFD)."""
    if not cac_ten:
        return None
    for ten in cac_ten:
        if ten in df.columns:
            return ten
    ten_dau = cac_ten[0]
    import unicodedata
    for c in df.columns:
        if unicodedata.normalize("NFC", c) == unicodedata.normalize("NFC", ten_dau):
            return c
        if ten_dau.lower() in c.lower() or c.lower() in ten_dau.lower():
            return c
    return cac_ten[0] if cac_ten[0] in df.columns else None


def _hien_thi_nqh_tab(df_kh: pd.DataFrame, username: str):
    """Sub-tab: No qua han phat sinh - pre-filter NQH, bo loc thoi gian bang Ngay so lieu."""

    cot_nqh = _tim_cot(df_kh, "D\u01b0 n\u1ee3 qu\u00e1 h\u1ea1n", "N\u1ee3 qu\u00e1 h\u1ea1n")
    cot_ngay_sl = _tim_cot(df_kh, "Ng\u00e0y s\u1ed1 li\u1ec7u")

    if cot_nqh and cot_nqh in df_kh.columns:
        mask_nqh = pd.to_numeric(df_kh[cot_nqh], errors="coerce").fillna(0) > 0
        df_nqh_all = df_kh[mask_nqh].copy()
    else:
        st.warning("Khong tim thay cot du no qua han trong du lieu.")
        df_nqh_all = pd.DataFrame()

    if df_nqh_all.empty:
        st.success("Khong co no qua han phat sinh.")
        return

    # Kiem tra CQH columns co gia tri > 0 khong
    cot_cqh_thang = _tim_cot(df_nqh_all, "Chuy\u1ec3n QH trong th\u00e1ng", "Chuy\u1ec3n n\u1ee3 QH trong th\u00e1ng")
    co_cqh = False
    if cot_cqh_thang and cot_cqh_thang in df_nqh_all.columns:
        if pd.to_numeric(df_nqh_all[cot_cqh_thang], errors="coerce").fillna(0).sum() > 0:
            co_cqh = True

    # Xay dung tuy chon loc
    lua_chon = {}
    if co_cqh:
        lua_chon["Trong thang"] = ("cqh", cot_cqh_thang)
    if cot_ngay_sl and cot_ngay_sl in df_nqh_all.columns:
        lua_chon["Ky hien tai"] = ("date", cot_ngay_sl)
    lua_chon["Toan thoi gian"] = ("all", None)

    ds_lua_chon = list(lua_chon.keys())
    mac_dinh = 0 if co_cqh else (ds_lua_chon.index("Toan thoi gian") if "Toan thoi gian" in ds_lua_chon else 0)

    chon = st.radio(
        "Loc theo thoi gian",
        ds_lua_chon,
        index=mac_dinh,
        horizontal=True,
        key="nqh_loc_tg",
    )
    loai_loc, cot_loc = lua_chon[chon]

    # Ap dung loc
    df_nqh = df_nqh_all.copy()
    if loai_loc == "cqh" and cot_loc and cot_loc in df_nqh.columns:
        mask_cqh = pd.to_numeric(df_nqh[cot_loc], errors="coerce").fillna(0) > 0
        df_nqh = df_nqh[mask_cqh]
    elif loai_loc == "date" and cot_ngay_sl and cot_ngay_sl in df_nqh.columns:
        ngay_sl = pd.to_datetime(df_nqh[cot_ngay_sl], errors="coerce")
        from dateutil.relativedelta import relativedelta
        moc = ngay_sl.max()
        if pd.notna(moc):
            dau_ky = moc - relativedelta(months=1)
            df_nqh = df_nqh[ngay_sl >= dau_ky]

    if df_nqh.empty:
        st.info("Khong co ho so NQH trong ky da chon. Chon 'Toan thoi gian' de xem tat ca.")
        return

    # Metrics
    tong_nqh = df_nqh[cot_nqh].sum() if cot_nqh and cot_nqh in df_nqh.columns else 0
    cot_tong_dn = _tim_cot(df_nqh, "T\u1ed5ng d\u01b0 n\u1ee3")
    tong_dn = df_nqh[cot_tong_dn].sum() if cot_tong_dn and cot_tong_dn in df_nqh.columns else 0
    cot_so_ku = _tim_cot(df_nqh, "S\u1ed1 kh\u1ebf \u01b0\u1edbc")

    k1, k2, k3 = st.columns(3)
    k1.metric("So ho so NQH", fmt_so(len(df_nqh)))
    k2.metric("Du no QH", fmt_ty(tong_nqh) if tong_nqh else "0")
    k3.metric("Ty le NQH", f"{tong_nqh / tong_dn * 100:.2f}%" if tong_dn else "0%")

    # Tong hop theo PGD
    cot_pgd = _tim_cot(df_nqh, "T\u00ean PGD")
    if cot_pgd and cot_pgd in df_nqh.columns:
        agg_cols = {}
        if cot_so_ku:
            agg_cols["So_ho_so_NQH"] = (cot_so_ku, "nunique")
        if cot_nqh and cot_nqh in df_nqh.columns:
            agg_cols["Tong_du_no_QH"] = (cot_nqh, "sum")
        if cot_tong_dn:
            agg_cols["Tong_du_no"] = (cot_tong_dn, "sum")
        if agg_cols:
            nqh_pgd = df_nqh.groupby(cot_pgd, dropna=False).agg(**agg_cols).reset_index()
            if "Tong_du_no" in nqh_pgd.columns:
                tdn_nqh = nqh_pgd["Tong_du_no"].replace(0, pd.NA)
                nqh_pgd["Ty_le_QH_pct"] = (nqh_pgd["Tong_du_no_QH"] / tdn_nqh * 100).round(1).fillna(0)
            st.markdown("**Tong hop theo PGD**")
            hien_thi_dataframe_phan_trang(nqh_pgd, key="nqh_pgd", height=280)

    # Chi tiet
    cols_mong_muon = [
        cot_pgd, "T\u00ean KH", cot_so_ku, "T\u00ean ch\u01b0\u01a1ng tr\u00ecnh",
        cot_nqh, cot_tong_dn,
        "Ng\u00e0y \u0110H theo h\u1ee3p \u0111\u1ed3ng", "Ng\u00e0y \u0110H theo Gia h\u1ea1n", "Ng\u00e0y \u0110H theo GDXA",
    ]
    cols_chi = [c for c in cols_mong_muon if c and c in df_nqh.columns]
    df_nqh_chi = df_nqh[cols_chi].reset_index(drop=True)

    st.markdown("**Danh sách chi tiết**")
    col1, col2 = st.columns([1, 1])
    with col1:
        st.download_button(
            label="⬇️ Xuất Excel (chuyên nghiệp)",
            type="primary",
            data=xuat_excel_chuyen_nghiep(
                df=df_nqh_chi,
                title="Danh sách Nợ quá hạn - QDD62",
                subtitle="Phân hệ Chi nhánh",
                nguoi_xuat=st.session_state.get("txt_username", ""),
                kpi_items=[
                    ("Số hồ sơ", fmt_so(len(df_nqh_chi)), ""),
                    ("PGD liên quan", fmt_so(df_nqh_chi[COT_TEN_PGD].nunique()), "") if COT_TEN_PGD in df_nqh_chi.columns else ("", "", ""),
                ],
            ),
            file_name=excel_ten_file("DS_NQH_QDD62"),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="nqh_xuat_pro",
        )
    with col2:
        buf = xuat_excel({"NQH": df_nqh_chi})
        st.download_button(
            f"⬇️ Excel cơ bản ({len(df_nqh_chi)} hồ sơ)", data=buf,
            file_name=f"DS_NQH_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="nqh_xuat",
        )
    hien_thi_dataframe_phan_trang(df_nqh_chi, key="nqh_chi", height=360)

def _render_dgd_to_tkvv(tab_parent=None, **kw):
    """Sub-tab Điểm GD & Tổ TK&VV — nested tabs."""
    from tabs import tab_quan_ly_dgd
    from tabs import tab_cdtotkvv

    if tab_parent is not None:
        ctx = tab_parent
    else:
        ctx = st.container()
    with ctx:
        _sub1, _sub2 = st.tabs(["📍 Điểm Giao Dịch", "🏘️ Tổ TK&VV"])
        tab_quan_ly_dgd.render(_sub1, **kw)
        tab_cdtotkvv.render(_sub2, **dict(kw, cdto_mode="cn"))


def _render_ndt_dp(role: str, username: str) -> None:
    """Tab quản lý Mã Nhà đầu tư Địa phương — dùng phân tầng GQVL ĐP."""
    from db import doc_ndt_dp_list, ghi_kv, ghi_audit

    st.subheader("🏦 Mã Nhà đầu tư Địa phương")
    st.info(
        "ℹ️ Mã NĐT lấy chính xác từ cột **'Mã nhà đầu tư'** trong file sao kê GQVL — "
        "món vay khớp với danh sách **Cấp Tỉnh** → xếp vào GQVL ĐP Cấp tỉnh, còn lại → Cấp xã/khác. "
        "Chỉ **Admin CN** mới có thể thêm / sửa / xóa."
    )

    with st.expander("📖 Hướng dẫn sử dụng", expanded=False):
        st.markdown("""
### Mục đích

Hệ thống phân loại mỗi món vay **Nguồn vốn ĐP (Địa phương)** thành 2 tầng:

| Tầng | Điều kiện | Ví dụ |
|---|---|---|
| **GQVL ĐP — Cấp tỉnh** | Mã NĐT của món vay **có trong danh sách Cấp Tỉnh** | UBND tỉnh Đồng Nai |
| **GQVL ĐP — Cấp xã/khác** | Mã NĐT **không có** trong danh sách | Vốn huyện, xã, tổ chức khác |

Danh sách này ảnh hưởng trực tiếp đến báo cáo **phân tầng GQVL** và tab **Phân tích** bên dưới.

---

### Các tab chức năng

**🏛️ Cấp Tỉnh** — Xem danh sách mã đang được xếp vào nhóm Cấp tỉnh.

**🏘️ Cấp Xã/Khác** — Xem danh sách mã đang được xếp vào nhóm Cấp xã/khác.

**➕ Thêm mới** *(chỉ Admin CN)*
1. Mở file sao kê GQVL → tìm cột **"Mã nhà đầu tư"**
2. Copy chính xác mã (dạng `INV` + dãy số, ví dụ `INV0802140002662`)
3. Dán vào ô **Mã NĐT đầy đủ**, điền ghi chú, chọn **Phân loại cấp** rồi nhấn **➕ Thêm**

**✏️ Chỉnh sửa / Xóa** *(chỉ Admin CN)*
- Sửa ghi chú hoặc đổi phân loại cấp → nhấn 💾 để lưu từng dòng
- Nhấn 🗑️ để xóa (không thể xóa khi chỉ còn 1 mã)

**📊 Phân tích**
- Hiển thị ngay tác động lên dữ liệu GQVL đang có trong cache:
  3 metric tổng quan + bảng chi tiết từng mã (số món, dư nợ trong hạn, dư nợ quá hạn)

---

### Sau khi thêm / sửa / xóa mã

> ⚠️ Thay đổi danh sách **chưa tự động cập nhật** dữ liệu phân tầng cũ.
> Để áp dụng: upload lại file GQVL **hoặc** nhấn **🔄 Làm mới** để tải lại cache,
> sau đó vào tab **📊 Phân tích** kiểm tra kết quả.

---

### Ai được làm gì?

| Thao tác | Admin CN | Manager CN | Xem |
|---|:---:|:---:|:---:|
| Xem danh sách & phân tích | ✅ | ✅ | ✅ |
| Thêm / Sửa / Xóa mã | ✅ | — | — |
| Xuất Excel | ✅ | ✅ | ✅ |
        """)

    ds       = doc_ndt_dp_list()   # list[dict] {"ma", "ghi_chu", "cap"}
    can_edit = normalize_role(str(role or "user")) == "admin_cn"

    ds_tinh = [x for x in ds if x.get("cap", "tinh") == "tinh"]
    ds_xa   = [x for x in ds if x.get("cap", "tinh") == "xa"]

    _CAP_OPTS = ["Cấp Tỉnh 🏛️", "Cấp Xã/Khác 🏘️"]
    _CAP_TO   = {"Cấp Tỉnh 🏛️": "tinh", "Cấp Xã/Khác 🏘️": "xa"}
    _CAP_FROM = {"tinh": "Cấp Tỉnh 🏛️", "xa": "Cấp Xã/Khác 🏘️"}

    _t1, _t2, _t3, _t4, _t5 = st.tabs([
        "🏛️ Cấp Tỉnh",
        "🏘️ Cấp Xã/Khác",
        "➕ Thêm mới",
        "✏️ Chỉnh sửa / Xóa",
        "📊 Phân tích",
    ])

    # ── Tab 1: Cấp Tỉnh (đọc) ────────────────────────────────────────────────
    with _t1:
        if ds_tinh:
            for item in ds_tinh:
                c1, c2 = st.columns([3, 5])
                c1.code(item["ma"])
                c2.markdown(item.get("ghi_chu", ""))
        else:
            st.info("Chưa có mã nào ở cấp Tỉnh.")

    # ── Tab 2: Cấp Xã/Khác (đọc) ─────────────────────────────────────────────
    with _t2:
        if ds_xa:
            for item in ds_xa:
                c1, c2 = st.columns([3, 5])
                c1.code(item["ma"])
                c2.markdown(item.get("ghi_chu", ""))
        else:
            st.info("Chưa có mã nào được đăng ký ở cấp Xã/Khác.")

    # ── Tab 3: Thêm mới ───────────────────────────────────────────────────────
    with _t3:
        if not can_edit:
            st.warning("⚠️ Chỉ Admin CN mới có thể thêm mã.")
        else:
            with st.form("form_them_ndt", clear_on_submit=True):
                ma_them = st.text_input(
                    "Mã NĐT đầy đủ",
                    placeholder="VD: INV0802140002662",
                    help="Lấy chính xác từ cột 'Mã nhà đầu tư' trong file GQVL",
                    key="ndt_ma_them",
                )
                ghi_chu_them = st.text_input(
                    "Ghi chú",
                    placeholder="VD: UBND tỉnh Đồng Nai",
                    key="ndt_gc_them",
                )
                cap_them = st.selectbox(
                    "Phân loại cấp",
                    _CAP_OPTS,
                    help="Cấp Tỉnh: vốn UBND tỉnh/ủy thác đầu tư cấp tỉnh. Cấp Xã/Khác: vốn cấp huyện/xã.",
                    key="ndt_cap_them",
                )
                submitted_them = st.form_submit_button("➕ Thêm", type="primary")

            if submitted_them:
                ma_them = ma_them.strip()
                if not ma_them:
                    st.error("Vui lòng nhập mã NĐT.")
                elif any(x["ma"] == ma_them for x in ds):
                    st.warning(f"Mã **{ma_them}** đã có trong danh sách.")
                else:
                    cap_val = _CAP_TO[cap_them]
                    ds_moi  = ds + [{"ma": ma_them, "ghi_chu": ghi_chu_them.strip(), "cap": cap_val}]
                    ghi_kv("ndt_dp_list", ds_moi, username)
                    ghi_audit(username, "them_ndt_dp",
                              f"Thêm mã {ma_them} — {ghi_chu_them} ({cap_them})")
                    st.success(f"✅ Đã thêm mã **{ma_them}** vào {cap_them}")
                    st.rerun()

    # ── Tab 4: Chỉnh sửa / Xóa ───────────────────────────────────────────────
    with _t4:
        if not can_edit:
            st.warning("⚠️ Chỉ Admin CN mới có thể chỉnh sửa / xóa mã.")
        elif not ds:
            st.info("Chưa có mã nào.")
        else:
            st.caption("Chỉnh sửa ghi chú hoặc đổi phân loại cấp, nhấn 💾 để lưu từng dòng.")
            for i, item in enumerate(ds):
                c1, c2, c3, c4, c5 = st.columns([3, 3, 2, 1, 1])
                c1.code(item["ma"])
                gc_edit = c2.text_input(
                    "Ghi chú",
                    value=item.get("ghi_chu", "") or "",
                    key=f"ndt_gc_{i}",
                    label_visibility="collapsed",
                )
                cap_current = _CAP_FROM.get(item.get("cap", "tinh"), _CAP_OPTS[0])
                cap_edit = c3.selectbox(
                    "Cấp",
                    _CAP_OPTS,
                    index=_CAP_OPTS.index(cap_current),
                    key=f"ndt_cap_{i}",
                    label_visibility="collapsed",
                )
                if c4.button("💾", key=f"luu_ndt_{i}", help="Lưu thay đổi"):
                    ds_moi = [dict(x) for x in ds]
                    ds_moi[i]["ghi_chu"] = (gc_edit or "").strip()
                    ds_moi[i]["cap"]     = _CAP_TO[cap_edit]
                    ghi_kv("ndt_dp_list", ds_moi, username)
                    ghi_audit(username, "sua_ndt_dp",
                              f"Sửa mã {item['ma']} → ghi chú: {gc_edit}, cấp: {cap_edit}")
                    st.rerun()
                if c5.button("🗑️", key=f"xoa_ndt_{i}",
                             disabled=(len(ds) <= 1),
                             help="Không thể xóa khi chỉ còn 1 mã"):
                    ds_moi = [x for j, x in enumerate(ds) if j != i]
                    ghi_kv("ndt_dp_list", ds_moi, username)
                    ghi_audit(username, "xoa_ndt_dp", f"Xóa mã {item['ma']}")
                    st.rerun()

    # ── Tab 5: Phân tích ─────────────────────────────────────────────────────
    with _t5:
        try:
            from pathlib import Path
            from config import CACHE_DIR, COT_MA_NDT

            gqvl_path = Path(CACHE_DIR) / "gqvl.parquet"
            if not gqvl_path.exists():
                st.info("Chưa có dữ liệu GQVL. Upload file để xem phân tích.")
            else:
                df_gqvl = pd.read_parquet(gqvl_path)
                if ("Nguồn vốn" not in df_gqvl.columns) or (COT_MA_NDT not in df_gqvl.columns):
                    st.warning("File GQVL không có đủ cột để phân tích.")
                elif df_gqvl["Nguồn vốn"].isna().all():
                    st.warning(
                        "⚠️ Cột 'Nguồn vốn' trong cache GQVL toàn NaN — "
                        "dữ liệu cũ bị lỗi định dạng. Vui lòng upload lại file GQVL."
                    )
                else:
                    df_dp         = df_gqvl[df_gqvl["Nguồn vốn"] == "ĐP"].copy()
                    ma_ndt_str    = df_dp[COT_MA_NDT].astype(str).str.strip()
                    ndt_tinh_list = [x["ma"] for x in ds_tinh]
                    mask_tinh     = ma_ndt_str.isin(ndt_tinh_list)
                    ghi_chu_map   = {x["ma"]: x.get("ghi_chu", "") for x in ds}

                    p1, p2, p3 = st.columns(3)
                    p1.metric("Tổng món ĐP",       fmt_so(len(df_dp)))
                    p2.metric("→ Cấp tỉnh 🏛️",    fmt_so(int(mask_tinh.sum())))
                    p3.metric("→ Cấp xã/khác 🏘️", fmt_so(int((~mask_tinh).sum())))

                    st.divider()
                    agg_kw: dict = {"Số món": ("Nhóm", "count")}
                    if "Dư nợ trong hạn" in df_dp.columns:
                        agg_kw["Dư nợ TH (tỷ)"] = ("Dư nợ trong hạn", "sum")
                    if "Dư nợ quá hạn" in df_dp.columns:
                        agg_kw["Dư nợ QH (tỷ)"] = ("Dư nợ quá hạn", "sum")
                    df_pv = (
                        df_dp
                        .assign(Nhóm=ma_ndt_str.where(mask_tinh, "— Cấp xã/khác"))
                        .groupby("Nhóm")
                        .agg(**agg_kw)
                        .reset_index()
                    )
                    for col in ("Dư nợ TH (tỷ)", "Dư nợ QH (tỷ)"):
                        if col in df_pv.columns:
                            df_pv[col] = df_pv[col].apply(fmt_ty)
                    df_pv["Ghi chú"] = df_pv["Nhóm"].map(lambda m: ghi_chu_map.get(m, ""))
                    st.dataframe(df_pv, hide_index=True, width='stretch')
        except Exception as e:
            st.warning(f"Không thể phân tích tác động GQVL: {e}")

    # ── Xuất Excel + Làm mới ─────────────────────────────────────────────────
    col_xl, col_rf = st.columns([3, 1])
    with col_xl:
        if st.button("📥 Xuất danh sách Excel", key="export_ndt_dp"):
            import io
            df_export = pd.DataFrame([
                {"Mã NĐT": x["ma"],
                 "Ghi chú": x.get("ghi_chu", ""),
                 "Phân loại cấp": _CAP_FROM.get(x.get("cap", "tinh"), "Cấp Tỉnh 🏛️")}
                for x in ds
            ])
            buf = io.BytesIO()
            df_export.to_excel(buf, index=False)
            st.download_button(
                "💾 Tải về",
                data=buf.getvalue(),
                file_name="danh_sach_ndt_dp.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="dl_ndt_dp",
            )
    with col_rf:
        if st.button("🔄 Làm mới", key="btn_refresh_ndt_dp", width='stretch',
                     help="Xóa cache và tải lại dữ liệu GQVL"):
            st.cache_data.clear()
            st.rerun()


def _render_quan_ly_template(df: pd.DataFrame):
    """
    Sub-tab Quản lý Template — Upload, xem, xóa file .docx và test mẫu.
    Chỉ dành cho role admin/manager.
    """
    st.subheader("📁 Quản lý Template Word")
    st.caption("Upload, quản lý và test các mẫu biểu .docx cho báo cáo tự động")

    # Tạo thư mục templates nếu chưa có
    templates_path = Path(TEMPLATES_DIR)
    templates_path.mkdir(exist_ok=True)

    tab_upload, tab_danh_sach, tab_test = st.tabs([
        "📤 Upload mẫu mới", "📋 Danh sách Template", "🧪 Test Template"
    ])

    # ══════════════════════════════════════════════════════════════════════════════
    # TAB 1: UPLOAD MẪU MỚI
    # ══════════════════════════════════════════════════════════════════════════════
    with tab_upload:
        st.markdown("**📤 Upload file template Word (.docx)**")
        
        uploaded_file = st.file_uploader(
            "Chọn file .docx",
            type=['docx'],
            help="Chỉ chấp nhận file .docx. Tên file nên mô tả rõ ràng mục đích sử dụng.",
            key="template_uploader"
        )
        
        if uploaded_file is not None:
            col1, col2 = st.columns([3, 1])
            
            with col1:
                # Hiển thị thông tin file
                st.info(f"📄 **{uploaded_file.name}**")
                st.text(f"Kích thước: {fmt_so(len(uploaded_file.getvalue()))} bytes")
                
                # Tùy chọn đổi tên file
                ten_file_moi = st.text_input(
                    "Tên file (để trống = giữ tên gốc)", 
                    value="",
                    help="VD: 'Mau_To_trinh_cho_vay_NOXH' (không cần .docx)",
                    key="template_new_name"
                )
            
            with col2:
                st.markdown("<br><br>", unsafe_allow_html=True)
                if st.button("💾 Lưu Template", type="primary", key="save_template"):
                    try:
                        # Xác định tên file
                        if ten_file_moi.strip():
                            # Loại bỏ .docx nếu user nhập
                            ten_file = ten_file_moi.strip().replace('.docx', '') + '.docx'
                        else:
                            ten_file = uploaded_file.name
                        
                        # Kiểm tra tên file hợp lệ
                        if not ten_file.lower().endswith('.docx'):
                            ten_file += '.docx'
                        
                        # Đường dẫn lưu
                        file_path = templates_path / ten_file
                        
                        # Kiểm tra file đã tồn tại
                        if file_path.exists():
                            st.warning(f"⚠️ File **{ten_file}** đã tồn tại!")
                            ghi_de = st.checkbox("✅ Ghi đè file cũ", key="overwrite_template")
                            if not ghi_de:
                                st.stop()
                        
                        # Lưu file
                        with open(file_path, 'wb') as f:
                            f.write(uploaded_file.getvalue())
                        
                        st.success(f"✅ Đã lưu template: **{ten_file}**")
                        st.balloons()
                        
                        # Reload để hiển thị file mới
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"❌ Lỗi lưu file: {e}")

    # ══════════════════════════════════════════════════════════════════════════════
    # TAB 2: DANH SÁCH TEMPLATE
    # ══════════════════════════════════════════════════════════════════════════════
    with tab_danh_sach:
        st.markdown("**📋 Danh sách Template hiện có**")
        
        # Quét danh sách template
        templates = quet_templates(TEMPLATES_DIR)
        
        if not templates:
            st.info("📭 Chưa có template nào. Hãy upload file .docx ở tab bên trái.")
        else:
            # Tạo DataFrame để hiển thị
            template_data = []
            for ten_hienthi, file_path in templates:
                file_stat = file_path.stat()
                template_data.append({
                    'Tên hiển thị': ten_hienthi,
                    'Tên file': file_path.name,
                    'Kích thước (KB)': f"{file_stat.st_size / 1024:.1f}",
                    'Ngày tạo': datetime.fromtimestamp(file_stat.st_ctime).strftime("%d/%m/%Y %H:%M"),
                    'Ngày sửa': datetime.fromtimestamp(file_stat.st_mtime).strftime("%d/%m/%Y %H:%M"),
                    'Đường dẫn': str(file_path)
                })
            
            df_templates = pd.DataFrame(template_data)
            hien_thi_dataframe_phan_trang(
                df_templates.drop(columns=['Đường dẫn']),
                key="mgmt_template_danh_sach",
            )
            
            st.divider()
            
            # Chức năng xóa template
            st.markdown("**🗑️ Xóa Template**")
            col_chon, col_xoa = st.columns([3, 1])
            
            with col_chon:
                chon_xoa = st.selectbox(
                    "Chọn template để xóa",
                    options=[f"{row['Tên hiển thị']} ({row['Tên file']})" for _, row in df_templates.iterrows()],
                    key="template_delete_select"
                )
            
            with col_xoa:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("🗑️ Xóa", type="secondary", key="delete_template"):
                    # Tìm file tương ứng
                    idx = [f"{row['Tên hiển thị']} ({row['Tên file']})" for _, row in df_templates.iterrows()].index(chon_xoa)
                    file_to_delete = Path(df_templates.iloc[idx]['Đường dẫn'])
                    
                    try:
                        file_to_delete.unlink()  # Xóa file
                        st.success(f"✅ Đã xóa: {file_to_delete.name}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Không thể xóa file: {e}")

    # ══════════════════════════════════════════════════════════════════════════════
    # TAB 3: TEST TEMPLATE
    # ══════════════════════════════════════════════════════════════════════════════
    with tab_test:
        st.markdown("**🧪 Test Template với dữ liệu mẫu**")
        
        if df is None or df.empty:
            st.warning("⚠️ Không có dữ liệu HSTD để test. Hãy upload dữ liệu trước.")
            return
        
        templates = quet_templates(TEMPLATES_DIR)
        if not templates:
            st.info("📭 Không có template để test.")
            return
        
        # Chọn template và hồ sơ
        col_template, col_hoso = st.columns(2)
        
        with col_template:
            chon_template = st.selectbox(
                "Chọn Template",
                options=[t[0] for t in templates],
                key="test_template_select"
            )
        
        with col_hoso:
            # Lấy 10 hồ sơ đầu làm mẫu
            df_sample = df.head(10) if len(df) >= 10 else df
            ds_khach_hang = [
                f"{row.get(COT_MA_KH, 'N/A')} - {row.get(COT_TEN_KH, 'Không tên')[:20]}"
                for _, row in df_sample.iterrows()
            ]
            
            chon_hoso = st.selectbox(
                "Chọn hồ sơ test",
                options=ds_khach_hang,
                key="test_hoso_select"
            )
        
        # Hiển thị thông tin hồ sơ được chọn
        idx_hoso = ds_khach_hang.index(chon_hoso)
        row_test = df_sample.iloc[idx_hoso]
        
        with st.expander("📄 Thông tin hồ sơ test", expanded=True):
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Mã KH:** {row_test.get(COT_MA_KH, 'N/A')}")
                st.write(f"**Tên KH:** {row_test.get(COT_TEN_KH, 'N/A')}")
                st.write(f"**Số khoản vay:** {row_test.get(COT_SO_KU, 'N/A')}")
                st.write(f"**Mức vay:** {fmt(row_test.get(COT_MUC_VAY, 0))} đồng")
            with col2:
                st.write(f"**Dư nợ:** {fmt(row_test.get(COT_TONG_DU_NO, 0))} đồng")
                st.write(f"**Ngày vay:** {row_test.get(COT_NGAY_VAY, 'N/A')}")
                st.write(f"**Thời hạn:** {row_test.get(COT_THOI_HAN, 'N/A')} tháng")
                st.write(f"**Lãi suất:** {row_test.get(COT_LAI_SUAT, 'N/A')}%")
        
        # Nút test
        if st.button("🚀 Test Template", type="primary", key="test_template_btn"):
            try:
                # Tìm template được chọn
                template_path = None
                for ten, path in templates:
                    if ten == chon_template:
                        template_path = path
                        break
                
                if template_path is None:
                    st.error("❌ Không tìm thấy template!")
                    return
                
                # Tạo dữ liệu bổ sung cho test
                extra_data = {
                    "{{nguoi_ky}}": "Nguyễn Văn Test Manager",
                    "{{chuc_vu}}": "Phó Giám đốc Chi nhánh",
                    "{{so_quyet_dinh}}": "001/QĐ-CN",
                }
                
                # Gọi hàm auto_fill_document
                doc_bytes = auto_fill_document(
                    data_row=row_test,
                    template_path=str(template_path),
                    tag_map=TAG_MAP,
                    extra=extra_data
                )
                
                # Download button
                file_name = f"Test_{chon_template.replace(' ', '_')}_{datetime.now().strftime('%d%m%Y_%H%M')}.docx"
                
                st.download_button(
                    label="⬇️ Tải file Word đã test",
                    data=doc_bytes,
                    file_name=file_name,
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    key="download_test_doc"
                )
                
                st.success("✅ Test thành công! Nhấn nút trên để tải file Word.")
                
            except Exception as e:
                st.error(f"❌ Lỗi test template: {e}")
                st.exception(e)  # Debug info


def _build_all_items(role: str, username: str, **kwargs) -> list:
    """Xây danh sách ALL_ITEMS — dùng chung cho sidebar và render."""
    df_full = kwargs.get("df_full")
    ds_pgd_all = kwargs.get("ds_pgd_all", [])
    can_upload = kwargs.get("can_upload", False)
    role_n = normalize_role(str(role or "user"))

    ALL_ITEMS = [
        {"group": "Giám sát",     "label": "Tổng quan CN", "icon": "chart-bar",      "fn": lambda: tab_tongquan.render(None, **kwargs)},
        {"group": "Giám sát",     "label": "Tiến độ Công việc", "icon": "calendar",       "fn": lambda: tab_tien_do.render(None, **kwargs)},
        {"group": "Giám sát",     "label": "Tiến độ PGD", "icon": "file", "fn": lambda: tab_tien_do_nop.render(None, **kwargs)},
        {"group": "Giám sát",     "label": "Cảnh báo NQH",     "icon": "alert-triangle", "fn": lambda: _render_canh_bao_no(df_full, ds_pgd_all, role, kwargs.get("username", "unknown"))},
        {"group": "Giám sát",     "label": "Giao & Theo dõi Nhiệm vụ", "icon": "check",  "fn": lambda: tab_nhiem_vu.render(None, **kwargs)},
        {"group": "Giám sát",     "label": "So sánh kỳ",            "icon": "chart-line", "fn": lambda: tab_so_sanh_ky.render(None, **kwargs)},
        {"group": "Kiểm soát",     "label": "Kiểm soát nội bộ",    "icon": "search",         "fn": lambda: tab_kiem_soat.render_tab(df_full, role, kwargs.get("username", "unknown"))},
        {"group": "Kiểm soát",     "label": "Xử lý nợ rủi ro",   "icon": "alert-circle",   "fn": lambda: tab_xlrr_tong_hop.render(None, **kwargs)},
        {"group": "Kiểm soát",     "label": "Cán bộ tín dụng",         "icon": "user",       "fn": lambda: tab_cbtd.render(None, **kwargs)},
        {"group": "Kiểm soát",     "label": "Tập trung rủi ro & HHI",  "icon": "chart-pie",  "fn": lambda: tab_hhi.render(None, **kwargs)},
        {"group": "Kiểm soát",     "label": "Nợ khoanh",                "icon": "lock",       "fn": lambda: tab_no_khoanh.render(None, **kwargs)},
        {"group": "Kế hoạch và Thực hiện KHTD", "label": "Kế hoạch tín dụng", "icon": "file-text",  "fn": lambda: tab_khtd.render(None, **dict(kwargs, khtd_mode="cn"))},
        {"group": "Kế hoạch và Thực hiện KHTD", "label": "Giao & Điều chỉnh KH", "icon": "upload", "fn": lambda: tab_khtd_giao_dc.render(None, **kwargs)},
        {"group": "Kế hoạch và Thực hiện KHTD", "label": "Cân đối - Điện báo", "icon": "chart-line", "fn": lambda: tab_kehoach.render(None, **kwargs)},
        {"group": "Kế hoạch và Thực hiện KHTD", "label": "Điện báo",            "icon": "antenna",    "fn": lambda: tab_candoi.render(None, **kwargs)},
        {"group": "Báo cáo",       "label": "Báo cáo tín dụng", "icon": "file",           "fn": lambda: tab_baocao.render(None, **kwargs)},
        {"group": "Báo cáo",       "label": "Checklist định kỳ", "icon": "calendar-check", "fn": lambda: tab_checklist_bc.render(None, **kwargs)},
        {"group": "Ủy Thác",       "label": "Ban Đại Diện HĐQT", "icon": "building",       "fn": lambda: tab_ban_dai_dien.render(None, cap="tinh", **kwargs)},
        {"group": "Ủy Thác",       "label": "Ủy thác CT-XH",     "icon": "handshake",      "fn": lambda: tab_uy_thac.render(None, **kwargs)},
        {"group": "Ủy Thác",       "label": "Điểm GD & Tổ TK&VV", "icon": "map-pin",        "fn": lambda: _render_dgd_to_tkvv(None, **kwargs)},
    ]

    if can_upload:
        ALL_ITEMS.append({"group": "Hệ thống", "label": "Template văn bản", "icon": "template", "fn": lambda: _render_quan_ly_template(df_full)})
    if role_n in ("admin_cn", "manager_cn"):
        ALL_ITEMS.append({"group": "Hệ thống", "label": "Mã NĐT địa phương", "icon": "building-bank", "fn": lambda: _render_ndt_dp(role_n, kwargs.get("username", "unknown"))})
    if role_n == "admin_cn":
        ALL_ITEMS.append({"group": "Hệ thống", "label": "Nhật ký hệ thống", "icon": "list", "fn": lambda: tab_audit_log.render(None, **kwargs)})
    ALL_ITEMS.append({"group": "Hệ thống", "label": "Trạng thái hệ thống", "icon": "pulse", "fn": lambda: tab_trang_thai_nguon.render(None, **kwargs)})
    ALL_ITEMS.append({"group": "Hệ thống", "label": "Upload dữ liệu", "icon": "upload", "fn": lambda: tab_upload_khnv.render(None, **kwargs)})
    ALL_ITEMS.append({"group": "Hệ thống", "label": "Hướng dẫn", "icon": "book", "fn": lambda: render_huong_dan()})

    return ALL_ITEMS


def render_sidebar_menu(role: str, username: str, **kwargs):
    """Render menu ĐIỀU HÀNH — gọi từ app.py bên trong with st.sidebar."""

    GROUP_COLORS = {
        "Giám sát":                    {"bg": "#E6F1FB", "border": "#378ADD", "text": "#185FA5"},
        "Kiểm soát":                   {"bg": "#FCEBEB", "border": "#E24B4A", "text": "#A32D2D"},
        "Kế hoạch và Thực hiện KHTD": {"bg": "#EAF3DE", "border": "#639922", "text": "#3B6D11"},
        "Báo cáo":                     {"bg": "#FAEEDA", "border": "#BA7517", "text": "#854F0B"},
        "Ủy Thác":                     {"bg": "#EEEDFE", "border": "#7F77DD", "text": "#3C3489"},
        "Hệ thống":                    {"bg": "#F1EFE8", "border": "#888780", "text": "#5F5E5A"},
    }

    all_items = _build_all_items(role, username, **kwargs)
    if not all_items:
        return

    if "ws_mgmt_menu" not in st.session_state:
        st.session_state["ws_mgmt_menu"] = all_items[0]["label"]

    valid_labels = [x["label"] for x in all_items]
    if st.session_state["ws_mgmt_menu"] not in valid_labels:
        st.session_state["ws_mgmt_menu"] = all_items[0]["label"]

    st.markdown(
        "<p style='font-size:12px;font-weight:500;"
        "color:#444;margin-bottom:4px'>MENU ĐIỀU HÀNH</p>",
        unsafe_allow_html=True
    )

    current_group = None
    for item in all_items:
        grp = item["group"]
        clr = GROUP_COLORS.get(grp, {"bg": "#F1EFE8", "border": "#888", "text": "#444"})

        if grp != current_group:
            current_group = grp
            st.markdown(
                f"<p style='font-size:10px;font-weight:500;"
                f"color:{clr['text']};text-transform:uppercase;"
                f"letter-spacing:0.06em;padding:10px 4px 2px;margin:0'>"
                f"{grp}</p>",
                unsafe_allow_html=True
            )

        is_active = st.session_state["ws_mgmt_menu"] == item["label"]

        if is_active:
            st.markdown(
                f"<div style='"
                f"background:#E65100;"
                f"border-left:2px solid #BF360C;"
                f"color:#FFFFFF;"
                f"font-size:13px;font-weight:600;"
                f"padding:6px 8px 6px 10px;"
                f"border-radius:0 5px 5px 0;"
                f"margin-bottom:2px'>"
                f"{item['label']}</div>",
                unsafe_allow_html=True
            )
        else:
            if st.button(
                item["label"],
                key=f"menu_{item['label']}",
                width='stretch',
            ):
                st.session_state["ws_mgmt_menu"] = item["label"]
                st.rerun()


def render(**kwargs):
    _wl = st.session_state.pop("_data_load_warning", None)
    if _wl:
        st.warning(_wl)

    def _tab_so_sanh_ky_fn(**kw):
        tab_so_sanh_ky.render(None, **kw)

    role       = kwargs.get("role")
    username   = kwargs.get("username", "unknown")
    df         = kwargs.get("df")
    df_full    = kwargs.get("df_full", df)
    ds_pgd_all = kwargs.get("ds_pgd_all", [])
    role_n = normalize_role(str(role or "user"))
    can_upload = get_permissions(role_n)["can_upload"]
    can_manage_users = get_permissions(role_n)["can_manage_users"]

    st.title("📋 Phòng KH-NV")
    st.caption("Giám sát chỉ tiêu · Cân đối vốn · Quản lý NQH · GQVL · Quản lý CBTD")

    filtered_kw = {k: v for k, v in kwargs.items()
                   if k not in ("role", "username", "df", "df_full", "ds_pgd_all")}
    ALL_ITEMS = _build_all_items(
        role, username,
        can_upload=can_upload, **filtered_kw
    )

    # ── Navigation: điều hướng hoàn toàn qua sidebar (render_sidebar_menu) ──
    valid_labels = [x["label"] for x in ALL_ITEMS]

    # Handle jump từ shortcut / nút điều hướng ngoài ws_management
    jump_label = st.session_state.pop("ws_mgmt_jump", None)
    if jump_label and jump_label in valid_labels:
        st.session_state["ws_mgmt_menu"] = jump_label
        st.toast(f"✨ Đã chuyển tới: {jump_label}", icon="👆")

    # Khởi tạo / validate ws_mgmt_menu
    if "ws_mgmt_menu" not in st.session_state or \
            st.session_state["ws_mgmt_menu"] not in valid_labels:
        st.session_state["ws_mgmt_menu"] = ALL_ITEMS[0]["label"]

    active_label = st.session_state["ws_mgmt_menu"]

    # ── Render DUY NHẤT mục đang chọn ────────────────────────────────────
    active_item = next((x for x in ALL_ITEMS if x["label"] == active_label), None)
    if active_item:
        fn = active_item.get("fn")
        if callable(fn):
            try:
                fn()
            except Exception as e:
                import traceback
                st.error(f"❌ Lỗi render **{active_label}**: {e}")
                st.code(traceback.format_exc())
        else:
            st.info(f"Tính năng **{active_label}** đang được phát triển.")
