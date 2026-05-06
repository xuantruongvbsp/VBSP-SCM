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

from config import (
    COT_TEN_KH, COT_MA_KH, COT_SO_KU, COT_TEN_CT,
    COT_DU_NO_QH, COT_TONG_DU_NO, COT_NGAY_DH,
    COT_TEN_PGD, COT_SDT, COT_DIA_CHI,
    COT_LAI_TON, COT_LAI_THANG, COT_DVUT, COT_TEN_TO,
    TEMPLATES_DIR, TAG_MAP,
)
from data import danh_dau_khong_hd, tong_hop_khong_hd, ds_chi_tiet_khong_hd
from utils import (
    fmt,
    fmt_so,
    vn,
    auto_fill_document,
    auto_fill_batch,
    quet_templates,
    xuat_excel,
    hien_thi_dataframe_phan_trang,
)
from tabs import (
    tab_tracuu,
    tab_danhsach,
    tab_khtd,
    tab_khtd_pgd,
    tab_nhiem_vu,
    tab_upload_pgd,
    tab_cdtotkvv_pgd,
    tab_khtd_mau07,
    tab_khtd_giao_dc,
    tab_diem_gd_pgd,
    tab_ban_dai_dien,
    tab_tongquan,
    tab_baocao,
    tab_nq11,
    tab_candoi,
    tab_hoi_doan_the,
)


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
    df_kh = danh_dau_khong_hd(df)
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
    k3.metric("Lãi tồn cần thu (tr.đ)", vn(tong_lai/1e6, 1))

    if n_khd == 0:
        st.success("✅ Không có món vay nào quá 3 tháng không hoạt động!")
        return

    st.divider()

    # ── Bảng tổng hợp theo ĐVUT ───────────────────────────────────────────
    st.markdown("**Tổng hợp theo Hội đoàn thể (ĐVUT)**")
    nhom_dvut = tong_hop_khong_hd(df_kh, nhom_theo="Tên ĐVUT")
    if not nhom_dvut.empty:
        hien_thi_dataframe_phan_trang(
            nhom_dvut,
            key="op_khd_nhom_dvut",
            height=220,
        )

    # Bảng theo Xã
    st.markdown("**Tổng hợp theo Xã/Phường**")
    nhom_xa = tong_hop_khong_hd(df_kh, nhom_theo="Tên xã")
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
            f"Lãi tồn: **{vn(tong_lai_ds/1e6,1)}** triệu đồng"
        )
    else:
        st.info("Không có hộ nào thỏa điều kiện.")


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
            "(xuất Word tại sub-tab **� Thông báo kết luận** → chọn loại Biên bản)."
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

    if st.button("🖨️ Tạo văn bản", type="primary", key="dh_btn_xuat"):
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
                        st.download_button(
                            f"⬇ {ten_mau} — {ten_kh}", data=data, file_name=fname,
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            key=f"dl_{ten_mau}_{i}",
                        )
                else:
                    fname = f"{path_mau.stem}_batch_{datetime.today().strftime('%d%m%Y')}.docx"
                    data  = auto_fill_batch(df_chon, str(path_mau), TAG_MAP)
                    st.download_button(
                        f"⬇ {ten_mau} — {len(df_chon)} hồ sơ (gộp)",
                        data=data, file_name=fname,
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        key=f"dl_batch_{ten_mau}",
                    )
                st.success(f"✅ Đã tạo: **{ten_mau}**")
            except Exception as e:
                st.error(f"Lỗi tạo {ten_mau}: {e}")


