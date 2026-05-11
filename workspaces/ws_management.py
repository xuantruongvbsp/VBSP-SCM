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
from auth import is_cn_role, is_pgd_role, get_permissions
from data import (
    danh_dau_khong_hd, tong_hop_khong_hd,
    ds_chi_tiet_khong_hd, canh_bao_migration,
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
from tabs import (
    tab_tongquan, tab_baocao, tab_nq11,
    tab_candoi, tab_cbtd, tab_khtd, tab_kehoach,
    tab_nhiem_vu, tab_cdtotkvv, tab_khtd_giao_dc, tab_kiem_soat,
    tab_ban_dai_dien,
    tab_uy_thac,
    tab_qd62,
    tab_tien_do,
)
from tabs import tab_upload_khnv
from tabs import tab_quan_ly_dgd
from tabs import tab_audit_log
from tabs.tab_kh_gqvl import render as render_kh_gqvl
from tabs.tab_den_han import render as render_den_han


def _render_canh_bao(df: pd.DataFrame, ds_pgd_all: list):
    """
    Tab Cảnh báo sớm — Migration & 3 tháng không hoạt động.
    Hiển thị bảng Top đơn vị cần chấn chỉnh + xuất KL giao ban.
    """
    st.subheader("🚨 Cảnh báo sớm — Phân loại nợ & 3 tháng không HĐ")

    if df is None or df.empty:
        st.warning("Chưa có dữ liệu HSTD."); return

    # Đánh dấu 3 tháng không hoạt động
    df_kh = danh_dau_khong_hd(df)

    # ── KPI nhanh ──────────────────────────────────────────────────────────
    tong_mon    = len(df_kh)
    khd_tong    = int(df_kh["is_3m_inactive"].sum()) if "is_3m_inactive" in df_kh.columns else 0
    df_amber    = canh_bao_migration(df_kh)
    amber_tong  = len(df_amber)
    tl_khd      = khd_tong / tong_mon * 100 if tong_mon > 0 else 0

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Tổng món vay",              fmt_so(tong_mon))
    k2.metric("3 tháng không HĐ 🔴",       fmt_so(khd_tong),
              delta=f"{tl_khd:.1f}% tổng món",
              delta_color="inverse" if tl_khd > 2 else "off")
    k3.metric("Sắp chuyển 3 tháng KHĐ ⚠️", fmt_so(amber_tong),
              help="Lãi tồn 2–3 tháng, chưa đủ 3 tháng không hoạt động — cần đôn đốc ngay")
    tong_lai_khd = df_kh[df_kh.get("is_3m_inactive", False)][COT_LAI_TON].sum() \
                   if COT_LAI_TON in df_kh.columns else 0
    k4.metric("Lãi tồn 3m KHĐ (tr.đ)",    vn(tong_lai_khd/1e6, 1))

    st.divider()

    # ── Bảng Top đơn vị cần chấn chỉnh ───────────────────────────────────
    st.markdown("**📋 Tổng hợp theo PGD**")
    nhom_pgd = tong_hop_khong_hd(df_kh, nhom_theo=COT_TEN_PGD)
    if not nhom_pgd.empty:
        hien_thi_dataframe_phan_trang(
            nhom_pgd,
            key="mgmt_khd_nhom_pgd",
            height=300,
        )

    st.markdown("**📋 Tổng hợp theo Hội đoàn thể (ĐVUT)**")
    nhom_dvut = tong_hop_khong_hd(df_kh, nhom_theo="Tên ĐVUT")
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
    """Cảnh báo nợ — 4 sub-tab: Đến hạn, 3 tháng KHĐ, Migration, Nợ QH phát sinh."""
    sub1, sub2, sub3, sub4 = st.tabs([
        "⏰ Đến hạn",
        "🔴 3 tháng KHĐ",
        "🚨 Migration (đủ chuẩn → NQH)",
        "📋 Nợ QH phát sinh",
    ])

    with sub1:
        render_den_han(role=role)

    if df_full is None or df_full.empty:
        for tab in [sub2, sub3, sub4]:
            with tab:
                st.warning("Chưa có dữ liệu HSTD.")
        return

    _cache_key = f"df_kh_{id(df_full)}"
    if _cache_key not in st.session_state:
        st.session_state[_cache_key] = danh_dau_khong_hd(df_full)
    df_kh = st.session_state[_cache_key]

    with sub2:
        _hien_thi_khd_tab(df_kh, ds_pgd_all)

    with sub3:
        _hien_thi_migration_tab(df_kh, ds_pgd_all)

    with sub4:
        _hien_thi_nqh_tab(df_kh, username)


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
    k3.metric("Lãi tồn (tr.đ)", vn(tong_lai / 1e6, 1))

    st.markdown("**📋 Tổng hợp theo PGD**")
    nhom_pgd = tong_hop_khong_hd(df_kh, nhom_theo=COT_TEN_PGD)
    if not nhom_pgd.empty:
        hien_thi_dataframe_phan_trang(nhom_pgd, key="khd_pgd", height=280)

    st.markdown("**📋 Tổng hợp theo Hội đoàn thể**")
    nhom_dvut = tong_hop_khong_hd(df_kh, nhom_theo="Tên ĐVUT")
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
            buf = xuat_excel({"3mKHD": df_chi_loc})
            st.download_button(
                f"⬇️ Excel ({len(df_chi_loc)} món)", data=buf,
                file_name=f"3mKHD_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="khd_xuat",
            )
        hien_thi_dataframe_phan_trang(df_chi_loc, key="khd_chi", height=320)


def _hien_thi_migration_tab(df_kh: pd.DataFrame, ds_pgd_all: list):
    """Sub-tab: Migration — món vay đủ chuẩn có nguy cơ chuyển NQH."""
    df_amber = canh_bao_migration(df_kh)
    amber_tong = len(df_amber)

    if amber_tong == 0:
        st.success("✅ Không có món vay nào có dấu hiệu rủi ro chuyển NQH.")
        return

    k1, k2 = st.columns(2)
    k1.metric("⚠️ Số món cần theo dõi", fmt_so(amber_tong))
    tong_lai = df_amber[COT_LAI_TON].sum() if COT_LAI_TON in df_amber.columns else 0
    k2.metric("Tổng lãi tồn (tr.đ)", vn(tong_lai / 1e6, 1))

    col_loc, col_xuat = st.columns([2, 1])
    with col_loc:
        loc_pgd = st.selectbox("Lọc PGD", ["Tất cả"] + ds_pgd_all, key="mg_loc_pgd")
    df_loc = df_amber if loc_pgd == "Tất cả" else df_amber[df_amber[COT_TEN_PGD] == loc_pgd]
    with col_xuat:
        st.markdown("<br>", unsafe_allow_html=True)
        buf = xuat_excel({"Migration": df_loc})
        st.download_button(
            f"⬇️ Excel ({len(df_loc)} món)", data=buf,
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

    st.markdown("**Danh sach chi tiet**")
    buf = xuat_excel({"NQH": df_nqh_chi})
    st.download_button(
        f"Xuat Excel ({len(df_nqh_chi)} ho so)", data=buf,
        file_name=f"DS_NQH_{datetime.now().strftime('%Y%m%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="nqh_xuat",
    )
    hien_thi_dataframe_phan_trang(df_nqh_chi, key="nqh_chi", height=360)

def _render_dgd_to_tkvv(tab_parent=None, **kw):
    """Sub-tab Điểm GD & Tổ TK&VV — nested tabs."""
    if tab_parent is not None:
        ctx = tab_parent
    else:
        ctx = st
    with ctx:
        _sub1, _sub2 = st.tabs(["📍 Điểm Giao Dịch", "🏘️ Tổ TK&VV"])
        tab_quan_ly_dgd.render(_sub1, **kw)
        tab_cdtotkvv.render(_sub2, **dict(kw, cdto_mode="cn"))


def _render_ndt_dp(role: str, username: str) -> None:
    """Tab quản lý Mã Nhà đầu tư Địa phương — dùng phân tầng GQVL ĐP."""
    from db import doc_ndt_dp_list, ghi_kv, ghi_audit

    st.subheader("🏦 Mã Nhà đầu tư Địa phương — Cấp tỉnh")
    st.caption(
        "Danh sách này dùng để phân loại nguồn vốn ĐP trong file GQVL. "
        "Món vay nào có Mã NĐT khớp chính xác (exact match) với 1 mã trong "
        "danh sách → xếp vào GQVL ĐP Cấp tỉnh. Còn lại → Cấp xã/khác."
    )

    ds = doc_ndt_dp_list()   # list[dict] {"ma", "ghi_chu"}
    can_edit = role in ("admin", "admin_cn")

    # Hiển thị bảng hiện tại
    if ds:
        for i, item in enumerate(ds):
            c1, c2, c3, c4 = st.columns([3, 4, 1, 1])
            c1.code(item["ma"])
            edit_key = f"edit_ndt_{i}"
            if st.session_state.get(edit_key) and can_edit:
                ghi_chu_moi = c2.text_input(
                    "Ghi chú",
                    value=item.get("ghi_chu", "") or "",
                    key=f"ndt_note_{i}",
                    label_visibility="collapsed",
                )
                if c3.button("💾", key=f"luu_ndt_{i}", help="Lưu"):
                    ghi_chu_cu = item.get("ghi_chu", "") or ""
                    ghi_chu_moi = (ghi_chu_moi or "").strip()
                    if ghi_chu_moi != ghi_chu_cu:
                        ds_moi = [dict(x) for x in ds]
                        ds_moi[i]["ghi_chu"] = ghi_chu_moi
                        ghi_kv("ndt_dp_list", ds_moi, username)
                        ghi_audit(username, "sua_ndt_dp",
                                  f"Sửa mã {item['ma']}: {ghi_chu_cu} → {ghi_chu_moi}")
                        st.cache_data.clear()
                    st.session_state.pop(edit_key, None)
                    st.rerun()
            else:
                c2.text(item.get("ghi_chu", ""))
            if can_edit:
                if c3.button("✏️", key=f"sua_ndt_{i}", help="Sửa ghi chú"):
                    st.session_state[edit_key] = True
                    st.rerun()
                if c4.button("🗑️", key=f"xoa_ndt_{i}",
                             disabled=(len(ds) <= 1),
                             help="Không thể xóa mã duy nhất"):
                    ds_moi = [x for j, x in enumerate(ds) if j != i]
                    ghi_kv("ndt_dp_list", ds_moi, username)
                    ghi_audit(username, "xoa_ndt_dp",
                              f"Xóa mã {item['ma']}")
                    st.cache_data.clear()
                    st.rerun()
    else:
        st.info("Chưa có mã nào.")

    if not can_edit:
        st.caption("⚠️ Chỉ admin mới có thể thêm/xóa.")

    with st.expander("📊 Xem tác động lên dữ liệu GQVL hiện tại", expanded=False):
        try:
            from pathlib import Path
            from config import CACHE_DIR, COT_MA_NDT

            gqvl_path = Path(CACHE_DIR) / "gqvl.parquet"
            if not gqvl_path.exists():
                st.info("Chưa có dữ liệu GQVL. Upload file để xem tác động.")
            else:
                df_gqvl = pd.read_parquet(gqvl_path)
                if ("Nguồn vốn" not in df_gqvl.columns) or (COT_MA_NDT not in df_gqvl.columns):
                    st.warning("File GQVL không có đủ cột để phân tích.")
                else:
                    df_dp = df_gqvl[df_gqvl["Nguồn vốn"] == "ĐP"].copy()
                    ma_ndt_str = df_dp[COT_MA_NDT].astype(str).str.strip()
                    ndt_list = [x.get("ma", "") for x in (ds or [])]
                    mask_cap_tinh = ma_ndt_str.isin(ndt_list)

                    p1, p2, p3 = st.columns(3)
                    p1.metric("Tổng món ĐP", fmt_so(len(df_dp)))
                    p2.metric("→ Cấp tỉnh 🏛️", fmt_so(int(mask_cap_tinh.sum())))
                    p3.metric("→ Cấp xã/khác 🏘️", fmt_so(int((~mask_cap_tinh).sum())))

                    df_preview = (
                        df_dp.assign(
                            _ma_label=ma_ndt_str.where(mask_cap_tinh, "Cấp xã/khác"),
                        )
                        .groupby("_ma_label")
                        .size()
                        .reset_index(name="Số món")
                        .rename(columns={"_ma_label": "Mã NĐT / Nhóm"})
                    )
                    ghi_chu_map = {x.get("ma", ""): x.get("ghi_chu", "") for x in (ds or [])}
                    df_preview["Ghi chú"] = df_preview["Mã NĐT / Nhóm"].map(
                        lambda m: ghi_chu_map.get(m, "")
                    )
                    st.dataframe(df_preview, hide_index=True, use_container_width=True)
        except Exception as e:
            st.warning(f"Không thể phân tích tác động GQVL: {e}")

    if can_edit:
        st.divider()
        st.markdown("##### ➕ Thêm mã mới")
        with st.form("form_them_ndt", clear_on_submit=True):
            ma_moi = st.text_input(
                "Mã NĐT đầy đủ",
                placeholder="VD: INV0802140002662",
                help="Lấy chính xác từ cột 'Mã nhà đầu tư' trong file GQVL"
            )
            ghi_chu_moi = st.text_input(
                "Ghi chú",
                placeholder="VD: UBND tỉnh Đồng Nai"
            )
            submitted = st.form_submit_button("➕ Thêm", type="primary")

        if submitted:
            ma_moi = ma_moi.strip()
            if not ma_moi:
                st.error("Vui lòng nhập mã NĐT.")
            elif any(x["ma"] == ma_moi for x in ds):
                st.warning(f"Mã {ma_moi} đã có trong danh sách.")
            else:
                ds_moi = ds + [{"ma": ma_moi, "ghi_chu": ghi_chu_moi.strip()}]
                ghi_kv("ndt_dp_list", ds_moi, username)
                ghi_audit(username, "them_ndt_dp",
                          f"Thêm mã {ma_moi} — {ghi_chu_moi}")
                st.cache_data.clear()
                st.success(f"✅ Đã thêm mã {ma_moi}")
                st.rerun()

    st.divider()
    if st.button("📥 Xuất danh sách Excel", key="export_ndt_dp"):
        import io

        df_export = pd.DataFrame(ds or [], columns=["ma", "ghi_chu"])
        df_export.columns = ["Mã NĐT", "Ghi chú"]
        buf = io.BytesIO()
        df_export.to_excel(buf, index=False)
        st.download_button(
            "💾 Tải về",
            data=buf.getvalue(),
            file_name="danh_sach_ndt_dp.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="dl_ndt_dp",
        )


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


def render(**kwargs):
    _wl = st.session_state.pop("_data_load_warning", None)
    if _wl:
        st.warning(_wl)

    role       = kwargs.get("role")
    df         = kwargs.get("df")
    df_full    = kwargs.get("df_full", df)
    ds_pgd_all = kwargs.get("ds_pgd_all", [])
    can_upload = get_permissions(role)["can_upload"]

    st.title("📋 Phòng KH-NV")
    st.caption("Giám sát chỉ tiêu · Cân đối vốn · Quản lý NQH · GQVL · Quản lý CBTD")

    # ── BƯỚC 1: Render layout 2 cột ───────────────────────────────────────
    col_sidebar, col_content = st.columns([1, 4], gap="small")

    # ── BƯỚC 2: Xây danh sách tất cả menu items ───────────────────────────
    ALL_ITEMS = [
        {"group": "Tổng quan",     "label": "Thông tin chung", "icon": "chart-bar",      "fn": lambda c=col_content: tab_tongquan.render(c, **kwargs)},
        {"group": "Tổng quan",     "label": "Tiến độ",         "icon": "calendar",       "fn": lambda c=col_content: tab_tien_do.render(c, **kwargs)},
        {"group": "Tổng quan",     "label": "Cảnh báo nợ",     "icon": "alert-triangle", "fn": lambda: _render_canh_bao_no(df_full, ds_pgd_all, role, kwargs.get("username", "unknown"))},
        {"group": "Kiểm soát",     "label": "Kiểm soát CN",    "icon": "search",         "fn": lambda: tab_kiem_soat.render_tab(df_full, role, kwargs.get("username", "unknown"))},
        {"group": "Kiểm soát",     "label": "Nợ rủi ro QĐ62",  "icon": "credit-card",    "fn": lambda: tab_qd62.render(mode="cn")},
        {"group": "Kiểm soát",     "label": "Quản lý CBTD",    "icon": "user",           "fn": lambda c=col_content: tab_cbtd.render(c, **kwargs)},
        {"group": "Kế hoạch",      "label": "KH Tín dụng Năm", "icon": "file-text",      "fn": lambda c=col_content: tab_khtd.render(c, **dict(kwargs, khtd_mode="cn"))},
        {"group": "Kế hoạch",      "label": "Giao KH theo Đợt", "icon": "upload",         "fn": lambda c=col_content: tab_khtd_giao_dc.render(c, **kwargs)},
        {"group": "Kế hoạch",      "label": "KH vs Thực hiện", "icon": "chart-line",     "fn": lambda c=col_content: tab_kehoach.render(c, **kwargs)},
        {"group": "Báo cáo",       "label": "Báo cáo chi tiết", "icon": "file",           "fn": lambda c=col_content: tab_baocao.render(c, **kwargs)},
        {"group": "Báo cáo",       "label": "Điện Báo",        "icon": "antenna",        "fn": lambda c=col_content: tab_candoi.render(c, **kwargs)},
        {"group": "Báo cáo",       "label": "Điểm GD & Tổ TK&VV", "icon": "map-pin",      "fn": lambda c=col_content: _render_dgd_to_tkvv(c, **kwargs)},
        {"group": "Hành chính",    "label": "Ban Đại Diện",    "icon": "building",       "fn": lambda c=col_content: tab_ban_dai_dien.render(c, cap="tinh", **kwargs)},
        {"group": "Hành chính",    "label": "Ủy thác",         "icon": "handshake",      "fn": lambda c=col_content: tab_uy_thac.render(c, **kwargs)},
        {"group": "Hành chính",    "label": "Nhiệm vụ",        "icon": "check",          "fn": lambda c=col_content: tab_nhiem_vu.render(c, **kwargs)},
    ]

    # Thêm theo điều kiện (giống logic cũ)
    if can_upload:
        ALL_ITEMS.append({"group": "Hành chính", "label": "Quản lý Template", "icon": "template", "fn": lambda: _render_quan_ly_template(df_full)})
    if role in ("admin", "admin_cn", "manager", "manager_cn"):
        ALL_ITEMS.append({"group": "Hành chính", "label": "Mã NĐT ĐP", "icon": "building-bank", "fn": lambda: _render_ndt_dp(role, kwargs.get("username", "unknown"))})
    if role in ("admin", "admin_cn"):
        ALL_ITEMS.append({"group": "Hành chính", "label": "Audit Log", "icon": "list", "fn": lambda c=col_content: tab_audit_log.render(c, **kwargs)})
    ALL_ITEMS.append({"group": "Hành chính", "label": "Upload KH-NV", "icon": "upload", "fn": lambda c=col_content: tab_upload_khnv.render(c, **kwargs)})

    # ── BƯỚC 3: Quản lý state menu item đang chọn ─────────────────────────
    if "ws_mgmt_menu" not in st.session_state:
        st.session_state["ws_mgmt_menu"] = ALL_ITEMS[0]["label"]

    valid_labels = [x["label"] for x in ALL_ITEMS]
    if st.session_state["ws_mgmt_menu"] not in valid_labels:
        st.session_state["ws_mgmt_menu"] = ALL_ITEMS[0]["label"]


    # Bảng màu theo nhóm
    GROUP_COLORS = {
        "Tổng quan":  {"bg": "#E6F1FB", "border": "#378ADD", "text": "#185FA5"},
        "Kiểm soát":  {"bg": "#FCEBEB", "border": "#E24B4A", "text": "#A32D2D"},
        "Kế hoạch":   {"bg": "#EAF3DE", "border": "#639922", "text": "#3B6D11"},
        "Báo cáo":    {"bg": "#FAEEDA", "border": "#BA7517", "text": "#854F0B"},
        "Hành chính": {"bg": "#EEEDFE", "border": "#7F77DD", "text": "#3C3489"},
    }

    with col_sidebar:
        current_group = None
        for item in ALL_ITEMS:
            grp = item["group"]
            clr = GROUP_COLORS.get(grp, {"bg": "#F1EFE8", "border": "#888780", "text": "#444441"})

            # Header nhóm — hiện khi đổi nhóm mới
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
                # Hiển thị item active bằng markdown (không dùng button để style tự do hơn)
                st.markdown(
                    f"<div style='"
                    f"background:{clr['bg']};"
                    f"border-left:2px solid {clr['border']};"
                    f"color:{clr['text']};"
                    f"font-size:13px;font-weight:500;"
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
                    use_container_width=True,
                ):
                    st.session_state["ws_mgmt_menu"] = item["label"]
                    st.rerun()

    # ── BƯỚC 4: Render nội dung bên phải ──────────────────────────────────
    with col_content:
        # Tìm item đang active và gọi hàm render của nó
        active_item = next(
            (x for x in ALL_ITEMS if x["label"] == st.session_state["ws_mgmt_menu"]),
            ALL_ITEMS[0]
        )
        active_item["fn"]()
