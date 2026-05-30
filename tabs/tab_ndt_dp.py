"""Tab Mã Nhà đầu tư Địa phương — Phiên bản PGD (chỉ xem).

Danh sách mã NĐT Cấp tỉnh dùng để phân tầng GQVL ĐP trong báo cáo.
PGD chỉ có quyền xem, không chỉnh sửa.
"""
from __future__ import annotations

from io import BytesIO

import pandas as pd
import streamlit as st
from streamlit.delta_generator import DeltaGenerator

import db
from auth import la_phan_he_cn
from utils import hien_thi_dataframe_phan_trang


def render(tab: DeltaGenerator = None, **kwargs) -> None:
    """Render tab NĐT ĐP — PGD mode chỉ xem, CN mode có thể chỉnh sửa."""
    df = kwargs.get("df")
    df_full = kwargs.get("df_full", df)
    role = kwargs.get("role", "user")
    username = kwargs.get("username", "unknown")
    pgd_user = kwargs.get("pgd_user", "")  # PGD mode filter

    ctx = tab if tab is not None else st.container()

    with ctx:
        st.subheader("🏦 Mã Nhà đầu tư Địa phương")

        if pgd_user:
            st.caption(
                f"Danh sách mã NĐT Cấp tỉnh — chỉ xem dữ liệu phân tầng GQVL ĐP tại **{pgd_user}**. "
                "Liên hệ Phòng KH-NV nếu cần thêm/sửa mã NĐT."
            )
        else:
            st.caption(
                "Danh sách mã NĐT Cấp tỉnh — dùng phân tầng GQVL ĐP trong báo cáo. "
                "Chỉ **Admin CN** mới có thể thêm / sửa / xóa."
            )

        # Đọc danh sách NĐT
        ds = db.doc_ndt_dp_list()

        if not ds:
            st.info("ℹ️ Chưa có danh sách mã NĐT. Vui lòng liên hệ Phòng KH-NV để cập nhật.")
            return

        # Hiển thị danh sách
        rows = []
        for x in ds:
            cap = x.get("cap", "tinh")
            cap_label = "Cấp Tỉnh 🏛️" if cap == "tinh" else "Cấp Xã 🏘️"
            rows.append({
                "Mã NĐT": x["ma"],
                "Ghi chú": x.get("ghi_chu", ""),
                "Phân loại cấp": cap_label,
                "Cập nhật": x.get("ngay_cap", ""),
            })

        df_ndt = pd.DataFrame(rows)

        # Filter theo PGD nếu có (hiển thị thông báo)
        if pgd_user:
            st.success(f"✅ Hiển thị toàn bộ {len(df_ndt)} mã NĐT từ danh sách Cấp tỉnh.")
            st.info(
                "💡 Mã NĐT này dùng để phân loại GQVL ĐP Cấp tỉnh trong báo cáo. "
                "PGD không cần quản lý trực tiếp."
            )

        hien_thi_dataframe_phan_trang(df_ndt, key="ndt_dp_table", height=400)

        # Thống kê
        col1, col2, col3 = st.columns(3)
        col1.metric("Tổng mã NĐT", len(ds))
        col2.metric("Cấp Tỉnh", sum(1 for x in ds if x.get("cap") == "tinh"))
        col3.metric("Cấp Xã", sum(1 for x in ds if x.get("cap") != "tinh"))

        # Hướng dẫn
        with st.expander("📖 Hướng dẫn sử dụng"):
            st.markdown("""
**Cách phân tầng GQVL ĐP:**

| Tầng | Điều kiện | Ví dụ |
|:---|:---|:---|
| **GQVL ĐP — Cấp tỉnh** | Mã NĐT của món vay **có trong danh sách Cấp Tỉnh** | UBND tỉnh Đồng Nai |
| **GQVL ĐP — Cấp xã/khác** | Mã NĐT **không có** trong danh sách | Vốn huyện, xã, tổ chức khác |

Danh sách này ảnh hưởng trực tiếp đến báo cáo **phân tầng GQVL**.
            """)

        # Xuất Excel (chỉ Admin CN)
        if la_phan_he_cn(role) and not pgd_user:
            st.divider()
            buf = BytesIO()
            df_ndt.to_excel(buf, index=False, engine="openpyxl")
            st.download_button(
                "📥 Xuất danh sách Excel",
                data=buf.getvalue(),
                file_name="Ma_NDT_Dia_Phuong.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="ndt_dp_export",
            )