@st.cache_data(show_spinner=False, ttl=300)
def _tinh_so_lieu_hdt(_df_bytes, ten_xa):
    """Cache tính toán — nhận bytes để tránh hash DataFrame."""
    import pickle
    df = pickle.loads(_df_bytes)
    from data import danh_dau_khong_hd
    df_m = danh_dau_khong_hd(df)
    DVUT_ORDER = ["Hội nông dân", "Hội liên hiệp phụ nữ",
                  "Hội cựu chiến binh", "Đoàn thanh niên"]
    t = df_m.groupby(COT_DVUT).agg(
        so_to   =(COT_TEN_TO,       "nunique"),
        so_kh   =(COT_MA_KH,        "nunique"),
        tong_dn =(COT_TONG_DU_NO,   "sum"),
        nqh     =(COT_DU_NO_QH,     "sum"),
        mon_3m  =("is_3m_inactive",  "sum"),
    ).reset_index()
    t = t[t["tong_dn"] > 0]
    t["_ord"] = t[COT_DVUT].apply(
        lambda x: DVUT_ORDER.index(x) if x in DVUT_ORDER else 99)
    t = t.sort_values("_ord").drop(columns="_ord")
    return t


def _render_thong_bao_ket_luan(tab, **kwargs):
    """Tab xuất Thông báo Kết luận giao ban (NĐ30) — tự quản lý chọn xã/năm."""
    from data.giao_ban import xuat_thong_bao_ket_luan_giao_ban
    from pdf_service import nut_xuat_pdf
    from config import danh_sach_nam_baseline, danh_sach_nam_baseline_pgd

    def _render_so_lieu_giao_ban(df_xa: pd.DataFrame, ten_xa: str):
        """Hiển thị số liệu giao ban theo Hội đoàn thể và Tổ TK&VV."""
        if df_xa is None or df_xa.empty:
            st.info(f"Không có dữ liệu HSTD cho xã **{ten_xa}**.")
            return

        st.markdown(f"#### 📊 Số liệu giao ban — xã {ten_xa}")

        # KPI nhanh
        k1, k2, k3, k4 = st.columns(4)
        tong_dn = df_xa[COT_TONG_DU_NO].sum() if COT_TONG_DU_NO in df_xa.columns else 0
        so_kh   = df_xa[COT_MA_KH].nunique() if COT_MA_KH in df_xa.columns else 0
        nqh     = df_xa[COT_DU_NO_QH].sum()  if COT_DU_NO_QH in df_xa.columns else 0
        so_to   = df_xa[COT_TEN_TO].nunique() if COT_TEN_TO in df_xa.columns else 0
        k1.metric("Tổng dư nợ (tr.đ)", fmt(tong_dn))
        k2.metric("Số khách hàng",     fmt_so(so_kh))
        k3.metric("Nợ quá hạn (tr.đ)", fmt(nqh))
        k4.metric("Số Tổ TK&VV",       fmt_so(so_to))

        st.divider()

        # Bảng theo Hội đoàn thể
        st.markdown("**Theo Hội đoàn thể (ĐVUT)**")
        import pickle
        try:
            t = _tinh_so_lieu_hdt(pickle.dumps(df_xa), ten_xa)
            if t.empty:
                st.info("Không có dữ liệu phân theo Hội đoàn thể.")
            else:
                t_hien = t.rename(columns={
                    COT_DVUT:   "Hội đoàn thể",
                    "so_to":    "Số Tổ",
                    "so_kh":    "Số KH",
                    "tong_dn":  "Dư nợ (tr.đ)",
                    "nqh":      "NQH (tr.đ)",
                    "mon_3m":   "Món 3T KHĐ",
                })
                t_hien["Dư nợ (tr.đ)"] = t_hien["Dư nợ (tr.đ)"].apply(fmt)
                t_hien["NQH (tr.đ)"]   = t_hien["NQH (tr.đ)"].apply(fmt)
                st.dataframe(t_hien, use_container_width=True, hide_index=True)
        except Exception as e:
            st.warning(f"Không thể tính số liệu Hội đoàn thể: {e}")

        st.divider()

        # Bảng theo Tổ TK&VV — top nợ xấu
        st.markdown("**Tổ TK&VV có NQH / lãi tồn**")
        cols_can = [COT_TEN_TO, COT_DVUT, COT_TONG_DU_NO, COT_DU_NO_QH, COT_LAI_TON]
        cols_co  = [c for c in cols_can if c in df_xa.columns]
        if cols_co and COT_DU_NO_QH in df_xa.columns:
            df_to = df_xa[cols_co].groupby(COT_TEN_TO).sum(numeric_only=True)
            df_to = df_to[df_to[COT_DU_NO_QH] > 0].sort_values(
                COT_DU_NO_QH, ascending=False).head(20)
            if df_to.empty:
                st.success("✅ Không có Tổ TK&VV nào có nợ quá hạn.")
            else:
                st.dataframe(df_to.reset_index(), use_container_width=True,
                             hide_index=True)

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

        # Lọc PGD nếu là user
        if role == "user" and pgd_user and COT_TEN_PGD in df.columns:
            df = df[df[COT_TEN_PGD] == pgd_user].copy()
            chon_pgd = pgd_user
        else:
            chon_pgd = pgd_user or ""

        ds_xa = sorted(df["Tên xã"].dropna().unique().tolist())
        if not ds_xa:
            st.warning("Không có dữ liệu xã.")
            return

        # Lấy danh sách năm từ config
        from config import DON_VI_CHI_NHANH
        ds_nam = danh_sach_nam_baseline_pgd(pgd_user or DON_VI_CHI_NHANH)
        if not ds_nam:
            ds_nam = danh_sach_nam_baseline() or []

        # Chọn xã (chung cho cả 2 sub-tab)
        col_a, col_b = st.columns(2)
        with col_a:
            chon_xa = st.selectbox("Xã / Phường", ds_xa, key="tbluan_xa")
        with col_b:
            thang_bc = st.selectbox("Tháng báo cáo", list(range(1, 13)),
                           index=date.today().month - 1, key="tbluan_thang")
            nam_bc = st.number_input("Năm báo cáo", value=date.today().year,
                           min_value=2020, max_value=2030, step=1,
                           key="tbluan_nam_bc")
            st.info(f"📊 Số liệu tự động từ HSTD\n\n**Xã:** {chon_xa or '(chưa chọn)'}  \n**Tháng:** {thang_bc}/{nam_bc}")

        df_xa_tb = df[df["Tên xã"] == chon_xa].copy()

        # 2 sub-tabs
        sub1, sub2 = st.tabs(["📊 Số liệu giao ban", "📄 Xuất Thông báo KL"])

        with sub1:
            _render_so_lieu_giao_ban(df_xa_tb, chon_xa)

        with sub2:
            # Layout 2 cột cho form xuất Word
            col_a2, col_b2 = st.columns(2)

            with col_a2:
                st.markdown("**Thông tin văn bản**")

                if ds_nam:
                    chon_nam = st.selectbox(
                        "Năm baseline", ds_nam, key="tbluan_nam"
                    )
                else:
                    chon_nam = date.today().year - 1

                tb_so_vb = st.text_input(
                    "Số văn bản", placeholder="VD: 12", key="tbluan_so_vb"
                )

                tb_dgd = st.text_input(
                    "Tên điểm giao dịch",
                    value=chon_xa,
                    key="tb_ten_dgd",
                    help="Mặc định là tên xã, chỉnh lại nếu khác",
                )

                tb_ngay = st.date_input("Ngày họp", value=date.today(), key="tb_ngay_hop")

            with col_b2:
                st.markdown("**Thông tin ký duyệt**")

                tb_nguoi_ky = st.text_input(
                    "Người ký", placeholder="VD: Nguyễn Văn A", key="tbluan_nguoi_ky"
                )

                tb_chuc_danh = st.text_input(
                    "Chức danh", placeholder="VD: Cán bộ tín dụng", key="tbluan_chuc_danh"
                )

            st.divider()

            tb_cs = st.text_area(
                "I. Chính sách mới trong tháng",
                placeholder="Để trống nếu không có chính sách mới...",
                height=100, key="tb_chinh_sach",
            )
            tb_tt = st.text_area(
                "II.2 Tồn tại, hạn chế",
                placeholder="Nêu cụ thể tồn tại của Hội, Tổ, khách hàng...",
                height=120, key="tb_ton_tai",
            )
            tb_nv = st.text_area(
                "III. Nhiệm vụ tháng tiếp theo",
                placeholder="Kế hoạch kiểm tra, xử lý nợ xấu, nội dung khác...",
                height=120, key="tb_nhiem_vu",
            )

            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                if st.button("🖨️ Xuất Thông báo Kết luận Word", type="primary", key="tb_xuat"):
                    try:
                        so_vb = st.session_state.get("tbluan_so_vb", "")
                        nguoi_ky_val = st.session_state.get("tbluan_nguoi_ky", "")
                        chuc_danh_val = st.session_state.get("tbluan_chuc_danh", "")

                        data = xuat_thong_bao_ket_luan_giao_ban(
                            df_xa=df_xa_tb,
                            ten_pgd=chon_pgd or pgd_user or "",
                            ten_xa=chon_xa,
                            ten_dgd=tb_dgd or chon_xa,
                            thang_bao_cao=int(thang_bc),
                            nam_bao_cao=int(nam_bc),
                            ngay_hop=tb_ngay.strftime("%d/%m/%Y"),
                            chinh_sach_moi=tb_cs,
                            ton_tai_han_che=tb_tt,
                            nhiem_vu_tiep=tb_nv,
                            so_van_ban=so_vb,
                            nguoi_ky=nguoi_ky_val,
                            chuc_danh=chuc_danh_val,
                            df_baseline=None,
                            nam_moc=chon_nam if isinstance(chon_nam, int) else date.today().year - 1,
                        )
                        ten_file = (
                            f"TB_KetLuan_{chon_xa.replace(' ', '_')}"
                            f"_{int(thang_bc):02d}{int(nam_bc)}.docx"
                        )
                        st.download_button(
                            "⬇️ Tải về Word",
                            data=data,
                            file_name=ten_file,
                            mime="application/vnd.openxmlformats-officedocument"
                            ".wordprocessingml.document",
                            key="tb_dl_word",
                        )
                        st.success("✅ Đã tạo Thông báo Kết luận!")
                    except Exception as e:
                        st.error(f"❌ Lỗi tạo file: {e}")

            with col_btn2:
                st.markdown("<br>", unsafe_allow_html=True)
                st.caption("📄 Xuất PDF: Đang phát triển")


