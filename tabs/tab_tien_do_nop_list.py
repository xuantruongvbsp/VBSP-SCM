"""UI danh sách nộp và export cho tab Tiến độ nộp báo cáo."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from services.report_submission_service import EMOJI, LABEL, gan_trang_thai
from utils import xuat_excel


def _chon_cot_chi_tiet(df: pd.DataFrame) -> pd.DataFrame:
    """Lấy các cột nghiệp vụ gọn để hiển thị/xuất báo cáo điều hành."""
    cols = [
        "Đơn vị",
        "Loại báo cáo",
        "Trạng thái",
        "Thời hạn",
        "Ngày nộp cuối",
        "Kỳ báo cáo",
        "Nguồn trạng thái",
        "Có file",
        "Quá hạn (ngày)",
        "Nhóm hành động",
        "Ghi chú",
    ]
    cols = [c for c in cols if c in df.columns]
    return df[cols].copy()


def render_submission_list(
    df: pd.DataFrame,
    deadline_cfg: dict,
    is_cn: bool,
    pgd_user: str | None,
    bao_cao_tien_do: dict,
) -> None:
    """Render danh sách lượt nộp, nghĩa vụ theo deadline và export."""
    if df.empty:
        st.info("Chưa có dữ liệu.")
        return

    col1, col2, col3 = st.columns(3)
    with col1:
        ds_loai = ["Tất cả"] + sorted(df["loai_bao_cao"].dropna().unique().tolist())
        loai_chon = st.selectbox("Loại báo cáo", ds_loai, key="ds_loai")
    with col2:
        if is_cn:
            ds_don_vi = ["Tất cả"] + sorted(df["ten_pgd"].dropna().unique().tolist())
            pgd_chon = st.selectbox("Đơn vị", ds_don_vi, key="ds_pgd")
        else:
            pgd_chon = pgd_user or "Tất cả"
            st.caption(f"Đơn vị: **{pgd_chon}**")
    with col3:
        ds_ky = sorted({str(x).strip() for x in df["ky_bao_cao"].dropna().tolist() if str(x).strip()})
        ky_chon = st.selectbox("Kỳ báo cáo", ["Tất cả"] + ds_ky, key="ds_ky")

    col4, col5 = st.columns(2)
    with col4:
        trang_thai_chon = st.selectbox(
            "Trạng thái",
            ["Tất cả", "Đúng hạn", "Trễ hạn", "Đã nộp chưa cài hạn", "Thiếu file"],
            key="ds_tt",
        )
    with col5:
        chat_luong_file = st.selectbox(
            "Chất lượng file",
            ["Tất cả", "Có file", "Thiếu file"],
            key="ds_file_status",
        )

    df_loc = df.copy()
    if loai_chon != "Tất cả":
        df_loc = df_loc[df_loc["loai_bao_cao"] == loai_chon]
    if pgd_chon and pgd_chon != "Tất cả":
        df_loc = df_loc[df_loc["ten_pgd"] == pgd_chon]
    if ky_chon != "Tất cả":
        df_loc = df_loc[df_loc["ky_bao_cao"].astype(str).str.strip() == ky_chon]

    df_loc, _ = gan_trang_thai(df_loc, deadline_cfg)
    df_loc["co_file_bool"] = df_loc["file_dinh_kem"].fillna("").astype(str).str.strip().ne("")
    df_loc["tt_hien"] = df_loc.apply(
        lambda r: f"{EMOJI['thieu_file']} {LABEL['thieu_file']}"
        if not r["co_file_bool"]
        else f"{EMOJI.get(r['tt'], '')} {LABEL.get(r['tt'], r['tt'])}",
        axis=1,
    )

    if trang_thai_chon == "Đúng hạn":
        df_loc = df_loc[(df_loc["tt"] == "dung_han") & df_loc["co_file_bool"]]
    elif trang_thai_chon == "Trễ hạn":
        df_loc = df_loc[(df_loc["tt"] == "tre") & df_loc["co_file_bool"]]
    elif trang_thai_chon == "Đã nộp chưa cài hạn":
        df_loc = df_loc[(df_loc["tt"] == "da_nop") & df_loc["co_file_bool"]]
    elif trang_thai_chon == "Thiếu file":
        df_loc = df_loc[~df_loc["co_file_bool"]]

    if chat_luong_file == "Có file":
        df_loc = df_loc[df_loc["co_file_bool"]]
    elif chat_luong_file == "Thiếu file":
        df_loc = df_loc[~df_loc["co_file_bool"]]

    st.caption(f"Hiển thị {len(df_loc)} / {len(df)} lượt nộp từ Google Form")

    df_hien = df_loc[
        [
            "thoi_gian",
            "ho_ten",
            "ten_pgd",
            "loai_bao_cao",
            "ky_bao_cao",
            "tt_hien",
            "noi_dung",
            "file_dinh_kem",
        ]
    ].copy()
    df_hien["thoi_gian"] = df_hien["thoi_gian"].dt.strftime("%d/%m/%Y %H:%M")
    df_hien["ky_bao_cao"] = df_hien["ky_bao_cao"].fillna("").astype(str).replace("", "—")
    df_hien = df_hien.rename(
        columns={
            "thoi_gian": "Thời gian",
            "ho_ten": "Họ tên",
            "ten_pgd": "Đơn vị",
            "loai_bao_cao": "Loại",
            "ky_bao_cao": "Kỳ báo cáo",
            "tt_hien": "Trạng thái",
            "noi_dung": "Nội dung",
            "file_dinh_kem": "File",
        }
    )
    st.dataframe(
        df_hien,
        use_container_width=True,
        hide_index=True,
        column_config={
            "File": st.column_config.LinkColumn("File", display_text="📎 Xem"),
            "Nội dung": st.column_config.TextColumn(width="large"),
        },
    )
    st.caption(
        "💡 Nếu link Drive không mở được: PGD cần set quyền chia sẻ file là "
        "**\"Anyone with the link can view\"** trước khi paste vào Form."
    )

    st.divider()
    st.markdown("### 📌 Kiểm soát nghĩa vụ theo deadline")
    loai_theo_doi = st.radio(
        "Chọn lớp theo dõi",
        ["Tất cả nghĩa vụ", "Chưa hoàn thành", "Cần xử lý hôm nay", "Sắp đến hạn"],
        horizontal=True,
        key="ds_nghia_vu_mode",
    )

    if loai_theo_doi == "Chưa hoàn thành":
        df_nghia_vu = bao_cao_tien_do.get("df_chua_hoan_thanh", pd.DataFrame()).copy()
    elif loai_theo_doi == "Cần xử lý hôm nay":
        df_nghia_vu = bao_cao_tien_do.get("df_can_xu_ly", pd.DataFrame()).copy()
    elif loai_theo_doi == "Sắp đến hạn":
        df_nghia_vu = bao_cao_tien_do.get("df_sap_den_han", pd.DataFrame()).copy()
    else:
        df_nghia_vu = bao_cao_tien_do.get("df_chi_tiet", pd.DataFrame()).copy()

    if not df_nghia_vu.empty:
        if loai_chon != "Tất cả":
            df_nghia_vu = df_nghia_vu[df_nghia_vu["Loại báo cáo"] == loai_chon]
        if pgd_chon and pgd_chon != "Tất cả":
            df_nghia_vu = df_nghia_vu[df_nghia_vu["Đơn vị"] == pgd_chon]
        if ky_chon != "Tất cả":
            df_nghia_vu = df_nghia_vu[df_nghia_vu["Kỳ báo cáo"] == ky_chon]
        if trang_thai_chon == "Đúng hạn":
            df_nghia_vu = df_nghia_vu[df_nghia_vu["Mã trạng thái"] == "dung_han"]
        elif trang_thai_chon == "Trễ hạn":
            df_nghia_vu = df_nghia_vu[df_nghia_vu["Mã trạng thái"] == "tre"]
        elif trang_thai_chon == "Đã nộp chưa cài hạn":
            df_nghia_vu = df_nghia_vu[df_nghia_vu["Mã trạng thái"] == "da_nop"]
        elif trang_thai_chon == "Thiếu file":
            df_nghia_vu = df_nghia_vu[df_nghia_vu["Mã trạng thái"] == "thieu_file"]
        if chat_luong_file == "Có file":
            df_nghia_vu = df_nghia_vu[df_nghia_vu["Có file"] == "Có"]
        elif chat_luong_file == "Thiếu file":
            df_nghia_vu = df_nghia_vu[df_nghia_vu["Có file"] == "Không"]

    if df_nghia_vu.empty:
        st.info("Không có nghĩa vụ nào khớp bộ lọc hiện tại.")
    else:
        st.caption(f"📋 {len(df_nghia_vu)} nghĩa vụ — **{loai_theo_doi}**")
        st.dataframe(_chon_cot_chi_tiet(df_nghia_vu), hide_index=True, use_container_width=True)

    st.divider()
    st.markdown("### 📥 Xuất danh sách lượt nộp")
    loai_xuat_ds = st.radio(
        "Chọn loại lượt nộp để xuất",
        ["Tất cả", "Có file hợp lệ", "Thiếu file"],
        horizontal=True,
        key="ds_loai_xuat",
    )
    if loai_xuat_ds == "Có file hợp lệ":
        df_xuat_ds = df_loc[df_loc["tt"].isin(["dung_han", "tre", "da_nop"]) & df_loc["co_file_bool"]]
    elif loai_xuat_ds == "Thiếu file":
        df_xuat_ds = df_loc[~df_loc["co_file_bool"]]
    else:
        df_xuat_ds = df_loc

    if df_xuat_ds.empty:
        st.info(f"Không có báo cáo **{loai_xuat_ds.lower()}**.")
    else:
        st.caption(f"📋 {len(df_xuat_ds)} lượt nộp — **{loai_xuat_ds}**")
        ten_file_ds = f"tien_do_nop_{loai_xuat_ds.replace(' ', '_').lower()}"
        col_excel, col_pdf, _ = st.columns([1, 1, 5])
        with col_excel:
            if st.button("📥 Xuất Excel", key="btn_xuat_tdn", use_container_width=True, type="primary"):
                df_export = df_xuat_ds.drop(columns=["tt", "tt_hien", "co_file_bool"], errors="ignore")
                st.session_state["_excel_tdn_bytes"] = xuat_excel({f"Tiến độ nộp — {loai_xuat_ds}": df_export})
                st.session_state["_excel_tdn_ten"] = f"{ten_file_ds}.xlsx"
        if st.session_state.get("_excel_tdn_bytes"):
            st.download_button(
                "⬇ Tải Excel",
                data=st.session_state["_excel_tdn_bytes"],
                file_name=st.session_state["_excel_tdn_ten"],
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="dl_excel_tdn",
            )
        with col_pdf:
            from pdf_service import nut_xuat_pdf

            df_for_pdf = df_xuat_ds.drop(
                columns=["tt", "tt_hien", "co_file_bool", "file_dinh_kem", "email"],
                errors="ignore",
            ).copy()
            if "thoi_gian" in df_for_pdf.columns:
                df_for_pdf["thoi_gian"] = df_for_pdf["thoi_gian"].dt.strftime("%d/%m/%Y")
            if "noi_dung" in df_for_pdf.columns:
                df_for_pdf["noi_dung"] = df_for_pdf["noi_dung"].astype(str).str[:80]
            df_for_pdf = df_for_pdf.rename(
                columns={
                    "thoi_gian": "Thời gian",
                    "ho_ten": "Họ tên",
                    "ten_pgd": "Đơn vị",
                    "loai_bao_cao": "Loại BC",
                    "ky_bao_cao": "Kỳ",
                    "noi_dung": "Nội dung",
                }
            )

            nut_xuat_pdf(
                df_for_pdf,
                f"Tiến độ nộp báo cáo — {loai_xuat_ds}",
                st.session_state.get("username", "unknown"),
                cols_tien=[],
                prefix_file=ten_file_ds,
                key="pdf_tdn",
            )
