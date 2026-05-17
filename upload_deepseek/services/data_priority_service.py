"""
Dịch vụ Trạng thái Dữ liệu - VBSP SCM
──────────────────────────────────────────────────────────────────
Hiển thị trạng thái file pgd_data/ cho sidebar và widget.
Không quyết định nguồn dữ liệu cho tab — đó là trách nhiệm của app.py.

Hai luồng dữ liệu độc lập:
  ws_management/executive → CACHE_HSTD/NQ11/GQVL (do KH-NV tạo)
  ws_operation            → pgd_data/{slug}/ (do PGD upload)
"""

import os
from datetime import datetime
from typing import Dict, Optional

import db
from config import DS_PGD, DON_VI_CHI_NHANH, UPLOAD_CANH_BAO_NGAY


class NguonDuLieu:
    PGD_UPLOAD = "pgd_upload"
    CHUA_UPLOAD = "chua_upload"
    KHONG_CO = "khong_co"


def kiem_tra_nguon_uu_tien(ten_don_vi: str, loai_file: str) -> Dict:
    """
    Kiểm tra trạng thái file pgd_data/ của một đơn vị.
    Chỉ dùng để hiển thị widget — không quyết định nguồn dữ liệu cho tab.
    """
    from data.pgd import duong_dan_pgd, doc_trang_thai_file

    canh_bao = []
    pgd_info = doc_trang_thai_file(ten_don_vi, loai_file)

    if pgd_info["co_file"]:
        nguon_uu_tien = NguonDuLieu.PGD_UPLOAD
        duong_dan = duong_dan_pgd(ten_don_vi, loai_file)
        ly_do = f"✅ Đã upload từ {ten_don_vi}"
        if pgd_info["canh_bao"] == "cu":
            canh_bao.append(f"⚠️ Dữ liệu {loai_file.upper()} đã cũ {pgd_info['so_ngay_cu']} ngày")
    else:
        nguon_uu_tien = NguonDuLieu.CHUA_UPLOAD
        duong_dan = ""
        ly_do = f"📤 {ten_don_vi} chưa upload {loai_file.upper()}"
        canh_bao.append(f"📤 {ten_don_vi} chưa upload {loai_file.upper()}")

    return {
        "nguon_uu_tien": nguon_uu_tien,
        "duong_dan": duong_dan,
        "pgd_info": pgd_info,
        "ly_do": ly_do,
        "canh_bao": canh_bao
    }


def bao_cao_trang_thai_nguon() -> Dict:
    """Báo cáo tổng quan trạng thái file pgd_data/ đã upload."""
    bao_cao = {
        "thoi_gian_kiem_tra": datetime.now().isoformat(),
        "don_vi": {},
        "tom_tat": {
            "tong_don_vi": len(DS_PGD) + 1,
            "pgd_upload_day_du": 0,
            "can_cap_nhat": 0,
            "chua_upload": 0
        }
    }

    ds_don_vi = [DON_VI_CHI_NHANH] + DS_PGD
    ds_loai_file = ["hstd", "nq11", "gqvl"]

    for don_vi in ds_don_vi:
        bao_cao["don_vi"][don_vi] = {}
        co_du_file_pgd = True
        can_cap_nhat = False

        for loai in ds_loai_file:
            tt = kiem_tra_nguon_uu_tien(don_vi, loai)
            bao_cao["don_vi"][don_vi][loai] = tt

            if tt["nguon_uu_tien"] != NguonDuLieu.PGD_UPLOAD:
                co_du_file_pgd = False
            if tt["canh_bao"]:
                can_cap_nhat = True

        if co_du_file_pgd and don_vi != DON_VI_CHI_NHANH:
            bao_cao["tom_tat"]["pgd_upload_day_du"] += 1
        if can_cap_nhat:
            bao_cao["tom_tat"]["can_cap_nhat"] += 1

        chua_upload = all(
            bao_cao["don_vi"][don_vi][loai]["nguon_uu_tien"] == NguonDuLieu.CHUA_UPLOAD
            for loai in ds_loai_file
        )
        if chua_upload:
            bao_cao["tom_tat"]["chua_upload"] += 1

    return bao_cao


def cap_nhat_nguon_uu_tien(username: str) -> Dict:
    """Cập nhật trạng thái file pgd_data/ toàn Chi nhánh."""
    bao_cao = bao_cao_trang_thai_nguon()

    db.ghi_kv("data_priority_report", bao_cao, username)

    tom_tat = bao_cao["tom_tat"]
    db.ghi_audit(
        username, "cap_nhat_trang_thai_pgd",
        f"PGD đã upload đầy đủ: {tom_tat['pgd_upload_day_du']}/{tom_tat['tong_don_vi']-1}"
    )

    return {
        "thanh_cong": True,
        "thong_bao": f"✅ Cập nhật thành công! PGD đầy đủ: {tom_tat['pgd_upload_day_du']}/{tom_tat['tong_don_vi']-1}"
    }


def lay_bao_cao_nguon() -> Optional[Dict]:
    """Lấy báo cáo gần nhất."""
    return db.doc_kv("data_priority_report")


