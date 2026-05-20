"""Tab Quản lý nội bộ Phòng KH-NV — 6 sub-tab theo luồng 5 bước:
1. 👥 Nhân sự & Chức vụ    — khai báo cán bộ một lần
2. 📋 Phân công công việc  — dropdown cán bộ → đầu việc lọc theo chức vụ
3. 📊 Tiến độ / Chỉnh sửa  — cập nhật nhanh + edit chi tiết + xóa
4. 📄 In báo cáo           — PDF, Excel, checklist cấp trên
5. 📅 Lịch công tác        — giữ nguyên
6. 📖 Thông tin đầu việc   — bảng tham chiếu tĩnh TP01–TP17 + 38 việc cấp dưới
"""

from uuid import uuid4
from datetime import date, datetime, timedelta
from collections import defaultdict

import streamlit as st
import pandas as pd

from auth import normalize_role, la_phan_he_cn
from db import doc_kv, ghi_kv, ghi_audit
from utils import get_tab_context, xuat_excel
from components.export_pdf import xuat_pdf_co_chart, download_pdf_button
from tabs import tab_checklist_bc

# ──────────────────────────────────────────────
# HẰNG SỐ & NHÃN
# ──────────────────────────────────────────────

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

# kv_store keys
KHNV_PHAN_CONG = "khnv_phan_cong_list"
KHNV_LICH      = "khnv_lich_list"
KHNV_CAN_BO    = "khnv_can_bo_list"   # {id, ho_ten, chuc_vu: "vp1"|"vp2"|"cbtd"}

# Chức vụ mapping
_CHUC_VU_MAP = {
    "vp1":  "Phó phòng (VT 1)",
    "vp2":  "Phó phòng (VT 2)",
    "cbtd": "Cán bộ TD",
}
_CHUC_VU_LABEL = {
    "vp1":  "👔 Phó phòng Vị trí 1",
    "vp2":  "👔 Phó phòng Vị trí 2",
    "cbtd": "🧑‍💼 Cán bộ Tín dụng",
}
# Tập nguoi_thuc_hien trong _MAU_GIAO_VIEC phù hợp với từng chức vụ
_CHUC_VU_TASK_FILTER = {
    "vp1":  {"Phó phòng (VT 1)", "Phó phòng (VT 1 & VT 2)",
             "Phó phòng (VT 1) + Cán bộ TD", "Phó phòng (VT 1 & VT 2), Cán bộ TD",
             "Tất cả cán bộ"},
    "vp2":  {"Phó phòng (VT 2)", "Phó phòng (VT 1 & VT 2)",
             "Phó phòng (VT 2) + Cán bộ TD", "Phó phòng (VT 1 & VT 2), Cán bộ TD",
             "Tất cả cán bộ"},
    "cbtd": {"Cán bộ TD", "Cán bộ TD (theo địa bàn)",
             "Phó phòng (VT 1) + Cán bộ TD", "Phó phòng (VT 2) + Cán bộ TD",
             "Phó phòng (VT 1 & VT 2), Cán bộ TD", "Tất cả cán bộ"},
}

# ──────────────────────────────────────────────
# DỮ LIỆU MẪU — 38 đầu việc cấp dưới (nhóm I–VIII)
# ──────────────────────────────────────────────

