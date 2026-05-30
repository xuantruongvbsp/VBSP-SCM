"""CRUD template cấu hình Google Sheet → kv_store."""
from __future__ import annotations

import uuid
from typing import Any

import db
from logger import get_logger

logger = get_logger(__name__)

KV_TEMPLATE_PREFIX = "gsheet_template_"


def _gen_id() -> str:
    return uuid.uuid4().hex[:12]


def doc_ds_template() -> list[dict]:
    """Danh sách template còn hiệu lực, mới nhất lên đầu."""
    raw = db.doc_kv_prefix(KV_TEMPLATE_PREFIX)
    result = [
        v for v in raw.values()
        if v and isinstance(v, dict) and not v.get("deleted")
    ]
    result.sort(key=lambda t: t.get("ngay_tao", ""), reverse=True)
    return result


def doc_template(template_id: str) -> dict | None:
    return db.doc_kv(f"{KV_TEMPLATE_PREFIX}{template_id}")


def luu_template(template: dict, username: str) -> str:
    """Lưu template. Tạo id mới nếu chưa có. Trả về template_id."""
    tid = template.get("id") or _gen_id()
    template["id"] = tid
    db.ghi_kv(
        f"{KV_TEMPLATE_PREFIX}{tid}",
        template,
        username,
        note=f"template: {template.get('ten', tid)}",
    )
    db.ghi_audit(username, "luu_gsheet_template",
                 f"id={tid}, ten={template.get('ten', '')}")
    logger.info("luu_template: id=%s, user=%s", tid, username)
    return tid


def xoa_template(template_id: str, username: str) -> None:
    """Soft-delete: đánh dấu deleted=True thay vì xóa hẳn."""
    existing = doc_template(template_id)
    if existing and isinstance(existing, dict):
        existing["deleted"] = True
        db.ghi_kv(
            f"{KV_TEMPLATE_PREFIX}{template_id}",
            existing,
            username,
            note="deleted",
        )
    db.ghi_audit(username, "xoa_gsheet_template", f"id={template_id}")
    logger.info("xoa_template: id=%s, user=%s", template_id, username)


def ten_da_ton_tai(ten: str, exclude_id: str | None = None) -> bool:
    """Kiểm tra tên template đã tồn tại (case-insensitive). Bỏ qua exclude_id khi edit."""
    ten_norm = ten.strip().lower()
    for t in doc_ds_template():
        if exclude_id and t.get("id") == exclude_id:
            continue
        if t.get("ten", "").strip().lower() == ten_norm:
            return True
    return False


def clone_template(template_id: str, new_ten: str, username: str) -> str | None:
    """Clone template. Trả về id mới hoặc None nếu template nguồn không tồn tại."""
    import copy
    from datetime import date as _d
    src = doc_template(template_id)
    if not src or not isinstance(src, dict) or src.get("deleted"):
        return None
    new_tpl = copy.deepcopy(src)
    new_tpl.pop("id", None)
    new_tpl["ten"]       = new_ten
    new_tpl["mo_ta"]     = f"Clone từ: {src.get('ten', '')}"
    new_tpl["nguoi_tao"] = username
    new_tpl["ngay_tao"]  = _d.today().isoformat()
    new_tpl.pop("deleted", None)
    return luu_template(new_tpl, username)


def goi_y_template(tab_name: str, templates: list[dict]) -> str | None:
    """
    Gợi ý template phù hợp nhất với tên tab GSheet.
    So sánh phần đầu tên template (trước dấu -) với tên tab.
    Trả về template_id hoặc None.
    """
    if not tab_name or not templates:
        return None
    tab_upper = tab_name.upper()
    best_id, best_score = None, 0
    for t in templates:
        # Lấy keyword đầu (VD: "NQH - Phân tích..." → "NQH")
        keyword = t.get("ten", "").upper().split(" - ")[0].split("-")[0].strip()
        if keyword and keyword in tab_upper and len(keyword) > best_score:
            best_score, best_id = len(keyword), t.get("id")
    return best_id


def ap_dung_template(
    template_id: str,
    sheet_id: str,
    sheet_tab: str,
    ten_hien_thi: str,
) -> dict | None:
    """
    Tạo sheet config từ template + thông tin sheet cụ thể.
    Trả về dict config sẵn dùng cho ds_sheet, hoặc None nếu template không hợp lệ.
    """
    tpl = doc_template(template_id)
    if not tpl or not isinstance(tpl, dict) or tpl.get("deleted"):
        return None
    return {
        "ten_hien_thi":    ten_hien_thi,
        "sheet_id":        sheet_id,
        "sheet_tab":       sheet_tab,
        "header_row":      tpl.get("header_row",       10),
        "stt_col":         tpl.get("stt_col",           1),
        "name_col":        tpl.get("name_col",          2),
        "pgd_col":         tpl.get("pgd_col",           1),
        "loai_cau_truc":   tpl.get("loai_cau_truc", "phan_cap_stt"),
        "ds_chuong_trinh": list(tpl.get("ds_chuong_trinh", [])),
        "template_id":     template_id,
    }
