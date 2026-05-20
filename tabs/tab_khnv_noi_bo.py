"""Tab Quản lý nội bộ Phòng KH-NV — 4 sub-tab:
1. Phân công cán bộ
2. Lịch công tác
3. Báo cáo cấp trên (wrapper)
4. Tiến độ thực hiện (tổng hợp tự động từ Phân công cán bộ)
"""

from uuid import uuid4
from datetime import date, datetime, timedelta
from collections import defaultdict

import streamlit as st
import pandas as pd

from auth import normalize_role, la_phan_he_cn
from db import doc_kv, ghi_kv, ghi_audit
from utils import get_tab_context
from components.export_pdf import xuat_pdf_co_chart, download_pdf_button
from tabs import tab_checklist_bc

LOAI_LICH = {
    "hop": "🗓️ Họp",
    "kiem_tra": "🔍 Kiểm tra thực địa",
    "cong_tac": "✈️ Công tác",
    "tap_huan": "🎓 Tập huấn",
    "khac": "📌 Khác",
}

_TRANG_THAI_CV = ["chua_lam", "dang_lam", "hoan_thanh", "tre_han"]
_TRANG_THAI_LABEL = {
    "chua_lam": "🔴 Chưa làm",
    "dang_lam": "🟡 Đang làm",
    "hoan_thanh": "✅ Hoàn thành",
    "tre_han": "⛔ Trễ hạn",
}
_UU_TIEN = ["khan_cap", "quan_trong", "binh_thuong"]
_UU_TIEN_LABEL = {
    "khan_cap": "🔴 Khẩn cấp",
    "quan_trong": "🟠 Quan trọng",
    "binh_thuong": "🔵 Bình thường",
}

KHNV_PHAN_CONG = "khnv_phan_cong_list"
KHNV_LICH = "khnv_lich_list"