_MAU_GIAO_VIEC = [
    # I. QUẢN LÝ CHUNG & HÀNH CHÍNH (5 việc)
    {"nhom": "I. Quản lý chung & Điều hành",
     "tieu_de": "Tổng hợp kế hoạch công tác tháng của Phòng, báo cáo Trưởng phòng",
     "nguoi_thuc_hien": "Phó phòng (VT 1)",
     "mo_ta": "⏱ 25 hàng tháng · 📄 Dự thảo kế hoạch"},
    {"nhom": "I. Quản lý chung & Điều hành",
     "tieu_de": "Theo dõi, đôn đốc tiến độ công việc; tổng hợp phiếu giao việc",
     "nguoi_thuc_hien": "Phó phòng (VT 1)",
     "mo_ta": "⏱ Hàng tuần · 📄 Báo cáo chiều thứ Sáu"},
    {"nhom": "I. Quản lý chung & Điều hành",
     "tieu_de": "Phân công cán bộ đi giao dịch xã theo lịch cố định",
     "nguoi_thuc_hien": "Phó phòng (VT 1)",
     "mo_ta": "⏱ Trước 20 hàng tháng · 📄 Danh sách phân công"},
    {"nhom": "I. Quản lý chung & Điều hành",
     "tieu_de": "Kiểm soát, ký nháy các văn bản do Phòng soạn thảo",
     "nguoi_thuc_hien": "Phó phòng (VT 1 & VT 2)",
     "mo_ta": "⏱ Trong ngày · 📄 Văn bản trình Giám đốc"},
    {"nhom": "I. Quản lý chung & Điều hành",
     "tieu_de": "Theo dõi chấm công, nghỉ phép, nghỉ bù của cán bộ Phòng",
     "nguoi_thuc_hien": "Phó phòng (VT 2)",
     "mo_ta": "⏱ Hàng tháng · 📄 Bảng chấm công"},
    # II. TÍN DỤNG & CHO VAY (6 việc)
    {"nhom": "II. Tín dụng & Cho vay",
     "tieu_de": "Thẩm định và phê duyệt các khoản vay theo phân quyền trên hệ thống Intellect",
     "nguoi_thuc_hien": "Phó phòng (VT 1)",
     "mo_ta": "⏱ Trong 2 ngày kể từ khi nhận hồ sơ · 📄 Kết quả thẩm định"},
    {"nhom": "II. Tín dụng & Cho vay",
     "tieu_de": "Tổng hợp nhu cầu vay vốn hộ nghèo, cận nghèo, đối tượng chính sách tại địa bàn TP",
     "nguoi_thuc_hien": "Phó phòng (VT 1)",
     "mo_ta": "⏱ Hàng quý · 📄 Báo cáo đề xuất bổ sung vốn"},
    {"nhom": "II. Tín dụng & Cho vay",
     "tieu_de": "Triển khai cho vay: HTTVL, hộ nghèo, cận nghèo, nhà ở xã hội, HS-SV, XKLĐ, NĐ75, QĐ755, 2085,...",
     "nguoi_thuc_hien": "Cán bộ TD (theo địa bàn)",
     "mo_ta": "⏱ Theo kế hoạch giải ngân · 📄 Hồ sơ giải ngân đúng quy trình"},
    {"nhom": "II. Tín dụng & Cho vay",
     "tieu_de": "Tập hợp, kiểm tra hồ sơ vay từ Tổ TK&VV, trình lãnh đạo phê duyệt",
     "nguoi_thuc_hien": "Cán bộ TD",
     "mo_ta": "⏱ Hàng tuần · 📄 Hồ sơ hợp lệ"},
    {"nhom": "II. Tín dụng & Cho vay",
     "tieu_de": "Xây dựng kế hoạch tín dụng năm của các xã, phường, trình Trưởng BĐD HĐQT TP phê duyệt",
     "nguoi_thuc_hien": "Phó phòng (VT 1)",
     "mo_ta": "⏱ Quý IV hàng năm · 📄 Kế hoạch được phê duyệt"},
    {"nhom": "II. Tín dụng & Cho vay",
     "tieu_de": "Xây dựng kế hoạch tín dụng toàn tỉnh, trình Trưởng BĐD HĐQT tỉnh",
     "nguoi_thuc_hien": "Phó phòng (VT 2)",
     "mo_ta": "⏱ Theo chỉ đạo · 📄 Kế hoạch trình Trung ương"},
    # III. NGUỒN VỐN & QUỸ (3 việc)
    {"nhom": "III. Nguồn vốn & Quỹ",
     "tieu_de": "Theo dõi biến động quỹ an toàn chi trả, đề xuất bổ sung hoặc điều chuyển",
     "nguoi_thuc_hien": "Phó phòng (VT 2)",
     "mo_ta": "⏱ Hàng ngày · 📄 Điện chuyển vốn kịp thời"},
    {"nhom": "III. Nguồn vốn & Quỹ",
     "tieu_de": "Huy động tiền gửi tiết kiệm từ tổ chức, cá nhân trên địa bàn",
     "nguoi_thuc_hien": "Phó phòng (VT 2) + Cán bộ TD",
     "mo_ta": "⏱ Hàng tháng · 📄 Báo cáo kết quả huy động"},
    {"nhom": "III. Nguồn vốn & Quỹ",
     "tieu_de": "Quản lý nguồn vốn nhận ủy thác từ UBND tỉnh, các tổ chức; theo dõi Quỹ QGVL",
     "nguoi_thuc_hien": "Phó phòng (VT 2)",
     "mo_ta": "⏱ Thường xuyên · 📄 Sổ theo dõi, báo cáo đối chiếu"},
    # IV. NỢ RỦI RO & QUẢN LÝ NỢ (5 việc)
    {"nhom": "IV. Nợ rủi ro & Quản lý nợ",
     "tieu_de": "Hướng dẫn, đôn đốc các đơn vị lập hồ sơ xử lý nợ rủi ro",
     "nguoi_thuc_hien": "Phó phòng (VT 2)",
     "mo_ta": "⏱ Theo phát sinh · 📄 Hồ sơ đầy đủ, đúng quy định"},
    {"nhom": "IV. Nợ rủi ro & Quản lý nợ",
     "tieu_de": "Kiểm tra, tổng hợp hồ sơ nợ rủi ro toàn tỉnh, trình cấp thẩm quyền",
     "nguoi_thuc_hien": "Phó phòng (VT 2)",
     "mo_ta": "⏱ Hàng quý · 📄 Tờ trình kèm hồ sơ"},
    {"nhom": "IV. Nợ rủi ro & Quản lý nợ",
     "tieu_de": "Thông báo công khai kết quả xử lý nợ rủi ro tại địa bàn thành phố",
     "nguoi_thuc_hien": "Phó phòng (VT 2)",
     "mo_ta": "⏱ Sau khi được phê duyệt · 📄 Biên bản, thông báo"},
    {"nhom": "IV. Nợ rủi ro & Quản lý nợ",
     "tieu_de": "Lưu giữ hồ sơ nợ rủi ro theo quy định",
     "nguoi_thuc_hien": "Phó phòng (VT 2)",
     "mo_ta": "⏱ Thường xuyên · 📄 Hồ sơ đầy đủ"},
    {"nhom": "IV. Nợ rủi ro & Quản lý nợ",
     "tieu_de": "Đôn đốc thu nợ đến hạn, quá hạn; lập danh sách nợ chây ỳ",
     "nguoi_thuc_hien": "Cán bộ TD",
     "mo_ta": "⏱ Hàng tháng · 📄 Báo cáo nợ chi tiết"},
    # V. ỦY THÁC CT-XH & TỔ TK&VV (4 việc)
    {"nhom": "V. Ủy thác CT-XH & Tổ TK&VV",
     "tieu_de": "Tham mưu ký Văn bản liên tịch, Hợp đồng ủy thác với các tổ chức CT-XH",
     "nguoi_thuc_hien": "Phó phòng (VT 1)",
     "mo_ta": "⏱ Khi có thay đổi · 📄 Hợp đồng đã ký"},
    {"nhom": "V. Ủy thác CT-XH & Tổ TK&VV",
     "tieu_de": "Tổ chức họp giao ban với các tổ chức CT-XH cấp tỉnh, thành phố",
     "nguoi_thuc_hien": "Phó phòng (VT 2)",
     "mo_ta": "⏱ Định kỳ (2 tháng/lần) · 📄 Biên bản, thông báo kết luận"},
    {"nhom": "V. Ủy thác CT-XH & Tổ TK&VV",
     "tieu_de": "Đánh giá chất lượng hoạt động Tổ TK&VV; đề xuất củng cố tổ yếu kém",
     "nguoi_thuc_hien": "Cán bộ TD (theo địa bàn)",
     "mo_ta": "⏱ Hàng tháng · 📄 Bảng xếp loại Tổ"},
    {"nhom": "V. Ủy thác CT-XH & Tổ TK&VV",
     "tieu_de": "Tham gia sinh hoạt Tổ TK&VV theo lịch; kiểm tra sổ sách của Tổ",
     "nguoi_thuc_hien": "Cán bộ TD",
     "mo_ta": "⏱ Hàng tháng · 📄 Biên bản kiểm tra"},
    # VI. GIAO DỊCH XÃ & KIỂM TRA CƠ SỞ (4 việc)
    {"nhom": "VI. Giao dịch xã & Kiểm tra cơ sở",
     "tieu_de": "Tham mưu tổ chức phiên giao dịch xã đúng lịch, an toàn",
     "nguoi_thuc_hien": "Phó phòng (VT 1)",
     "mo_ta": "⏱ Theo lịch cố định · 📄 Báo cáo sau phiên giao dịch"},
    {"nhom": "VI. Giao dịch xã & Kiểm tra cơ sở",
     "tieu_de": "Kiểm tra, giám sát hoạt động tại Điểm giao dịch xã; tỷ lệ giải ngân, thu nợ, thu lãi",
     "nguoi_thuc_hien": "Phó phòng (VT 1) + Cán bộ TD",
     "mo_ta": "⏱ Hàng quý · 📄 Báo cáo đánh giá"},
    {"nhom": "VI. Giao dịch xã & Kiểm tra cơ sở",
     "tieu_de": "Kiểm tra sử dụng vốn vay 100% món vay trong vòng 30 ngày sau giải ngân",
     "nguoi_thuc_hien": "Cán bộ TD",
     "mo_ta": "⏱ Hàng tháng · 📄 Mẫu 06/TD"},
    {"nhom": "VI. Giao dịch xã & Kiểm tra cơ sở",
     "tieu_de": "Mở hòm thư góp ý, tổng hợp ý kiến khách hàng tại Điểm giao dịch xã",
     "nguoi_thuc_hien": "Cán bộ TD",
     "mo_ta": "⏱ Hàng tháng · 📄 Báo cáo tham mưu giải quyết"},
    # VII. BÁO CÁO THỐNG KÊ & TỔNG HỢP (6 việc)
    {"nhom": "VII. Báo cáo & Thống kê",
     "tieu_de": "Tổng hợp báo cáo thống kê tín dụng toàn tỉnh gửi NHCSXH TW, NHNN, các sở ngành",
     "nguoi_thuc_hien": "Phó phòng (VT 2)",
     "mo_ta": "⏱ Trước ngày 10 hàng tháng · 📄 Báo cáo đầy đủ biểu"},
    {"nhom": "VII. Báo cáo & Thống kê",
     "tieu_de": "Dự thảo Nghị quyết, báo cáo kết quả hoạt động của BĐD HĐQT tỉnh",
     "nguoi_thuc_hien": "Phó phòng (VT 2)",
     "mo_ta": "⏱ Theo kỳ họp · 📄 Nghị quyết trình ký"},
    {"nhom": "VII. Báo cáo & Thống kê",
     "tieu_de": "Xây dựng dự thảo báo cáo kết quả hoạt động chi nhánh tháng, quý, năm",
     "nguoi_thuc_hien": "Phó phòng (VT 2)",
     "mo_ta": "⏱ Theo định kỳ · 📄 Báo cáo trình Giám đốc"},
    {"nhom": "VII. Báo cáo & Thống kê",
     "tieu_de": "Lập dự toán, tờ trình văn phòng phẩm theo tháng; thanh toán các khoản của Phòng",
     "nguoi_thuc_hien": "Phó phòng (VT 2)",
     "mo_ta": "⏱ Hàng tháng · 📄 Dự toán, chứng từ"},
    {"nhom": "VII. Báo cáo & Thống kê",
     "tieu_de": "Kiểm soát, chỉnh sửa các cảnh báo trên chương trình TTBC-IMS",
     "nguoi_thuc_hien": "Cán bộ TD",
     "mo_ta": "⏱ Hàng tuần · 📄 Báo cáo kết quả chỉnh sửa"},
    {"nhom": "VII. Báo cáo & Thống kê",
     "tieu_de": "Chấm điểm 05 chuyên đề thi đua của chi nhánh",
     "nguoi_thuc_hien": "Phó phòng (VT 1)",
     "mo_ta": "⏱ Hàng quý · 📄 Bảng chấm điểm"},
    # VIII. ĐÀO TẠO & CÔNG TÁC KHÁC (5 việc)
    {"nhom": "VIII. Đào tạo & Công tác khác",
     "tieu_de": "Dự thảo kế hoạch, tài liệu tập huấn nghiệp vụ cho cán bộ trong và ngoài ngành",
     "nguoi_thuc_hien": "Phó phòng (VT 2)",
     "mo_ta": "⏱ Quý II hàng năm · 📄 Kế hoạch, tài liệu"},
    {"nhom": "VIII. Đào tạo & Công tác khác",
     "tieu_de": "Tham gia tập huấn, bồi dưỡng nghiệp vụ khi được phân công",
     "nguoi_thuc_hien": "Cán bộ TD",
     "mo_ta": "⏱ Theo yêu cầu · 📄 Giấy chứng nhận (nếu có)"},
    {"nhom": "VIII. Đào tạo & Công tác khác",
     "tieu_de": "Thành viên Tổ giao dịch lưu động tại xã, phường",
     "nguoi_thuc_hien": "Phó phòng (VT 1 & VT 2), Cán bộ TD",
     "mo_ta": "⏱ Theo lịch phân công · 📄 Thực hiện giao dịch"},
    {"nhom": "VIII. Đào tạo & Công tác khác",
     "tieu_de": "Làm thư ký giúp việc cho thành viên BĐD HĐQT các cấp khi kiểm tra địa bàn",
     "nguoi_thuc_hien": "Phó phòng (VT 1 & VT 2), Cán bộ TD",
     "mo_ta": "⏱ Theo phân công · 📄 Biên bản kiểm tra"},
    {"nhom": "VIII. Đào tạo & Công tác khác",
     "tieu_de": "Thực hiện nhiệm vụ đột xuất do Trưởng phòng / Ban Giám đốc giao",
     "nguoi_thuc_hien": "Tất cả cán bộ",
     "mo_ta": "⏱ Theo yêu cầu · 📄 Báo cáo hoàn thành"},
]

