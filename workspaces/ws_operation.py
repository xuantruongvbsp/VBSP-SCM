"""
Không gian Tác nghiệp (Operation View)
────────────────────────────────────────
Dành cho CBTD — Tra cứu chi tiết + Document Hub (Trung tâm văn bản tự động).
"""
import socket

import streamlit as st
import pandas as pd
import os
from io import BytesIO
from datetime import date, datetime

import db
from config import (
    COT_TEN_KH, COT_MA_KH, COT_SO_KU, COT_TEN_CT,
    COT_DU_NO_QH, COT_TONG_DU_NO, COT_NGAY_DH,
    COT_TEN_PGD, COT_SDT, COT_DIA_CHI,
    COT_LAI_TON, COT_LAI_THANG, COT_DVUT, COT_TEN_XA,
    TEMPLATES_DIR, TAG_MAP, PGD_XA_MAP,
)
from auth import co_quyen_upload_pgd, is_cn_role, is_pgd_role, get_permissions, get_tab_permissions
from data import (
    danh_dau_khong_hd, danh_dau_khong_hd_cached,
    tong_hop_khong_hd, tong_hop_khong_hd_cached,
    ds_chi_tiet_khong_hd,
)
from data.pgd import pgd_slug
from utils import (
    fmt,
    fmt_ty,
    fmt_so,
    vn,
    auto_fill_document,
    auto_fill_batch,
    quet_templates,
    xuat_excel,
    hien_thi_dataframe_phan_trang,
    get_tab_context,
)
from services.excel_service import xuat_excel_chuyen_nghiep, ten_file_xuat as excel_ten_file
from pdf_service import xuat_pdf, kiem_tra_pdf_dependency, render_huong_dan
from components.delta_card import delta_card, kpi_row
from components.filter_bar import filter_bar, apply_filters
from components.loan_drawer import loan_detail_drawer
from components.export_pdf import download_pdf_button, xuat_pdf_co_chart


# ── Helper: tính 4 KPI DeltaCard cho trang chủ PGD ──────────────────────────

def _kpi_pgd_list(df_pgd: pd.DataFrame, pgd_user: str) -> list[dict]:
    """Tính 4 KPI DeltaCard cho trang chủ / sidebar PGD.

    Returns:
        List dict (kwargs cho delta_card), tối đa 4 phần tử.
    """
    kpi: list[dict] = []
    if df_pgd is None or df_pgd.empty:
        return kpi

    # ── Tính trước để dùng chung ───────────────────────────────────────────
    tong_dn = (
        pd.to_numeric(df_pgd[COT_TONG_DU_NO], errors="coerce").sum()
        if COT_TONG_DU_NO in df_pgd.columns else 0.0
    )
    nqh_dn = (
        pd.to_numeric(df_pgd[COT_DU_NO_QH], errors="coerce").sum()
        if COT_DU_NO_QH in df_pgd.columns else 0.0
    )

    # ── KPI 1: Tổng dư nợ ─────────────────────────────────────────────────
    try:
        pct_nqh = (nqh_dn / tong_dn * 100) if tong_dn > 0 else 0.0
        kpi.append({
            "label":       "Tổng dư nợ",  # noqa: COT
            "value":       fmt_ty(tong_dn),
            "delta":       -pct_nqh,         # ↓ mũi tên xuống, inverse → xanh khi thấp
            "delta_label": "% NQH",
            "icon":        "💰",
            "suffix":      "",
            "precision":   2,
            "help":        "Tổng dư nợ toàn PGD",
            "delta_color": "inverse",
        })
    except Exception:
        pass

    # ── KPI 2: Nợ quá hạn ─────────────────────────────────────────────────
    try:
        ty_le_nqh = (nqh_dn / tong_dn * 100) if tong_dn > 0 else 0.0
        kpi.append({
            "label":       "Nợ quá hạn",  # noqa: COT
            "value":       fmt_ty(nqh_dn),
            "delta":       ty_le_nqh,         # ↑ mũi tên lên, inverse → đỏ khi cao
            "delta_label": "% so dư nợ",
            "icon":        "🔴",
            "suffix":      "",
            "precision":   2,
            "help":        "Dư nợ quá hạn toàn PGD",
            "delta_color": "inverse",
        })
    except Exception:
        pass

    # ── KPI 3: 3 tháng KHĐ ────────────────────────────────────────────────
    try:
        df_kh   = danh_dau_khong_hd_cached(df_pgd)
        n_khd   = int(df_kh["is_3m_inactive"].sum()) if "is_3m_inactive" in df_kh.columns else 0
        pct_khd = (n_khd / len(df_pgd) * 100) if len(df_pgd) > 0 else 0.0
        kpi.append({
            "label":       "3 tháng KHĐ",
            "value":       fmt_so(n_khd),
            "delta":       pct_khd,           # ↑ mũi tên lên, inverse → đỏ khi nhiều KHĐ
            "delta_label": "% tổng hồ sơ",
            "icon":        "📅",
            "suffix":      "món",
            "precision":   1,
            "help":        "Khoản hộ vay 3 tháng không hoạt động",
            "delta_color": "inverse",
        })
    except Exception:
        pass

    # ── KPI 4: Tiến độ KHTD ───────────────────────────────────────────────
    try:
        # khtd_xa: {ten_xa}|{ma_ct_key} → gia_tri_dong (VND)
        kh_xa  = db.doc_kv("khtd_xa") or {}
        ds_xa  = set(PGD_XA_MAP.get(pgd_user, []))
        tong_kh = sum(
            float(v)
            for k, v in kh_xa.items()
            if "|" in k and k.split("|", 1)[0] in ds_xa
        ) if (kh_xa and ds_xa) else 0.0

        if tong_kh > 0:
            pct_khtd  = tong_dn / tong_kh * 100   # TH = tổng dư nợ PGD
            khtd_val  = f"{pct_khtd:.0f}%"
        else:
            khtd_val  = "—"

        kpi.append({
            "label":       "KHTD",
            "value":       khtd_val,
            "delta":       None,              # không so sánh
            "icon":        "📊",
            "suffix":      "",
            "precision":   0,
            "help":        "Tiến độ thực hiện KHTD",
            "delta_color": "off",
        })
    except Exception:
        pass

    return kpi


def _render_trang_chu(tab, df_pgd: pd.DataFrame, role: str, pgd_user: str, kwargs: dict):
    """
    Trang chủ dashboard PGD — tổng quan KPI, shortcut, cảnh báo, nhiệm vụ.
    """
    ctx = tab if tab is not None else st.container()
    with ctx:
        st.subheader("🏠 Trang Chủ")

        # ── Vùng A: Header ──────────────────────────────────────────────────
        try:
            col_info, col_btn = st.columns([3, 1])
            with col_info:
                ten_pgd = pgd_user or "Chi nhánh"
                so_ho_so = len(df_pgd) if df_pgd is not None and not df_pgd.empty else 0
                st.markdown(f"**{ten_pgd}** · {fmt_so(so_ho_so)} hồ sơ")
            with col_btn:
                if st.button("🔄 Làm mới", use_container_width=True, key="trang_chu_refresh"):
                    st.rerun()
        except Exception as e:
            st.error(f"❌ Lỗi header: {e}")

        # ── Vùng B: 4 KPI cards ────────────────────────────────────────────
        try:
            if df_pgd is None or df_pgd.empty:
                st.warning("⚠️ Chưa có dữ liệu. Vui lòng upload file HSTD.")
            else:
                kpi_data = _kpi_pgd_list(df_pgd, pgd_user or "")
                if kpi_data:
                    kpi_row(kpi_data, num_columns=4)
        except Exception as e:
            st.error(f"❌ Lỗi KPI: {e}")

        st.divider()

        # ── Vùng C: 2 cột ngang ────────────────────────────────────────────
        col_left, col_right = st.columns([1, 1])

        # Cột trái: Truy cập nhanh
        with col_left:
            st.markdown("**🚀 Truy cập nhanh**")
            try:
                shortcuts = [
                    ("🔍", "Tra cứu hồ sơ", "Tìm kiếm chi tiết", "nghiep_vu_pgd", 2),
                    ("📈", "Báo cáo chi tiết", "Xem báo cáo", "bao_cao_giao_ban", 0),
                    ("⏰", "Đến hạn", "Khoản đến hạn", "nghiep_vu_pgd", 4),
                    ("📝", "Giao ban xã", "Biên bản giao ban", "bao_cao_giao_ban", 2),
                    ("🎯", "KHTD PGD", "Kế hoạch tín dụng", "ke_hoach_pgd", 0),
                    ("🔔", "Đôn đốc KHĐ", "Khoản 3m KHĐ", "kiem_soat_rr", 0),
                ]

                for i in range(0, len(shortcuts), 2):
                    s1, s2 = st.columns(2)

                    if i < len(shortcuts):
                        icon, title, desc, nhom, tab_idx = shortcuts[i]
                        with s1:
                            if st.button(f"{icon} {title}\n_{desc}_", use_container_width=True,
                                       key=f"sc_1_{i}"):
                                st.session_state["ws_op_nhom"] = nhom
                                st.session_state["ws_op_jump_tab"] = tab_idx
                                st.rerun()

                    if i + 1 < len(shortcuts):
                        icon, title, desc, nhom, tab_idx = shortcuts[i + 1]
                        with s2:
                            if st.button(f"{icon} {title}\n_{desc}_", use_container_width=True,
                                       key=f"sc_1_{i+1}"):
                                st.session_state["ws_op_nhom"] = nhom
                                st.session_state["ws_op_jump_tab"] = tab_idx
                                st.rerun()
            except Exception as e:
                st.error(f"❌ Lỗi shortcut: {e}")

        # Cột phải: Cảnh báo + Nhiệm vụ
        with col_right:
            # Phần cảnh báo
            st.markdown("**⚠️ Cảnh báo**")
            try:
                if df_pgd is None or df_pgd.empty:
                    st.info("Không có dữ liệu để hiển thị cảnh báo.")
                else:
                    alerts = []

                    # Cảnh báo NQH
                    try:
                        nqh_count = (pd.to_numeric(df_pgd[COT_DU_NO_QH], errors="coerce") > 0).sum()
                        if nqh_count > 0:
                            alerts.append(("🔴", f"NQH > 0: {fmt_so(nqh_count)} khoản", "danger", "bao_cao_giao_ban", 1))
                    except Exception:
                        pass

                    # Cảnh báo 3m KHĐ
                    try:
                        df_kh = danh_dau_khong_hd_cached(df_pgd)
                        khd_count = int(df_kh["is_3m_inactive"].sum()) if "is_3m_inactive" in df_kh.columns else 0
                        if khd_count > 0:
                            alerts.append(("📅", f"3m KHĐ: {fmt_so(khd_count)} khoản", "danger", "kiem_soat_rr", 0))
                    except Exception:
                        pass

                    if alerts:
                        for icon, text, color, nhom, tab_idx in alerts:
                            if st.button(f"{icon} {text}", use_container_width=True, key=f"alert_{text}"):
                                st.session_state["ws_op_nhom"] = nhom
                                st.session_state["ws_op_jump_tab"] = tab_idx
                                st.rerun()
                    else:
                        st.success("✅ Không có cảnh báo nào")
            except Exception as e:
                st.error(f"❌ Lỗi cảnh báo: {e}")

            # Phần nhiệm vụ
            st.markdown("**✅ Nhiệm vụ đang chờ**")
            try:
                nhiem_vu_list = db.doc_kv("nhiem_vu_list", [])
                if not nhiem_vu_list:
                    st.success("Không có nhiệm vụ nào đang chờ")
                else:
                    # Lọc nhiệm vụ của PGD hiện tại
                    nv_pgd = [nv for nv in nhiem_vu_list
                             if nv.get("pgd") == pgd_user and nv.get("trang_thai") != "hoan_thanh"]

                    if not nv_pgd:
                        st.success("Không có nhiệm vụ nào đang chờ")
                    else:
                        for nv in nv_pgd[:3]:
                            st.caption(f"📌 {nv.get('tieu_de', '—')}")
                            st.caption(f"Hạn: {nv.get('ngay_deadline', '—')}")
            except Exception as e:
                st.warning(f"⚠️ Không thể tải danh sách nhiệm vụ: {e}")