# 32 đầu việc mẫu — Bảng giao việc Trưởng phòng KH-NVTD
_MAU_GIAO_VIEC = [
    # I. CÔNG TÁC QUẢN LÝ CHUNG & ĐIỀU HÀNH
    {"tieu_de": "Tổng hợp kế hoạch công tác tháng của Phòng, báo cáo Trưởng phòng",                          "nguoi_thuc_hien": "Phó phòng (VP 1)",                      "mo_ta": "⏱ 25 hàng tháng · 📄 Dự thảo kế hoạch"},
    {"tieu_de": "Theo dõi, đôn đốc tiến độ công việc; tổng hợp phiếu giao việc",                             "nguoi_thuc_hien": "Phó phòng (VP 1)",                      "mo_ta": "⏱ Hàng tuần · 📄 Báo cáo chiều thứ Sáu"},
    {"tieu_de": "Phân công cán bộ đi giao dịch xã theo lịch cố định",                                        "nguoi_thuc_hien": "Phó phòng (VP 1)",                      "mo_ta": "⏱ Trước 20 hàng tháng · 📄 Danh sách phân công"},
    {"tieu_de": "Kiểm soát, ký nháy các văn bản do Phòng soạn thảo",                                         "nguoi_thuc_hien": "Phó phòng (VP 1 & VP 2)",               "mo_ta": "⏱ Trong ngày · 📄 Văn bản trình Giám đốc"},
    # II. CÔNG TÁC TÍN DỤNG & CHO VAY
    {"tieu_de": "Thẩm định và phê duyệt các khoản vay theo phân quyền trên hệ thống Intellect",              "nguoi_thuc_hien": "Phó phòng (VP 1)",                      "mo_ta": "⏱ Trong 2 ngày kể từ khi nhận hồ sơ · 📄 Kết quả thẩm định"},
    {"tieu_de": "Tổng hợp nhu cầu vay vốn hộ nghèo, cận nghèo, đối tượng chính sách tại địa bàn TP",        "nguoi_thuc_hien": "Phó phòng (VP 1)",                      "mo_ta": "⏱ Hàng quý · 📄 Báo cáo đề xuất bổ sung vốn"},
    {"tieu_de": "Triển khai cho vay: HTTVL, hộ nghèo, cận nghèo, nhà ở xã hội, HS-SV, XKLĐ,...",            "nguoi_thuc_hien": "Cán bộ TD (theo địa bàn)",              "mo_ta": "⏱ Theo kế hoạch giải ngân · 📄 Hồ sơ giải ngân đúng quy trình"},
    {"tieu_de": "Tập hợp, kiểm tra hồ sơ vay từ Tổ TK&VV, trình lãnh đạo phê duyệt",                        "nguoi_thuc_hien": "Cán bộ TD",                             "mo_ta": "⏱ Hàng tuần · 📄 Hồ sơ hợp lệ"},
    {"tieu_de": "Xây dựng kế hoạch tín dụng năm của các xã, phường, trình Trưởng BĐD HĐQT TP phê duyệt",    "nguoi_thuc_hien": "Phó phòng (VP 1)",                      "mo_ta": "⏱ Quý IV hàng năm · 📄 Kế hoạch được phê duyệt"},
    # III. CÔNG TÁC NGUỒN VỐN & QUỸ
    {"tieu_de": "Theo dõi biến động quỹ an toàn chi trả, đề xuất bổ sung hoặc điều chuyển",                  "nguoi_thuc_hien": "Phó phòng (VP 2)",                      "mo_ta": "⏱ Hàng ngày · 📄 Điện chuyển vốn kịp thời"},
    {"tieu_de": "Huy động tiền gửi tiết kiệm từ tổ chức, cá nhân trên địa bàn",                              "nguoi_thuc_hien": "Phó phòng (VP 2) + Cán bộ TD",          "mo_ta": "⏱ Hàng tháng · 📄 Báo cáo kết quả huy động"},
    {"tieu_de": "Quản lý nguồn vốn nhận ủy thác từ UBND tỉnh, các tổ chức",                                  "nguoi_thuc_hien": "Phó phòng (VP 2)",                      "mo_ta": "⏱ Thường xuyên · 📄 Sổ theo dõi, báo cáo đối chiếu"},
    # IV. XỬ LÝ NỢ RỦI RO & QUẢN LÝ NỢ
    {"tieu_de": "Hướng dẫn, đôn đốc các đơn vị lập hồ sơ xử lý nợ rủi ro",                                  "nguoi_thuc_hien": "Phó phòng (VP 2)",                      "mo_ta": "⏱ Theo phát sinh · 📄 Hồ sơ đầy đủ, đúng quy định"},
    {"tieu_de": "Kiểm tra, tổng hợp hồ sơ nợ rủi ro toàn tỉnh, trình cấp thẩm quyền",                       "nguoi_thuc_hien": "Phó phòng (VP 2)",                      "mo_ta": "⏱ Hàng quý · 📄 Tờ trình kèm hồ sơ"},
    {"tieu_de": "Thông báo công khai kết quả xử lý nợ rủi ro tại địa bàn thành phố",                         "nguoi_thuc_hien": "Phó phòng (VP 2)",                      "mo_ta": "⏱ Sau khi được phê duyệt · 📄 Biên bản, thông báo"},
    {"tieu_de": "Đôn đốc thu nợ đến hạn, quá hạn; lập danh sách nợ chây ỳ",                                  "nguoi_thuc_hien": "Cán bộ TD",                             "mo_ta": "⏱ Hàng tháng · 📄 Báo cáo nợ chi tiết"},
    # V. ỦY THÁC QUA TỔ CHỨC CT-XH & TỔ TK&VV
    {"tieu_de": "Tham mưu ký Văn bản liên tịch, Hợp đồng ủy thác với các tổ chức CT-XH",                    "nguoi_thuc_hien": "Phó phòng (VP 1)",                      "mo_ta": "⏱ Khi có thay đổi · 📄 Hợp đồng đã ký"},
    {"tieu_de": "Tổ chức họp giao ban với các tổ chức CT-XH cấp tỉnh, thành phố",                            "nguoi_thuc_hien": "Phó phòng (VP 2)",                      "mo_ta": "⏱ Định kỳ (2 tháng/lần) · 📄 Biên bản, thông báo kết luận"},
    {"tieu_de": "Đánh giá chất lượng hoạt động Tổ TK&VV; đề xuất củng cố tổ yếu kém",                       "nguoi_thuc_hien": "Cán bộ TD (theo địa bàn)",              "mo_ta": "⏱ Hàng tháng · 📄 Bảng xếp loại Tổ"},
    {"tieu_de": "Tham gia sinh hoạt Tổ TK&VV theo lịch; kiểm tra sổ sách của Tổ",                            "nguoi_thuc_hien": "Cán bộ TD",                             "mo_ta": "⏱ Hàng tháng · 📄 Biên bản kiểm tra"},
    # VI. GIAO DỊCH XÃ & KIỂM TRA CƠ SỞ
    {"tieu_de": "Tham mưu tổ chức phiên giao dịch xã đúng lịch, an toàn",                                    "nguoi_thuc_hien": "Phó phòng (VP 1)",                      "mo_ta": "⏱ Theo lịch cố định · 📄 Báo cáo sau phiên giao dịch"},
    {"tieu_de": "Kiểm tra, giám sát hoạt động tại Điểm giao dịch xã; tỷ lệ giải ngân, thu nợ, thu lãi",      "nguoi_thuc_hien": "Phó phòng (VP 1) + Cán bộ TD",          "mo_ta": "⏱ Hàng quý · 📄 Báo cáo đánh giá"},
    {"tieu_de": "Kiểm tra sử dụng vốn vay 100% món vay trong vòng 30 ngày sau giải ngân",                    "nguoi_thuc_hien": "Cán bộ TD",                             "mo_ta": "⏱ Hàng tháng · 📄 Mẫu 06/TD"},
    {"tieu_de": "Mở hòm thư góp ý, tổng hợp ý kiến khách hàng tại Điểm giao dịch xã",                       "nguoi_thuc_hien": "Cán bộ TD",                             "mo_ta": "⏱ Hàng tháng · 📄 Báo cáo tham mưu giải quyết"},
    # VII. BÁO CÁO THỐNG KÊ & TỔNG HỢP
    {"tieu_de": "Tổng hợp báo cáo thống kê tín dụng toàn tỉnh gửi NHCSXH TW, NHNN, các sở ngành",           "nguoi_thuc_hien": "Phó phòng (VP 2)",                      "mo_ta": "⏱ Trước ngày 10 hàng tháng · 📄 Báo cáo đầy đủ biểu"},
    {"tieu_de": "Dự thảo Nghị quyết, báo cáo kết quả hoạt động của BĐD HĐQT tỉnh",                          "nguoi_thuc_hien": "Phó phòng (VP 2)",                      "mo_ta": "⏱ Theo kỳ họp · 📄 Nghị quyết trình ký"},
    {"tieu_de": "Kiểm soát, chỉnh sửa các cảnh báo trên chương trình TTBC-IMS",                              "nguoi_thuc_hien": "Cán bộ TD",                             "mo_ta": "⏱ Hàng tuần · 📄 Báo cáo kết quả chỉnh sửa"},
    {"tieu_de": "Chấm điểm 05 chuyên đề thi đua của chi nhánh",                                              "nguoi_thuc_hien": "Phó phòng (VP 1)",                      "mo_ta": "⏱ Hàng quý · 📄 Bảng chấm điểm"},
    # VIII. ĐÀO TẠO, TẬP HUẤN & CÔNG TÁC KHÁC
    {"tieu_de": "Dự thảo kế hoạch, tài liệu tập huấn nghiệp vụ cho cán bộ trong và ngoài ngành",             "nguoi_thuc_hien": "Phó phòng (VP 2)",                      "mo_ta": "⏱ Quý II hàng năm · 📄 Kế hoạch, tài liệu"},
    {"tieu_de": "Tham gia tập huấn, bồi dưỡng nghiệp vụ khi được phân công",                                 "nguoi_thuc_hien": "Cán bộ TD",                             "mo_ta": "⏱ Theo yêu cầu · 📄 Giấy chứng nhận (nếu có)"},
    {"tieu_de": "Làm thư ký giúp việc cho thành viên BĐD HĐQT các cấp khi kiểm tra địa bàn",                 "nguoi_thuc_hien": "Phó phòng (VP 1 & VP 2), Cán bộ TD",    "mo_ta": "⏱ Theo phân công · 📄 Biên bản kiểm tra"},
    {"tieu_de": "Thực hiện nhiệm vụ đột xuất do Trưởng phòng / Ban Giám đốc giao",                           "nguoi_thuc_hien": "Tất cả cán bộ",                         "mo_ta": "⏱ Theo yêu cầu · 📄 Báo cáo hoàn thành"},
]