# ──────────────────────────────────────────────
# DỮ LIỆU TĨNH — 17 đầu việc Trưởng phòng (chỉ hiển thị tham chiếu, không lưu kv)
# ──────────────────────────────────────────────

_MAU_GIAO_VIEC_TP = [
    {"ma": "TP01", "tieu_de": "Xây dựng chương trình, kế hoạch công tác của Phòng",
     "mo_ta": "Lập kế hoạch tháng, quý, năm; tổng hợp, đánh giá kết quả thực hiện; báo cáo Ban Giám đốc",
     "tan_suat": "Tháng/Quý/Năm"},
    {"ma": "TP02", "tieu_de": "Quản lý, phân công, giám sát và đánh giá cán bộ",
     "mo_ta": "Phân công nhiệm vụ cụ thể; theo dõi, đôn đốc, kiểm tra, nhận xét, đánh giá kết quả",
     "tan_suat": "Hàng tuần/Tháng"},
    {"ma": "TP03", "tieu_de": "Kiểm soát, ký nháy văn bản do Phòng soạn thảo",
     "mo_ta": "Kiểm soát văn bản trước khi trình Giám đốc tỉnh phê duyệt hoặc ban hành",
     "tan_suat": "Hàng ngày"},
    {"ma": "TP04", "tieu_de": "Đầu mối triển khai tín dụng chính sách trên địa bàn",
     "mo_ta": "Hướng dẫn, triển khai các chương trình tín dụng; phát hiện vướng mắc, đề xuất giải pháp",
     "tan_suat": "Thường xuyên"},
    {"ma": "TP05", "tieu_de": "Tham mưu Ban đại diện HĐQT tỉnh",
     "mo_ta": "Tham mưu tổ chức họp, ban hành Nghị quyết; giao chỉ tiêu tín dụng; đề xuất bổ sung vốn",
     "tan_suat": "Theo định kỳ/Đột xuất"},
    {"ma": "TP06", "tieu_de": "Điều hành công tác nguồn vốn",
     "mo_ta": "Giao hạn mức quỹ; điều hành quỹ hàng ngày; chỉ đạo huy động tiền gửi; quản lý vốn ủy thác",
     "tan_suat": "Hàng ngày/Tháng"},
    {"ma": "TP07", "tieu_de": "Chỉ đạo thực hiện và điều chỉnh kế hoạch tín dụng",
     "mo_ta": "Chỉ đạo xây dựng kế hoạch; tổng hợp trình phê duyệt; điều chỉnh chỉ tiêu; đảm bảo tăng trưởng",
     "tan_suat": "Quý/Năm"},
    {"ma": "TP08", "tieu_de": "Chỉ đạo rà soát nhu cầu vay vốn",
     "mo_ta": "Đảm bảo 100% hộ nghèo, cận nghèo, đối tượng chính sách có nhu cầu được tiếp cận vốn",
     "tan_suat": "Năm/Đột xuất"},
    {"ma": "TP09", "tieu_de": "Tham mưu ký kết và giám sát ủy thác qua tổ chức CT-XH",
     "mo_ta": "Ký văn bản liên tịch, hợp đồng ủy thác; tổ chức triển khai; duy trì giao ban, sơ kết, tập huấn",
     "tan_suat": "Theo định kỳ"},
    {"ma": "TP10", "tieu_de": "Chỉ đạo xử lý nợ rủi ro",
     "mo_ta": "Tham mưu chỉ đạo xử lý nợ rủi ro; thành lập đoàn kiểm tra; kiểm soát hồ sơ; tổng hợp trình cấp thẩm quyền",
     "tan_suat": "Thường xuyên"},
    {"ma": "TP11", "tieu_de": "Giám sát hoạt động giao dịch xã",
     "mo_ta": "Chỉ đạo tổ chức giao dịch xã; kiểm tra mạng lưới điểm giao dịch; đánh giá chất lượng; đề xuất chấn chỉnh",
     "tan_suat": "Tháng/Quý"},
    {"ma": "TP12", "tieu_de": "Tổ chức đào tạo, tập huấn nghiệp vụ",
     "mo_ta": "Dự thảo kế hoạch, chương trình, tài liệu; tham mưu tổ chức tập huấn cho thành viên BĐD HĐQT huyện",
     "tan_suat": "Năm/Đột xuất"},
    {"ma": "TP13", "tieu_de": "Kiểm soát và phê duyệt báo cáo thống kê",
     "mo_ta": "Lập báo cáo định tính tập thể Phòng; kiểm soát, phê duyệt chỉ tiêu được phân quyền; tổng hợp theo quy định",
     "tan_suat": "Tháng"},
    {"ma": "TP14", "tieu_de": "Dự thảo báo cáo định kỳ và đột xuất",
     "mo_ta": "Dự thảo báo cáo tín dụng, tham luận, giải trình, trả lời kiến nghị, góp ý dự thảo văn bản",
     "tan_suat": "Theo yêu cầu"},
    {"ma": "TP15", "tieu_de": "Làm thư ký cho thành viên BĐD HĐQT tỉnh",
     "mo_ta": "Thư ký giúp việc khi thành viên BĐD HĐQT kiểm tra, giám sát địa bàn xã được phân công",
     "tan_suat": "Theo phân công"},
    {"ma": "TP16", "tieu_de": "Đầu mối giao dịch với Sở, ban, ngành, tổ chức CT-XH",
     "mo_ta": "Phối hợp triển khai các hoạt động liên quan đến tín dụng chính sách",
     "tan_suat": "Thường xuyên"},
    {"ma": "TP17", "tieu_de": "Thực hiện nhiệm vụ khác do Ban Giám đốc giao",
     "mo_ta": "Triển khai các nhiệm vụ phát sinh ngoài kế hoạch",
     "tan_suat": "Đột xuất"},
]


# ──────────────────────────────────────────────
# UTILITIES
# ──────────────────────────────────────────────


def _doc_ds(key: str) -> list:
    """Đọc danh sách từ kv_store, trả về list rỗng nếu chưa có."""
    val = doc_kv(key)
    return val if isinstance(val, list) else []


def _ghi_ds(key: str, ds: list, username: str, action: str, mo_ta: str):
    """Ghi danh sách + audit."""
    ghi_kv(key, ds, username)
    ghi_audit(username, action, mo_ta)
    st.cache_data.clear()


def _tinh_so_task(vp1: str, vp2: str, cbtd_list: list) -> int:
    """Ước tính số task sau khi nhân bản theo danh sách cán bộ điền vào."""
    n = len(cbtd_list) if cbtd_list else 1
    total = 0
    for t in _MAU_GIAO_VIEC:
        ng = t["nguoi_thuc_hien"]
        if ng in ("Phó phòng (VT 1)", "Phó phòng (VT 2)"):
            total += 1
        elif ng == "Phó phòng (VT 1 & VT 2)":
            total += 2
        elif ng in ("Cán bộ TD", "Cán bộ TD (theo địa bàn)"):
            total += n
        elif ng in ("Phó phòng (VT 1) + Cán bộ TD", "Phó phòng (VT 2) + Cán bộ TD"):
            total += 1 + n
        elif ng in ("Phó phòng (VT 1 & VT 2), Cán bộ TD",):
            total += 2 + n
        elif ng == "Tất cả cán bộ":
            total += 2 + n
        else:
            total += 1
    return total


