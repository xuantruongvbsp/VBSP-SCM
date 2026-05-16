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
    COT_LAI_TON, COT_LAI_THANG, COT_DVUT,
    TEMPLATES_DIR, TAG_MAP,
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
)


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
                k1, k2, k3, k4 = st.columns(4)

                # KPI 1: Tổng dư nợ
                try:
                    tong_dn = pd.to_numeric(df_pgd[COT_TONG_DU_NO], errors="coerce").sum() / 1e6
                    k1.metric("💰 Tổng dư nợ", f"{fmt(tong_dn * 1e6)} triệu", help="Đơn vị: triệu đồng")
                except Exception:
                    k1.metric("💰 Tổng dư nợ", "—")

                # KPI 2: Nợ quá hạn
                try:
                    nqh = pd.to_numeric(df_pgd[COT_DU_NO_QH], errors="coerce").sum() / 1e6
                    pct_nqh = (nqh / (tong_dn or 1) * 100) if tong_dn > 0 else 0
                    k2.metric("🔴 Nợ quá hạn", f"{fmt(nqh * 1e6)} triệu",
                             delta=f"{pct_nqh:.1f}%" if pct_nqh > 0 else "0%",
                             delta_color="inverse" if nqh > 0 else "off",
                             help="Đơn vị: triệu đồng")
                except Exception:
                    k2.metric("🔴 Nợ quá hạn", "—")

                # KPI 3: 3 tháng KHĐ
                try:
                    df_kh = danh_dau_khong_hd_cached(df_pgd)
                    n_khd = int(df_kh["is_3m_inactive"].sum()) if "is_3m_inactive" in df_kh.columns else 0
                    pct_khd = (n_khd / len(df_pgd) * 100) if len(df_pgd) > 0 else 0
                    k3.metric("📅 3 tháng KHĐ", fmt_so(n_khd),
                             delta=f"{pct_khd:.1f}%",
                             delta_color="inverse" if n_khd > 0 else "off",
                             help="Khoản hộ vay 3 tháng không hoạt động")
                except Exception:
                    k3.metric("📅 3 tháng KHĐ", "—")

                # KPI 4: Tiến độ KHTD
                try:
                    slug = pgd_slug(pgd_user) if pgd_user else ""
                    khtd_key = f"khtd_pgd_{slug}" if slug else None
                    if khtd_key:
                        khtd_data = db.doc_kv(khtd_key)
                        if khtd_data and isinstance(khtd_data, dict):
                            tong_kh = khtd_data.get("tong_kh", 0)
                            tong_th = khtd_data.get("tong_th", 0)
                            pct_tien_do = (tong_th / (tong_kh or 1) * 100) if tong_kh > 0 else 0
                            k4.metric("📊 KHTD", f"{pct_tien_do:.0f}%",
                                     delta="Thực hiện / Kế hoạch",
                                     help="Tiến độ thực hiện KHTD")
                        else:
                            k4.metric("📊 KHTD", "—", help="Chưa có dữ liệu KHTD")
                    else:
                        k4.metric("📊 KHTD", "—")
                except Exception:
                    k4.metric("📊 KHTD", "—")

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
    nhom_dvut = tong_hop_khong_hd_cached(df_kh, nhom_theo="Tên ĐVUT")
    if not nhom_dvut.empty:
        hien_thi_dataframe_phan_trang(
            nhom_dvut,
            key="op_khd_nhom_dvut",
            height=220,
        )

    # Bảng theo Xã
    st.markdown("**Tổng hợp theo Xã/Phường**")
    nhom_xa = tong_hop_khong_hd_cached(df_kh, nhom_theo="Tên xã")
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
        if "Tên ĐVUT" in df_kh.columns:
            ds_dvut += sorted(df_kh["Tên ĐVUT"].dropna().unique().tolist())
        chon_dvut = st.selectbox("Lọc Hội đoàn thể", ds_dvut, key="op_khd_dvut")

    gia_tri = None if chon_dvut == "Tất cả" else chon_dvut
    df_dondoc = ds_chi_tiet_khong_hd(df_kh, nhom_theo="Tên ĐVUT",
                                      gia_tri_nhom=gia_tri)

    with col_xuat:
        st.markdown("<br>", unsafe_allow_html=True)
        if not df_dondoc.empty:
            buf = xuat_excel({"Đôn đốc 3m KHĐ": df_dondoc})
            st.download_button(
                label=f"⬇️ Xuất Excel ({len(df_dondoc)} hộ)",
                data=buf,
                file_name=f"DonDoc_3m_{chon_dvut}_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="op_xuat_khd",
                type="primary",
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
    else:
        st.info("Không có hộ nào thỏa điều kiện.")


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
        horizontal=True, key="dh_doi_tuong", label_visibility="collapsed",
    )

    df_chon = None

    if doi_tuong == "Từng hồ sơ khách hàng":
        kw = st.text_input("🔍 Tìm khách hàng",
                           placeholder="Tên KH hoặc Số khế ước...", key="dh_kw")
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
                                      opts.tolist(), key="dh_hs_sel")
                if chon:
                    idx_list = [opts.tolist().index(c) for c in chon]
                    df_chon  = df_tim.iloc[idx_list].reset_index(drop=True)
                    st.info(f"Đã chọn **{len(df_chon)}** hồ sơ")
    else:
        COT_XA = "Tên xã"
        if COT_XA in df.columns:
            ds_xa   = sorted(df[COT_XA].dropna().unique().tolist())
            chon_xa = st.selectbox("Chọn Xã/Phường", ds_xa, key="dh_xa")
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
                                   ten_mau_list, key="dh_mau_sel")

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
        horizontal=True, key="dh_xuat_mode",
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
    if "Tên xã" not in df.columns:
        return
    ds_xa = sorted(df["Tên xã"].dropna().unique().tolist())
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

        ds_xa = sorted(df["Tên xã"].dropna().unique().tolist())
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
            key="tb_chon_xa",
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
                key="tb_ten_dgd",
                help="Mặc định là tên xã, chỉnh lại nếu khác",
            )
            tb_ngay = st.date_input("Ngày họp", value=date.today(), key="tb_ngay_hop")
        with col_b:
            tb_so_vb = st.text_input(
                "Số văn bản",
                placeholder="VD: 05",
                key="tb_so_van_ban",
                help="Phần số trong 'Số: .../TB-KLGB'",
            )
            tb_ten_ky = st.text_input(
                "Tên người ký",
                placeholder="VD: Nguyễn Văn A",
                key="tb_ten_nguoi_ky",
                help="Tên Phó Giám đốc ký văn bản",
            )

        # Preview số liệu tự động
        from config import COT_LAI_TON_QH, COT_SO_DU_TG
        df_xa_preview = df[df["Tên xã"] == chon_xa].copy()
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
                        key=f"gn_{dvut}_{to}_{ct}",
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
            key="tb_chinh_sach",
        )
        tb_tt = st.text_area(
            "II.2 Tồn tại, hạn chế",
            placeholder="Nêu cụ thể tồn tại của Hội, Tổ, khách hàng...",
            height=120,
            key="tb_ton_tai",
        )
        tb_nv = st.text_area(
            "III. Nhiệm vụ tháng tiếp theo",
            placeholder="Kế hoạch kiểm tra, xử lý nợ xấu, nội dung khác...",
            height=120,
            key="tb_nhiem_vu",
        )

        if st.button("🖨️ Xuất Thông báo Kết luận Word", type="primary", key="tb_xuat"):
            df_xa_tb = df[df["Tên xã"] == chon_xa].copy()
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
        ds_xa = sorted(df["Tên xã"].dropna().unique().tolist())
        chon_xa = st.selectbox("Chọn xã / điểm giao dịch", ds_xa,
                               key="gb2_xa")

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
                key="gb2_nam")
            # Đọc dữ liệu đã merge từ tất cả đơn vị
            fp_check = baseline_pgd_path(DON_VI_CHI_NHANH if not pgd_user else pgd_user, chon_nam)
            _ts = os.path.getmtime(fp_check) if os.path.exists(fp_check) else 0
            df_bl = doc_baseline_merged(chon_nam, _ts=_ts)

        # 3. Nhập giải ngân (tuỳ chọn)
        with st.expander("✏️ Nhập kế hoạch giải ngân tháng tới (tuỳ chọn)"):
            st.caption("Để trống nếu chưa có kế hoạch.")
            gn_tong = st.number_input(
                "Tổng giải ngân dự kiến (triệu đồng)", min_value=0.0,
                step=1.0, key="gb2_gn")
            # Đơn giản: nhập 1 số tổng — code điền vào dòng Cộng
            # Nếu sau này cần chi tiết theo Tổ thì mở rộng thêm

        # 4. Xuất
        template = str(TEMPLATES_DIR / "BB_giao_ban_xa_template.docx")
        if not os.path.exists(template):
            st.error("Chưa có file template BB_giao_ban_xa_template.docx "
                     "trong thư mục templates/")
            return

        if st.button("🖨️ Xuất Biên bản Word", type="primary", key="gb2_xuat"):
            df_xa = df[df["Tên xã"] == chon_xa].copy()
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
                    chon_pgd = st.selectbox("Chọn Phòng Giao dịch", ds_pgd, key="gb_pgd")
                    df_filtered = df[df[COT_TEN_PGD] == chon_pgd].copy()
        
        # Chọn Xã
        if "Tên xã" in df_filtered.columns:
            ds_xa = sorted(df_filtered["Tên xã"].dropna().unique().tolist())
            if not ds_xa:
                st.warning("Không có dữ liệu xã nào trong PGD được chọn.")
                return
            chon_xa = st.selectbox("Chọn Xã/Phường", ds_xa, key="gb_xa")
            df_xa = df_filtered[df_filtered["Tên xã"] == chon_xa].copy()
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
            chon_dgd = st.selectbox("📍 Điểm giao dịch", ds_dgd, key="gb_dgd")
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
        if "Tên ĐVUT" not in df_dgd.columns:
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
        
        if valid_agg_dict and "Tên ĐVUT" in df_dgd.columns:
            df_bang = df_dgd.groupby("Tên ĐVUT").agg(valid_agg_dict).reset_index()
            
            # Đổi tên cột về tên hiển thị
            rename_dict = {}
            for col_name, (data_col, agg_func) in agg_dict.items():
                if data_col in df_dgd.columns and data_col in df_bang.columns:
                    rename_dict[data_col] = col_name
            df_bang = df_bang.rename(columns=rename_dict)
        else:
            # Tạo DataFrame rỗng với cấu trúc cơ bản
            df_bang = pd.DataFrame({"Tên ĐVUT": []})
        
        # Tính tỷ trọng %
        if "Tổng dư nợ" in df_bang.columns and df_bang["Tổng dư nợ"].sum() > 0:
            df_bang["Tỷ trọng %"] = (df_bang["Tổng dư nợ"] / df_bang["Tổng dư nợ"].sum() * 100).round(1)
        
        # Thêm dòng Cộng
        dong_cong = {"Tên ĐVUT": "CỘNG"}
        for col in df_bang.columns:
            if col != "Tên ĐVUT":
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
        dong_cong_data = df_bang[df_bang["Tên ĐVUT"] == "CỘNG"].iloc[0]
        
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
                     key="gb_tom_tat")
        
        st.divider()
        
        # ④ Xuất Excel
        st.markdown("**④ Xuất Excel**")
        
        if st.button("⬇️ Xuất Excel", type="primary", key="gb_xuat_excel"):
            try:
                buf = xuat_excel({"Giao ban": df_bang})
                # Tạo tên file với thông tin điểm giao dịch
                ten_file_safe = (ten_dgd or chon_xa).replace("/", "_").replace("\\", "_")
                ten_file = f"GiaoBan_{chon_xa}_{ten_file_safe}_{datetime.now().strftime('%Y%m%d')}.xlsx"
                st.session_state["_bytes_gb"] = buf
                st.session_state["_file_gb"] = ten_file
                st.success(f"✅ Đã tạo file Excel: **{ten_file}**")
            except Exception as e:
                st.error(f"❌ Lỗi xuất Excel: {e}")

        if st.session_state.get("_bytes_gb"):
            st.download_button(
                label=f"📥 Tải về {st.session_state['_file_gb']}",
                data=st.session_state["_bytes_gb"],
                file_name=st.session_state["_file_gb"],
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="gb_download"
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
        tab_trang_thai_nguon,
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

    # ── Helpers render ──────────────────────────────────────────────────
    def _render_diem_gd_va_to_tkvv(tab_parent, **kw):
        with tab_parent:
            _sub1, _sub2 = st.tabs(["📍 Điểm Giao Dịch", "🏘️ Tổ TK&VV"])
            tab_diem_gd_pgd.render(_sub1, **kw)
            tab_cdtotkvv_pgd.render(_sub2, **kw)

    def _render_mau_bieu_tab(tab_parent) -> None:
        with tab_parent:
            _init_gb2_session_for_doc_hub(kwargs)
            doc_t1, doc_t2, doc_t3 = st.tabs(
                ["📄 Trung tâm mẫu biểu", "📋 Biên bản giao ban", "📢 Thông báo kết luận"]
            )
            with doc_t1:
                _render_doc_hub(df, df_nq11, role)
            with doc_t2:
                _render_bien_ban_giao_ban(doc_t2, **kwargs)
            with doc_t3:
                _render_thong_bao_ket_luan(doc_t3, **kwargs)

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
                ("📈 Tiến độ", lambda tab: tab_tien_do.render(tab, **kwargs)),
                ("🔍 Tra cứu hồ sơ", lambda tab: tab_tracuu.render(tab, **kwargs)),
                ("📋 Danh sách & Lọc", lambda tab: tab_danhsach.render(tab, **kwargs)),
                ("⏰ Đến hạn", lambda tab: render_den_han(role=role, pgd_user=pgd_user)),
            ],
        },
        "bao_cao_giao_ban": {
            "label": "📈 Báo cáo & Giao ban",
            "tabs": [
                ("📈 Báo cáo chi tiết", lambda tab: tab_baocao.render(tab, **_pgd_df_kwargs)),
                ("📡 Điện Báo", lambda tab: tab_candoi.render(
                    tab, **{**kwargs, "pgd_mode": True, "df": df, "df_full": df}
                )),
                ("📝 Báo cáo Giao ban", lambda tab: _render_bao_cao_giao_ban(tab, **kwargs)),
                ("📄 Mẫu biểu", lambda tab: _render_mau_bieu_tab(tab)),
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
                ("💳 Nợ rủi ro QĐ62", lambda tab: tab_qd62.render(
                    mode="pgd", pgd_filter=pgd_user or pgd_filter
                )),
                ("📍 Điểm GD & Tổ TK&VV", lambda tab: _render_diem_gd_va_to_tkvv(tab, **kwargs)),
                ("🏛️ Ban Đại Diện", lambda tab: tab_ban_dai_dien.render(tab, cap="xa", **kwargs)),
                ("🤝 Ủy thác", lambda tab: tab_uy_thac.render(tab, **kwargs)),
            ],
        },
        "quan_tri_pgd": {
            "label": "⚙️ Quản trị PGD",
            "tabs": [
                ("✅ Nhiệm vụ", lambda tab: tab_nhiem_vu.render(tab, **kwargs)),
                ("📤 Upload Dữ liệu", lambda tab: tab_upload_pgd.render(tab, **kwargs)),
                ("📤 Upload HSTD", lambda tab: tab_upload_pgd.render(tab, **kwargs)),
                ("🔍 Trạng thái hệ thống", lambda tab: tab_trang_thai_nguon.render(tab, **kwargs)),
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

    # Kiểm tra nếu có yêu cầu nhảy tab từ shortcut
    jump_idx = st.session_state.pop("ws_op_jump_tab", None)

    tabs_con = st.tabs(ten_tabs)
    for i, tab_c in enumerate(tabs_con):
        with tab_c:
            renderers[i](tab_c)
            # Hiển thị gợi ý nếu user đặc biệt yêu cầu nhảy đến tab này
            if jump_idx == i and jump_idx is not None:
                st.toast(f"✨ Đã chuyển tới: {ten_tabs[i]}", icon="👆")