def _doc_ds(key: str) -> list:
    """Đọc danh sách từ kv_store, trả về list rỗng nếu chưa có."""
    val = doc_kv(key)
    return val if isinstance(val, list) else []


def _ghi_ds(key: str, ds: list, username: str, action: str, mo_ta: str):
    """Ghi danh sách + audit."""
    ghi_kv(key, ds, username)
    ghi_audit(username, action, mo_ta)
    st.cache_data.clear()


def _tai_mau_giao_viec(ds: list, username: str) -> None:
    """Thêm 32 đầu việc mẫu vào danh sách phân công, lưu kv_store."""
    today_str = date.today().isoformat()
    new_tasks = [
        {
            "id": str(uuid4()),
            "tieu_de": t["tieu_de"],
            "mo_ta": t["mo_ta"],
            "nguoi_thuc_hien": t["nguoi_thuc_hien"],
            "uu_tien": "binh_thuong",
            "trang_thai": "chua_lam",
            "ngay_giao": today_str,
            "ngay_deadline": "",
            "ghi_chu_ket_qua": "",
            "ngay_hoan_thanh": None,
        }
        for t in _MAU_GIAO_VIEC
    ]
    ds.extend(new_tasks)
    _ghi_ds(KHNV_PHAN_CONG, ds, username, "khnv_tai_mau_giao_viec",
            f"Tải 32 đầu việc mẫu (Bảng giao việc Trưởng phòng KH-NVTD)")
    st.success(f"✅ Đã tải {len(new_tasks)} đầu việc mẫu vào danh sách!")
    st.rerun()


# ──────────────────────────────────────────────
# SUB-TAB 1: 📋 Phân công cán bộ
# ──────────────────────────────────────────────