def _guess_chuc_vu(cv: dict) -> str:
    """Đoán chức vụ từ task (field chuc_vu mới hoặc fallback từ nguoi_thuc_hien cũ)."""
    cv_field = cv.get("chuc_vu")
    if cv_field in _CHUC_VU_LABEL:
        return cv_field
    nguoi = cv.get("nguoi_thuc_hien", "")
    if "VT 1" in nguoi and "VT 2" not in nguoi:
        return "vp1"
    if "VT 2" in nguoi:
        return "vp2"
    if "Phó phòng" in nguoi:
        return "vp1"
    return "cbtd"


# ──────────────────────────────────────────────
# TẢI MẪU GIAO VIỆC
# ──────────────────────────────────────────────


def _tai_mau_giao_viec_v2(ds: list, username: str,
                           vp1: str, vp2: str, cbtd_list: list) -> None:
    """Tải mẫu giao việc — nhân bản task Cán bộ TD theo danh sách tên thực tế."""
    today_str = date.today().isoformat()
    vp1_name = vp1 or "Phó phòng (VT 1)"
    vp2_name = vp2 or "Phó phòng (VT 2)"
    cb_names = cbtd_list if cbtd_list else ["Cán bộ TD"]

    _nhom_ref = [""]  # mutable container để closure _mk đọc được nhom hiện tại

    def _mk(tieu_de: str, mo_ta: str, nguoi: str, chuc_vu: str) -> dict:
        return {
            "id": str(uuid4()),
            "tieu_de": tieu_de,
            "mo_ta": mo_ta,
            "nguoi_thuc_hien": nguoi,
            "chuc_vu": chuc_vu,
            "nhom": _nhom_ref[0],
            "uu_tien": "binh_thuong",
            "trang_thai": "chua_lam",
            "ngay_giao": today_str,
            "ngay_deadline": "",
            "ghi_chu_ket_qua": "",
            "ngay_hoan_thanh": None,
        }

    new_tasks = []
    for t in _MAU_GIAO_VIEC:
        _nhom_ref[0] = t.get("nhom", "")
        td, mo, ng = t["tieu_de"], t["mo_ta"], t["nguoi_thuc_hien"]
        if ng == "Phó phòng (VT 1)":
            new_tasks.append(_mk(td, mo, vp1_name, "vp1"))
        elif ng == "Phó phòng (VT 2)":
            new_tasks.append(_mk(td, mo, vp2_name, "vp2"))
        elif ng == "Phó phòng (VT 1 & VT 2)":
            new_tasks += [_mk(td, mo, vp1_name, "vp1"), _mk(td, mo, vp2_name, "vp2")]
        elif ng in ("Cán bộ TD", "Cán bộ TD (theo địa bàn)"):
            new_tasks += [_mk(td, mo, n, "cbtd") for n in cb_names]
        elif ng == "Phó phòng (VT 1) + Cán bộ TD":
            new_tasks.append(_mk(td, mo, vp1_name, "vp1"))
            new_tasks += [_mk(td, mo, n, "cbtd") for n in cb_names]
        elif ng == "Phó phòng (VT 2) + Cán bộ TD":
            new_tasks.append(_mk(td, mo, vp2_name, "vp2"))
            new_tasks += [_mk(td, mo, n, "cbtd") for n in cb_names]
        elif ng == "Phó phòng (VT 1 & VT 2), Cán bộ TD":
            new_tasks += [_mk(td, mo, vp1_name, "vp1"), _mk(td, mo, vp2_name, "vp2")]
            new_tasks += [_mk(td, mo, n, "cbtd") for n in cb_names]
        elif ng == "Tất cả cán bộ":
            new_tasks += [_mk(td, mo, vp1_name, "vp1"), _mk(td, mo, vp2_name, "vp2")]
            new_tasks += [_mk(td, mo, n, "cbtd") for n in cb_names]
        else:
            new_tasks.append(_mk(td, mo, ng, "cbtd"))

    ds.extend(new_tasks)
    _ghi_ds(KHNV_PHAN_CONG, ds, username, "khnv_tai_mau_giao_viec",
            f"Tải {len(new_tasks)} task từ Bảng giao việc Trưởng phòng KH-NVTD")
    st.success(f"✅ Đã tải {len(new_tasks)} task!")
    st.rerun()


def _tai_mau_tu_kv(ds: list, username: str) -> None:
    """Tải 38 đầu việc mẫu — đọc tên cán bộ từ KHNV_CAN_BO."""
    can_bo = _doc_ds(KHNV_CAN_BO)
    vp1_cb = next((c["ho_ten"] for c in can_bo if c["chuc_vu"] == "vp1"), "")
    vp2_cb = next((c["ho_ten"] for c in can_bo if c["chuc_vu"] == "vp2"), "")
    cbtd_list = [c["ho_ten"] for c in can_bo if c["chuc_vu"] == "cbtd"]
    _tai_mau_giao_viec_v2(ds, username, vp1_cb, vp2_cb, cbtd_list)


# ──────────────────────────────────────────────
# MINI DASHBOARD TIẾN ĐỘ
# ──────────────────────────────────────────────


def _render_mini_tien_do(ds: list, today: date) -> None:
    """Compact progress dashboard — 4 metrics + progress bar mỗi cán bộ."""
    total_all = ht_all = tre_all = dl_all = 0
    per_person: dict = {}   # nguoi → {total, hoan_thanh, tre_han}

    for c in ds:
        tt    = c.get("trang_thai", "chua_lam")
        nguoi = c.get("nguoi_thuc_hien") or "Không rõ"
        if nguoi not in per_person:
            per_person[nguoi] = {"total": 0, "hoan_thanh": 0, "tre_han": 0}
        per_person[nguoi]["total"] += 1
        total_all += 1

        is_overdue = False
        if tt in ("chua_lam", "dang_lam") and c.get("ngay_deadline"):
            try:
                is_overdue = date.fromisoformat(c["ngay_deadline"]) < today
            except ValueError:
                pass

        if tt == "hoan_thanh":
            per_person[nguoi]["hoan_thanh"] += 1
            ht_all += 1
        elif tt == "tre_han" or is_overdue:
            per_person[nguoi]["tre_han"] += 1
            tre_all += 1
        elif tt == "dang_lam":
            dl_all += 1

    pct_all = round(ht_all / total_all * 100, 1) if total_all else 0.0

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("📋 Tổng việc",    total_all)
    m2.metric("✅ Hoàn thành",   f"{ht_all}  ({pct_all}%)")
    m3.metric("🟡 Đang làm",    dl_all)
    m4.metric("⛔ Trễ hạn",     tre_all,
              delta=f"-{tre_all}" if tre_all else None, delta_color="inverse")

    if per_person:
        bars_html = ""
        for nguoi, s in sorted(per_person.items()):
            pct = round(s["hoan_thanh"] / s["total"] * 100) if s["total"] else 0
            color = (
                "#22c55e" if pct == 100 else
                "#3b82f6" if pct >= 70 else
                "#f59e0b" if pct >= 30 else
                "#ef4444"
            )
            tre_badge = (
                f' <span style="color:#b91c1c;font-size:0.72rem;font-weight:700">⛔{s["tre_han"]}</span>'
                if s["tre_han"] else ""
            )
            bars_html += (
                f'<div style="display:flex;align-items:center;gap:8px;margin:3px 0;font-size:0.83rem">'
                f'<span style="min-width:140px;font-weight:600">{nguoi}{tre_badge}</span>'
                f'<div style="flex:1;background:#e5e7eb;border-radius:4px;height:10px">'
                f'<div style="background:{color};width:{pct}%;height:100%;border-radius:4px"></div></div>'
                f'<span style="min-width:60px;text-align:right;opacity:0.65">{s["hoan_thanh"]}/{s["total"]} ({pct}%)</span>'
                f'</div>'
            )
        st.markdown(bars_html, unsafe_allow_html=True)

    st.divider()