def _render_don_doc(df: pd.DataFrame, pgd_user: str, role: str):
    """
    Widget 3 tháng không hoạt động — dành cho CBTD địa bàn.
    Hiển thị bảng theo ĐVUT + xuất danh sách đôn đốc.
    """
    st.subheader("🔴 Món vay 3 tháng không hoạt động")
    st.caption("Lãi tồn > 3 tháng lãi dự thu — cần đôn đốc thu hồi trước khi phát sinh NQH")

    if df is None or df.empty:
        st.warning("Chưa có dữ liệu."); return

    # Đánh dấu 3 tháng không hoạt động
    df_kh = danh_dau_khong_hd_cached(df)
    n_khd = int(df_kh["is_3m_inactive"].sum()) if "is_3m_inactive" in df_kh.columns else 0
    n_tong = len(df_kh)

    # KPI
    k1, k2, k3 = st.columns(3)
    k1.metric("Tổng món vay", fmt_so(n_tong))
    k2.metric("Cần đôn đốc 🔴", fmt_so(n_khd),
              delta=f"{n_khd/n_tong*100:.1f}% tổng món" if n_tong > 0 else "0%",
              delta_color="inverse" if n_khd > 0 else "off")
    tong_lai = df_kh[df_kh.get("is_3m_inactive", False)][COT_LAI_TON].sum() \
               if COT_LAI_TON in df_kh.columns else 0
    k3.metric("Lãi tồn cần thu (triệu đồng)", fmt(tong_lai))

    if n_khd == 0:
        st.success("✅ Không có món vay nào quá 3 tháng không hoạt động!")
        return

    st.divider()

    # ── Bảng tổng hợp theo ĐVUT ───────────────────────────────────────────
    st.markdown("**Tổng hợp theo Hội đoàn thể (ĐVUT)**")
    nhom_dvut = tong_hop_khong_hd_cached(df_kh, nhom_theo=COT_DVUT)
    if not nhom_dvut.empty:
        hien_thi_dataframe_phan_trang(
            nhom_dvut,
            key="op_khd_nhom_dvut",
            height=220,
        )

    # Bảng theo Xã
    st.markdown("**Tổng hợp theo Xã/Phường**")
    nhom_xa = tong_hop_khong_hd_cached(df_kh, nhom_theo=COT_TEN_XA)
    if not nhom_xa.empty:
        hien_thi_dataframe_phan_trang(
            nhom_xa,
            key="op_khd_nhom_xa",
            height=220,
        )

    st.divider()

    # ── Danh sách chi tiết + xuất Excel ──────────────────────────────────
    st.markdown("**📋 Danh sách hộ cần đôn đốc**")
    col_loc, col_xuat = st.columns([2, 1])

    with col_loc:
        ds_dvut = ["Tất cả"]
        if COT_DVUT in df_kh.columns:
            ds_dvut += sorted(df_kh[COT_DVUT].dropna().unique().tolist())
        chon_dvut = st.selectbox("Lọc Hội đoàn thể", ds_dvut, key="op_khd_dvut")

    gia_tri = None if chon_dvut == "Tất cả" else chon_dvut
    df_dondoc = ds_chi_tiet_khong_hd(df_kh, nhom_theo=COT_DVUT,
                                      gia_tri_nhom=gia_tri)

    with col_xuat:
        st.markdown("<br>", unsafe_allow_html=True)
        if not df_dondoc.empty:
            from services.excel_service import xuat_excel_chuyen_nghiep, ten_file_xuat as excel_ten_file
            kpi_don_doc = [
                ("Số hộ KHĐ", fmt_so(len(df_dondoc)), f"Lọc: {chon_dvut}"),
            ]
            if COT_LAI_TON in df_dondoc.columns:
                kpi_don_doc.append(("Lãi tồn", fmt_ty(df_dondoc[COT_LAI_TON].sum()), "triệu đồng"))
            st.download_button(
                label=f"⬇️ Xuất Excel chuyên nghiệp ({len(df_dondoc)} hộ)",
                type="primary",
                data=xuat_excel_chuyen_nghiep(
                    df=df_dondoc,
                    title="Danh sách Đôn đốc 3 tháng KHĐ",
                    subtitle=f"PGD: {pgd_user} - {chon_dvut}",
                    nguoi_xuat=st.session_state.get("txt_username", ""),
                    kpi_items=kpi_don_doc,
                ),
                file_name=excel_ten_file("DonDoc_3m_KHD"),
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="op_xuat_khd_pro",
            )

    if not df_dondoc.empty:
        hien_thi_dataframe_phan_trang(
            df_dondoc,
            key="op_khd_dondoc",
            height=360,
        )
        tong_lai_ds = df_dondoc[COT_LAI_TON].sum() \
                      if COT_LAI_TON in df_dondoc.columns else 0
        st.caption(
            f"**{fmt_so(len(df_dondoc))}** món · "
            f"Lãi tồn: **{fmt(tong_lai_ds)}** triệu đồng"
        )

        # ── LoanDetailDrawer ───────────────────────────────────────────
        st.divider()
        st.markdown("**🔍 Tra cứu chi tiết khoản vay**")
        cols_chon = [c for c in [COT_SO_KU, COT_TEN_KH, COT_MA_KH] if c in df_dondoc.columns]
        if cols_chon:
            df_chon = df_dondoc.copy()
            df_chon["_hien_thi"] = df_chon[cols_chon[0]].astype(str)
            if len(cols_chon) > 1:
                for c in cols_chon[1:]:
                    df_chon["_hien_thi"] += " | " + df_chon[c].astype(str)
            options = dict(zip(df_chon["_hien_thi"], df_dondoc.index))
            selected_label = st.selectbox(
                "Chọn khoản vay để xem chi tiết",
                options=list(options.keys()),
                key="op_khd_chon_drawer",
            )
            if selected_label:
                row_idx = options[selected_label]
                row_data = df_dondoc.loc[row_idx]
                loan_detail_drawer(row_data)
    else:
        st.info("Không có hộ nào thỏa điều kiện.")


def _render_canh_bao_som_pgd(tab, **kwargs) -> None:
    """Cảnh báo sớm NQH cho phân hệ PGD."""
    from tabs import tab_canh_bao_som

    tab_canh_bao_som.render(tab, **kwargs)


def _banner_canh_bao_khd(df_pgd: pd.DataFrame, role: str) -> None:
    if df_pgd is None or df_pgd.empty:
        return
    df_kh = danh_dau_khong_hd_cached(df_pgd)
    n_khd = int(df_kh["is_3m_inactive"].sum()) if "is_3m_inactive" in df_kh.columns else 0
    if n_khd == 0:
        return
    du_no_khd = 0.0
    if COT_TONG_DU_NO in df_kh.columns and "is_3m_inactive" in df_kh.columns:
        du_no_khd = pd.to_numeric(
            df_kh.loc[df_kh["is_3m_inactive"], COT_TONG_DU_NO], errors="coerce"
        ).sum() / 1e6
    st.warning(
        f"⚠️ **{fmt_so(n_khd)} món vay 3 tháng không hoạt động** · "
        f"Dư nợ: **{du_no_khd:,.0f} triệu đồng** · "
        f"Vào nhóm **🔍 Kiểm soát & Rủi ro → Tab Đôn đốc KHĐ** để xem chi tiết.",
        icon="🔴",
    )