def _render_phan_cong(tab, role_n: str, username: str):
    """Form + bảng phân công việc nội bộ phòng."""
    co_quyen_ghi = role_n in ("admin_cn", "manager_cn")
    co_quyen_xoa = role_n == "admin_cn"

    ds = _doc_ds(KHNV_PHAN_CONG)

    # ── Form thêm mới ──
    if co_quyen_ghi:
        with st.expander("➕ Giao việc mới", expanded=False):
            with st.form("form_phan_cong", clear_on_submit=True):
                tieu_de = st.text_input("Tiêu đề *")
                mo_ta = st.text_area("Mô tả / hướng dẫn")
                nguoi = st.text_input("Người thực hiện *")
                uu_tien = st.selectbox("Ưu tiên", _UU_TIEN, format_func=lambda x: _UU_TIEN_LABEL[x])
                ngay_giao = st.date_input("Ngày giao", value=date.today())
                ngay_deadline = st.date_input("Deadline *", value=date.today())
                submitted = st.form_submit_button("🚀 Giao việc", type="primary")
                if submitted:
                    if not tieu_de.strip() or not nguoi.strip():
                        st.error("Vui lòng nhập Tiêu đề và Người thực hiện.")
                    else:
                        ds.append({
                            "id": str(uuid4()),
                            "tieu_de": tieu_de.strip(),
                            "mo_ta": mo_ta.strip(),
                            "nguoi_thuc_hien": nguoi.strip(),
                            "uu_tien": uu_tien,
                            "trang_thai": "chua_lam",
                            "ngay_giao": ngay_giao.isoformat(),
                            "ngay_deadline": ngay_deadline.isoformat(),
                            "ghi_chu_ket_qua": "",
                            "ngay_hoan_thanh": None,
                        })
                        _ghi_ds(KHNV_PHAN_CONG, ds, username, "khnv_giao_viec",
                                f"Giao: {tieu_de.strip()} → {nguoi.strip()}")
                        st.success("✅ Đã giao việc thành công!")
                        st.rerun()

    # ── Tải dữ liệu mẫu (chỉ admin_cn / manager_cn) ──
    if co_quyen_ghi:
        if not ds:
            st.info("💡 Danh sách đang trống. Bấm bên dưới để tải sẵn **32 đầu việc mẫu** từ Bảng giao việc Trưởng phòng KH-NVTD.")
            col_seed, _ = st.columns([2, 4])
            with col_seed:
                if st.button("📥 Tải 32 đầu việc mẫu", type="primary",
                             key="btn_seed_tasks", use_container_width=True):
                    _tai_mau_giao_viec(ds, username)
        else:
            with st.expander("📥 Tải đầu việc mẫu (thêm vào cuối danh sách)", expanded=False):
                st.caption(f"Thêm 32 đầu việc từ Bảng giao việc chuẩn vào cuối danh sách hiện tại ({len(ds)} việc).")
                if st.button("✅ Xác nhận thêm 32 đầu việc mẫu", key="btn_seed_append"):
                    _tai_mau_giao_viec(ds, username)

    # ── Bảng danh sách ──
    # Sắp xếp: chưa làm / đang làm lên trước
    ds_sorted = sorted(ds, key=lambda x: (
        0 if x.get("trang_thai") in ("chua_lam", "dang_lam") else 1,
        x.get("ngay_deadline", ""),
    )) if ds else []

    st.markdown("### 📋 Danh sách phân công")

    # ── Xuất PDF — luôn hiển thị, disabled khi chưa có dữ liệu ──
    col_pdf, _ = st.columns([1, 5])
    with col_pdf:
        if ds:
            _uu_map = {"khan_cap": "Khẩn cấp", "quan_trong": "Quan trọng", "binh_thuong": "Bình thường"}
            _tt_map = {"chua_lam": "Chưa làm", "dang_lam": "Đang làm", "hoan_thanh": "Hoàn thành", "tre_han": "Trễ hạn"}
            _df_pc = pd.DataFrame([
                {
                    "Tiêu đề": c.get("tieu_de", ""),
                    "Người thực hiện": c.get("nguoi_thuc_hien", ""),
                    "Mức ưu tiên": _uu_map.get(c.get("uu_tien", ""), c.get("uu_tien", "")),
                    "Ngày giao": c.get("ngay_giao", ""),
                    "Deadline": c.get("ngay_deadline", ""),
                    "Trạng thái": _tt_map.get(c.get("trang_thai", ""), c.get("trang_thai", "")),
                    "Ghi chú": c.get("ghi_chu_ket_qua", ""),
                }
                for c in ds
            ])
            _pdf_bytes = xuat_pdf_co_chart(
                _df_pc, "Phân công cán bộ - Phòng KH-NV", username,
                them_dong_tong=False, cols_tien=None,
            )
            download_pdf_button(_pdf_bytes, "phan_cong_can_bo.pdf",
                                "📥 Xuất PDF", key="pdf_phan_cong")
        else:
            st.button("📥 Xuất PDF", disabled=True, key="pdf_phan_cong_dis",
                      use_container_width=True)

    if not ds:
        st.info("ℹ️ Chưa có việc nào được giao.")
        return

    today = date.today()
    for i, cv in enumerate(ds_sorted):
        trang_thai = cv.get("trang_thai", "chua_lam")
        deadline_str = cv.get("ngay_deadline", "")
        try:
            deadline = date.fromisoformat(deadline_str) if deadline_str else None
        except ValueError:
            deadline = None

        # Màu dòng
        row_class = ""
        if trang_thai == "tre_han":
            row_class = "background-color: #ffe0e0;"  # đỏ nhạt
        elif deadline and trang_thai in ("chua_lam", "dang_lam"):
            delta_days = (deadline - today).days
            if delta_days < 0:
                row_class = "background-color: #ffe0e0;"
            elif delta_days <= 3:
                row_class = "background-color: #fff3cd;"  # vàng nhạt

        with st.container():
            st.markdown(f"<div style='{row_class} padding:8px; border-radius:4px; margin-bottom:4px;'>", unsafe_allow_html=True)
            cols = st.columns([3, 1.5, 1.5, 1.5, 2])
            with cols[0]:
                st.markdown(f"**{cv.get('tieu_de','')}**")
                if cv.get("mo_ta"):
                    st.caption(cv["mo_ta"])
            with cols[1]:
                st.markdown(f"👤 {cv.get('nguoi_thuc_hien','')}")
            with cols[2]:
                uu = cv.get("uu_tien", "binh_thuong")
                st.markdown(f"{_UU_TIEN_LABEL.get(uu, uu)}")
            with cols[3]:
                st.markdown(f"📅 {deadline_str}")
            with cols[4]:
                st.markdown(f"{_TRANG_THAI_LABEL.get(trang_thai, trang_thai)}")
                if cv.get("ngay_hoan_thanh"):
                    st.caption(f"✓ {cv['ngay_hoan_thanh']}")

            # Cập nhật trạng thái + ghi chú
            with st.expander("📝 Cập nhật", expanded=False):
                new_status = st.selectbox(
                    "Trạng thái",
                    _TRANG_THAI_CV,
                    index=_TRANG_THAI_CV.index(trang_thai) if trang_thai in _TRANG_THAI_CV else 0,
                    key=f"status_{cv['id']}",
                    format_func=lambda x: _TRANG_THAI_LABEL.get(x, x),
                )
                new_ghi_chu = st.text_area(
                    "Ghi chú kết quả",
                    value=cv.get("ghi_chu_ket_qua", ""),
                    key=f"note_{cv['id']}",
                )
                col1, col2 = st.columns([1, 1])
                with col1:
                    if st.button("💾 Cập nhật", key=f"update_{cv['id']}"):
                        cv["trang_thai"] = new_status
                        cv["ghi_chu_ket_qua"] = new_ghi_chu
                        if new_status == "hoan_thanh" and not cv.get("ngay_hoan_thanh"):
                            cv["ngay_hoan_thanh"] = today.isoformat()
                        _ghi_ds(KHNV_PHAN_CONG, ds, username, "khnv_cap_nhat_trang_thai",
                                f"Cập nhật {cv.get('tieu_de','')} → {new_status}")
                        st.success("✅ Đã cập nhật!")
                        st.rerun()
                with col2:
                    if co_quyen_xoa:
                        confirm_key = f"del_confirm_{cv['id']}"
                        if st.checkbox("☑ Xác nhận xóa", key=confirm_key):
                            if st.button("🗑️ Xóa", key=f"del_{cv['id']}"):
                                ds.remove(cv)
                                _ghi_ds(KHNV_PHAN_CONG, ds, username, "khnv_xoa_viec",
                                        f"Xóa: {cv.get('tieu_de','')}")
                                st.success("✅ Đã xóa!")
                                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)