# ──────────────────────────────────────────────
# HELPER: TASK CARD (dùng chung ở Tab 2 và Tab 3)
# ──────────────────────────────────────────────


def _render_task_card(cv: dict, ds: list, today: date,
                      role_n: str, username: str, key_prefix: str = "") -> None:
    """Render 1 task card: 4 cols + quick buttons + edit/delete expander."""
    k = cv["id"]
    trang_thai = cv.get("trang_thai", "chua_lam")
    co_quyen_ghi = role_n in ("admin_cn", "manager_cn")
    co_quyen_xoa = role_n == "admin_cn"

    deadline_str = cv.get("ngay_deadline", "")
    try:
        deadline_date = date.fromisoformat(deadline_str) if deadline_str else None
    except ValueError:
        deadline_date = None

    # Màu nền theo mức độ trễ
    row_style = ""
    if trang_thai == "tre_han":
        row_style = "background:#ffe0e0;"
    elif deadline_date and trang_thai in ("chua_lam", "dang_lam"):
        delta = (deadline_date - today).days
        if delta < 0:
            row_style = "background:#ffe0e0;"
        elif delta <= 3:
            row_style = "background:#fff3cd;"

    st.markdown(
        f"<div style='{row_style}padding:8px;border-radius:4px;margin-bottom:4px;'>",
        unsafe_allow_html=True,
    )
    cols = st.columns([4, 1.5, 1.5, 2])
    with cols[0]:
        st.markdown(f"**{cv.get('tieu_de', '')}**")
        _nguoi = cv.get("nguoi_thuc_hien", "")
        _mo_ta = cv.get("mo_ta", "")
        st.caption(f"👤 {_nguoi}" + (f"  ·  {_mo_ta}" if _mo_ta else ""))
    with cols[1]:
        uu = cv.get("uu_tien", "binh_thuong")
        st.markdown(_UU_TIEN_LABEL.get(uu, uu))
    with cols[2]:
        if deadline_str:
            overdue_icon = "⚠️ " if (deadline_date and deadline_date < today
                                     and trang_thai not in ("hoan_thanh", "tre_han")) else "📅 "
            st.markdown(f"{overdue_icon}{deadline_str}")
        if cv.get("ngay_hoan_thanh"):
            st.caption(f"✓ {cv['ngay_hoan_thanh']}")
    with cols[3]:
        st.markdown(_TRANG_THAI_LABEL.get(trang_thai, trang_thai))

    # Quick status buttons — chỉ hiện nút ≠ trạng thái hiện tại
    if co_quyen_ghi:
        _sq1, _sq2, _sq3 = st.columns(3)
        with _sq1:
            if trang_thai != "chua_lam":
                if st.button("🔴 Chưa làm", key=f"{key_prefix}q_cl_{k}",
                             use_container_width=True):
                    cv["trang_thai"] = "chua_lam"
                    cv["ngay_hoan_thanh"] = None
                    _ghi_ds(KHNV_PHAN_CONG, ds, username, "khnv_cap_nhat_trang_thai",
                            f"Đổi → chưa làm: {cv.get('tieu_de', '')}")
                    st.rerun()
        with _sq2:
            if trang_thai != "dang_lam":
                if st.button("🟡 Đang làm", key=f"{key_prefix}q_dl_{k}",
                             use_container_width=True):
                    cv["trang_thai"] = "dang_lam"
                    _ghi_ds(KHNV_PHAN_CONG, ds, username, "khnv_cap_nhat_trang_thai",
                            f"Đổi → đang làm: {cv.get('tieu_de', '')}")
                    st.rerun()
        with _sq3:
            if trang_thai != "hoan_thanh":
                if st.button("✅ Xong", key=f"{key_prefix}q_ht_{k}",
                             use_container_width=True):
                    cv["trang_thai"] = "hoan_thanh"
                    if not cv.get("ngay_hoan_thanh"):
                        cv["ngay_hoan_thanh"] = today.isoformat()
                    _ghi_ds(KHNV_PHAN_CONG, ds, username, "khnv_cap_nhat_trang_thai",
                            f"Đổi → hoàn thành: {cv.get('tieu_de', '')}")
                    st.rerun()

        with st.expander("✏️ Chỉnh sửa / Xóa", expanded=False):
            new_td = st.text_input("Tiêu đề",
                                   value=cv.get("tieu_de", ""),
                                   key=f"{key_prefix}td_edit_{k}")
            new_mo = st.text_area("Mô tả / hướng dẫn",
                                  value=cv.get("mo_ta", ""),
                                  key=f"{key_prefix}mo_edit_{k}")
            _ec1, _ec2 = st.columns(2)
            with _ec1:
                new_ng = st.text_input("Người thực hiện",
                                       value=cv.get("nguoi_thuc_hien", ""),
                                       key=f"{key_prefix}ng_edit_{k}")
            with _ec2:
                _uu_idx = _UU_TIEN.index(cv.get("uu_tien", "binh_thuong")) \
                          if cv.get("uu_tien") in _UU_TIEN else 2
                new_uu = st.selectbox("Ưu tiên", _UU_TIEN,
                                      index=_uu_idx,
                                      format_func=lambda x: _UU_TIEN_LABEL.get(x, x),
                                      key=f"{key_prefix}uu_edit_{k}")
            try:
                _dl_val = date.fromisoformat(cv["ngay_deadline"]) \
                          if cv.get("ngay_deadline") else today
            except ValueError:
                _dl_val = today
            new_dl = st.date_input("Deadline", value=_dl_val,
                                   key=f"{key_prefix}dl_edit_{k}")
            new_gc = st.text_area("Ghi chú kết quả",
                                  value=cv.get("ghi_chu_ket_qua", ""),
                                  key=f"{key_prefix}gc_edit_{k}")
            col_save, col_del = st.columns(2)
            with col_save:
                if st.button("💾 Lưu", key=f"{key_prefix}save_{k}",
                             use_container_width=True):
                    if new_td.strip():
                        cv["tieu_de"] = new_td.strip()
                    cv["mo_ta"] = new_mo.strip()
                    if new_ng.strip():
                        cv["nguoi_thuc_hien"] = new_ng.strip()
                    cv["uu_tien"] = new_uu
                    cv["ngay_deadline"] = new_dl.isoformat()
                    cv["ghi_chu_ket_qua"] = new_gc.strip()
                    _ghi_ds(KHNV_PHAN_CONG, ds, username, "khnv_sua_task",
                            f"Sửa: {cv.get('tieu_de', '')}")
                    st.success("✅ Đã lưu!")
                    st.rerun()
            with col_del:
                if co_quyen_xoa:
                    if st.checkbox("☑ Xác nhận xóa",
                                   key=f"{key_prefix}del_confirm_{k}"):
                        if st.button("🗑️ Xóa", key=f"{key_prefix}del_{k}",
                                     use_container_width=True):
                            ds.remove(cv)
                            _ghi_ds(KHNV_PHAN_CONG, ds, username, "khnv_xoa_task",
                                    f"Xóa: {cv.get('tieu_de', '')}")
                            st.success("✅ Đã xóa!")
                            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)


# ──────────────────────────────────────────────
# TAB 1: 👥 Nhân sự & Chức vụ
# ──────────────────────────────────────────────