def _render_doc_hub(df: pd.DataFrame, df_nq11, role: str):
    """Module Trung tâm Tự động hóa Văn bản."""
    st.subheader("📄 Trung tâm Tự động hóa Văn bản")
    st.caption("Chọn hồ sơ → Chọn mẫu biểu → Tải về bản hoàn thiện tự động")

    templates = quet_templates(TEMPLATES_DIR)
    if not templates:
        st.warning(f"⚠️ Chưa có file mẫu nào trong thư mục `templates/`")
        st.info(
            "**Cách thêm mẫu biểu:**\n"
            f"1. Tạo file Word `.docx` với các tag như `{{{{ten_kh}}}}`, `{{{{so_ku}}}}` ...\n"
            f"2. Copy vào thư mục: `{TEMPLATES_DIR}`\n"
            "3. Reload trang là xuất hiện trong danh sách\n\n"
            "**Các tag hỗ trợ sẵn:**\n"
            + "\n".join(f"- `{tag}` → cột *{col}*" for tag, col in TAG_MAP.items())
        )
        return

    st.success(f"✅ Có **{len(templates)}** mẫu biểu sẵn sàng")

    st.markdown("**① Chọn đối tượng**")
    doi_tuong = st.radio(
        "Chọn đối tượng xuất văn bản",
        ["Từng hồ sơ khách hàng", "Theo Xã/Phường (xuất hàng loạt)"],
        horizontal=True, key="op_dh_doi_tuong", label_visibility="collapsed",
    )

    df_chon = None

    if doi_tuong == "Từng hồ sơ khách hàng":
        kw = st.text_input("🔍 Tìm khách hàng",
                           placeholder="Tên KH hoặc Số khế ước...", key="op_dh_kw")
        if kw:
            mask = df[[c for c in [COT_TEN_KH, COT_SO_KU, COT_MA_KH] if c in df.columns]]\
                     .astype(str).apply(lambda c: c.str.contains(kw, case=False, na=False)).any(axis=1)
            df_tim = df[mask]
            if df_tim.empty:
                st.warning("Không tìm thấy.")
            else:
                opts = (df_tim[COT_TEN_KH].astype(str) + "  —  " +
                        df_tim[COT_SO_KU].astype(str)) if COT_SO_KU in df_tim.columns \
                       else df_tim[COT_TEN_KH].astype(str)
                chon = st.multiselect("Chọn hồ sơ (có thể chọn nhiều)",
                                      opts.tolist(), key="op_dh_hs_sel")
                if chon:
                    idx_list = [opts.tolist().index(c) for c in chon]
                    df_chon  = df_tim.iloc[idx_list].reset_index(drop=True)
                    st.info(f"Đã chọn **{len(df_chon)}** hồ sơ")
    else:
        COT_XA = COT_TEN_XA
        if COT_XA in df.columns:
            ds_xa   = sorted(df[COT_XA].dropna().unique().tolist())
            chon_xa = st.selectbox("Chọn Xã/Phường", ds_xa, key="op_dh_xa")
            df_chon = df[df[COT_XA] == chon_xa].copy()
            st.info(f"Xã **{chon_xa}**: **{len(df_chon)}** hồ sơ")
        else:
            st.warning("Không tìm thấy cột Tên xã trong dữ liệu.")

    if df_chon is None or len(df_chon) == 0:
        st.info("👆 Chọn hồ sơ hoặc xã/phường để tiếp tục.")
        return

    st.markdown("**② Chọn mẫu biểu**")
    ten_mau_list  = [t[0] for t in templates]
    path_mau_list = [t[1] for t in templates]
    chon_mau_list = st.multiselect("Chọn 1 hoặc nhiều mẫu biểu",
                                   ten_mau_list, key="op_dh_mau_sel")

    with st.expander("📋 Xem tất cả mẫu biểu & tag hỗ trợ"):
        for ten, path in templates:
            st.markdown(f"**📄 {ten}**  `{path.name}`")
        st.markdown(
            "**📋 Biên bản giao ban xã** — `BB_giao_ban_xa_template.docx` "
            "(xuất Word tại sub-tab **📋 Biên bản giao ban**)."
        )
        st.divider()
        st.markdown("**Tag hỗ trợ trong file Word:**")
        for tag, col in TAG_MAP.items():
            st.caption(f"`{tag}` → {col}")

    if not chon_mau_list:
        st.info("👆 Chọn ít nhất 1 mẫu biểu.")
        return

    st.markdown("**③ Xuất văn bản**")
    che_do_xuat = st.radio(
        "Chế độ xuất",
        ["Mỗi hồ sơ 1 file riêng", "Gộp tất cả vào 1 file (hàng loạt)"],
        horizontal=True, key="op_dh_xuat_mode",
    ) if len(df_chon) > 1 else "Mỗi hồ sơ 1 file riêng"

    dh_ss_key = "_dh_docx_hub"
    if st.button("🖨️ Tạo văn bản", type="primary", key="dh_btn_xuat"):
        results = []
        for ten_mau in chon_mau_list:
            idx_mau  = ten_mau_list.index(ten_mau)
            path_mau = path_mau_list[idx_mau]
            if not path_mau.exists():
                st.error(f"Không tìm thấy file: {path_mau}"); continue
            try:
                if che_do_xuat == "Mỗi hồ sơ 1 file riêng":
                    for i, (_, row) in enumerate(df_chon.iterrows()):
                        ten_kh = str(row.get(COT_TEN_KH, f"hs_{i+1}"))
                        fname  = f"{path_mau.stem}_{ten_kh}_{datetime.today().strftime('%d%m%Y')}.docx"
                        data   = auto_fill_document(row, str(path_mau), TAG_MAP)
                        results.append((f"{ten_mau} — {ten_kh}", data, fname, f"dl_{ten_mau}_{i}"))
                else:
                    fname = f"{path_mau.stem}_batch_{datetime.today().strftime('%d%m%Y')}.docx"
                    data  = auto_fill_batch(df_chon, str(path_mau), TAG_MAP)
                    results.append((f"⬇ {ten_mau} — {len(df_chon)} hồ sơ (gộp)", data, fname, f"dl_batch_{ten_mau}"))
                st.success(f"✅ Đã tạo: **{ten_mau}**")
            except Exception as e:
                st.error(f"Lỗi tạo {ten_mau}: {e}")
        st.session_state[dh_ss_key] = results

    if st.session_state.get(dh_ss_key):
        for label, data, fname, key in st.session_state[dh_ss_key]:
            st.download_button(
                f"⬇ {label}", data=data, file_name=fname,
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                key=key,
            )


def _init_gb2_session_for_doc_hub(kwargs: dict) -> None:
    """
    Khởi tạo st.session_state gb2_xa / gb2_nam để tab Thông báo KL
    dùng chung lựa chọn với tab Biên bản (cùng key widget).
    """
    from config import (
        danh_sach_nam_baseline,
        danh_sach_nam_baseline_pgd,
    )

    df = kwargs.get("df")
    role = kwargs.get("role")
    pgd_user = kwargs.get("pgd_user")
    if df is None or df.empty:
        return
    if is_pgd_role(role) and pgd_user and COT_TEN_PGD in df.columns:
        df = df[df[COT_TEN_PGD] == pgd_user].copy()
    if COT_TEN_XA not in df.columns:
        return
    ds_xa = sorted(df[COT_TEN_XA].dropna().unique().tolist())
    if not ds_xa:
        return
    if "gb2_xa" not in st.session_state or st.session_state.gb2_xa not in ds_xa:
        st.session_state.gb2_xa = ds_xa[0]
    ds_nam = danh_sach_nam_baseline_pgd() or danh_sach_nam_baseline()
    if ds_nam and (
        "gb2_nam" not in st.session_state or st.session_state.gb2_nam not in ds_nam
    ):
        st.session_state.gb2_nam = ds_nam[0]