# ──────────────────────────────────────────────
# SUB-TAB 2: 📅 Lịch công tác
# ──────────────────────────────────────────────


def _render_lich_cong_tac(tab, role_n: str, username: str):
    """Quản lý lịch họp / kiểm tra / công tác / tập huấn."""
    co_quyen_ghi = role_n in ("admin_cn", "manager_cn")
    co_quyen_xoa = role_n == "admin_cn"

    ds = _doc_ds(KHNV_LICH)
    today = date.today()

    # Tự động cập nhật trạng thái sự kiện đã qua
    changed = False
    for ev in ds:
        if ev.get("trang_thai") == "sap_dien_ra":
            try:
                ngay = date.fromisoformat(ev["ngay"])
                if ngay < today:
                    ev["trang_thai"] = "da_hoan_thanh"
                    changed = True
            except (ValueError, KeyError):
                pass
    if changed:
        ghi_kv(KHNV_LICH, ds, username)
        ghi_audit(username, "khnv_tu_dong_cap_nhat_lich", "Tự động cập nhật trạng thái lịch đã qua")

    # ── Form thêm sự kiện ──
    if co_quyen_ghi:
        with st.expander("➕ Thêm sự kiện", expanded=False):
            with st.form("form_lich", clear_on_submit=True):
                tieu_de = st.text_input("Tiêu đề *")
                loai = st.selectbox("Loại", list(LOAI_LICH.keys()), format_func=lambda x: LOAI_LICH[x])
                ngay = st.date_input("Ngày *", value=today)
                dia_diem = st.text_input("Địa điểm")
                thanh_vien = st.text_area("Thành viên tham dự")
                ghi_chu = st.text_area("Ghi chú")
                submitted = st.form_submit_button("🚀 Thêm", type="primary")
                if submitted:
                    if not tieu_de.strip():
                        st.error("Vui lòng nhập Tiêu đề.")
                    else:
                        ds.append({
                            "id": str(uuid4()),
                            "tieu_de": tieu_de.strip(),
                            "loai": loai,
                            "ngay": ngay.isoformat(),
                            "dia_diem": dia_diem.strip(),
                            "thanh_vien": thanh_vien.strip(),
                            "ghi_chu": ghi_chu.strip(),
                            "trang_thai": "sap_dien_ra",
                        })
                        _ghi_ds(KHNV_LICH, ds, username, "khnv_them_lich",
                                f"{LOAI_LICH.get(loai,loai)}: {tieu_de.strip()} ngày {ngay.isoformat()}")
                        st.success("✅ Đã thêm sự kiện!")
                        st.rerun()

    if not ds:
        col_pdf, _ = st.columns([1, 5])
        with col_pdf:
            st.button("📥 Xuất PDF", disabled=True, key="pdf_lich_dis_empty",
                      use_container_width=True)
        st.info("ℹ️ Chưa có lịch công tác nào.")
        return

    # ── Bộ lọc ──
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        thang_loc = st.selectbox("Tháng", list(range(1, 13)), index=today.month - 1, key="lich_thang")
    with col_f2:
        nam_loc = st.selectbox("Năm", list(range(today.year - 2, today.year + 3)), index=2, key="lich_nam")
    loai_loc = st.selectbox("Loại", ["Tất cả"] + list(LOAI_LICH.keys()),
                            format_func=lambda x: "Tất cả" if x == "Tất cả" else LOAI_LICH[x],
                            key="lich_loai")

    # Lọc
    ds_loc = []
    for ev in ds:
        try:
            ev_date = date.fromisoformat(ev["ngay"])
        except (ValueError, KeyError):
            continue
        if ev_date.month != thang_loc or ev_date.year != nam_loc:
            continue
        if loai_loc != "Tất cả" and ev.get("loai") != loai_loc:
            continue
        ds_loc.append(ev)

    ds_loc.sort(key=lambda x: x.get("ngay", ""))

    # ── Xuất PDF — luôn hiển thị, disabled khi tháng lọc không có dữ liệu ──
    col_pdf, _ = st.columns([1, 5])
    with col_pdf:
        if ds_loc:
            _loai_map = {k: v.replace("🗓️ ", "").replace("🔍 ", "").replace("✈️ ", "").replace("🎓 ", "").replace("📌 ", "") for k, v in LOAI_LICH.items()}
            _tt_lich = {"sap_dien_ra": "Sắp diễn ra", "da_hoan_thanh": "Đã hoàn thành", "huy_bo": "Hủy bỏ"}
            _df_lich = pd.DataFrame([
                {
                    "Ngày": e.get("ngay", ""),
                    "Loại": _loai_map.get(e.get("loai", ""), e.get("loai", "")),
                    "Tiêu đề": e.get("tieu_de", ""),
                    "Địa điểm": e.get("dia_diem", ""),
                    "Thành viên": e.get("thanh_vien", ""),
                    "Ghi chú": e.get("ghi_chu", ""),
                    "Trạng thái": _tt_lich.get(e.get("trang_thai", ""), e.get("trang_thai", "")),
                }
                for e in ds_loc
            ])
            _pdf_bytes = xuat_pdf_co_chart(
                _df_lich, "Lịch công tác Phòng KH-NV", username,
                them_dong_tong=False, cols_tien=None,
            )
            download_pdf_button(_pdf_bytes, "lich_cong_tac.pdf",
                                "📥 Xuất PDF", key="pdf_lich")
        else:
            st.button("📥 Xuất PDF", disabled=True, key="pdf_lich_dis",
                      use_container_width=True)

    # ── Bảng ──
    st.markdown("### 📅 Lịch công tác trong tháng")
    for ev in ds_loc:
        try:
            ev_date = date.fromisoformat(ev["ngay"])
        except (ValueError, KeyError):
            ev_date = None

        # Highlight tuần hiện tại
        is_current_week = False
        if ev_date:
            start_week = today - timedelta(days=today.weekday())
            end_week = start_week + timedelta(days=6)
            is_current_week = start_week <= ev_date <= end_week

        bg = "#e8f4fd;" if is_current_week else ""
        st.markdown(f"<div style='background-color:{bg} padding:8px; border-radius:4px; margin-bottom:4px;'>", unsafe_allow_html=True)

        cols = st.columns([1.5, 1.5, 3, 2, 2, 1.5])
        with cols[0]:
            st.markdown(f"**{ev.get('ngay','')}**")
        with cols[1]:
            loai = ev.get("loai", "khac")
            st.markdown(LOAI_LICH.get(loai, loai))
        with cols[2]:
            st.markdown(f"**{ev.get('tieu_de','')}**")
        with cols[3]:
            st.markdown(f"📍 {ev.get('dia_diem','')}")
        with cols[4]:
            st.markdown(f"👥 {ev.get('thanh_vien','')}")
        with cols[5]:
            tt = ev.get("trang_thai", "sap_dien_ra")
            if tt == "sap_dien_ra":
                st.markdown("🟡 Sắp diễn ra")
            elif tt == "da_hoan_thanh":
                st.markdown("✅ Đã hoàn thành")
            elif tt == "huy_bo":
                st.markdown("❌ Hủy bỏ")

        if co_quyen_ghi:
            with st.expander("✏️ Sửa / Xóa", expanded=False):
                new_tieu_de = st.text_input("Tiêu đề", value=ev.get("tieu_de", ""), key=f"lt_{ev['id']}")
                new_loai = st.selectbox("Loại", list(LOAI_LICH.keys()),
                                        index=list(LOAI_LICH.keys()).index(ev.get("loai", "khac")) if ev.get("loai") in LOAI_LICH else 0,
                                        key=f"ll_{ev['id']}",
                                        format_func=lambda x: LOAI_LICH[x])
                new_ngay = st.date_input("Ngày",
                                         value=date.fromisoformat(ev["ngay"]) if ev.get("ngay") else today,
                                         key=f"ln_{ev['id']}")
                new_dia_diem = st.text_input("Địa điểm", value=ev.get("dia_diem", ""), key=f"ld_{ev['id']}")
                new_thanh_vien = st.text_area("Thành viên", value=ev.get("thanh_vien", ""), key=f"ltv_{ev['id']}")
                new_ghi_chu = st.text_area("Ghi chú", value=ev.get("ghi_chu", ""), key=f"lg_{ev['id']}")
                new_trang_thai = st.selectbox("Trạng thái",
                                              ["sap_dien_ra", "da_hoan_thanh", "huy_bo"],
                                              index=["sap_dien_ra", "da_hoan_thanh", "huy_bo"].index(ev.get("trang_thai", "sap_dien_ra")),
                                              key=f"ltt_{ev['id']}",
                                              format_func=lambda x: {"sap_dien_ra": "🟡 Sắp diễn ra",
                                                                     "da_hoan_thanh": "✅ Đã hoàn thành",
                                                                     "huy_bo": "❌ Hủy bỏ"}.get(x, x))
                col_s1, col_s2 = st.columns(2)
                with col_s1:
                    if st.button("💾 Lưu", key=f"save_lich_{ev['id']}"):
                        if new_tieu_de.strip():
                            ev["tieu_de"] = new_tieu_de.strip()
                            ev["loai"] = new_loai
                            ev["ngay"] = new_ngay.isoformat()
                            ev["dia_diem"] = new_dia_diem.strip()
                            ev["thanh_vien"] = new_thanh_vien.strip()
                            ev["ghi_chu"] = new_ghi_chu.strip()
                            ev["trang_thai"] = new_trang_thai
                            _ghi_ds(KHNV_LICH, ds, username, "khnv_sua_lich",
                                    f"Sửa: {new_tieu_de.strip()}")
                            st.success("✅ Đã lưu!")
                            st.rerun()
                with col_s2:
                    if co_quyen_xoa:
                        confirm_key = f"del_lich_confirm_{ev['id']}"
                        if st.checkbox("☑ Xác nhận xóa", key=confirm_key):
                            if st.button("🗑️ Xóa", key=f"del_lich_{ev['id']}"):
                                ds.remove(ev)
                                _ghi_ds(KHNV_LICH, ds, username, "khnv_xoa_lich",
                                        f"Xóa: {ev.get('tieu_de','')}")
                                st.success("✅ Đã xóa!")
                                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)