def _render_nhan_su(role_n: str, username: str) -> None:
    """Quản lý danh sách cán bộ — lưu vào KHNV_CAN_BO."""
    co_quyen = role_n in ("admin_cn", "manager_cn")
    can_bo = _doc_ds(KHNV_CAN_BO)

    st.markdown("### 👥 Danh sách cán bộ Phòng KH-NV")
    st.caption("Khai báo tên cán bộ tại đây — dùng để phân công và tải đầu việc mẫu ở Tab Phân công.")

    if not can_bo:
        st.info("ℹ️ Chưa có cán bộ. Thêm cán bộ để bắt đầu phân công.")
    else:
        for chuc_vu, label in _CHUC_VU_LABEL.items():
            nhom_cb = [c for c in can_bo if c["chuc_vu"] == chuc_vu]
            if not nhom_cb:
                continue
            st.markdown(f"**{label}**")
            for cb in nhom_cb:
                col_ten, col_xoa = st.columns([6, 1])
                col_ten.write(f"👤 {cb['ho_ten']}")
                if co_quyen:
                    if col_xoa.button("🗑️", key=f"xoa_cb_{cb['id']}",
                                      help="Xóa cán bộ này"):
                        can_bo.remove(cb)
                        _ghi_ds(KHNV_CAN_BO, can_bo, username,
                                "khnv_xoa_can_bo", f"Xóa cán bộ: {cb['ho_ten']}")
                        st.rerun()

    if co_quyen:
        st.divider()
        with st.expander("➕ Thêm cán bộ", expanded=not can_bo):
            with st.form("form_them_can_bo", clear_on_submit=True):
                ho_ten = st.text_input("Họ và tên *")
                chuc_vu_sel = st.selectbox(
                    "Chức vụ / Vị trí",
                    list(_CHUC_VU_LABEL.keys()),
                    format_func=lambda x: _CHUC_VU_LABEL[x],
                    key="them_cb_chuc_vu",
                )
                if st.form_submit_button("✅ Thêm cán bộ", type="primary"):
                    if ho_ten.strip():
                        can_bo.append({
                            "id": str(uuid4()),
                            "ho_ten": ho_ten.strip(),
                            "chuc_vu": chuc_vu_sel,
                        })
                        _ghi_ds(KHNV_CAN_BO, can_bo, username,
                                "khnv_them_can_bo",
                                f"Thêm: {ho_ten.strip()} — {chuc_vu_sel}")
                        st.success(f"✅ Đã thêm {ho_ten.strip()}!")
                        st.rerun()
                    else:
                        st.error("Vui lòng nhập họ và tên.")


# ──────────────────────────────────────────────
# TAB 2: 📋 Phân công công việc
# ──────────────────────────────────────────────


def _render_phan_cong_v2(role_n: str, username: str) -> None:
    """Phân công: chọn cán bộ → dropdown đầu việc theo chức vụ → gom nhóm theo vị trí."""
    co_quyen_ghi = role_n in ("admin_cn", "manager_cn")
    today = date.today()

    can_bo_list = _doc_ds(KHNV_CAN_BO)
    ds = _doc_ds(KHNV_PHAN_CONG)

    # Mini dashboard ở trên nếu có dữ liệu
    if ds:
        _render_mini_tien_do(ds, today)

    if co_quyen_ghi:
        # ── Form giao việc từ dropdown ──
        if not can_bo_list:
            st.warning("⚠️ Chưa có cán bộ. Vào tab **Nhân sự & Chức vụ** để thêm trước.")
        else:
            with st.expander("➕ Giao việc từ danh sách mẫu", expanded=not ds):
                options_cb = [(c["id"], f"{c['ho_ten']} — {_CHUC_VU_LABEL[c['chuc_vu']]}") for c in can_bo_list]
                id_to_label = dict(options_cb)
                sel_id = st.selectbox(
                    "① Cán bộ thực hiện",
                    [x[0] for x in options_cb],
                    format_func=lambda i: id_to_label.get(i, i),
                    key="pc2_sel_cb",
                )
                sel_cb = next((c for c in can_bo_list if c["id"] == sel_id), None)

                if sel_cb:
                    allowed = _CHUC_VU_TASK_FILTER[sel_cb["chuc_vu"]]
                    mau_loc = [t for t in _MAU_GIAO_VIEC if t["nguoi_thuc_hien"] in allowed]
                    options_td = [
                        f"[{t['nhom'].split('.')[0]}] {t['tieu_de']}" for t in mau_loc
                    ]
                    sel_td_idx = st.selectbox(
                        "② Chọn đầu việc",
                        range(len(options_td)),
                        format_func=lambda i: options_td[i],
                        key="pc2_sel_td",
                    )
                    sel_mau = mau_loc[sel_td_idx]
                    st.caption(f"📝 {sel_mau['mo_ta']}")

                    _fc1, _fc2 = st.columns(2)
                    with _fc1:
                        dl = st.date_input("Deadline", value=today, key="pc2_dl")
                    with _fc2:
                        uu_sel = st.selectbox(
                            "Ưu tiên", _UU_TIEN,
                            format_func=lambda x: _UU_TIEN_LABEL[x],
                            index=2, key="pc2_uu",
                        )

                    if st.button("➕ Thêm đầu việc này", type="primary",
                                 key="pc2_btn_add", use_container_width=True):
                        ds.append({
                            "id": str(uuid4()),
                            "tieu_de": sel_mau["tieu_de"],
                            "mo_ta": sel_mau["mo_ta"],
                            "nguoi_thuc_hien": sel_cb["ho_ten"],
                            "chuc_vu": sel_cb["chuc_vu"],
                            "nhom": sel_mau["nhom"],
                            "uu_tien": uu_sel,
                            "trang_thai": "chua_lam",
                            "ngay_giao": today.isoformat(),
                            "ngay_deadline": dl.isoformat(),
                            "ghi_chu_ket_qua": "",
                            "ngay_hoan_thanh": None,
                        })
                        _ghi_ds(KHNV_PHAN_CONG, ds, username, "khnv_giao_viec",
                                f"Giao: {sel_mau['tieu_de']} → {sel_cb['ho_ten']}")
                        st.success("✅ Đã thêm!")
                        st.rerun()

        # ── Form giao việc thủ công ──
        with st.expander("✍️ Giao việc thủ công", expanded=False):
            with st.form("form_phan_cong_manual", clear_on_submit=True):
                tieu_de = st.text_input("Tiêu đề *")
                mo_ta   = st.text_area("Mô tả / hướng dẫn")
                nguoi   = st.text_input("Người thực hiện *")
                uu_tien = st.selectbox("Ưu tiên", _UU_TIEN,
                                       format_func=lambda x: _UU_TIEN_LABEL[x])
                _mc1, _mc2 = st.columns(2)
                ngay_giao     = _mc1.date_input("Ngày giao",  value=today)
                ngay_deadline = _mc2.date_input("Deadline *", value=today)
                if st.form_submit_button("🚀 Giao việc", type="primary"):
                    if not tieu_de.strip() or not nguoi.strip():
                        st.error("Vui lòng nhập Tiêu đề và Người thực hiện.")
                    else:
                        ds.append({
                            "id": str(uuid4()),
                            "tieu_de": tieu_de.strip(),
                            "mo_ta": mo_ta.strip(),
                            "nguoi_thuc_hien": nguoi.strip(),
                            "nhom": "📌 Thêm thủ công",
                            "uu_tien": uu_tien,
                            "trang_thai": "chua_lam",
                            "ngay_giao": ngay_giao.isoformat(),
                            "ngay_deadline": ngay_deadline.isoformat(),
                            "ghi_chu_ket_qua": "",
                            "ngay_hoan_thanh": None,
                        })
                        _ghi_ds(KHNV_PHAN_CONG, ds, username, "khnv_giao_viec",
                                f"Giao: {tieu_de.strip()} → {nguoi.strip()}")
                        st.success("✅ Đã giao việc!")
                        st.rerun()

        # ── Nút tải toàn bộ 38 đầu việc mẫu ──
        if can_bo_list:
            with st.expander("⚙️ Tải toàn bộ 38 đầu việc mẫu", expanded=not ds):
                vp1_cb = next((c["ho_ten"] for c in can_bo_list if c["chuc_vu"] == "vp1"), "—")
                vp2_cb = next((c["ho_ten"] for c in can_bo_list if c["chuc_vu"] == "vp2"), "—")
                cbtd_list = [c["ho_ten"] for c in can_bo_list if c["chuc_vu"] == "cbtd"]
                _est = _tinh_so_task(vp1_cb, vp2_cb, cbtd_list)
                st.caption(
                    f"Sẽ gán: VP1 → **{vp1_cb}**, VP2 → **{vp2_cb}**, "
                    f"CBTD → {', '.join(cbtd_list) or '—'}  "
                    f"· Ước tính: **{_est} task**"
                )
                if ds:
                    st.warning("⚠️ Danh sách đang có dữ liệu — task mẫu sẽ được **thêm vào cuối**.")
                if st.button("✅ Tải toàn bộ đầu việc mẫu", type="primary",
                             key="pc2_btn_seed", use_container_width=True):
                    _tai_mau_tu_kv(ds, username)

    # ── Danh sách task gom nhóm theo chức vụ ──
    if not ds:
        st.info("ℹ️ Chưa có việc nào được giao.")
        return

    st.markdown("### 📋 Danh sách phân công theo vị trí")

    ds_sorted = sorted(ds, key=lambda x: (
        0 if x.get("trang_thai") in ("chua_lam", "dang_lam") else 1,
        x.get("ngay_deadline", ""),
    ))

    # Gom nhóm theo chức vụ
    nhom_cv: dict = {"vp1": [], "vp2": [], "cbtd": [], "other": []}
    for cv in ds_sorted:
        g = _guess_chuc_vu(cv)
        nhom_cv.get(g, nhom_cv["other"]).append(cv)

    cv_order = list(_CHUC_VU_LABEL.items()) + [("other", "📌 Thêm thủ công")]
    for chuc_vu, label in cv_order:
        tasks = nhom_cv.get(chuc_vu, [])
        if not tasks:
            continue
        ht = sum(1 for t in tasks if t.get("trang_thai") == "hoan_thanh")
        tre = sum(1 for t in tasks
                  if t.get("trang_thai") not in ("hoan_thanh",)
                  and t.get("ngay_deadline")
                  and _safe_date_lt(t["ngay_deadline"], today))
        badge_tre = f"  ·  ⛔ {tre} trễ" if tre else ""
        hdr = f"{label}  ·  {ht}/{len(tasks)} ✅{badge_tre}"
        with st.expander(hdr, expanded=True):
            for cv in tasks:
                _render_task_card(cv, ds, today, role_n, username, key_prefix="pc2_")