def _render_thong_bao_ket_luan(tab, **kwargs):
    """Tab xuất Thông báo Kết luận giao ban (NĐ30) — dùng gb2_xa / gb2_nam từ tab Biên bản."""
    from config import (
        danh_sach_nam_baseline,
        danh_sach_nam_baseline_pgd,
        baseline_pgd_path,
        DON_VI_CHI_NHANH,
    )
    from data.hstd import doc_baseline_merged
    from data.giao_ban import xuat_thong_bao_ket_luan_giao_ban

    ctx = tab if tab is not None else st
    df = kwargs.get("df")
    pgd_user = kwargs.get("pgd_user")
    role = kwargs.get("role")

    with ctx:
        st.subheader("📢 Thông báo Kết luận Giao ban")
        st.caption(
            "Xuất Thông báo kết luận họp giao ban tháng "
            "tại điểm giao dịch — chuẩn thể thức NĐ30/2020"
        )

        if df is None or df.empty:
            st.warning("⚠️ Chưa có dữ liệu HSTD.")
            return
        if is_pgd_role(role) and pgd_user and COT_TEN_PGD in df.columns:
            df = df[df[COT_TEN_PGD] == pgd_user].copy()

        ds_xa = sorted(df[COT_TEN_XA].dropna().unique().tolist())
        if not ds_xa:
            st.warning("Không có cột Tên xã.")
            return

        default_xa = st.session_state.get("gb2_xa", ds_xa[0] if ds_xa else None)
        if default_xa not in ds_xa:
            default_xa = ds_xa[0] if ds_xa else None
        chon_xa = st.selectbox(
            "Chọn xã / điểm giao dịch",
            ds_xa,
            index=ds_xa.index(default_xa) if default_xa in ds_xa else 0,
            key="op_tb_chon_xa",
        )
        st.session_state["gb2_xa"] = chon_xa

        ds_nam = danh_sach_nam_baseline_pgd() or danh_sach_nam_baseline()
        chon_nam = st.session_state.get("gb2_nam")
        if ds_nam and chon_nam not in ds_nam:
            chon_nam = ds_nam[0]
        df_bl = None
        if ds_nam and chon_nam is not None:
            fp_check = baseline_pgd_path(
                DON_VI_CHI_NHANH if not pgd_user else pgd_user, chon_nam
            )
            _ts = os.path.getmtime(fp_check) if os.path.exists(fp_check) else 0
            df_bl = doc_baseline_merged(chon_nam, _ts=_ts)

        col_a, col_b = st.columns(2)
        with col_a:
            tb_dgd = st.text_input(
                "Tên điểm giao dịch",
                value=chon_xa,
                key="op_tb_ten_dgd",
                help="Mặc định là tên xã, chỉnh lại nếu khác",
            )
            tb_ngay = st.date_input("Ngày họp", value=date.today(), format="DD/MM/YYYY", key="op_tb_ngay_hop")
        with col_b:
            tb_so_vb = st.text_input(
                "Số văn bản",
                placeholder="VD: 05",
                key="op_tb_so_van_ban",
                help="Phần số trong 'Số: .../TB-KLGB'",
            )
            tb_ten_ky = st.text_input(
                "Tên người ký",
                placeholder="VD: Nguyễn Văn A",
                key="op_tb_ten_nguoi_ky",
                help="Tên Phó Giám đốc ký văn bản",
            )

        # Preview số liệu tự động
        from config import COT_LAI_TON_QH, COT_SO_DU_TG
        df_xa_preview = df[df[COT_TEN_XA] == chon_xa].copy()
        if not df_xa_preview.empty:
            dn_prev = pd.to_numeric(df_xa_preview[COT_TONG_DU_NO], errors="coerce").sum() / 1e6
            nqh_prev = pd.to_numeric(df_xa_preview[COT_DU_NO_QH], errors="coerce").sum() / 1e6
            lai_prev = (
                pd.to_numeric(df_xa_preview.get(COT_LAI_TON, 0), errors="coerce").sum()
                + pd.to_numeric(df_xa_preview.get(COT_LAI_TON_QH, 0), errors="coerce").sum()
            ) / 1e6
            tg_prev = pd.to_numeric(df_xa_preview.get(COT_SO_DU_TG, 0), errors="coerce").sum() / 1e6
            st.info(
                f"📊 **Số liệu tự động — {chon_xa}**\n\n"
                f"Dư nợ: **{fmt(dn_prev * 1e6)}** triệu · "
                f"NQH: **{fmt(nqh_prev * 1e6)}** triệu · "
                f"Lãi tồn: **{fmt(lai_prev * 1e6)}** triệu · "
                f"Tiền gửi TK: **{fmt(tg_prev * 1e6)}** triệu"
            )

        # Giải ngân kế hoạch tháng tới
        from dateutil.relativedelta import relativedelta
        from config import COT_TEN_TO
        thang_toi = date.today() + relativedelta(months=1)
        ngay_dh_col = "Ngày ĐH theo Gia hạn" if "Ngày ĐH theo Gia hạn" in df_xa_preview.columns else COT_NGAY_DH
        mask_dh = (
            pd.to_datetime(df_xa_preview[ngay_dh_col], errors="coerce").dt.month == thang_toi.month
        ) & (
            pd.to_datetime(df_xa_preview[ngay_dh_col], errors="coerce").dt.year == thang_toi.year
        )
        df_dh_prev = df_xa_preview[mask_dh].copy()
        giai_ngan_input = {}
        with st.expander("💰 Nhập số giải ngân dự kiến tháng tới (tùy chọn)"):
            st.caption("Để trống nếu chưa xác định. Nhập theo đơn vị triệu đồng.")
            if not df_dh_prev.empty and COT_TEN_TO in df_dh_prev.columns:
                for (dvut, to, ct), grp in df_dh_prev.groupby([COT_DVUT, COT_TEN_TO, COT_TEN_CT]):
                    val = st.number_input(
                        f"{to} — {ct}",
                        min_value=0.0,
                        value=0.0,
                        step=1.0,
                        format="%.0f",
                        key=f"op_gn_{dvut}_{to}_{ct}",
                        help="Triệu đồng",
                    )
                    if val > 0:
                        giai_ngan_input[(dvut, to, ct)] = val * 1e6
            else:
                st.caption("Không có món đến hạn tháng tới hoặc chưa có dữ liệu.")
                giai_ngan_input = None

        tb_cs = st.text_area(
            "I. Chính sách mới trong tháng",
            placeholder="Để trống nếu không có chính sách mới...",
            height=100,
            key="op_tb_chinh_sach",
        )
        tb_tt = st.text_area(
            "II.2 Tồn tại, hạn chế",
            placeholder="Nêu cụ thể tồn tại của Hội, Tổ, khách hàng...",
            height=120,
            key="op_tb_ton_tai",
        )
        tb_nv = st.text_area(
            "III. Nhiệm vụ tháng tiếp theo",
            placeholder="Kế hoạch kiểm tra, xử lý nợ xấu, nội dung khác...",
            height=120,
            key="op_tb_nhiem_vu",
        )

        if st.button("🖨️ Xuất Thông báo Kết luận Word", type="primary", key="tb_xuat"):
            df_xa_tb = df[df[COT_TEN_XA] == chon_xa].copy()
            try:
                data = xuat_thong_bao_ket_luan_giao_ban(
                    df_xa=df_xa_tb,
                    ten_pgd=pgd_user or "",
                    ten_xa=chon_xa,
                    ten_dgd=tb_dgd or chon_xa,
                    thang_bao_cao=date.today().month,
                    nam_bao_cao=date.today().year,
                    ngay_hop=tb_ngay.strftime("%d/%m/%Y"),
                    chinh_sach_moi=tb_cs,
                    ton_tai_han_che=tb_tt,
                    nhiem_vu_tiep=tb_nv,
                    so_van_ban=tb_so_vb,
                    ten_nguoi_ky=tb_ten_ky,
                    giai_ngan_input=giai_ngan_input,
                    df_baseline=df_bl,
                    nam_moc=chon_nam or date.today().year - 1,
                )
                ten_file = (
                    f"TB_KetLuan_{chon_xa.replace(' ', '_')}"
                    f"_{date.today().strftime('%m%Y')}.docx"
                )
                st.session_state["tb_data"] = data
                st.session_state["tb_ten_file"] = ten_file
                st.success("✅ Đã tạo Thông báo Kết luận! Nhấn nút bên dưới để tải về.")

            except Exception as e:
                st.error(f"❌ Lỗi tạo file: {e}")

        if st.session_state.get("tb_data"):
            st.download_button(
                "⬇️ Tải về Word",
                data=st.session_state["tb_data"],
                file_name=st.session_state["tb_ten_file"],
                mime="application/vnd.openxmlformats-officedocument"
                ".wordprocessingml.document",
                key="tb_dl_word",
            )

        if st.session_state.get("tb_data") and st.button("📄 Xuất PDF", type="primary", key="tb_xuat_pdf"):
            try:
                import tempfile, os
                from docx2pdf import convert
                data_pdf = st.session_state["tb_data"]
                ten_file_pdf = st.session_state["tb_ten_file"]
                with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
                    tmp.write(data_pdf)
                    tmp_path = tmp.name
                pdf_path = tmp_path.replace(".docx", ".pdf")
                convert(tmp_path, pdf_path)
                with open(pdf_path, "rb") as f:
                    pdf_bytes = f.read()
                os.unlink(tmp_path)
                os.unlink(pdf_path)
                ten_pdf = ten_file_pdf.replace(".docx", ".pdf")
                st.session_state["_tb_pdf_bytes"] = pdf_bytes
                st.session_state["_tb_pdf_file"] = ten_pdf
            except ImportError:
                st.warning("⚠️ Chưa cài docx2pdf. Chạy: pip install docx2pdf")
                st.info("💡 Mở file Word rồi chọn **Save As → PDF** thủ công.")
                st.session_state["_tb_pdf_bytes"] = None
            except Exception as _e_pdf:
                st.error(f"❌ Lỗi chuyển PDF: {_e_pdf}")
                st.session_state["_tb_pdf_bytes"] = None

        if st.session_state.get("_tb_pdf_bytes"):
            st.download_button(
                "⬇️ Tải về PDF",
                data=st.session_state["_tb_pdf_bytes"],
                file_name=st.session_state.get("_tb_pdf_file", "output.pdf"),
                mime="application/pdf",
                key="tb_dl_pdf",
            )


def _render_bien_ban_giao_ban(tab, **kwargs):
    ctx = tab if tab is not None else st
    from config import (danh_sach_nam_baseline, baseline_path, TEMPLATES_DIR,
                        baseline_pgd_path, danh_sach_nam_baseline_pgd,
                        trang_thai_baseline_pgd, DON_VI_CHI_NHANH)
    from data.hstd import doc_baseline_merged
    from data.giao_ban import xuat_bien_ban_giao_ban
    from datetime import date

    df = kwargs.get("df")
    pgd_user = kwargs.get("pgd_user")
    role = kwargs.get("role")

    if df is not None and not df.empty and is_pgd_role(role) and pgd_user and COT_TEN_PGD in df.columns:
        df = df[df[COT_TEN_PGD] == pgd_user].copy()

    with ctx:
        st.subheader("📋 Biên bản họp giao ban xã")

        if df is None or df.empty:
            st.warning("Chưa có dữ liệu HSTD.")
            return

        # 1. Chọn xã thuộc PGD
        ds_xa = sorted(df[COT_TEN_XA].dropna().unique().tolist())
        chon_xa = st.selectbox("Chọn xã / điểm giao dịch", ds_xa,
                               key="op_gb2_xa")

        # 2. Chọn năm mốc so sánh — dùng doc_baseline_merged() để tổng hợp từ 22 đơn vị
        ds_nam = danh_sach_nam_baseline_pgd()
        if not ds_nam:
            ds_nam = danh_sach_nam_baseline()  # fallback năm cũ
        if not ds_nam:
            st.info("ℹ️ Chưa có dữ liệu mốc 31/12. "
                    "Vẫn xuất được — cột so sánh đầu năm sẽ trống.")
            chon_nam = None
            df_bl = None
        else:
            chon_nam = st.selectbox(
                "So sánh với mốc năm", ds_nam,
                format_func=lambda n: f"31/12/{n}",
                key="op_gb2_nam")
            # Đọc dữ liệu đã merge từ tất cả đơn vị
            fp_check = baseline_pgd_path(DON_VI_CHI_NHANH if not pgd_user else pgd_user, chon_nam)
            _ts = os.path.getmtime(fp_check) if os.path.exists(fp_check) else 0
            df_bl = doc_baseline_merged(chon_nam, _ts=_ts)

        # 3. Nhập giải ngân (tuỳ chọn)
        with st.expander("✏️ Nhập kế hoạch giải ngân tháng tới (tuỳ chọn)"):
            st.caption("Để trống nếu chưa có kế hoạch.")
            gn_tong = st.number_input(
                "Tổng giải ngân dự kiến (triệu đồng)", min_value=0.0,
                step=1.0, key="op_gb2_gn")
            # Đơn giản: nhập 1 số tổng — code điền vào dòng Cộng
            # Nếu sau này cần chi tiết theo Tổ thì mở rộng thêm

        # 4. Xuất
        template = str(TEMPLATES_DIR / "BB_giao_ban_xa_template.docx")
        if not os.path.exists(template):
            st.error("Chưa có file template BB_giao_ban_xa_template.docx "
                     "trong thư mục templates/")
            return

        if st.button("🖨️ Xuất Biên bản Word", type="primary", key="gb2_xuat"):
            df_xa = df[df[COT_TEN_XA] == chon_xa].copy()
            gn_input = {"__tong__": gn_tong * 1_000_000} if gn_tong > 0 else None
            try:
                data = xuat_bien_ban_giao_ban(
                    df_xa=df_xa,
                    df_baseline=df_bl,
                    nam_moc=chon_nam or date.today().year - 1,
                    template_path=template,
                    giai_ngan_input=gn_input,
                )
                thang = date.today().strftime("%m%Y")
                ten_file = f"BB_GiaoBan_{chon_xa.replace(' ','_')}_{thang}.docx"
                st.session_state["_bytes_gb2"] = data
                st.session_state["_file_gb2"] = ten_file
                st.success("✅ Đã tạo biên bản! Nhấn nút bên dưới để tải về.")
            except Exception as e:
                st.error(f"❌ Lỗi xuất file: {e}")
                st.exception(e)

        if st.session_state.get("_bytes_gb2"):
            st.download_button(
                "⬇️ Tải về Word",
                data=st.session_state["_bytes_gb2"],
                file_name=st.session_state["_file_gb2"],
                mime="application/vnd.openxmlformats-officedocument"
                     ".wordprocessingml.document",
                key="gb2_dl_word",
            )