def render_widget_trang_thai(pgd_user: Optional[str] = None) -> str:
    """Tạo widget hiển thị trạng thái ngắn gọn."""
    don_vi = pgd_user if pgd_user else DON_VI_CHI_NHANH
    
    ds_loai = ["hstd", "nq11", "gqvl"]
    co_canh_bao = False
    co_loi = False
    
    for loai in ds_loai:
        tt = kiem_tra_nguon_uu_tien(don_vi, loai)
        if tt["nguon_uu_tien"] == NguonDuLieu.KHONG_CO:
            co_loi = True
            break
        elif tt["canh_bao"]:
            co_canh_bao = True
    
    if co_loi:
        return "🔴 Thiếu dữ liệu"
    elif co_canh_bao:
        return "🟡 Cần cập nhật"
    else:
        return "🟢 Dữ liệu tốt"


def lay_thong_tin_nguon_hien_tai(ten_don_vi: str) -> Dict:
    """
    Lấy thông tin trạng thái file pgd_data/ của một đơn vị.
    Chỉ dùng để hiển thị widget.
    """
    ds_loai_file = ["hstd", "nq11", "gqvl", "cdtotkvv"]
    thong_tin = {}

    for loai in ds_loai_file:
        tt = kiem_tra_nguon_uu_tien(ten_don_vi, loai)
        pgd_info = tt.get("pgd_info", {})

        thong_tin[loai] = {
            "nguon": tt["nguon_uu_tien"],
            "trang_thai": {
                "co_file": pgd_info.get("co_file", False),
                "canh_bao": "ok" if not tt["canh_bao"] else "cu",
                "so_ngay_cu": pgd_info.get("so_ngay_cu", 0),
                "ngay_upload": pgd_info.get("ngay_upload"),
            },
            "ly_do": tt.get("ly_do", ""),
        }

    return thong_tin


def thong_ke_su_dung_nguon() -> Dict:
    """
    Thống kê tổng quan về trạng thái file pgd_data/ của các PGD.
    """
    thong_ke = {
        "pgd_upload": 0,
        "chua_upload": 0,
        "chi_tiet": {}
    }

    for pgd in DS_PGD:
        tt_hstd = kiem_tra_nguon_uu_tien(pgd, "hstd")
        nguon = tt_hstd["nguon_uu_tien"]

        thong_ke["chi_tiet"][pgd] = nguon

        if nguon == NguonDuLieu.PGD_UPLOAD:
            thong_ke["pgd_upload"] += 1
        else:
            thong_ke["chua_upload"] += 1

    return thong_ke


def hien_thi_trang_thai_nguon_widget(ten_don_vi: str) -> None:
    """
    Hiển thị widget trạng thái file pgd_data/ cho một đơn vị (Streamlit).
    """
    import streamlit as st

    thong_tin = lay_thong_tin_nguon_hien_tai(ten_don_vi)

    st.markdown(f"### 📊 Trạng thái dữ liệu địa bàn: **{ten_don_vi}**")

    cols = st.columns(len(thong_tin))

    for idx, (loai, info) in enumerate(thong_tin.items()):
        with cols[idx]:
            nguon = info["nguon"]
            tt = info["trang_thai"]

            if nguon == NguonDuLieu.PGD_UPLOAD and tt["co_file"]:
                if tt["canh_bao"] == "ok":
                    st.success(f"✅ **{loai.upper()}**\n\nĐã upload")
                    if tt.get("ngay_upload"):
                        st.caption(f"📅 {tt['ngay_upload']}")
                else:
                    st.warning(f"⚠️ **{loai.upper()}**\n\nCần cập nhật")
                    st.caption(f"⏰ {tt['so_ngay_cu']} ngày")
            else:
                st.error(f"📤 **{loai.upper()}**\n\nChưa upload")

    st.caption(info.get("ly_do", ""))


def hien_thi_tong_quan_nguon() -> None:
    """
    Hiển thị tổng quan trạng thái upload toàn Chi nhánh (Streamlit).
    """
    import streamlit as st

    thong_ke = thong_ke_su_dung_nguon()
    tong_pgd = len(DS_PGD)

    st.markdown("### 📊 Tổng quan dữ liệu địa bàn toàn Chi nhánh")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Tổng PGD", tong_pgd)
    with col2:
        st.metric("✅ Đã upload", thong_ke["pgd_upload"])
    with col3:
        st.metric("📤 Chưa upload", thong_ke["chua_upload"])

    ty_le = (thong_ke["pgd_upload"] / tong_pgd * 100) if tong_pgd > 0 else 0
    st.progress(ty_le / 100, text=f"Tỷ lệ PGD đã upload: {ty_le:.1f}%")

    if ty_le < 50:
        st.warning("💡 Khuyến khích các PGD upload dữ liệu địa bàn")
    elif ty_le < 80:
        st.info("📊 Tỷ lệ upload đang ở mức trung bình")
    else:
        st.success("🎉 Tỷ lệ upload tốt!")