def render(**kwargs):
    _wl = st.session_state.pop("_data_load_warning", None)
    if _wl:
        st.warning(_wl)

    df       = kwargs.get("df")
    df_nq11  = kwargs.get("df_nq11")
    role     = kwargs.get("role")
    pgd_user = kwargs.get("pgd_user")

    st.title("🗺️ Hỗ Trợ Địa Bàn PGD/Biên Hòa")
    st.caption("Tra cứu hồ sơ · Danh sách · Báo cáo giao ban · Văn bản tự động · Nhiệm vụ · Upload dữ liệu")

    tab_names_op = [
        "📊 Tổng quan",
        "📈 Báo cáo chi tiết",
        "📋 NQ11",
        "📡 Điện Báo",
        "🔍 Tra cứu hồ sơ",
        "📋 Danh sách & Lọc",
        "🎯 KHTD",
        "📋 Giao & ĐC KHTD",
        "🏘️ Tổ TK&VV",
        "🤝 Hội đoàn thể",
        "📢 Giao ban",
        "📍 Điểm GD của tôi",
        "📄 Mẫu biểu",
        "📋 Nhiệm vụ",
        "📤 Upload Dữ liệu",
        "📋 Mẫu 07 Giao KH",
        "🏛️ Ban Đại Diện",
    ]
    # Lazy render: chỉ chạy nội dung tab đang mở (cần key + on_change="rerun";
    # nhãn tab hiện tại: st.session_state["ws_op_active_tab"]).
    tabs_op = st.tabs(tab_names_op, key="ws_op_active_tab", on_change="rerun")

    _ix_mau_bieu = tab_names_op.index("📄 Mẫu biểu")

    def _render_mau_bieu_tab() -> None:
        with tabs_op[_ix_mau_bieu]:
            _render_doc_hub(df, df_nq11, role)

    def _render_hoi_doan_the_tab() -> None:
        """Render tab Hội đoàn thể với 2 luồng dữ liệu: CN vs PGD."""
        with tabs_op[9]:  # "🤝 Hội đoàn thể"
            # Xác định luồng dữ liệu
            if role == "user" and pgd_user:
                # PGD mode: chỉ dữ liệu PGD của user
                df_hdt = df.copy() if df is not None else pd.DataFrame()
                st.info(f"📍 Dữ liệu PGD: **{pgd_user}**")
            else:
                # CN mode: toàn bộ dữ liệu (admin/manager)
                df_hdt = df.copy() if df is not None else pd.DataFrame()
                if df_hdt.empty:
                    st.warning("⚠️ Chưa có dữ liệu HSTD.")
                    return
                # Cho phép chọn PGD nếu là admin/manager
                chon_pgd_filter = "Tất cả"  # Default
                if COT_TEN_PGD in df_hdt.columns:
                    ds_pgd = sorted(df_hdt[COT_TEN_PGD].dropna().unique().tolist())
                    if ds_pgd:
                        chon_pgd_filter = st.selectbox("Lọc theo PGD", ["Tất cả"] + ds_pgd, key="hdt_cn_pgd_filter")
                        if chon_pgd_filter != "Tất cả":
                            df_hdt = df_hdt[df_hdt[COT_TEN_PGD] == chon_pgd_filter].copy()
                        st.success(f"📊 Dữ liệu CN: **{len(df_hdt)}** hồ sơ" + (f" | PGD: {chon_pgd_filter}" if chon_pgd_filter != "Tất cả" else f" | **{len(ds_pgd)}** PGD"))

            # Gọi render của tab_hoi_doan_the với df đã lọc
            if not df_hdt.empty:
                hdt_kwargs = {**kwargs, "df": df_hdt, "df_full": df_hdt, "role": role}
                tab_hoi_doan_the.render(tabs_op[9], **hdt_kwargs)

    # Lọc df theo PGD nếu là role user
    if role == "user" and pgd_user and df is not None and COT_TEN_PGD in df.columns:
        df_pgd = df[df[COT_TEN_PGD] == pgd_user].copy()
    else:
        df_pgd = df  # admin/manager giữ nguyên toàn CN

    _pgd_df_kwargs = {**kwargs, "df": df_pgd, "df_full": df_pgd}
    _tab_renderers = (
        lambda: tab_tongquan.render(tabs_op[0], **_pgd_df_kwargs),
        lambda: tab_baocao.render(tabs_op[1], **_pgd_df_kwargs),
        lambda: tab_nq11.render(tabs_op[2], **_pgd_df_kwargs),
        lambda: tab_candoi.render(
            tabs_op[3], **{**kwargs, "pgd_mode": True, "df": df, "df_full": df}
        ),
        lambda: tab_tracuu.render(tabs_op[4], **kwargs),
        lambda: tab_danhsach.render(tabs_op[5], **kwargs),
        lambda: tab_khtd_pgd.render(tabs_op[6], **kwargs),
        lambda: tab_khtd_giao_dc.render(tabs_op[7], **kwargs),
        lambda: tab_cdtotkvv_pgd.render(tabs_op[8], **kwargs),
        lambda: _render_hoi_doan_the_tab(),
        lambda: _render_thong_bao_ket_luan(tabs_op[10], **_pgd_df_kwargs),
        lambda: tab_diem_gd_pgd.render(tabs_op[11], **kwargs),
        lambda: _render_mau_bieu_tab(),
        lambda: tab_nhiem_vu.render(tabs_op[13], **kwargs),
        lambda: tab_upload_pgd.render(tabs_op[14], **kwargs),
        lambda: tab_khtd_mau07.render(tabs_op[15], **kwargs),
        lambda: tab_ban_dai_dien.render(tabs_op[16], cap="xa", **kwargs),
    )
    assert len(tab_names_op) == len(_tab_renderers), (
        "tab_names_op và _tab_renderers phải cùng số phần tử"
    )

    for i, tab_c in enumerate(tabs_op):
        if tab_c.open:
            _tab_renderers[i]()