def _safe_date_lt(date_str: str, ref: date) -> bool:
    """True nếu date_str < ref, bắt lỗi parse."""
    try:
        return date.fromisoformat(date_str) < ref
    except ValueError:
        return False


# ──────────────────────────────────────────────
# TAB 3: 📊 Tiến độ / Chỉnh sửa / Xóa
# ──────────────────────────────────────────────


def _render_tien_do_edit(role_n: str, username: str) -> None:
    """Tab tiến độ: mini dashboard + bộ lọc + quick buttons + edit chi tiết."""
    ds = _doc_ds(KHNV_PHAN_CONG)
    today = date.today()

    if not ds:
        st.info("📭 Chưa có đầu việc. Vào tab **Phân công** để thêm.")
        return

    _render_mini_tien_do(ds, today)

    # Bộ lọc
    col_f1, col_f2 = st.columns(2)
    filter_tt = col_f1.multiselect(
        "Lọc trạng thái",
        list(_TRANG_THAI_LABEL.keys()),
        format_func=lambda x: _TRANG_THAI_LABEL[x],
        key="td_filter_tt",
    )
    nguoi_options = ["Tất cả"] + sorted(
        {c.get("nguoi_thuc_hien", "") for c in ds if c.get("nguoi_thuc_hien")}
    )
    filter_nguoi = col_f2.selectbox("Lọc người", nguoi_options, key="td_filter_nguoi")

    ds_view = [
        c for c in ds
        if (not filter_tt or c.get("trang_thai") in filter_tt)
        and (filter_nguoi == "Tất cả" or c.get("nguoi_thuc_hien") == filter_nguoi)
    ]
    ds_view.sort(key=lambda x: (
        0 if x.get("trang_thai") in ("chua_lam", "dang_lam") else 1,
        x.get("ngay_deadline", ""),
    ))

    st.markdown(f"**{len(ds_view)} đầu việc**" + (" (đã lọc)" if filter_tt or filter_nguoi != "Tất cả" else ""))

    for cv in ds_view:
        _render_task_card(cv, ds, today, role_n, username, key_prefix="td_")


# ──────────────────────────────────────────────
# TAB 4: 📄 In báo cáo
# ──────────────────────────────────────────────


def _render_bao_cao(role_n: str, username: str, **kwargs) -> None:
    """Tab báo cáo: PDF tiến độ, Excel phân công, checklist cấp trên."""
    ds = _doc_ds(KHNV_PHAN_CONG)

    st.markdown("### 📄 Xuất báo cáo")

    col_a, col_b = st.columns(2)

    # PDF tiến độ
    with col_a:
        st.markdown("**📊 Báo cáo tiến độ thực hiện (PDF)**")
        if ds:
            _tt_map = {
                "chua_lam": "Chưa làm", "dang_lam": "Đang làm",
                "hoan_thanh": "Hoàn thành", "tre_han": "Trễ hạn",
            }
            _df_td = pd.DataFrame([{
                "Tiêu đề": c.get("tieu_de", ""),
                "Người TH": c.get("nguoi_thuc_hien", ""),
                "Trạng thái": _tt_map.get(c.get("trang_thai", ""), ""),
                "Deadline": c.get("ngay_deadline", ""),
                "Ghi chú": c.get("ghi_chu_ket_qua", ""),
            } for c in ds])
            _pdf_td = xuat_pdf_co_chart(
                _df_td, "Tiến độ thực hiện - Phòng KH-NV", username,
                them_dong_tong=False, cols_tien=None,
            )
            download_pdf_button(_pdf_td, "tien_do_khnv.pdf",
                                "🖨️ Xuất PDF tiến độ", key="bc_pdf_td")
            ghi_audit(username, "xuat_bieu_cn", "Xuất PDF tiến độ Phòng KH-NV")
        else:
            st.button("🖨️ Xuất PDF tiến độ", disabled=True,
                      key="bc_pdf_td_dis", use_container_width=True)
            st.caption("Chưa có dữ liệu phân công.")

    # Excel phân công
    with col_b:
        st.markdown("**📋 Xuất Excel danh sách phân công**")
        if ds:
            _uu_map = {
                "khan_cap": "Khẩn cấp",
                "quan_trong": "Quan trọng",
                "binh_thuong": "Bình thường",
            }
            _tt_map2 = {
                "chua_lam": "Chưa làm", "dang_lam": "Đang làm",
                "hoan_thanh": "Hoàn thành", "tre_han": "Trễ hạn",
            }
            _df_xls = pd.DataFrame([{
                "Tiêu đề": c.get("tieu_de", ""),
                "Nhóm": c.get("nhom", ""),
                "Người TH": c.get("nguoi_thuc_hien", ""),
                "Ưu tiên": _uu_map.get(c.get("uu_tien", ""), ""),
                "Ngày giao": c.get("ngay_giao", ""),
                "Deadline": c.get("ngay_deadline", ""),
                "Trạng thái": _tt_map2.get(c.get("trang_thai", ""), ""),
                "Ghi chú": c.get("ghi_chu_ket_qua", ""),
            } for c in ds])
            _xl_bytes = xuat_excel({"Phân công": _df_xls})
            st.download_button(
                "📥 Tải Excel phân công",
                data=_xl_bytes,
                file_name="phan_cong_khnv.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="bc_excel_dl",
                use_container_width=True,
            )
            ghi_audit(username, "xuat_bieu_cn", "Xuất Excel phân công Phòng KH-NV")
        else:
            st.button("📥 Tải Excel phân công", disabled=True,
                      key="bc_excel_dis", use_container_width=True)
            st.caption("Chưa có dữ liệu phân công.")

    st.divider()
    st.markdown("### 📤 Checklist Báo cáo cấp trên")
    tab_checklist_bc.render(None, **kwargs)