def _render_bao_cao_giao_ban(tab, **kwargs):
    """
    Render tab Báo cáo Giao ban - tạo báo cáo tổng hợp theo xã với bảng tóm tắt theo ĐVUT.
    """
    ctx = tab if tab is not None else st
    with ctx:
        st.subheader("📝 Báo cáo Giao ban")
        st.caption("Tổng hợp tình hình dư nợ, cho vay, thu nợ theo ĐVUT và Xã")
        
        df = kwargs.get("df")
        pgd_user = kwargs.get("pgd_user")
        role = kwargs.get("role")
        
        if df is None or df.empty:
            st.warning("Chưa có dữ liệu HSTD.")
            return
        
        # ① Bộ lọc
        st.markdown("**① Bộ lọc dữ liệu**")
        
        # Lọc theo PGD
        df_filtered = df.copy()
        if is_pgd_role(role) and pgd_user:
            if COT_TEN_PGD in df.columns:
                df_filtered = df[df[COT_TEN_PGD] == pgd_user].copy()
            st.info(f"Dữ liệu đã lọc theo PGD: **{pgd_user}**")
        elif is_cn_role(role):
            if COT_TEN_PGD in df.columns:
                ds_pgd = sorted(df[COT_TEN_PGD].dropna().unique().tolist())
                if ds_pgd:
                    chon_pgd = st.selectbox("Chọn Phòng Giao dịch", ds_pgd, key="op_gb_pgd")
                    df_filtered = df[df[COT_TEN_PGD] == chon_pgd].copy()
        
        # Chọn Xã
        if COT_TEN_XA in df_filtered.columns:
            ds_xa = sorted(df_filtered[COT_TEN_XA].dropna().unique().tolist())
            if not ds_xa:
                st.warning("Không có dữ liệu xã nào trong PGD được chọn.")
                return
            chon_xa = st.selectbox("Chọn Xã/Phường", ds_xa, key="op_gb_xa")
            df_xa = df_filtered[df_filtered[COT_TEN_XA] == chon_xa].copy()
        else:
            st.warning("Không tìm thấy cột 'Tên xã' trong dữ liệu.")
            return
        
        if df_xa.empty:
            st.warning(f"Không có dữ liệu cho xã **{chon_xa}**")
            return

        # Chọn điểm giao dịch
        import db
        dgd_map = db.doc_dgd_map()
        
        # Lấy PGD hiện tại
        current_pgd = pgd_user if is_pgd_role(role) else (
            chon_pgd if 'chon_pgd' in locals() else pgd_user
        )
        
        ds_dgd = []
        chon_dgd = None
        ds_thon_dgd = None
        ten_dgd = None
        
        if current_pgd and current_pgd in dgd_map and chon_xa in dgd_map[current_pgd]:
            ds_dgd = list(dgd_map[current_pgd][chon_xa].keys())
        
        if not ds_dgd:
            st.info(
                "⚠️ Xã này chưa cấu hình điểm giao dịch. "
                "Vào tab **📍 Điểm GD của tôi** để thêm/cập nhật."
            )
            # Vẫn cho phép tiếp tục - lọc theo toàn xã
            chon_dgd = None
            ds_thon_dgd = None
            df_dgd = df_xa.copy()
            ten_dgd = chon_xa
        else:
            chon_dgd = st.selectbox("📍 Điểm giao dịch", ds_dgd, key="op_gb_dgd")
            ds_thon_dgd = dgd_map[current_pgd][chon_xa][chon_dgd]
            ten_dgd = chon_dgd
            st.caption(f"Quản lý: {', '.join(ds_thon_dgd)}")
            
            # Lọc df theo thôn/ấp của điểm giao dịch
            if "Tên thôn" in df_xa.columns:
                df_dgd = df_xa[df_xa["Tên thôn"].isin(ds_thon_dgd)].copy()
            else:
                df_dgd = df_xa.copy()
                st.warning("Không tìm thấy cột 'Tên thôn' để lọc theo điểm giao dịch.")
        
        if df_dgd.empty:
            st.warning(f"Không có dữ liệu cho điểm giao dịch **{chon_dgd or chon_xa}**")
            return
        
        st.divider()
        
        # ② Bảng tổng hợp theo ĐVUT
        st.markdown("**② Tổng hợp theo ĐVUT**")
        
        # Đánh dấu khách hàng 3 tháng không hoạt động
        df_dgd_marked = danh_dau_khong_hd_cached(df_dgd)
        
        # Groupby theo Tên ĐVUT
        if COT_DVUT not in df_dgd.columns:
            st.warning("Không tìm thấy cột 'Tên ĐVUT' trong dữ liệu.")
            return
        
        # Tính toán các cột
        agg_dict = {
            "Số Tổ": ("Tên tổ", lambda x: x.nunique() if "Tên tổ" in df_dgd.columns else 0),
            "Số KH": (COT_MA_KH, lambda x: x.nunique()),
            "Tổng dư nợ": (COT_TONG_DU_NO, lambda x: pd.to_numeric(x, errors="coerce").fillna(0).sum()),
            "Nợ quá hạn": (COT_DU_NO_QH, lambda x: pd.to_numeric(x, errors="coerce").fillna(0).sum()),
        }
        
        # Thêm các cột có điều kiện
        if "Giải ngân trong tháng" in df_dgd.columns:
            agg_dict["Doanh số cho vay tháng"] = ("Giải ngân trong tháng", 
                lambda x: pd.to_numeric(x, errors="coerce").fillna(0).sum())
        
        # Tính doanh số thu nợ (cộng 3 cột nếu có)
        thu_no_cols = ["Thu nợ TH tháng", "Thu nợ QH tháng", "Thu nợ khoanh tháng"]
        existing_thu_no_cols = [col for col in thu_no_cols if col in df_dgd.columns]
        if existing_thu_no_cols:
            for col in existing_thu_no_cols:
                df_dgd[col] = pd.to_numeric(df_dgd[col], errors="coerce").fillna(0)
            df_dgd["Tổng thu nợ tháng"] = df_dgd[existing_thu_no_cols].sum(axis=1)
            agg_dict["Doanh số thu nợ tháng"] = ("Tổng thu nợ tháng", "sum")
        
        if "Dư nợ khoanh" in df_dgd.columns:
            agg_dict["Nợ khoanh"] = ("Dư nợ khoanh", 
                lambda x: pd.to_numeric(x, errors="coerce").fillna(0).sum())
        
        # Số khoản 3m KHĐ
        if "is_3m_inactive" in df_dgd_marked.columns:
            df_dgd["is_3m_inactive"] = df_dgd_marked["is_3m_inactive"]
            agg_dict["Số khoản 3m KHĐ"] = ("is_3m_inactive", "sum")
        
        # Tạo bảng tổng hợp - chỉ sử dụng những cột thực sự tồn tại
        valid_agg_dict = {}
        for col_name, (data_col, agg_func) in agg_dict.items():
            if data_col in df_dgd.columns:
                valid_agg_dict[data_col] = agg_func
        
        if valid_agg_dict and COT_DVUT in df_dgd.columns:
            df_bang = df_dgd.groupby(COT_DVUT).agg(valid_agg_dict).reset_index()
            
            # Đổi tên cột về tên hiển thị
            rename_dict = {}
            for col_name, (data_col, agg_func) in agg_dict.items():
                if data_col in df_dgd.columns and data_col in df_bang.columns:
                    rename_dict[data_col] = col_name
            df_bang = df_bang.rename(columns=rename_dict)
        else:
            # Tạo DataFrame rỗng với cấu trúc cơ bản
            df_bang = pd.DataFrame({COT_DVUT: []})
        
        # Tính tỷ trọng %
        if "Tổng dư nợ" in df_bang.columns and df_bang["Tổng dư nợ"].sum() > 0:
            df_bang["Tỷ trọng %"] = (df_bang["Tổng dư nợ"] / df_bang["Tổng dư nợ"].sum() * 100).round(1)
        
        # Thêm dòng Cộng
        dong_cong = {COT_DVUT: "CỘNG"}
        for col in df_bang.columns:
            if col != COT_DVUT:
                if col == "Tỷ trọng %":
                    dong_cong[col] = 100.0
                else:
                    dong_cong[col] = df_bang[col].sum()
        
        df_bang = pd.concat([df_bang, pd.DataFrame([dong_cong])], ignore_index=True)
        
        # Định dạng hiển thị (chia triệu đồng cho các cột tiền)
        df_display = df_bang.copy()
        tien_cols = ["Tổng dư nợ", "Nợ quá hạn", "Nợ khoanh", "Doanh số cho vay tháng", "Doanh số thu nợ tháng"]
        for col in tien_cols:
            if col in df_display.columns:
                df_display[col] = (df_display[col] / 1e6).round(1)
        
        hien_thi_dataframe_phan_trang(df_display, key="op_bao_cao_dvut_bang")
        
        # Ghi chú đơn vị
        st.caption("*Đơn vị tiền: triệu đồng*")
        
        st.divider()
        
        # ③ Đoạn tóm tắt văn bản
        st.markdown("**③ Tóm tắt báo cáo**")
        
        # Lấy các số liệu từ dòng Cộng
        dong_cong_data = df_bang[df_bang[COT_DVUT] == "CỘNG"].iloc[0]
        
        tong_dn = dong_cong_data.get("Tổng dư nợ", 0) / 1e6
        so_kh = int(dong_cong_data.get("Số KH", 0))
        so_to = int(dong_cong_data.get("Số Tổ", 0))
        nqh = dong_cong_data.get("Nợ quá hạn", 0) / 1e6
        nkh = dong_cong_data.get("Nợ khoanh", 0) / 1e6
        ds_cv = dong_cong_data.get("Doanh số cho vay tháng", 0) / 1e6
        ds_thu = dong_cong_data.get("Doanh số thu nợ tháng", 0) / 1e6
        
        tl_nqh = (nqh / tong_dn * 100) if tong_dn > 0 else 0
        
        # Thông tin khu vực
        khu_vuc_text = f"{ten_dgd}"
        if ds_thon_dgd:
            khu_vuc_text += f" (gồm: {', '.join(ds_thon_dgd)})"
        
        tom_tat = f"""Khu vực {khu_vuc_text}, xã {chon_xa}: Tổng dư nợ đạt {tong_dn:,.0f} triệu đồng, với {fmt_so(so_kh)} khách hàng còn dư nợ, thông qua {so_to} Tổ TK&VV. Trong đó, nợ quá hạn {nqh:,.0f} triệu đồng, tỷ lệ {tl_nqh:.2f}%; nợ khoanh {nkh:,.0f} triệu đồng.
Doanh số cho vay trong tháng: {ds_cv:,.0f} triệu đồng; doanh số thu nợ trong tháng: {ds_thu:,.0f} triệu đồng."""
        
        st.text_area("📋 Đoạn tóm tắt (copy vào báo cáo)",
                     value=tom_tat,
                     height=150,
                     key="op_gb_tom_tat")
        
        st.divider()
        
        # ④ Xuất báo cáo
        st.markdown("**④ Xuất báo cáo**")
        
        _pdf_dep = kiem_tra_pdf_dependency()
        if not _pdf_dep["reportlab"]:
            for msg in _pdf_dep["messages"]:
                st.warning(msg)
        
        cols_xuat = [c for c in df_bang.columns if c != "Tỷ trọng %"] or list(df_bang.columns)
        
        col_excel, col_pdf = st.columns([1, 1])
        with col_excel:
            st.download_button(
                label="⬇️ Xuất Excel chuyên nghiệp",
                type="primary",
                data=xuat_excel_chuyen_nghiep(
                    df=df_bang,
                    title="Báo cáo Giao ban",
                    subtitle=f"Xã {chon_xa} · {ten_dgd or ''} · {datetime.now().strftime('%d/%m/%Y')}",
                    nguoi_xuat=st.session_state.get("txt_username", ""),
                    columns=cols_xuat,
                    kpi_items=[
                        ("Điểm GD", ten_dgd or chon_xa, ""),
                        ("Tổng dư nợ", fmt_ty(tong_dn * 1e6) if tong_dn > 0 else "—", "triệu đồng"),
                        ("Số khách hàng", fmt_so(so_kh) if so_kh > 0 else "—", ""),
                        ("Nợ quá hạn", fmt_ty(nqh * 1e6) if nqh > 0 else "—", "triệu đồng"),
                        ("Tỷ lệ NQH", f"{tl_nqh:.2f}%" if tl_nqh > 0 else "0%", ""),
                        ("Doanh số cho vay", fmt_ty(ds_cv * 1e6) if ds_cv > 0 else "—", "triệu đồng"),
                        ("Doanh số thu nợ", fmt_ty(ds_thu * 1e6) if ds_thu > 0 else "—", "triệu đồng"),
                    ],
                ),
                file_name=f"GiaoBan_{chon_xa}_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="gb_download",
                use_container_width=True,
            )
        with col_pdf:
            cols_tien_gb = [c for c in ["Tổng dư nợ", "Nợ quá hạn", "Nợ khoanh", "Doanh số cho vay tháng", "Doanh số thu nợ tháng"] if c in df_bang.columns]
            import plotly.express as px
            df_chart = df_bang[df_bang[COT_DVUT] != "CỘNG"].copy()
            fig_list = []
            if not df_chart.empty and "Tổng dư nợ" in df_chart.columns:
                fig_dn = px.bar(
                    df_chart, x=COT_DVUT, y="Tổng dư nợ",
                    title="Tổng dư nợ theo ĐVUT",
                    text_auto=".1s", color_discrete_sequence=["#2E7D32"],
                )
                fig_dn.update_layout(xaxis_title="", yaxis_title="Triệu đồng")
                fig_list.append((fig_dn, "Tổng dư nợ theo ĐVUT"))
            if "Nợ quá hạn" in df_chart.columns:
                fig_nqh = px.bar(
                    df_chart, x=COT_DVUT, y="Nợ quá hạn",
                    title="Nợ quá hạn theo ĐVUT",
                    text_auto=".1s", color_discrete_sequence=["#E53935"],
                )
                fig_nqh.update_layout(xaxis_title="", yaxis_title="Triệu đồng")
                fig_list.append((fig_nqh, "Nợ quá hạn theo ĐVUT"))

            download_pdf_button(
                pdf_bytes=xuat_pdf_co_chart(
                    df=df_bang,
                    tieu_de=f"Báo cáo Giao ban - {chon_xa}",
                    nguoi_xuat=st.session_state.get("txt_username", ""),
                    figs=fig_list if fig_list else None,
                    cols_tien=cols_tien_gb,
                    prefix_file="GiaoBan",
                    them_dong_tong=False,
                ),
                filename=f"GiaoBan_{chon_xa}_{datetime.now().strftime('%Y%m%d')}.pdf",
                label=f"📥 Tải PDF ({len(df_bang)} dòng)",
                key="gb_pdf_download_v2",
            )