# ──────────────────────────────────────────────
# SUB-TAB 4: 📊 Tiến độ thực hiện
# ──────────────────────────────────────────────


def _render_tien_do_thuc_hien(tab, role_n: str, username: str):
    """Tổng hợp tiến độ thực hiện cán bộ — tự động từ dữ liệu Phân công cán bộ."""
    today = date.today()
    ds = _doc_ds(KHNV_PHAN_CONG)

    st.markdown("### 📊 Tiến độ thực hiện cán bộ Phòng KH-NV")

    # ── Bộ lọc ──
    col_f1, col_f2, col_f3 = st.columns([1, 1, 2])
    with col_f1:
        thang_opt = ["Tất cả"] + list(range(1, 13))
        thang_loc = st.selectbox(
            "Tháng (deadline)", thang_opt,
            index=today.month,  # mặc định = tháng hiện tại
            format_func=lambda x: "Tất cả" if x == "Tất cả" else f"Tháng {x}",
            key="td_thang",
        )
    with col_f2:
        nam_opts = list(range(today.year - 1, today.year + 2))
        nam_loc = st.selectbox(
            "Năm", nam_opts, index=nam_opts.index(today.year), key="td_nam",
        )
    with col_f3:
        ds_nguoi = sorted({c.get("nguoi_thuc_hien", "") for c in ds if c.get("nguoi_thuc_hien")})
        nguoi_loc = st.selectbox("Cán bộ", ["Tất cả"] + ds_nguoi, key="td_nguoi")

    # ── Lọc ──
    ds_loc = list(ds)
    if thang_loc != "Tất cả":
        filtered = []
        for c in ds_loc:
            try:
                dl = date.fromisoformat(c.get("ngay_deadline", ""))
                if dl.month == int(thang_loc) and dl.year == nam_loc:
                    filtered.append(c)
            except (ValueError, TypeError):
                pass
        ds_loc = filtered
    if nguoi_loc != "Tất cả":
        ds_loc = [c for c in ds_loc if c.get("nguoi_thuc_hien") == nguoi_loc]

    # ── Tổng hợp per-person ──
    stats: dict = defaultdict(lambda: {
        "total": 0, "hoan_thanh": 0, "dang_lam": 0, "chua_lam": 0, "tre_han": 0,
    })
    for c in ds_loc:
        nguoi = c.get("nguoi_thuc_hien") or "Không rõ"
        tt = c.get("trang_thai", "chua_lam")
        stats[nguoi]["total"] += 1

        is_overdue = False
        if tt in ("chua_lam", "dang_lam"):
            try:
                dl = date.fromisoformat(c.get("ngay_deadline", ""))
                is_overdue = dl < today
            except (ValueError, TypeError):
                pass

        if tt == "hoan_thanh":
            stats[nguoi]["hoan_thanh"] += 1
        elif tt == "tre_han" or is_overdue:
            stats[nguoi]["tre_han"] += 1
        elif tt == "dang_lam":
            stats[nguoi]["dang_lam"] += 1
        else:
            stats[nguoi]["chua_lam"] += 1

    # Build summary DataFrame
    rows = []
    for nguoi, s in sorted(stats.items()):
        pct = round(s["hoan_thanh"] / s["total"] * 100, 1) if s["total"] else 0.0
        rows.append({
            "Cán bộ": nguoi,
            "Tổng": s["total"],
            "✅ Xong": s["hoan_thanh"],
            "🟡 Đang làm": s["dang_lam"],
            "🔴 Chưa làm": s["chua_lam"],
            "⛔ Trễ hạn": s["tre_han"],
            "Tỷ lệ (%)": pct,
        })
    df_summary = pd.DataFrame(rows) if rows else pd.DataFrame()

    # ── Nút Xuất PDF — luôn hiển thị ──
    col_pdf, _ = st.columns([1, 5])
    with col_pdf:
        if not df_summary.empty:
            _pdf_bytes = xuat_pdf_co_chart(
                df_summary, "Tiến độ thực hiện cán bộ Phòng KH-NV", username,
                them_dong_tong=False, cols_tien=None,
            )
            download_pdf_button(_pdf_bytes, "tien_do_can_bo.pdf",
                                "📥 Xuất PDF", key="td_pdf")
        else:
            st.button("📥 Xuất PDF", disabled=True, key="td_pdf_dis",
                      use_container_width=True)

    if not ds:
        st.info("ℹ️ Chưa có việc nào. Hãy giao việc trong tab 📋 Phân công cán bộ trước.")
        return
    if not ds_loc:
        st.info("ℹ️ Không có dữ liệu phù hợp với bộ lọc đã chọn.")
        return

    # ── Metrics tổng quan ──
    total_all  = sum(s["total"]       for s in stats.values())
    ht_all     = sum(s["hoan_thanh"]  for s in stats.values())
    dl_all     = sum(s["dang_lam"]    for s in stats.values())
    tre_all    = sum(s["tre_han"]     for s in stats.values())
    pct_all    = round(ht_all / total_all * 100, 1) if total_all else 0.0

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("📋 Tổng việc",    total_all)
    m2.metric("✅ Hoàn thành",   ht_all)
    m3.metric("🟡 Đang làm",    dl_all)
    m4.metric("⛔ Trễ hạn",     tre_all,
              delta=f"-{tre_all}" if tre_all else None,
              delta_color="inverse")
    m5.metric("📈 Tỷ lệ chung", f"{pct_all}%")

    st.divider()

    # ── Progress bars từng cán bộ ──
    st.markdown("#### Tiến độ từng cán bộ")

    bars_html = ""
    for row in rows:
        nguoi = row["Cán bộ"]
        pct   = row["Tỷ lệ (%)"]
        ht    = row["✅ Xong"]
        total = row["Tổng"]
        tre   = row["⛔ Trễ hạn"]
        dl_   = row["🟡 Đang làm"]
        cl    = row["🔴 Chưa làm"]

        if pct == 100:
            bar_color = "#22c55e"   # xanh lá
        elif pct >= 70:
            bar_color = "#3b82f6"   # xanh dương
        elif pct >= 30:
            bar_color = "#f59e0b"   # cam
        else:
            bar_color = "#ef4444"   # đỏ

        alert_badge = (
            f'<span style="background:#fee2e2;color:#b91c1c;'
            f'font-size:0.75rem;padding:1px 7px;border-radius:999px;'
            f'font-weight:700;margin-left:6px">⛔ {tre} trễ</span>'
            if tre > 0 else ""
        )
        stats_txt = (
            f'<span>✅ {ht} xong</span>'
            f'<span style="margin-left:10px">🟡 {dl_} làm</span>'
            f'<span style="margin-left:10px">🔴 {cl} chưa</span>'
            + (f'<span style="margin-left:10px;color:#b91c1c;font-weight:600">⛔ {tre} trễ</span>' if tre > 0 else "")
        )
        bars_html += f"""
        <div style="margin:12px 0 4px">
          <div style="display:flex;align-items:center;margin-bottom:4px">
            <span style="font-weight:700;font-size:0.97rem">{nguoi}</span>
            {alert_badge}
            <span style="margin-left:auto;font-size:0.85rem;opacity:0.7">{ht}/{total} &nbsp;({pct}%)</span>
          </div>
          <div style="background:#e5e7eb;border-radius:6px;height:14px;overflow:hidden">
            <div style="background:{bar_color};width:{pct}%;height:100%;border-radius:6px"></div>
          </div>
          <div style="display:flex;gap:0;margin-top:4px;font-size:0.79rem;opacity:0.7">
            {stats_txt}
          </div>
        </div>
        """
    st.markdown(bars_html, unsafe_allow_html=True)

    st.divider()

    # ── Bảng chi tiết ──
    st.markdown("#### Bảng chi tiết")
    df_display = df_summary.copy()
    df_display["Tỷ lệ (%)"] = df_display["Tỷ lệ (%)"].apply(lambda x: f"{x:.1f}%")
    st.dataframe(df_display, hide_index=True, use_container_width=True)


# ──────────────────────────────────────────────
# RENDER CHÍNH
# ──────────────────────────────────────────────


def render(tab=None, **kwargs):
    """4 sub-tab: Phân công cán bộ, Lịch công tác, Báo cáo cấp trên, Tiến độ thực hiện.

    Chỉ khả dụng cho phòng KH-NV (admin_cn, manager_cn, chuyenvien_cn, executive).
    """
    ctx = get_tab_context(tab)
    role_n = normalize_role(str(kwargs.get("role", "user")))
    username = kwargs.get("username", "unknown")

    if role_n in ("user", "manager_pgd", "admin_pgd"):
        with ctx:
            st.warning("⚠️ Tab này chỉ dành cho phòng KH-NV.")
        return

    with ctx:
        t1, t2, t3, t4 = st.tabs([
            "📋 Phân công cán bộ",
            "📅 Lịch công tác",
            "📤 Báo cáo cấp trên",
            "📊 Tiến độ thực hiện",
        ])
        with t1:
            _render_phan_cong(t1, role_n, username)
        with t2:
            _render_lich_cong_tac(t2, role_n, username)
        with t3:
            tab_checklist_bc.render(t3, **kwargs)
        with t4:
            _render_tien_do_thuc_hien(t4, role_n, username)