# ──────────────────────────────────────────────
# TAB 5: 📅 Lịch công tác
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

    # ── Xuất PDF ──
    col_pdf, _ = st.columns([1, 5])
    with col_pdf:
        if ds_loc:
            _loai_map = {
                k: v.replace("🗓️ ", "").replace("🔍 ", "").replace("✈️ ", "")
                    .replace("🎓 ", "").replace("📌 ", "")
                for k, v in LOAI_LICH.items()
            }
            _tt_lich = {"sap_dien_ra": "Sắp diễn ra", "da_hoan_thanh": "Đã hoàn thành", "huy_bo": "Hủy bỏ"}
            _df_lich = pd.DataFrame([{
                "Ngày": e.get("ngay", ""),
                "Loại": _loai_map.get(e.get("loai", ""), e.get("loai", "")),
                "Tiêu đề": e.get("tieu_de", ""),
                "Địa điểm": e.get("dia_diem", ""),
                "Thành viên": e.get("thanh_vien", ""),
                "Ghi chú": e.get("ghi_chu", ""),
                "Trạng thái": _tt_lich.get(e.get("trang_thai", ""), e.get("trang_thai", "")),
            } for e in ds_loc])
            _pdf_bytes = xuat_pdf_co_chart(
                _df_lich, "Lịch công tác Phòng KH-NV", username,
                them_dong_tong=False, cols_tien=None,
            )
            download_pdf_button(_pdf_bytes, "lich_cong_tac.pdf",
                                "📥 Xuất PDF", key="pdf_lich")
        else:
            st.button("📥 Xuất PDF", disabled=True, key="pdf_lich_dis",
                      use_container_width=True)

    st.markdown("### 📅 Lịch công tác trong tháng")
    for ev in ds_loc:
        try:
            ev_date = date.fromisoformat(ev["ngay"])
        except (ValueError, KeyError):
            ev_date = None

        is_current_week = False
        if ev_date:
            start_week = today - timedelta(days=today.weekday())
            end_week = start_week + timedelta(days=6)
            is_current_week = start_week <= ev_date <= end_week

        bg = "#e8f4fd;" if is_current_week else ""
        st.markdown(
            f"<div style='background-color:{bg} padding:8px; border-radius:4px; margin-bottom:4px;'>",
            unsafe_allow_html=True,
        )

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
                new_loai = st.selectbox(
                    "Loại", list(LOAI_LICH.keys()),
                    index=list(LOAI_LICH.keys()).index(ev.get("loai", "khac")) if ev.get("loai") in LOAI_LICH else 0,
                    key=f"ll_{ev['id']}",
                    format_func=lambda x: LOAI_LICH[x],
                )
                new_ngay = st.date_input(
                    "Ngày",
                    value=date.fromisoformat(ev["ngay"]) if ev.get("ngay") else today,
                    key=f"ln_{ev['id']}",
                )
                new_dia_diem   = st.text_input("Địa điểm", value=ev.get("dia_diem", ""), key=f"ld_{ev['id']}")
                new_thanh_vien = st.text_area("Thành viên", value=ev.get("thanh_vien", ""), key=f"ltv_{ev['id']}")
                new_ghi_chu    = st.text_area("Ghi chú", value=ev.get("ghi_chu", ""), key=f"lg_{ev['id']}")
                new_trang_thai = st.selectbox(
                    "Trạng thái",
                    ["sap_dien_ra", "da_hoan_thanh", "huy_bo"],
                    index=["sap_dien_ra", "da_hoan_thanh", "huy_bo"].index(ev.get("trang_thai", "sap_dien_ra")),
                    key=f"ltt_{ev['id']}",
                    format_func=lambda x: {
                        "sap_dien_ra": "🟡 Sắp diễn ra",
                        "da_hoan_thanh": "✅ Đã hoàn thành",
                        "huy_bo": "❌ Hủy bỏ",
                    }.get(x, x),
                )
                col_s1, col_s2 = st.columns(2)
                with col_s1:
                    if st.button("💾 Lưu", key=f"save_lich_{ev['id']}"):
                        if new_tieu_de.strip():
                            ev["tieu_de"]     = new_tieu_de.strip()
                            ev["loai"]        = new_loai
                            ev["ngay"]        = new_ngay.isoformat()
                            ev["dia_diem"]    = new_dia_diem.strip()
                            ev["thanh_vien"]  = new_thanh_vien.strip()
                            ev["ghi_chu"]     = new_ghi_chu.strip()
                            ev["trang_thai"]  = new_trang_thai
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
# TAB 6: 📖 Thông tin đầu việc (tham chiếu tĩnh)
# ──────────────────────────────────────────────


def _render_thong_tin_dau_viec() -> None:
    """Bảng tham chiếu tĩnh: đầu việc Trưởng phòng TP01–TP17 + 38 việc cấp dưới."""

    # ── Phần 1: Đầu việc Trưởng phòng ──
    st.markdown("## 📌 Bảng đầu việc của Trưởng phòng KH-NVTD")
    st.caption("17 đầu việc chính (TP01–TP17) — chỉ đọc, dùng để tra cứu và tham chiếu")

    rows_tp = ""
    for t in _MAU_GIAO_VIEC_TP:
        rows_tp += (
            f"<tr style='border-bottom:1px solid #e5e7eb'>"
            f"<td style='padding:7px 10px;white-space:nowrap;font-weight:700;color:#1e3a5f'>{t['ma']}</td>"
            f"<td style='padding:7px 10px'>{t['tieu_de']}</td>"
            f"<td style='padding:7px 10px;color:#374151;font-size:0.82rem'>{t['mo_ta']}</td>"
            f"<td style='padding:7px 10px;white-space:nowrap;color:#6b7280;font-size:0.82rem'>{t['tan_suat']}</td>"
            f"</tr>"
        )
    st.markdown(
        f"""<div style="overflow-x:auto;margin-bottom:24px">
        <table style="width:100%;border-collapse:collapse;font-size:0.85rem">
          <thead>
            <tr style="background:#1e3a5f;color:white">
              <th style="padding:9px 10px;text-align:left;white-space:nowrap">Mã</th>
              <th style="padding:9px 10px;text-align:left">Đầu việc</th>
              <th style="padding:9px 10px;text-align:left">Mô tả chi tiết</th>
              <th style="padding:9px 10px;text-align:left">Tần suất</th>
            </tr>
          </thead>
          <tbody>{rows_tp}</tbody>
        </table></div>""",
        unsafe_allow_html=True,
    )

    st.divider()

    # ── Phần 2: Bảng giao việc cấp dưới (38 việc) ──
    st.markdown("## 📋 Bảng giao việc cấp dưới (38 đầu việc nhóm I–VIII)")
    st.caption("Phó phòng VP1, VP2 và Cán bộ TD tại Hội sở")

    nhom_groups: dict = {}
    for idx, t in enumerate(_MAU_GIAO_VIEC, start=1):
        nh = t.get("nhom", "")
        nhom_groups.setdefault(nh, []).append((idx, t))

    for nhom_name, items in dict(sorted(nhom_groups.items())).items():
        st.markdown(f"### {nhom_name}")
        rows = ""
        for stt, t in items:
            rows += (
                f"<tr style='border-bottom:1px solid #e5e7eb'>"
                f"<td style='padding:6px 8px;text-align:center;color:#6b7280;width:40px'>{stt}</td>"
                f"<td style='padding:6px 8px'>{t['tieu_de']}</td>"
                f"<td style='padding:6px 8px;white-space:nowrap;color:#1d4ed8;font-size:0.82rem'>{t['nguoi_thuc_hien']}</td>"
                f"<td style='padding:6px 8px;color:#374151;font-size:0.8rem'>{t['mo_ta']}</td>"
                f"</tr>"
            )
        st.markdown(
            f"""<div style="overflow-x:auto;margin-bottom:16px">
            <table style="width:100%;border-collapse:collapse;font-size:0.85rem">
              <thead>
                <tr style="background:#f3f4f6">
                  <th style="padding:6px 8px;width:40px">STT</th>
                  <th style="padding:6px 8px;text-align:left">Đầu việc</th>
                  <th style="padding:6px 8px;text-align:left">Người thực hiện</th>
                  <th style="padding:6px 8px;text-align:left">Thời hạn / Sản phẩm</th>
                </tr>
              </thead>
              <tbody>{rows}</tbody>
            </table></div>""",
            unsafe_allow_html=True,
        )


# ──────────────────────────────────────────────
# RENDER CHÍNH — 6 tab
# ──────────────────────────────────────────────


def render(tab=None, **kwargs):
    """6 sub-tab theo luồng: Nhân sự → Phân công → Tiến độ → Báo cáo → Lịch → Thông tin.

    Chỉ khả dụng cho phòng KH-NV (admin_cn, manager_cn, executive).
    """
    ctx = get_tab_context(tab)
    role_n = normalize_role(str(kwargs.get("role", "user")))
    username = kwargs.get("username", "unknown")

    if role_n in ("user", "manager_pgd", "admin_pgd"):
        with ctx:
            st.warning("⚠️ Tab này chỉ dành cho phòng KH-NV.")
        return

    with ctx:
        t1, t2, t3, t4, t5, t6 = st.tabs([
            "👥 Nhân sự & Chức vụ",
            "📋 Phân công công việc",
            "📊 Tiến độ / Chỉnh sửa",
            "📄 In báo cáo",
            "📅 Lịch công tác",
            "📖 Thông tin đầu việc",
        ])
        with t1:
            _render_nhan_su(role_n, username)
        with t2:
            _render_phan_cong_v2(role_n, username)
        with t3:
            _render_tien_do_edit(role_n, username)
        with t4:
            _render_bao_cao(role_n, username, **kwargs)
        with t5:
            _render_lich_cong_tac(t5, role_n, username)
        with t6:
            _render_thong_tin_dau_viec()
