"""Registry tập trung cho tất cả tab trong hệ thống.

Thêm tab mới:
  1. Tạo file tabs/tab_xxx.py với hàm render(tab=None, **kwargs)
  2. Thêm register(TabDef(...)) vào đúng workspace bên dưới
  3. Workspace sẽ tự đọc từ registry — không cần sửa workspace

Workspace:
  - "cn"   → ws_management  (Phòng KH-NV, toàn chi nhánh)
  - "pgd"  → ws_operation   (Hỗ trợ địa bàn PGD)
  - "exec" → ws_executive   (Ban Giám đốc, chỉ đọc)

Lưu ý:
  - Các tab là hàm nội bộ (không phải module) → KHÔNG đăng ký ở đây,
    giữ nguyên hardcode trong workspace.
  - roles=None → mọi role trong workspace đều thấy.
  - roles=["admin_cn"] → chỉ role cụ thể mới thấy.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TabDef:
    module: str           # "tab_tongquan"
    label: str            # "📊 Thông tin chung"
    group: str            # "Tổng quan"
    workspace: str        # "cn", "pgd", "exec"
    icon: str = ""
    roles: list[str] | None = None  # None = all roles in workspace
    extra_kwargs: dict = field(default_factory=dict)
    render_fn: str = "render"
    order: int = 0        # sort order within group


# Registry: list of all tab definitions
_REGISTRY: list[TabDef] = []


def register(tab: TabDef) -> None:
    _REGISTRY.append(tab)


def get_tabs(workspace: str, role: str | None = None) -> list[TabDef]:
    """Lấy danh sách tab cho workspace, lọc theo role."""
    result = [t for t in _REGISTRY if t.workspace == workspace]
    if role:
        result = [t for t in result if t.roles is None or role in t.roles]
    return sorted(result, key=lambda t: (t.group, t.order))


def get_groups(workspace: str, role: str | None = None) -> dict[str, list[TabDef]]:
    """Lấy tab theo nhóm cho workspace."""
    tabs = get_tabs(workspace, role)
    groups: dict[str, list[TabDef]] = {}
    for t in tabs:
        groups.setdefault(t.group, []).append(t)
    return groups


# ═══════════════════════════════════════════════════════════════════════════════
# Workspace CN — ws_management (Phòng KH-NV)
# ═══════════════════════════════════════════════════════════════════════════════

# ── Tổng quan ─────────────────────────────────────────────────────────────────
register(TabDef("tab_tongquan", "📊 Thông tin chung", "Tổng quan", "cn", icon="info-circle", order=1))
register(TabDef("tab_pgd_cards", "🏢 Toàn cảnh 22 PGD", "Tổng quan", "cn", icon="grid", order=2))
register(TabDef("tab_tracuu_v2", "🔍 Tra cứu Khách hàng", "Tổng quan", "cn", icon="search", order=3))

# ── Nội bộ Phòng ─────────────────────────────────────────────────────────────
register(TabDef("tab_khnv_noi_bo", "🗂️ Nội bộ Phòng KH-NV", "Nội bộ Phòng", "cn", icon="users", order=1))
register(TabDef("tab_quan_ly_cv", " Quản lý Công việc & Nhiệm vụ", "Nội bộ Phòng", "cn", icon="layout", order=2))

# ── Báo cáo ──────────────────────────────────────────────────────────────────
register(TabDef("tab_baocao", "📊 Báo cáo tín dụng", "Báo cáo", "cn", icon="file", order=1))
register(TabDef("tab_den_han", "⏰ Nợ Đến Hạn", "Báo cáo", "cn", icon="clock", order=2))
register(TabDef("tab_bao_cao_dinh_ky", "📅 Báo cáo định kỳ", "Báo cáo", "cn", icon="calendar", order=3))
register(TabDef("tab_khnv_bao_cao", "📄 Báo cáo KHNV", "Báo cáo", "cn", icon="file-report", order=4))
register(TabDef("tab_tien_do_nop", "📥 Tiến độ nộp BC", "Báo cáo", "cn", icon="inbox", order=5))
register(TabDef("tab_theo_doi_nhap", "📋 Theo dõi nhập liệu", "Báo cáo", "cn", icon="clipboard-list", order=6))

# ── Giám sát ─────────────────────────────────────────────────────────────────
# ⚠️ "🔴 NQH tăng đột biến" là hàm nội bộ (_render_nqh_tang_dot_bien) — giữ trong workspace
register(TabDef("tab_canh_bao_nqh", "⚠️ Cảnh báo Tín dụng", "Giám sát", "cn", icon="alert-triangle", order=1))
register(TabDef("tab_so_sanh_ky", "📊 So sánh kỳ", "Giám sát", "cn", icon="chart-line", order=2))
register(TabDef("tab_data_quality", "🛡️ Chất lượng Dữ liệu", "Giám sát", "cn", icon="shield-check", order=4))
register(TabDef("tab_phan_ky_nxh", "🏠 Phân kỳ NXH", "Giám sát", "cn", icon="home", order=5))
register(TabDef("tab_phan_loai_kh", "🏷️ Phân loại Khách hàng", "Giám sát", "cn", icon="tag", order=6))
register(TabDef("tab_stress_test", "🧪 Stress Test Danh mục", "Giám sát", "cn", icon="flask", order=7))

# ── Kiểm soát ────────────────────────────────────────────────────────────────
register(TabDef("tab_kiem_soat", "🔎 Kiểm soát nội bộ", "Kiểm soát", "cn", icon="search", render_fn="render_tab", order=1))
register(TabDef("tab_ktnb", "🔍 Kiểm toán Nội bộ (KTNB)", "Kiểm soát", "cn", icon="file-search", order=2))
register(TabDef("tab_xu_ly_rui_ro", "⚡ Xử lý Rủi ro", "Kiểm soát", "cn", icon="alert-circle", order=3))
# Nợ Khoanh — accordion 2 con trong workspace, cùng module tab_no_khoanh
register(TabDef("tab_no_khoanh", "📊 Tổng quan Nợ Khoanh", "Kiểm soát", "cn", icon="lock", extra_kwargs={"nhom": "tongquan"}, order=4))
register(TabDef("tab_no_khoanh", "🔒 Quản lý Nợ Khoanh theo CV 368", "Kiểm soát", "cn", icon="lock", extra_kwargs={"nhom": "cv368"}, order=5))

# ── Kế hoạch Tín dụng ────────────────────────────────────────────────────────
# ⚠️ "🏦 Nguồn vốn địa phương" là hàm nội bộ (_render_nguon_von_dia_phuong) — giữ trong workspace
register(TabDef("tab_khtd", "📈 Kế hoạch tín dụng", "Kế hoạch Tín dụng", "cn", icon="file-text", extra_kwargs={"khtd_mode": "cn"}, order=1))
register(TabDef("tab_khtd_giao_dc", "📋 Giao & ĐC KHTD", "Kế hoạch Tín dụng", "cn", icon="upload", order=2))
register(TabDef("tab_candoi", "📡 Điện báo Cân đối", "Kế hoạch Tín dụng", "cn", icon="antenna", order=3))
register(TabDef("tab_khtd_xuat", "📤 Xuất báo cáo KHTD", "Kế hoạch Tín dụng", "cn", icon="file-export", render_fn="render_xuat_baocao", order=4))

# ── Ủy Thác ──────────────────────────────────────────────────────────────────
# ⚠️ "👔 CBTD & Địa bàn" là hàm nội bộ (_render_cbtd_dia_ban) — giữ trong workspace
register(TabDef("tab_ban_dai_dien", "🏛️ Ban Đại Diện", "Ủy Thác", "cn", icon="building", extra_kwargs={"cap": "tinh"}, order=1))
register(TabDef("tab_uy_thac", "🤝 Ủy thác", "Ủy Thác", "cn", icon="handshake", order=2))

# ── Hệ thống ─────────────────────────────────────────────────────────────────
register(TabDef("tab_audit_log", "Nhật ký hệ thống", "Hệ thống", "cn", icon="list", roles=["admin_cn"], order=1))
register(TabDef("tab_security", "🔐 Quản lý bảo mật", "Hệ thống", "cn", icon="shield", roles=["admin_cn"], order=2))
register(TabDef("tab_telegram_admin", "🤖 Bot Telegram", "Hệ thống", "cn", icon="message", roles=["admin_cn"], order=3))
register(TabDef("tab_trang_thai_nguon", "🔍 Trạng thái hệ thống", "Hệ thống", "cn", icon="pulse", order=4))
register(TabDef("tab_upload_khnv", "Upload dữ liệu", "Hệ thống", "cn", icon="upload", order=5))
# ⚠️ "📖 Hướng dẫn" là hàm nội bộ (render_huong_dan từ pdf_service) — giữ trong workspace


# ═══════════════════════════════════════════════════════════════════════════════
# Workspace PGD — ws_operation (Hỗ trợ địa bàn)
# ═══════════════════════════════════════════════════════════════════════════════

# ── Tổng quan ─────────────────────────────────────────────────────────────────
register(TabDef("tab_trang_chu_pgd", "🏠 Trang Chủ", "Tổng quan", "pgd", order=1))
register(TabDef("tab_dashboard_suc_khoe_pgd", "📊 Dashboard Sức khỏe", "Tổng quan", "pgd", order=2))
register(TabDef("tab_dashboard_dgd_pgd", "📍 Tổng quan ĐGD & Tổ TK&VV", "Tổng quan", "pgd", order=3))

# ── Tác nghiệp ───────────────────────────────────────────────────────────────
register(TabDef("tab_tongquan", "📊 Thông tin chung", "Tác nghiệp", "pgd", order=1))
register(TabDef("tab_tien_do", "📈 Tiến độ công việc", "Tác nghiệp", "pgd", order=2))
register(TabDef("tab_tracuu_v2", "🔍 Tra cứu hồ sơ", "Tác nghiệp", "pgd", order=3))
register(TabDef("tab_danhsach", "📋 Danh sách & Lọc", "Tác nghiệp", "pgd", order=4))
register(TabDef("tab_den_han", "⏰ Đến hạn", "Tác nghiệp", "pgd", order=5))
register(TabDef("tab_du_phong_dong_tien_pgd", "📈 Dự phóng Dòng tiền", "Tác nghiệp", "pgd", order=6))
register(TabDef("tab_heatmap_dao_han_pgd", "🔥 Heatmap Đáo hạn", "Tác nghiệp", "pgd", order=7))
register(TabDef("tab_histogram_du_no_pgd", "📊 Histogram Dư nợ", "Tác nghiệp", "pgd", order=8))
register(TabDef("tab_donut_co_cau_pgd", "🍩 Cơ cấu CT", "Tác nghiệp", "pgd", order=9))
register(TabDef("tab_so_sanh_ky", "📊 So sánh kỳ", "Tác nghiệp", "pgd", extra_kwargs={"pgd_mode": True}, order=10))
register(TabDef("tab_phan_loai_kh", "🏷️ Phân loại KH", "Tác nghiệp", "pgd", order=11))

# ── Báo cáo ──────────────────────────────────────────────────────────────────
register(TabDef("tab_baocao", "📊 Báo cáo tín dụng", "Báo cáo", "pgd", order=1))
register(TabDef("tab_bao_cao_dinh_ky", "📅 Báo cáo định kỳ", "Báo cáo", "pgd", order=2))
register(TabDef("tab_candoi", "📡 Điện báo", "Báo cáo", "pgd", extra_kwargs={"pgd_mode": True}, order=3))
register(TabDef("tab_bao_cao_giao_ban_pgd", "📝 Báo cáo Giao ban", "Báo cáo", "pgd", order=4))
register(TabDef("tab_doc_hub", "📄 Trung tâm mẫu biểu", "Báo cáo", "pgd", order=5))
register(TabDef("tab_bien_ban_giao_ban", "📋 Biên bản giao ban", "Báo cáo", "pgd", order=6))
register(TabDef("tab_thong_bao_ket_luan", "📢 Thông báo kết luận", "Báo cáo", "pgd", order=7))
register(TabDef("tab_theo_doi_nhap", "📋 Theo dõi nhập liệu", "Báo cáo", "pgd", order=8))
register(TabDef("tab_tien_do_nop", "📥 Tiến độ nộp BC", "Báo cáo", "pgd", order=9))
register(TabDef("tab_checklist_bc", "✅ Checklist BC", "Báo cáo", "pgd", order=10))

# ── Kế hoạch ─────────────────────────────────────────────────────────────────
register(TabDef("tab_khtd_pgd", "🎯 KHTD", "Kế hoạch", "pgd", order=1))
register(TabDef("tab_kehoach", "⚖️ Kế hoạch/Cân đối", "Kế hoạch", "pgd", extra_kwargs={"pgd_mode": True}, order=2))
register(TabDef("tab_khtd_giao_dc", "📋 Giao & ĐC KHTD", "Kế hoạch", "pgd", order=3))
register(TabDef("tab_khtd_mau07", "📋 Mẫu 07 Giao KH", "Kế hoạch", "pgd", order=4))
register(TabDef("tab_nq11", "📋 NQ11", "Kế hoạch", "pgd", order=5))
register(TabDef("tab_gqvl_pgd", "📊 Dashboard GQVL", "Kế hoạch", "pgd", order=6))
register(TabDef("tab_khtd_xuat", "📊 Xuất báo cáo KHTD", "Kế hoạch", "pgd", render_fn="render_xuat_baocao", order=7))

# ── Kiểm soát ────────────────────────────────────────────────────────────────
register(TabDef("tab_canh_bao_nqh", "🚨 Cảnh báo Tín dụng", "Kiểm soát", "pgd", order=1))
register(TabDef("tab_don_doc_khd", "🔔 Đôn đốc KHĐ", "Kiểm soát", "pgd", order=2))
register(TabDef("tab_canh_bao_som", "⚡ Nợ đến hạn có nguy cơ", "Kiểm soát", "pgd", order=3))
register(TabDef("tab_canh_bao_som_pgd", "🚨 Cảnh báo sớm (Full)", "Kiểm soát", "pgd", order=4))
register(TabDef("tab_kiem_soat_noi_bo_pgd", "✅ Checklist Nội bộ PGD", "Kiểm soát", "pgd", order=5))
register(TabDef("tab_kiem_soat_du_lieu_pgd", "🔍 Kiểm soát Dữ liệu", "Kiểm soát", "pgd", order=6))
register(TabDef("tab_cbtd", "👔 CBTD & Địa bàn", "Kiểm soát", "pgd", order=7))
register(TabDef("tab_xu_ly_rui_ro", "💳 Xử lý Rủi ro", "Kiểm soát", "pgd", order=8))
register(TabDef("tab_phan_tich_nqh_pgd", "📈 Phân tích NQH", "Kiểm soát", "pgd", order=9))
register(TabDef("tab_diem_gd_pgd", "📍 Điểm Giao Dịch", "Kiểm soát", "pgd", order=10))
register(TabDef("tab_cdtotkvv_pgd", "🏘️ Tổ TK&VV", "Kiểm soát", "pgd", order=11))
register(TabDef("tab_ban_dai_dien", "🏛️ Ban Đại Diện", "Kiểm soát", "pgd", extra_kwargs={"cap": "xa"}, order=12))
register(TabDef("tab_uy_thac", "🤝 Ủy thác", "Kiểm soát", "pgd", order=13))
register(TabDef("tab_no_khoanh", "📊 Tổng quan Nợ Khoanh", "Kiểm soát", "pgd", extra_kwargs={"nhom": "tongquan"}, order=14))
register(TabDef("tab_no_khoanh", "🔒 Quản lý Nợ Khoanh CV 368", "Kiểm soát", "pgd", extra_kwargs={"nhom": "cv368"}, order=15))

# ── Công cụ ──────────────────────────────────────────────────────────────────
register(TabDef("tab_nhiem_vu", "✅ Nhiệm vụ", "Công cụ", "pgd", order=1))
register(TabDef("tab_upload_pgd", "📤 Upload Dữ liệu", "Công cụ", "pgd", order=2))
register(TabDef("tab_upload_pgd", "📤 Upload HSTD", "Công cụ", "pgd", order=3))
register(TabDef("tab_hhi", "🏦 Nguồn vốn ĐP", "Công cụ", "pgd", order=4))
register(TabDef("tab_ndt_dp", "🏦 Mã NĐT địa phương", "Công cụ", "pgd", order=5))
register(TabDef("tab_audit_log", "📋 Nhật ký hoạt động", "Công cụ", "pgd", order=6))
register(TabDef("tab_xu_huong_pgd", "📈 Phân tích xu hướng", "Công cụ", "pgd", order=7))
register(TabDef("tab_trang_thai_nguon", "🔍 Trạng thái hệ thống", "Công cụ", "pgd", order=8))
# ⚠️ "📖 Hướng dẫn" là hàm nội bộ (render_huong_dan từ pdf_service) — giữ trong workspace


# ═══════════════════════════════════════════════════════════════════════════════
# Workspace Exec — ws_executive (Ban Giám đốc)
# ═══════════════════════════════════════════════════════════════════════════════
# Phần lớn mục trong ws_executive là hàm nội bộ (_render_hom_nay, _render_suc_khoe_tong_quan,
# _render_tien_do_va_kh, _render_so_sanh_xep_hang_pgd, _render_nqh_xa_canh_bao,
# _render_migration_section, _render_pdf_section, render_huong_dan) — giữ trong workspace.
# Chỉ đăng ký các tab module-based:

# ── Cảnh báo rủi ro ──────────────────────────────────────────────────────────
register(TabDef("tab_qlnk_dashboard", "📊 Tổng hợp nợ khoanh", "Cảnh báo rủi ro", "exec", order=3))

# ── Kiểm soát ────────────────────────────────────────────────────────────────
register(TabDef("tab_kiem_soat", "Kiểm soát CN", "Kiểm soát", "exec", render_fn="render_tab", order=1))
register(TabDef("tab_xu_ly_rui_ro", "Xử lý Rủi ro", "Kiểm soát", "exec", order=2))
register(TabDef("tab_khtd_giao_dc", "Giao & Điều chỉnh KHTD", "Kiểm soát", "exec", order=3))

# ── Báo cáo ──────────────────────────────────────────────────────────────────
register(TabDef("tab_so_sanh_ky", "So sánh kỳ", "Báo cáo", "exec", order=1))
register(TabDef("tab_bao_cao_dinh_ky", "📅 Báo cáo định kỳ", "Báo cáo", "exec", order=2))