def render(**kwargs):
    _wl = st.session_state.pop("_data_load_warning", None)
    if _wl:
        st.warning(_wl)

    # ── Lazy import tab modules ──────────────────────────────────────────
    from tabs import (
        tab_tracuu, tab_danhsach,
        tab_khtd_pgd, tab_nhiem_vu, tab_upload_pgd,
        tab_cdtotkvv_pgd, tab_khtd_mau07, tab_khtd_giao_dc,
        tab_diem_gd_pgd, tab_ban_dai_dien,
        tab_tongquan, tab_tien_do, tab_baocao,
        tab_nq11, tab_candoi, tab_uy_thac, tab_qd62,
        tab_trang_thai_nguon, tab_so_sanh_ky,
        tab_no_khoanh,
    )
    from tabs.tab_den_han import render as render_den_han

    df = kwargs.get("df")
    df_nq11 = kwargs.get("df_nq11")
    role = kwargs.get("role")
    pgd_user = kwargs.get("pgd_user")

    st.title("🗺️ Hỗ Trợ Địa Bàn PGD/Biên Hòa")
    st.caption("Tra cứu hồ sơ · Danh sách · Báo cáo giao ban · Văn bản tự động · Nhiệm vụ · Upload dữ liệu")

    # ── Phân quyền tab theo role ─────────────────────────────────────────
    tab_perm = get_tab_permissions(role)
    nhom_duoc_phep = tab_perm["nhom_duoc_phep"]

    # Dropdown chọn PGD cho admin_cn/manager_cn — hiển thị trước tabs
    pgd_filter: str | None = None
    if is_cn_role(role) and pgd_user is None and df is not None and COT_TEN_PGD in df.columns:
        ds_pgd_all: list = kwargs.get("ds_pgd_all", [])
        _pgd_filter_val = st.selectbox(
            "🔎 Xem theo PGD",
            ["Toàn Chi nhánh"] + ds_pgd_all,
            key="ws_op_pgd_filter",
        )
        if _pgd_filter_val != "Toàn Chi nhánh":
            pgd_filter = _pgd_filter_val

    # Lọc df theo PGD
    if is_pgd_role(role) and pgd_user and df is not None and COT_TEN_PGD in df.columns:
        df_pgd = df[df[COT_TEN_PGD] == pgd_user].copy()
    elif is_cn_role(role) and pgd_filter is not None and df is not None and COT_TEN_PGD in df.columns:
        df_pgd = df[df[COT_TEN_PGD] == pgd_filter].copy()
    else:
        df_pgd = df
    _pgd_df_kwargs = {**kwargs, "df": df_pgd, "df_full": df_pgd, "pgd_filter": pgd_filter}

    _banner_canh_bao_khd(df_pgd, role)

    # ── KPI Dashboard (4 cards) ─────────────────────────────────────────
    try:
        kpi_data = _kpi_pgd_list(df_pgd, pgd_user or pgd_filter or "")
        if kpi_data:
            kpi_row(kpi_data, num_columns=4)
            st.divider()
    except Exception:
        pass

    # ── Helpers render ──────────────────────────────────────────────────
    def _render_diem_gd_va_to_tkvv(tab_parent, **kw):
        with get_tab_context(tab_parent):
            _sub1, _sub2 = st.tabs(["📍 Điểm Giao Dịch", "🏘️ Tổ TK&VV"])
            tab_diem_gd_pgd.render(_sub1, **kw)
            tab_cdtotkvv_pgd.render(_sub2, **kw)

    def _render_du_phong_dong_tien(tab_parent, **kw) -> None:
        with get_tab_context(tab_parent):
            from services.du_phong_service import du_phong_dong_tien, du_phong_chi_tiet
            from dateutil.relativedelta import relativedelta

            df_loc = kw.get("df")
            pgd = kw.get("pgd_user") or kw.get("pgd_filter") or ""

            st.subheader("📈 Dự phóng Doanh số & Kế hoạch Dòng tiền")

            if df_loc is None or df_loc.empty:
                st.info("Chưa có dữ liệu HSTD.")
                return

            if pgd:
                st.caption(f"📍 Địa bàn: **{pgd}**")

            hom_nay = datetime.now().date()
            thang_ht = date(hom_nay.year, hom_nay.month, 1)

            col_xa, col_ct = st.columns(2)
            with col_xa:
                ds_xa = ["Tất cả"] + sorted(df_loc[COT_TEN_XA].dropna().unique().tolist()) if COT_TEN_XA in df_loc.columns else ["Tất cả"]
                loc_xa = st.selectbox("🏘️ Xã", ds_xa, key="op_dp_xa")
            with col_ct:
                ds_ct = ["Tất cả"] + sorted(df_loc[COT_TEN_CT].dropna().unique().tolist()) if COT_TEN_CT in df_loc.columns else ["Tất cả"]
                loc_ct = st.selectbox("📌 Chương trình", ds_ct, key="op_dp_ct")

            df_work = df_loc.copy()
            if loc_xa != "Tất cả" and COT_TEN_XA in df_work.columns:
                df_work = df_work[df_work[COT_TEN_XA] == loc_xa]
            if loc_ct != "Tất cả" and COT_TEN_CT in df_work.columns:
                df_work = df_work[df_work[COT_TEN_CT] == loc_ct]

            if df_work.empty:
                st.info("Không có dữ liệu phù hợp với bộ lọc.")
                return

            df_dp = du_phong_dong_tien(df_work)

            if df_dp.empty:
                st.warning("⚠️ Không đủ dữ liệu Ngày vay / Ngày ĐH để dự phóng.")
                return

            # Chia 2 phần: tháng đã qua và tháng tương lai
            df_qua = df_dp[df_dp["thang"] < thang_ht].copy()
            df_lai = df_dp[df_dp["thang"] >= thang_ht].copy()

            tong_goc_qua = df_qua["du_kien_thu_goc"].sum() if not df_qua.empty else 0
            tong_goc_lai = df_lai["du_kien_thu_goc"].sum() if not df_lai.empty else 0

            c1, c2, c3 = st.columns(3)
            c1.metric("📊 Số tháng dự phóng", f"{len(df_dp)} tháng")
            c2.metric("✅ Đã qua (dự kiến)", fmt_ty(tong_goc_qua))
            c3.metric("🔮 Tương lai (dự kiến)", fmt_ty(tong_goc_lai))

            st.divider()

            # Biểu đồ cột
            st.markdown("**📊 Biểu đồ Dự phóng Dòng tiền theo tháng**")

            import plotly.graph_objects as go

            fig = go.Figure()

            if not df_qua.empty:
                fig.add_trace(go.Bar(
                    x=df_qua["thang_label"],
                    y=df_qua["du_kien_thu_goc_trieu"],
                    name="Đã qua (dự kiến)",
                    marker_color="#9e9e9e",
                    hovertemplate="%{y:,.0f} triệu<extra></extra>",
                ))

            if not df_lai.empty:
                fig.add_trace(go.Bar(
                    x=df_lai["thang_label"],
                    y=df_lai["du_kien_thu_goc_trieu"],
                    name="Tương lai (dự kiến)",
                    marker_color="#1565c0",
                    hovertemplate="%{y:,.0f} triệu<extra></extra>",
                ))

            fig.update_layout(
                barmode="stack",
                height=350,
                margin=dict(l=0, r=20, t=10, b=10),
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                font_family="Arial",
                xaxis=dict(title=""),
                yaxis=dict(title="Triệu đồng", tickformat=",.0f"),
                legend=dict(orientation="h", y=1.08),
            )
            st.plotly_chart(fig, use_container_width=True)

            # Bảng dữ liệu
            with st.expander("📋 Xem bảng số liệu chi tiết", expanded=False):
                df_show = df_dp[["thang_label", "so_mon", "tong_du_no_trieu", "du_kien_thu_goc_trieu"]].copy()
                df_show.columns = ["Tháng", "Số món", "Tổng dư nợ (tr.đ)", "Dự kiến thu gốc (tr.đ)"]
                st.dataframe(df_show, hide_index=True, use_container_width=True)

            # Chọn tháng xem chi tiết
            st.markdown("**🔍 Xem chi tiết tháng cụ thể**")
            thang_xem = st.selectbox(
                "Chọn tháng",
                df_dp["thang_label"].tolist(),
                key="op_dp_thang_xem",
            )
            thang_date = df_dp[df_dp["thang_label"] == thang_xem]["thang"].iloc[0]

            df_ct_detail = du_phong_chi_tiet(df_work, thang_date)
            if not df_ct_detail.empty:
                st.caption(f"**{len(df_ct_detail)}** khế ước có gốc đến hạn trong tháng {thang_xem}")
                cols_show = [c for c in ["ten_kh", "ten_xa", "ten_ct", "du_no_trieu", "goc_ht_trieu", "ngay_vay", "ngay_dh"]
                             if c in df_ct_detail.columns]
                df_ct_show = df_ct_detail[cols_show].copy()
                col_map = {"ten_kh": "Khách hàng", "ten_xa": "Xã", "ten_ct": "Chương trình",
                           "du_no_trieu": "Dư nợ (tr.đ)", "goc_ht_trieu": "Gốc/tháng (tr.đ)",
                           "ngay_vay": "Ngày vay", "ngay_dh": "Ngày ĐH"}
                df_ct_show = df_ct_show.rename(columns={k: v for k, v in col_map.items() if k in df_ct_show.columns})
                st.dataframe(df_ct_show, hide_index=True, use_container_width=True, height=300)
            else:
                st.info("Không có khế ước nào đến hạn thu gốc trong tháng này.")

    def _render_heatmap_dao_han(tab_parent, **kw) -> None:
        with get_tab_context(tab_parent):
            import plotly.express as px
            from dateutil.relativedelta import relativedelta

            df_loc = kw.get("df")
            st.subheader("🔥 Heatmap Đáo hạn — Dư nợ đến hạn theo Tháng × Chương trình")

            if df_loc is None or df_loc.empty:
                st.info("Chưa có dữ liệu HSTD.")
                return

            hom_nay = datetime.now().date()
            thang_ht = date(hom_nay.year, hom_nay.month, 1)

            cot_ngay_vay = COT_NGAY_VAY if COT_NGAY_VAY in df_loc.columns else (COT_NGAY_DH if COT_NGAY_DH in df_loc.columns else None)
            if cot_ngay_vay is None:
                st.warning("Không tìm thấy cột ngày vay/ngày ĐH để tính đáo hạn.")
                return

            cot_tien = COT_TONG_DU_NO if COT_TONG_DU_NO in df_loc.columns else COT_DU_NO_TH
            if cot_tien not in df_loc.columns:
                st.warning("Không tìm thấy cột dư nợ để tính.")
                return

            df_hm = df_loc.copy()
            df_hm[cot_ngay_vay] = pd.to_datetime(df_hm[cot_ngay_vay], errors="coerce")
            df_hm = df_hm.dropna(subset=[cot_ngay_vay])

            df_hm["thang_dh"] = df_hm[cot_ngay_vay].dt.to_period("M").astype(str)
            df_hm["nam"] = df_hm[cot_ngay_vay].dt.year.astype(int)

            nam_min = max(df_hm["nam"].min(), hom_nay.year - 1)
            nam_max = min(df_hm["nam"].max(), hom_nay.year + 2)

            df_loc_hm = df_hm[(df_hm["nam"] >= nam_min) & (df_hm["nam"] <= nam_max)].copy()

            if df_loc_hm.empty:
                st.info("Không có dữ liệu trong khoảng thời gian này.")
                return

            nhom_ct = COT_TEN_CT if COT_TEN_CT in df_loc_hm.columns else None

            if nhom_ct:
                pivot = df_loc_hm.pivot_table(
                    index="thang_dh", columns=nhom_ct, values=cot_tien, aggfunc="sum"
                ).fillna(0)
            else:
                pivot = df_loc_hm.groupby("thang_dh")[cot_tien].sum().to_frame("Tổng")

            fig = px.imshow(
                pivot if nhom_ct else pivot.T,
                text_auto=".0f",
                aspect="auto",
                color_continuous_scale="YlOrRd",
                labels=dict(x="Chương trình" if nhom_ct else "", y="Tháng", color="Dư nợ (triệu)"),
                title="Dư nợ đến hạn theo Tháng × Chương trình",
            )
            fig.update_layout(
                height=max(350, len(pivot) * 40),
                margin=dict(l=0, r=0, t=40, b=0),
                font_family="Arial",
            )
            if nhom_ct:
                fig.update_xaxes(tickangle=45)
            st.plotly_chart(fig, use_container_width=True)

            with st.expander("📋 Bảng số liệu", expanded=False):
                df_show = pivot.reset_index() if nhom_ct else pivot.reset_index()
                st.dataframe(df_show, hide_index=True, use_container_width=True)

            if not nhom_ct:
                st.caption("💡 Thêm dữ liệu cột Chương trình để xem heatmap chi tiết theo từng CT.")

            st.divider()
            col1, col2 = st.columns([1, 1])
            with col1:
                st.download_button(
                    label="⬇️ Xuất Excel (chuyên nghiệp)",
                    type="primary",
                    data=xuat_excel_chuyen_nghiep(
                        df=df_show,
                        title="Heatmap Đáo hạn",
                        subtitle=f"Kỳ: {nam_min}-{nam_max}",
                        nguoi_xuat=st.session_state.get("txt_username", ""),
                        kpi_items=[
                            ("Tổng số tháng", fmt_so(len(pivot)), ""),
                            ("Dư nợ b/q tháng", fmt_ty(pivot.values.mean()), "triệu đồng"),
                        ],
                    ),
                    file_name=excel_ten_file("Heatmap_DaoHan"),
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )

    def _render_histogram_du_no(tab_parent, **kw) -> None:
        with get_tab_context(tab_parent):
            import plotly.express as px

            df_loc = kw.get("df")
            st.subheader("📊 Histogram — Phân bố Dư nợ theo Khoản vay")

            if df_loc is None or df_loc.empty:
                st.info("Chưa có dữ liệu HSTD.")
                return

            cot_tien = COT_TONG_DU_NO if COT_TONG_DU_NO in df_loc.columns else (COT_DU_NO_TH if COT_DU_NO_TH in df_loc.columns else None)
            if cot_tien is None:
                st.warning("Không tìm thấy cột dư nợ.")
                return

            df_hist = df_loc.copy()
            df_hist[cot_tien] = pd.to_numeric(df_hist[cot_tien], errors="coerce").fillna(0)
            df_hist = df_hist[df_hist[cot_tien] > 0]

            if df_hist.empty:
                st.info("Không có dữ liệu dư nợ dương.")
                return

            max_val = df_hist[cot_tien].max()
            bins = st.slider("Số khoảng (bins)", min_value=5, max_value=50, value=20, key="op_hist_bins")

            fig = px.histogram(
                df_hist,
                x=cot_tien,
                nbins=bins,
                labels={cot_tien: "Dư nợ (đồng)"},
                title="Phân bố dư nợ",
                color_discrete_sequence=["#2E7D32"],
            )
            fig.update_layout(
                height=400,
                margin=dict(l=0, r=20, t=40, b=0),
                font_family="Arial",
                xaxis=dict(tickformat=",.0f"),
                yaxis=dict(title="Số khoản vay"),
                bargap=0.05,
            )
            fig.add_vline(x=df_hist[cot_tien].median(), line_dash="dash", line_color="#C62828",
                          annotation_text=f"Trung vị: {df_hist[cot_tien].median():,.0f}")
            st.plotly_chart(fig, use_container_width=True)

            col_s1, col_s2, col_s3 = st.columns(3)
            with col_s1:
                st.metric("Trung bình", fmt_ty(df_hist[cot_tien].mean()), help="Dư nợ bình quân/khoản")
            with col_s2:
                st.metric("Trung vị", fmt_ty(df_hist[cot_tien].median()), help="Dư nợ trung vị")
            with col_s3:
                st.metric("Tổng số khoản", fmt_so(len(df_hist)), help="Số khoản vay có dư nợ")

    def _render_donut_co_cau(tab_parent, **kw) -> None:
        with get_tab_context(tab_parent):
            import plotly.graph_objects as go

            df_loc = kw.get("df")
            st.subheader("🍩 Donut — Cơ cấu Dư nợ theo Chương trình")

            if df_loc is None or df_loc.empty:
                st.info("Chưa có dữ liệu HSTD.")
                return

            nhom_ct = COT_TEN_CT if COT_TEN_CT in df_loc.columns else None
            if nhom_ct is None:
                st.warning("Không tìm thấy cột Chương trình.")
                return

            cot_tien = COT_TONG_DU_NO if COT_TONG_DU_NO in df_loc.columns else (COT_DU_NO_TH if COT_DU_NO_TH in df_loc.columns else None)
            if cot_tien is None:
                st.warning("Không tìm thấy cột dư nợ.")
                return

            df_donut = df_loc.copy()
            df_donut[cot_tien] = pd.to_numeric(df_donut[cot_tien], errors="coerce").fillna(0)
            df_donut = df_donut[df_donut[cot_tien] > 0]

            if df_donut.empty:
                st.info("Không có dữ liệu dư nợ dương.")
                return

            ct_group = df_donut.groupby(nhom_ct)[cot_tien].sum().sort_values(ascending=False)

            top_n = st.slider("Hiển thị Top N chương trình", min_value=3, max_value=10, value=5, key="op_donut_top")
            ct_show = ct_group.head(top_n)
            ct_others = ct_group.iloc[top_n:].sum() if len(ct_group) > top_n else 0

            labels = list(ct_show.index)
            values = [v / 1e6 for v in ct_show.values]
            if ct_others > 0:
                labels.append("Khác")
                values.append(ct_others / 1e6)

            colors = ["#2E7D32", "#1565C0", "#F9A825", "#C62828", "#6A1B9A",
                      "#00838F", "#E65100", "#4E342E", "#37474F", "#827717"]

            fig = go.Figure(data=[go.Pie(
                labels=labels,
                values=values,
                hole=0.4,
                marker=dict(colors=colors[:len(labels)]),
                textinfo="label+percent",
                texttemplate="%{label}<br>%{percent:.1f}%",
                hovertemplate="<b>%{label}</b><br>Dư nợ: %{value:,.0f} tr.đ<br>Tỷ trọng: %{percent:.1f}%<extra></extra>",
            )])
            fig.update_layout(
                height=450,
                margin=dict(l=0, r=0, t=10, b=0),
                font_family="Arial",
                legend=dict(orientation="h", y=-0.1),
            )
            st.plotly_chart(fig, use_container_width=True)

            with st.expander("📋 Bảng số liệu", expanded=False):
                df_ct = ct_group.reset_index()
                df_ct.columns = ["Chương trình", "Dư nợ (đồng)"]
                df_ct["Dư nợ (triệu)"] = (df_ct["Dư nợ (đồng)"] / 1e6).round(1)
                df_ct["Tỷ trọng %"] = (df_ct["Dư nợ (đồng)"] / df_ct["Dư nợ (đồng)"].sum() * 100).round(1)
                st.dataframe(df_ct, hide_index=True, use_container_width=True)

    def _render_doc_hub_tab(tab_parent) -> None:
        with get_tab_context(tab_parent):
            _init_gb2_session_for_doc_hub(kwargs)
            _render_doc_hub(df, df_nq11, role)

    # ── Định nghĩa nhóm tab ─────────────────────────────────────────────
    CAC_NHOM = {
        "trang_chu": {
            "label": "🏠 Trang Chủ",
            "tabs": [
                ("🏠 Trang Chủ", lambda tab: _render_trang_chu(tab, df_pgd, role, pgd_user, kwargs)),
            ],
        },
        "nghiep_vu_pgd": {
            "label": "📋 Nghiệp vụ hàng ngày",
            "tabs": [
                ("📊 Thông tin chung", lambda tab: tab_tongquan.render(tab, **_pgd_df_kwargs)),
                ("📈 Tiến độ công việc", lambda tab: tab_tien_do.render(tab, **kwargs)),
                ("🔍 Tra cứu hồ sơ", lambda tab: tab_tracuu.render(tab, **kwargs)),
                ("📋 Danh sách & Lọc", lambda tab: tab_danhsach.render(tab, **kwargs)),
                ("⏰ Đến hạn", lambda tab: render_den_han(role=role, pgd_user=pgd_user)),
                ("📈 Dự phóng Dòng tiền", lambda tab: _render_du_phong_dong_tien(tab, **_pgd_df_kwargs)),
                ("🔥 Heatmap Đáo hạn", lambda tab: _render_heatmap_dao_han(tab, **_pgd_df_kwargs)),
                ("📊 Histogram Dư nợ", lambda tab: _render_histogram_du_no(tab, **_pgd_df_kwargs)),
                ("🍩 Cơ cấu CT", lambda tab: _render_donut_co_cau(tab, **_pgd_df_kwargs)),
                ("📊 So sánh kỳ", lambda tab: tab_so_sanh_ky.render(
                    tab, df=df, df_full=df_full, role=role, username=username,
                    pgd_user=pgd_user, pgd_mode=True,
                )),
            ],
        },
        "bao_cao_giao_ban": {
            "label": "📈 Báo cáo & Giao ban",
            "tabs": [
                ("📊 Báo cáo tín dụng", lambda tab: tab_baocao.render(tab, **_pgd_df_kwargs)),
                ("📡 Điện báo", lambda tab: tab_candoi.render(
                    tab, **{**kwargs, "pgd_mode": True, "df": df, "df_full": df}
                )),
                ("📝 Báo cáo Giao ban", lambda tab: _render_bao_cao_giao_ban(tab, **kwargs)),
                ("📄 Trung tâm mẫu biểu",       lambda tab: _render_doc_hub_tab(tab)),
                ("📋 Biên bản giao ban",         lambda tab: _render_bien_ban_giao_ban(tab, **kwargs)),
                ("📢 Thông báo kết luận",        lambda tab: _render_thong_bao_ket_luan(tab, **kwargs)),
            ],
        },
        "ke_hoach_pgd": {
            "label": "🎯 Kế hoạch PGD",
            "tabs": [
                ("🎯 KHTD", lambda tab: tab_khtd_pgd.render(tab, **kwargs)),
                ("📋 Giao & ĐC KHTD", lambda tab: tab_khtd_giao_dc.render(tab, **kwargs)),
                ("📋 Mẫu 07 Giao KH", lambda tab: tab_khtd_mau07.render(tab, **kwargs)),
                ("📋 NQ11", lambda tab: tab_nq11.render(tab, **_pgd_df_kwargs)),
            ],
        },
        "kiem_soat_rr": {
            "label": "🔍 Kiểm soát & Rủi ro",
            "tabs": [
                ("🔔 Đôn đốc KHĐ", lambda tab: _render_don_doc(df_pgd, pgd_user or pgd_filter or "", role)),
                ("⚡ Cảnh báo sớm", lambda tab: _render_canh_bao_som_pgd(tab, **kwargs)),
                ("💳 Nợ rủi ro QĐ62", lambda tab: tab_qd62.render(
                    mode="pgd", pgd_filter=pgd_user or pgd_filter
                )),
                ("📍 Điểm Giao Dịch", lambda tab: tab_diem_gd_pgd.render(tab, **kwargs)),
                ("🏘️ Tổ TK&VV",       lambda tab: tab_cdtotkvv_pgd.render(tab, **kwargs)),
                ("🏛️ Ban Đại Diện", lambda tab: tab_ban_dai_dien.render(tab, cap="xa", **kwargs)),
                ("🤝 Ủy thác", lambda tab: tab_uy_thac.render(tab, **kwargs)),
                ("📊 Tổng quan Nợ Khoanh", lambda tab: tab_no_khoanh.render(
                    tab,
                    df=df_pgd,
                    df_full=None,
                    role=role,
                    username=username,
                    pgd_user=pgd_user,
                    nhom="tongquan",
                )),
                ("🔒 Quản lý Nợ Khoanh CV 368", lambda tab: tab_no_khoanh.render(
                    tab,
                    df=df_pgd,
                    df_full=None,
                    role=role,
                    username=username,
                    pgd_user=pgd_user,
                    nhom="cv368",
                )),
            ],
        },
        "quan_tri_pgd": {
            "label": "⚙️ Quản trị PGD",
            "tabs": [
                ("✅ Nhiệm vụ", lambda tab: tab_nhiem_vu.render(tab, **kwargs)),
                ("📤 Upload Dữ liệu", lambda tab: tab_upload_pgd.render(tab, **kwargs)),
                ("📤 Upload HSTD", lambda tab: tab_upload_pgd.render(tab, **kwargs)),
                ("🔍 Trạng thái hệ thống", lambda tab: tab_trang_thai_nguon.render(tab, **kwargs)),
                ("📖 Hướng dẫn", lambda tab: render_huong_dan()),
            ],
        },
    }

    # ── Lọc nhóm được phép ──────────────────────────────────────────────
    nhom_kha_dung = {}
    for key, info in CAC_NHOM.items():
        if key in nhom_duoc_phep:
            # Ẩn Upload HSTD nếu không phải admin_pgd
            if key == "quan_tri_pgd" and not tab_perm["co_quyen_upload_hstd"]:
                info_copy = dict(info)
                info_copy["tabs"] = [t for t in info["tabs"] if "Upload HSTD" not in t[0]]
                nhom_kha_dung[key] = info_copy
            else:
                nhom_kha_dung[key] = info

    # ── Render ───────────────────────────────────────────────────────────
    ds_key = list(nhom_kha_dung.keys())
    ds_label = [nhom_kha_dung[k]["label"] for k in ds_key]

    nhom_chon = st.radio(
        "Chọn nhóm công việc",
        ds_label,
        horizontal=True,
        key="ws_op_nhom",
    )

    idx_chon = ds_label.index(nhom_chon)
    key_chon = ds_key[idx_chon]
    tabs_info = nhom_kha_dung[key_chon]["tabs"]

    ten_tabs = [t[0] for t in tabs_info]
    renderers = [t[1] for t in tabs_info]

    # ── Lazy tab — chỉ render tab đang chọn, không chạy tất cả ──────────
    # (Streamlit st.tabs chạy ALL renderers mỗi rerun → dùng radio thay thế)
    tab_key = f"ws_op_tab_{key_chon}"

    # Nhảy tab từ shortcut: ghi index vào session_state trước khi radio render
    jump_idx = st.session_state.pop("ws_op_jump_tab", None)
    if jump_idx is not None and 0 <= jump_idx < len(ten_tabs):
        st.session_state[tab_key] = jump_idx
        st.toast(f"✨ Đã chuyển tới: {ten_tabs[jump_idx]}", icon="👆")

    # Khởi tạo nếu chưa có
    if tab_key not in st.session_state:
        st.session_state[tab_key] = 0

    # Radio làm tab selector — ẩn label, nằm ngang
    sel_idx = st.radio(
        "Tab",
        options=range(len(ten_tabs)),
        format_func=lambda i: ten_tabs[i],
        horizontal=True,
        key=tab_key,
        label_visibility="collapsed",
    )

    st.divider()

    # Chỉ gọi renderer của tab đang active
    renderers[sel_idx](None)
