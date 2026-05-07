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
    COT_LAI_TON, COT_LAI_THANG, COT_DVUT,
    TEMPLATES_DIR, TAG_MAP,
)
from auth import co_quyen_upload_pgd, is_cn_role, is_pgd_role, get_permissions
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
    tab_uy_thac,
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

        chon_xa = st.session_state.get("gb2_xa", ds_xa[0])
        if chon_xa not in ds_xa:
            chon_xa = ds_xa[0]

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
            st.info(
                f"📊 Số liệu tự động từ HSTD\n\n"
                f"**Xã:** {chon_xa}  \n"
                f"**Tháng:** {date.today().month}/{date.today().year}\n\n"
                "Chọn xã và mốc baseline ở tab **Biên bản giao ban** "
                "(cùng màn hình Mẫu biểu)."
            )

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
                    df_baseline=df_bl,
                    nam_moc=chon_nam or date.today().year - 1,
                )
                ten_file = (
                    f"TB_KetLuan_{chon_xa.replace(' ', '_')}"
                    f"_{date.today().strftime('%m%Y')}.docx"
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
                st.download_button(
                    "⬇️ Tải về Word", data=data, file_name=ten_file,
                    mime="application/vnd.openxmlformats-officedocument"
                         ".wordprocessingml.document",
                    key="gb2_dl_word",
                )
                st.success("✅ Đã tạo biên bản!")
            except Exception as e:
                st.error(f"❌ Lỗi xuất file: {e}")
                st.exception(e)


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
        df_dgd_marked = danh_dau_khong_hd(df_dgd)
        
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
        
        tom_tat = f"""Khu vực {khu_vuc_text}, xã {chon_xa}: Tổng dư nợ đạt {tong_dn:.1f} triệu đồng, với {fmt_so(so_kh)} khách hàng còn dư nợ, thông qua {so_to} Tổ TK&VV. Trong đó, nợ quá hạn {nqh:.1f} triệu đồng, tỷ lệ {tl_nqh:.2f}%; nợ khoanh {nkh:.1f} triệu đồng.
Doanh số cho vay trong tháng: {ds_cv:.1f} triệu đồng; doanh số thu nợ trong tháng: {ds_thu:.1f} triệu đồng."""
        
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
                
                st.download_button(
                    label=f"📥 Tải về {ten_file}",
                    data=buf,
                    file_name=ten_file,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="gb_download"
                )
                st.success(f"✅ Đã tạo file Excel: **{ten_file}**")
            except Exception as e:
                st.error(f"❌ Lỗi xuất Excel: {e}")


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
        "📍 Điểm GD & Tổ TK&VV",
        "📝 Báo cáo Giao ban",
        "📄 Mẫu biểu",
        "📋 Nhiệm vụ",
        "📤 Upload Dữ liệu",
        "📋 Mẫu 07 Giao KH",
        "🏛️ Ban Đại Diện",
        "🤝 Ủy thác",
    ]
    # Thêm tab Upload HSTD cho admin_pgd/manager_pgd
    if co_quyen_upload_pgd(role):
        tab_names_op.append("📤 Upload HSTD")

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

    # Lazy render: chỉ chạy nội dung tab đang mở (cần key + on_change="rerun";
    # nhãn tab hiện tại: st.session_state["ws_op_active_tab"]).
    tabs_op = st.tabs(tab_names_op, key="ws_op_active_tab", on_change="rerun")

    _ix_mau_bieu = tab_names_op.index("📄 Mẫu biểu")

    def _render_mau_bieu_tab() -> None:
        with tabs_op[_ix_mau_bieu]:
            _init_gb2_session_for_doc_hub(kwargs)
            doc_t1, doc_t2, doc_t3 = st.tabs(
                [
                    "📄 Trung tâm mẫu biểu",
                    "📋 Biên bản giao ban",
                    "📢 Thông báo kết luận",
                ]
            )
            with doc_t1:
                _render_doc_hub(df, df_nq11, role)
            with doc_t2:
                _render_bien_ban_giao_ban(doc_t2, **kwargs)
            with doc_t3:
                _render_thong_bao_ket_luan(doc_t3, **kwargs)

    # Lọc df theo PGD cho user để tab Tổng quan hiển thị đúng phạm vi
    if is_pgd_role(role) and pgd_user and df is not None and COT_TEN_PGD in df.columns:
        df_pgd = df[df[COT_TEN_PGD] == pgd_user].copy()
    elif is_cn_role(role) and pgd_filter is not None and df is not None and COT_TEN_PGD in df.columns:
        df_pgd = df[df[COT_TEN_PGD] == pgd_filter].copy()
    else:
        df_pgd = df
    _pgd_df_kwargs = {**kwargs, "df": df_pgd, "df_full": df_pgd, "pgd_filter": pgd_filter}

    def _render_diem_gd_va_to_tkvv(tab_parent, **kw):
        with tab_parent:
            _sub1, _sub2 = st.tabs(["📍 Điểm Giao Dịch", "🏘️ Tổ TK&VV"])
            tab_diem_gd_pgd.render(_sub1, **kw)
            tab_cdtotkvv_pgd.render(_sub2, **kw)

    _tab_renderers = [
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
        lambda: _render_diem_gd_va_to_tkvv(tabs_op[8], **kwargs),
        lambda: _render_bao_cao_giao_ban(tabs_op[9], **kwargs),
        lambda: _render_mau_bieu_tab(),
        lambda: tab_nhiem_vu.render(tabs_op[11], **kwargs),
        lambda: tab_upload_pgd.render(tabs_op[12], **kwargs),
        lambda: tab_khtd_mau07.render(tabs_op[13], **kwargs),
        lambda: tab_ban_dai_dien.render(tabs_op[14], cap="xa", **kwargs),
        lambda: tab_uy_thac.render(tabs_op[15], **kwargs),
    ]

    # Thêm renderer cho tab Upload HSTD nếu có quyền
    if co_quyen_upload_pgd(role):
        from tabs.tab_upload_pgd import render as render_upload_pgd
        _tab_renderers.append(lambda: render_upload_pgd(pgd_user=pgd_user, role=role))

    _tab_renderers = tuple(_tab_renderers)
    assert len(tab_names_op) == len(_tab_renderers), (
        "tab_names_op và _tab_renderers phải cùng số phần tử"
    )

    for i, tab_c in enumerate(tabs_op):
        if tab_c.open:
            _tab_renderers[i]()
