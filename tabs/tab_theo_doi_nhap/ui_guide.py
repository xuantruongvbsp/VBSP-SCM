"""Hướng dẫn sử dụng tab Theo dõi Nhập liệu."""
from __future__ import annotations

import streamlit as st

from .constants import MOCKUP_HTML


def render_huong_dan() -> None:
    st.markdown("### 📖 Hướng dẫn sử dụng Theo dõi nhập liệu")

    st.markdown("""
    **Mục đích:** Theo dõi tiến trình nhập liệu của các PGD trên Google Sheets —
    giúp Ban Giám đốc và Phòng KH-NV nắm được PGD nào đã điền đầy đủ số liệu,
    PGD nào còn thiếu, và thiếu ở chỉ tiêu nào.
    """)

    st.divider()

    st.markdown("#### 🟢🟡🔴 Cách đọc kết quả")
    st.markdown("""
    | Biểu tượng | Ý nghĩa |
    |---|---|
    | 🟢 | **Hoàn thành** — tất cả các hàng trong PGD đã được điền đầy đủ |
    | 🟡 | **Một phần** — có điền nhưng chưa đầy đủ |
    | 🔴 | **Chưa điền** — chưa có dữ liệu nào |
    """)

    st.markdown("**Ví dụ:** `🟢 14/14 (100%)` → PGD có 14 xã/phường, đã điền đủ 14/14.")

    st.divider()

    st.markdown("#### 📊 Các tab chức năng")
    st.markdown("""
    - **📊 Tổng quan** — Dashboard KPI + Biểu đồ tiến độ + Ma trận Heatmap, giúp nhìn nhanh toàn cảnh
    - **📋 Chi tiết** — Bảng số liệu chi tiết, lọc theo chương trình, drill-down xã/phường, xuất Excel
    - **⚙️ Cài đặt** — *(Chỉ dành cho Admin/Manager CN)* Thêm/sửa/xóa cấu hình Google Sheet
    """)

    st.divider()

    st.markdown("#### 🗂️ Cấu trúc Google Sheet được hỗ trợ")

    st.markdown("Có **3 kiểu cấu trúc** sheet:")

    st.markdown("""
    **1. 📊 Phân cấp STT** *(mặc định, phổ biến nhất)*
    - Hàng PGD: Cột STT là chữ La Mã (I, II, III...), Cột tên = "PGD X"
    - Hàng xã/phường: Cột STT là số (1, 2, 3...), Cột tên = "Phường Y"
    - Mỗi PGD có nhiều xã/phường con bên dưới

    **2. 📋 Phẳng**
    - Mỗi hàng = 1 đơn vị, không có hàng con
    - Phù hợp khi sheet chỉ liệt kê các PGD (không có xã)

    **3. 🗂 Cột PGD riêng**
    - Có một cột riêng ghi tên PGD cho mỗi hàng
    - Phù hợp khi sheet không dùng STT phân cấp
    """)

    st.markdown("##### Ví dụ minh họa — Kiểu Phân cấp STT")
    st.html(MOCKUP_HTML)

    st.divider()

    st.markdown("#### 🔌 Cách thêm Google Sheet mới *(dành cho Admin/Manager)*")
    st.markdown("""
    1. Vào tab **⚙️ Cài đặt**
    2. Kéo xuống mục **➕ Thêm Google Sheet mới**
    3. Paste link Google Sheet vào ô nhập
    4. Hệ thống sẽ tự động đọc danh sách tab — chọn tab cần theo dõi
    5. Đặt tên hiển thị cho sheet
    6. Nhấn **➕ Thêm**

    **Lưu ý:**
    - Google Sheet phải được chia sẻ quyền **Viewer** cho tài khoản service account trong `credentials.json`
    - Nếu các sheet có cùng cấu trúc cột, hệ thống sẽ tự copy cấu hình từ sheet đầu tiên
    - Sau khi thêm, có thể mở expander để chỉnh lại cấu hình cột nếu cần
    """)

    st.divider()

    st.markdown("#### ⚙️ Các thông số cấu hình chính")
    st.markdown("""
    | Thông số | Giải thích | Ví dụ |
    |---|---|---|
    | **Header row** | Hàng chứa tên cột (STT, Tên PGD...) | `8` → dữ liệu bắt đầu từ hàng 9 |
    | **Cột STT** | Cột phân biệt PGD (chữ) và xã (số) | `1` → cột A |
    | **Cột Tên đơn vị** | Cột chứa tên PGD hoặc tên xã | `2` → cột B |
    | **Cột theo dõi** | Các cột cần kiểm tra đã điền hay chưa | `4` → cột D (HSSV) |
    | **Hạn chót** | ⭐ *Mới* — Ngày deadline nhập liệu | `15/06/2026` |
    """)

    st.info(
        "💡 **Mẹo:** Mở Google Sheet → đếm cột từ trái sang phải để biết số cột. "
        "Cột A = 1, B = 2, C = 3..."
    )

    st.divider()

    st.markdown("#### 🔄 Làm mới dữ liệu")
    st.markdown("""
    - Dữ liệu được cache **5 phút** để tránh gọi GSheet liên tục
    - Nhấn nút **🔄** bên cạnh ô chọn sheet để làm mới ngay
    - Sau khi sửa cấu hình → dữ liệu tự động làm mới
    """)

    st.divider()

    st.markdown("#### ⭐ Tính năng mới")
    st.markdown("""
    - **📊 So sánh kỳ** — So sánh tiến độ với lần kiểm tra trước
    - **🗺️ Ma trận Heatmap** — Nhìn trực quan tiến độ từng PGD với màu sắc
    - **📊 Progress Bars** — Thanh tiến trình ngang cho từng đơn vị
    - **🔍 Drill-down xã/phường** — Xem chi tiết từng xã/phường của một PGD
    - **⏰ Hạn chót** — Đặt deadline nhập liệu cho mỗi sheet
    """)

    st.divider()

    st.markdown("#### ❓ Câu hỏi thường gặp")
    with st.expander("Tôi không thấy tab ⚙️ Cài đặt?"):
        st.markdown(
            "Tab ⚙️ Cài đặt chỉ hiển thị cho **Admin CN** và **Manager CN**. "
            "Nếu bạn là PGD, vui lòng liên hệ Phòng KH-NV để được hỗ trợ cấu hình."
        )
    with st.expander("Sheet báo lỗi khi đọc?"):
        st.markdown(
            "Kiểm tra:\n"
            "1. Sheet đã được chia sẻ cho service account chưa?\n"
            "2. Sheet ID và tên tab có đúng không?\n"
            "3. `credentials.json` đã có trong thư mục dự án chưa?"
        )
    with st.expander("Sao kết quả không khớp với sheet?"):
        st.markdown(
            "Kiểm tra:\n"
            "1. **Header row** đã đúng hàng chứa tên cột chưa?\n"
            "2. **Cột STT** và **Cột Tên đơn vị** đã đúng vị trí chưa?\n"
            "3. **Cột theo dõi** đã trỏ đúng cột cần kiểm tra chưa?\n"
            "4. Nhấn **🔄** để làm mới dữ liệu."
        )
