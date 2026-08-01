"""Tab Cân đối — Điện báo Chi nhánh.

Redesign 2026-06-04:
- Upload lên đầu (state-based): chưa có file → form nổi bật; đã có file → thanh trạng thái + quản lý tệp inline
- Sheet selector: chọn sheet HIỆN TẠI và sheet SO SÁNH từ cùng 1 file (M↔Y, DB↔KH_GIAO_DAU_NAM…)
- Gọi doc_dienbao() với sheet_name được chọn → KPI/bảng luôn đọc đúng sheet
- 3 sub-tabs: Tổng quan, Theo chương trình, Biểu đồ

Fix 2026-07-30:
- _to_ty() chia đúng hệ số theo don_vi_trieu (triệu→/1000, nghìn→/1_000_000)
- doc_dienbao_matrix có cache
- Đổi tên tab: "Điện báo Cân đối" (bỏ "KH vs TH" đã xóa)

Mốc so sánh 2026-07-30:
- Thêm selector "Mốc so sánh": vs 31/12 năm trước, vs Kế hoạch giao, Tùy chọn khác
- Auto-map sheet so sánh theo mốc (31/12 → Y, KH → KH_GIAO_DAU_NAM)
- _KH_NAME_MAP: ánh xạ tên chỉ tiêu giữa sheet M/DB và sheet KH giao
- KH mode: hiển thị % Hoàn thành KH thay vì delta tăng/giảm
- Badge tỷ lệ khớp dữ liệu so sánh (xanh/vàng/đỏ)
- Cảnh báo khi không tìm thấy chỉ tiêu KH

Redesign 2026-08-01:
- Loại bỏ toàn bộ expander; dùng container cho dữ liệu cần quan sát trực tiếp, popover chỉ còn cho hướng dẫn
"""

from __future__ import annotations

from logger import get_logger
logger = get_logger(__name__)

import os
import ntpath
import socket
import html
import re
from io import BytesIO
from datetime import datetime, date, timedelta
from numbers import Number
from typing import TYPE_CHECKING, Any

import streamlit as st
import pandas as pd

from config import (
    DB_HT_CACHE,
    DB_PREV_CACHE,
    DB_PREV_MONTH_CACHE,
    FILE_PATH_DB,
    FILE_PATH_DB_PREV,
)
from utils import (
    fmt_ty,
    fmt_cl,
    xuat_excel,
    ten_file_xuat,
    hien_thi_dataframe_phan_trang,
)
from state_manager import SCMStateManager
import db
from data import ts_file, doc_dienbao, db_lookup
from data.pgd import duong_dan_pgd, pgd_slug
from services import luu_dienbao


if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator


# ── Auto-map sheet hiện tại → gợi ý sheet so sánh ──────────────────────────
_AUTO_MAP_PREV: dict[str, str] = {
    "M": "Y",
    "Y": "M",
    "DB": "KH_GIAO_DAU_NAM",
    "KH_GIAO_DAU_NAM": "DB",
    "DB1": "Y",
    "DIEU_CHINH_KHTD": "KH_GIAO_DAU_NAM",
}

# ── Ánh xạ tên chỉ tiêu Điện báo → tên trong sheet KH giao ─────────────
# Dùng khi so sánh mốc "vs Kế hoạch giao" (sheet KH có tên chỉ tiêu khác M/DB)
_KH_NAME_MAP: dict[str, list[str]] = {
    "Tổng dư nợ":                   ["Tổng dư nợ", "Tổng kế hoạch", "Kế hoạch tổng", "KH tổng"],
    "Nguồn vốn cân đối từ TW (KHA)": ["Nguồn TW", "Vốn TW", "Kế hoạch TW", "Vốn cân đối TW"],
    "Tổng huy động vốn":            ["Huy động vốn", "Tổng huy động", "HĐV", "Huy động"],
    "Tiền gửi tiết kiệm qua Tổ TK&VV": [
        "Tiền gửi tiết kiệm qua Tổ TK&VV",
        "Tiền gửi tiết kiệm qua Tổ TKVV",
        "Tiết kiệm qua Tổ TK&VV",
        "Tiết kiệm qua Tổ TKVV",
    ],
    "Nguồn vốn nhận UTĐT tại ĐP":    ["UTĐT", "Ủy thác ĐP", "Vốn UTĐT", "Nhận UTĐT"],
    "Dư nợ Kế hoạch A":             ["KHA", "Kế hoạch A", "Dư nợ KHA", "KH A"],
    "Dư nợ Kế hoạch B":             ["KHB", "Kế hoạch B", "Dư nợ KHB", "KH B"],
    "Dư nợ Quá hạn KHA":            ["NQH KHA", "Quá hạn KHA"],
    "Dư nợ Quá hạn KHB":            ["NQH KHB", "Quá hạn KHB"],
}

# ── Danh sách chương trình cho sub-tab Theo CT ──────────────────────────────
_CHUONG_TRINH_CANDOI: list[tuple[str, str | None]] = [
    ("── KẾ HOẠCH A ──",          None),
    ("Hộ nghèo KHA",               "Dư nợ hộ nghèo KHA"),
    ("Hộ cận nghèo KHA",           "Dư nợ hộ cận nghèo KHA"),
    ("Hộ mới thoát nghèo KHA",     "Dư nợ hộ mới thoát nghèo KHA"),
    ("HSSV có HCKK",               "Dư nợ HSSV"),
    ("Giải quyết việc làm KHA",    "Dư nợ GQVL KHA"),
    ("NSVSMT nông thôn",           "Dư nợ NSVSMT NT"),
    ("SXKD vùng KK",               "Dư nợ SXKD VKK"),
    ("TN vùng KK",                 "Dư nợ TN VKK"),
    ("Nhà ở hộ nghèo",             "Dư nợ hộ nghèo về nhà ở"),
    ("Nhà ở giai đoạn 2 KHA",      "Dư nợ nhà ở gđ 2 KHA"),
    ("Cho vay XKLĐ",               "Dư nợ XKLĐ"),
    ("KFW",                        "Dư nợ KFW"),
    ("DTTS ĐBKK KHA",              "Dư nợ DTTS ĐBKK KHA"),
    ("DTTS 2085 KHA",              "Dư nợ DTTS 2085 KHA"),
    ("NOXH 100% KHA",              "Dư nợ NOXH100 KHA"),
    ("Khác KHA",                   "Dư nợ Khác KHA"),
    ("Nợ quá hạn KHA",             "Dư nợ Quá hạn KHA"),
    ("Nợ khoanh KHA",              "Dư nợ Khoanh KHA"),
    ("── KẾ HOẠCH B ──",          None),
    ("Hộ nghèo KHB",               "Dư nợ hộ nghèo KHB"),
    ("Hộ cận nghèo KHB",           "Dư nợ hộ cận nghèo KHB"),
    ("Hộ mới thoát nghèo KHB",     "Dư nợ hộ mới thoát nghèo KHB"),
    ("Giải quyết việc làm KHB",    "Dư nợ GQVL KHB"),
    ("NSVSMT NT KHB",              "Dư nợ NSVSMT NT KHB"),
    ("DTTS ĐBKK KHB",              "Dư nợ DTTS ĐBKK KHB"),
    ("DTTS 2085 KHB",              "Dư nợ DTTS 2085 KHB"),
    ("NOXH 100% KHB",              "Dư nợ NOXH100 KHB"),
    ("Khác KHB",                   "Dư nợ Khác KHB"),
    ("Nợ quá hạn KHB",             "Dư nợ Quá hạn KHB"),
    ("Nợ khoanh KHB",              "Dư nợ Khoanh KHB"),
]


def _lay_nqh_con(rows: list[dict], ten_cha: str) -> float:
    """Tìm giá trị dòng NQH con ngay sau ten_cha."""
    for r in rows:
        if r["la_nqh_con"] and r["cha"] == ten_cha:
            return r["val"]
    return 0.0


def _to_vnd(x: float, he_so: int) -> float:
    if pd.isna(x):
        return 0.0
    return float(x) * he_so


def _row_vnd(row: dict, fallback_he_so: int) -> float:
    return _to_vnd(row.get("val", 0), int(row.get("he_so_vnd") or fallback_he_so))


def _lookup_vnd(rows: list[dict] | None, ten_search: str, he_so: int) -> float:
    return _to_vnd(db_lookup(rows, ten_search), he_so) if rows else 0.0


def _lookup_optional_vnd(rows: list[dict] | None, ten_search: str, he_so: int) -> float | None:
    """Tra chỉ tiêu Điện báo thường, trả None khi không tìm thấy."""
    if not rows:
        return None
    ten_l = ten_search.strip().lower()
    for row in rows:
        if not row.get("la_nqh_con") and str(row.get("ten", "")).strip() == ten_search.strip():
            return _row_vnd(row, he_so)
    for row in rows:
        if not row.get("la_nqh_con") and ten_l in str(row.get("ten", "")).lower():
            return _row_vnd(row, he_so)
    return None


def _nqh_con_vnd(rows: list[dict] | None, ten_cha: str, he_so: int) -> float:
    return _to_vnd(_lay_nqh_con(rows, ten_cha), he_so) if rows else 0.0


def _lookup_kh_vnd(rows: list[dict] | None, ten_goc: str, he_so: int) -> float:
    """Tra trong sheet KH giao với ánh xạ tên chỉ tiêu."""
    if not rows:
        return 0.0
    candidates = _KH_NAME_MAP.get(ten_goc, [ten_goc])
    for cand in candidates:
        val = db_lookup(rows, cand)
        if val > 0:
            return _to_vnd(val, he_so)
    return _to_vnd(db_lookup(rows, ten_goc), he_so)


def _normalize_indicator_name(value: object) -> str:
    """Chuẩn hóa tên chỉ tiêu để TK&VV và TKVV được xem là tương đương."""
    return "".join(ch for ch in str(value).casefold() if ch.isalnum())


def _lookup_kh_optional_vnd(
    rows: list[dict] | None,
    ten_goc: str,
    he_so: int,
) -> float | None:
    """Tra chỉ tiêu KH và phân biệt rõ không tìm thấy với giá trị thực bằng 0."""
    if not rows:
        return None

    candidates = _KH_NAME_MAP.get(ten_goc, [ten_goc])
    candidate_names = {
        normalized
        for candidate in candidates
        if (normalized := _normalize_indicator_name(candidate))
    }
    main_rows = [row for row in rows if not row.get("la_nqh_con")]

    for exact_match in (True, False):
        for row in main_rows:
            row_name = _normalize_indicator_name(row.get("ten", ""))
            matched = (
                row_name in candidate_names
                if exact_match
                else any(candidate in row_name for candidate in candidate_names)
            )
            if matched:
                return _row_vnd(row, he_so)
    return None


def _lookup_prev_vnd(
    rows_prev: list[dict] | None,
    ten_search: str,
    he_so_prev: int,
    kh_mode: bool,
) -> float:
    if not rows_prev:
        return 0.0
    return (
        _lookup_kh_vnd(rows_prev, ten_search, he_so_prev)
        if kh_mode
        else _lookup_vnd(rows_prev, ten_search, he_so_prev)
    )


def _lookup_khoanh_vnd(
    rows: list[dict] | None,
    he_so: int,
    *,
    kh_mode: bool = False,
) -> float:
    """Cộng dư nợ khoanh KHA và KHB theo đúng chế độ so sánh."""
    lookup = _lookup_kh_vnd if kh_mode else _lookup_vnd
    return sum(
        lookup(rows, indicator, he_so)
        for indicator in ("Dư nợ Khoanh KHA", "Dư nợ Khoanh KHB")
    )


def _match_prev_row_vnd(
    row_ht: dict,
    rows_prev: list[dict] | None,
    he_so_prev: int,
    kh_mode: bool,
) -> float:
    if not rows_prev:
        return 0.0
    val_pv = 0.0
    matched_exact = False
    for row_pv in rows_prev:
        same_type = row_pv["la_nqh_con"] == row_ht["la_nqh_con"]
        same_parent = row_pv.get("cha") == row_ht.get("cha")
        same_name = row_pv["ten"] == row_ht["ten"]
        same_main_name = (
            not row_ht["la_nqh_con"]
            and not row_pv["la_nqh_con"]
            and same_name
        )
        if same_type and same_name and (same_parent or same_main_name):
            val_pv = _row_vnd(row_pv, he_so_prev)
            matched_exact = True
            break
    if kh_mode and (not matched_exact or val_pv == 0):
        val_kh = _lookup_kh_vnd(rows_prev, row_ht["ten"], he_so_prev)
        if val_kh or not matched_exact:
            val_pv = val_kh
    return val_pv


def _should_persist_moc_choice(
    saved_moc: str | None,
    selected_moc: str,
    *,
    changed_by_user: bool,
) -> bool:
    """Chỉ lưu khi radio thực sự thay đổi do thao tác của user."""
    return changed_by_user and selected_moc != saved_moc


def _normalize_ky_label(value: object) -> str:
    """Chuẩn hóa nhãn kỳ số liệu trước khi so sánh và lưu kv_store."""
    return "" if value is None else str(value).strip()


def _parse_ddmmyyyy(s: str) -> date | None:
    """Parse 'DD/MM/YYYY' → date, trả về None nếu không hợp lệ."""
    s = (s or "").strip()
    if not s:
        return None
    try:
        return datetime.strptime(s, "%d/%m/%Y").date()
    except ValueError:
        return None


def _last_day_previous_month(today: date | None = None) -> date:
    today = today or date.today()
    return today.replace(day=1) - timedelta(days=1)


def _should_persist_ky_label(saved_label: object, input_label: object) -> bool:
    """Lưu cả trường hợp user xóa nhãn để quay về giá trị fallback."""
    return _normalize_ky_label(input_label) != _normalize_ky_label(saved_label)


def _persist_ky_label_if_changed(
    kv_key: str,
    saved_label: object,
    input_label: object,
    username: str,
    audit_name: str,
) -> bool:
    """Lưu nhãn kỳ khi thay đổi và audit ngay sau lần ghi kv_store."""
    value = _normalize_ky_label(input_label)
    if not _should_persist_ky_label(saved_label, value):
        return False

    audit_message = f"Đặt {audit_name}: {value}" if value else f"Xóa {audit_name}"
    db.ghi_kv(kv_key, value, username)
    db.ghi_audit(username, "dienbao_ky", audit_message)
    return True


_FILE_PREV_SENTINEL = "__FILE_PREV__"


def _custom_sheet_options(
    sheet_options: list[str],
    current_sheet: str | None,
) -> list[str]:
    """Các sheet có thể dùng làm mốc custom, không gồm sheet hiện tại."""
    return [sheet for sheet in sheet_options if sheet != current_sheet]


def _first_comparison_sheet(
    sheet_options: list[str],
    current_sheet: str | None,
    preferred_sheets: list[str],
) -> str | None:
    """Chọn sheet so sánh ưu tiên nhưng không được trùng sheet hiện tại."""
    return next(
        (
            sheet
            for sheet in preferred_sheets
            if sheet in sheet_options and sheet != current_sheet
        ),
        None,
    )


def _custom_comparison_options(
    sheet_options: list[str],
    current_sheet: str | None,
    *,
    has_previous_file: bool,
) -> list[str]:
    """Nguồn so sánh custom: sheet khác và, nếu có, file kỳ trước."""
    options = _custom_sheet_options(sheet_options, current_sheet)
    if has_previous_file:
        options.append(_FILE_PREV_SENTINEL)
    return options


def _fmt_nguon_ss(
    s: str,
    sheet_info_m: dict[str, dict],
    path_prev: str | None,
) -> str:
    """Label cho selectbox nguồn so sánh (sheet hoặc file kỳ trước)."""
    if s == _FILE_PREV_SENTINEL:
        # ntpath nhận đúng cả path Windows khi test chạy trên CI Linux.
        ten = ntpath.basename(path_prev) if path_prev else "—"
        return f"📁 File kỳ trước ({ten})"
    info = sheet_info_m.get(s, {})
    label = f"{s} · {info.get('rows', '?')} dòng"
    if info.get("ngay"):
        label += f" · {info['ngay'][:22]}"
    return label


def _has_previous_file(path_prev: str | None, path_ht: str | None) -> bool:
    """Chỉ nhận fallback khi đó là một file khác file hiện tại."""
    if not path_prev or not os.path.isfile(path_prev):
        return False
    if not path_ht:
        return True
    try:
        return not os.path.samefile(path_prev, path_ht)
    except OSError:
        # Fallback cho filesystem không hỗ trợ samefile hoặc path hiện tại
        # vừa biến mất giữa hai lần kiểm tra.
        prev_norm = os.path.normcase(os.path.abspath(path_prev))
        ht_norm = os.path.normcase(os.path.abspath(path_ht))
        return prev_norm != ht_norm


def _db_file_chip(store_path: str, empty_text: str = "Chưa có file — vui lòng upload") -> str:
    """HTML chip hiển thị trạng thái file Điện báo (đã lưu / chưa có)."""
    if store_path and os.path.exists(store_path):
        try:
            _mt = datetime.fromtimestamp(os.path.getmtime(store_path)).strftime("%d/%m/%Y %H:%M")
            _kb = os.path.getsize(store_path) // 1024
        except Exception:
            _mt, _kb = "—", "—"
        return (
            '<div class="db-up-file"><span class="dot"></span>'
            f'<span>{os.path.basename(store_path)}</span>'
            f'<span class="meta">{_kb} KB · {_mt}</span></div>'
        )
    return f'<div class="db-up-file empty"><span class="dot"></span>{empty_text}</div>'


# ── KPI cards Cân đối (CSS .cdk — utils_theme.py section 21) ─────────────────
def _fmt_so_vn(x: float, d: int = 1) -> str:
    """Số kiểu VN: 13.694,01 (chấm=phần nghìn, phẩy=thập phân)."""
    try:
        return f"{float(x):,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "—"


def _stat_ty(vnd: float, caption: str) -> dict:
    """Stat giá trị tỷ đồng từ VND."""
    return {"v": _fmt_so_vn((vnd or 0) / 1_000_000_000, 1), "c": caption}


def _stat_cl(ht_vnd: float, pv_vnd: float) -> dict:
    """Stat chênh lệch tuyệt đối (tỷ) giữa kỳ hiện tại và kỳ trước."""
    cl = (ht_vnd or 0) - (pv_vnd or 0)
    sign = "+" if cl >= 0 else "-"
    return {
        "v": f"{sign}{_fmt_so_vn(abs(cl) / 1_000_000_000, 1)}",
        "c": "chênh lệch",
        "cls": "pos" if cl >= 0 else "neg",
    }


def _stat_pct(x: float, tong: float, caption: str) -> dict:
    """Stat tỷ lệ % trên tổng."""
    v = (x / tong * 100) if tong else 0
    return {"v": _fmt_so_vn(v, 1) + "%", "c": caption}


def _kpi_card_html(
    label: str,
    icon: str,
    value: float,
    precision: int = 1,
    delta: float | None = None,
    delta_label: str = "",
    delta_color: str = "normal",
    stats: list[dict] | None = None,
    tone: str = "accent",
    idx: int = 0,
) -> str:
    """HTML cho 1 card KPI Cân đối (class .cdk)."""
    val_str = _fmt_so_vn(value, precision)

    pill = ""
    if delta is not None:
        try:
            d_val = float(delta)
        except Exception:
            d_val = 0.0
        if d_val > 0:
            arrow, sign = "▲", "+"
            cls = "down" if delta_color == "inverse" else "up"
        elif d_val < 0:
            arrow, sign = "▼", ""
            cls = "up" if delta_color == "inverse" else "down"
        else:
            arrow, sign = "◆", ""
            cls = "flat"
        title = f' title="{delta_label}"' if delta_label else ""
        pill = (
            f'<span class="cdk-delta {cls}"{title}>'
            f'<span class="arr">{arrow}</span>{sign}{_fmt_so_vn(abs(d_val), 1)}%</span>'
        )

    stats_html = ""
    if stats:
        cells = []
        for s in stats:
            bcls = f' class="{s["cls"]}"' if s.get("cls") else ""
            cells.append(
                f'<div class="cdk-stat"><span>{s.get("c", "")}</span>'
                f'<b{bcls}>{s.get("v", "—")}</b></div>'
            )
        stats_html = f'<div class="cdk-stats">{"".join(cells)}</div>'

    tone_cls = "" if tone == "accent" else f" cdk--{tone}"
    return (
        f'<div class="cdk{tone_cls}" style="--i:{idx}">'
        f'<div class="cdk-top">'
        f'<span class="cdk-ico">{icon}</span>'
        f'<span class="cdk-label">{label}</span>'
        f'{pill}</div>'
        f'<div class="cdk-val">{val_str}<span class="cdk-unit">tỷ đồng</span></div>'
        f'{stats_html}</div>'
    )


def _render_kpi_grid(cards: list[dict], num_columns: int = 4) -> None:
    """Render lưới KPI cards Cân đối. Mỗi dict = kwargs cho _kpi_card_html."""
    cols = st.columns(num_columns)
    for i, c in enumerate(cards):
        with cols[i % num_columns]:
            st.html(_kpi_card_html(idx=i, **c))


def _build_print_html(
    df1: pd.DataFrame,
    df2: pd.DataFrame,
    label_pv: str,
    label_ht: str,
    pgd_user: str | None,
    pgd_mode: bool,
) -> str:
    """Tạo HTML standalone có 2 bảng + CSS print + nút In tự động."""
    _scope = pgd_user if pgd_mode else "Toàn Chi nhánh"
    _title = f"So sánh Cân đối — {_scope}"
    _sub = f"{label_pv} vs {label_ht} · Xuất ngày {datetime.today().strftime('%d/%m/%Y %H:%M')}"

    def _esc(value: object) -> str:
        return html.escape(str(value), quote=True)

    def _df_to_html(df: pd.DataFrame, caption: str) -> str:
        """DataFrame → HTML table với format số."""
        hdr = "".join(f"<th>{_esc(c)}</th>" for c in df.columns)
        rows = []
        for _, r in df.iterrows():
            cells = []
            for c in df.columns:
                v = r[c]
                if pd.isna(v):
                    cells.append('<td class="num">—</td>')
                elif isinstance(v, Number) and not isinstance(v, bool):
                    if "Tỷ lệ" in c:
                        cells.append(f'<td class="num">{float(v):+.1f}%</td>')
                    else:
                        cells.append(f'<td class="num">{float(v):,.0f}</td>')
                else:
                    cells.append(f"<td>{_esc(v)}</td>")
            rows.append(f"<tr>{''.join(cells)}</tr>")
        return (
            f'<h3>{_esc(caption)}</h3>'
            f'<table><thead><tr>{hdr}</tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table>'
        )

    t1 = _df_to_html(df1, "Tổng hợp chỉ tiêu")
    t2 = _df_to_html(df2, "Theo chương trình") if not df2.empty else ""

    return f"""<!DOCTYPE html>
<html lang="vi"><head><meta charset="utf-8">
<title>{_esc(_title)}</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family: "Segoe UI", Arial, sans-serif; padding: 24px; color: #1a1a1a; background: #fff; }}
  h1 {{ font-size: 18px; text-align: center; margin-bottom: 4px; }}
  .sub {{ text-align: center; font-size: 13px; color: #666; margin-bottom: 18px; }}
  h3 {{ font-size: 14px; margin: 18px 0 6px; border-bottom: 2px solid #2E7D32; padding-bottom: 4px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 12px; margin-bottom: 16px; }}
  th, td {{ border: 1px solid #ccc; padding: 5px 8px; text-align: left; }}
  th {{ background: #2E7D32; color: #fff; font-weight: 600; }}
  td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  tr:nth-child(even) {{ background: #f5f5f5; }}
  .no-print {{ text-align: center; margin: 16px 0; }}
  .no-print button {{
    padding: 10px 28px; font-size: 14px; font-weight: 600;
    background: #2E7D32; color: #fff; border: none; border-radius: 6px; cursor: pointer;
  }}
  .no-print button:hover {{ background: #1B5E20; }}
  @media print {{
    .no-print {{ display: none !important; }}
    body {{ padding: 10px; }}
    th {{ background: #2E7D32 !important; color: #fff !important; -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
    tr:nth-child(even) {{ background: #f5f5f5 !important; -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
  }}
</style>
</head><body>
<h1>{_esc(_title)}</h1>
<p class="sub">{_esc(_sub)}</p>
<div class="no-print"><button onclick="window.print()">🖨️ In trang này</button></div>
{t1}
{t2}
<script>window.onload=function(){{/* auto-focus for Ctrl+P */}}</script>
</body></html>"""


def _build_export_frames(
    rows_ht: list[dict],
    rows_prev: list[dict] | None,
    he_so_ht: int,
    he_so_prev: int,
    kh_mode: bool,
    label_prev: str,
    label_ht: str,
    rows_prev_month: list[dict] | None = None,
    he_so_prev_month: int = 1_000_000,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Chuẩn bị hai bảng xuất độc lập với sub-tab đang mở."""
    rows_ex1: list[dict[str, Any]] = []
    rows_ex2: list[dict[str, Any]] = []
    skip_indicators = ("tiền gửi của tổ chức", "tiền gửi tiết kiệm dân cư")

    def _to_trieu(value_vnd: float) -> float:
        return value_vnd / 1_000_000

    huy_dong_ht = _lookup_vnd(rows_ht, "Tổng huy động vốn", he_so_ht)
    tiet_kiem_tkvv_ht = _lookup_vnd(rows_ht, "Tiền gửi tiết kiệm qua Tổ TK&VV", he_so_ht)
    tien_gui_tt_ht = huy_dong_ht - tiet_kiem_tkvv_ht

    tien_gui_tt_prev: float | None = 0.0
    if rows_prev:
        if kh_mode:
            huy_dong_prev = _lookup_kh_optional_vnd(rows_prev, "Tổng huy động vốn", he_so_prev)
            tiet_kiem_tkvv_prev = _lookup_kh_optional_vnd(
                rows_prev, "Tiền gửi tiết kiệm qua Tổ TK&VV", he_so_prev,
            )
            tien_gui_tt_prev = (
                huy_dong_prev - tiet_kiem_tkvv_prev
                if huy_dong_prev is not None and tiet_kiem_tkvv_prev is not None
                else None
            )
        else:
            tien_gui_tt_prev = (
                _lookup_vnd(rows_prev, "Tổng huy động vốn", he_so_prev)
                - _lookup_vnd(rows_prev, "Tiền gửi tiết kiệm qua Tổ TK&VV", he_so_prev)
            )

    tien_gui_tt_pm: float | None = None
    if rows_prev_month:
        huy_dong_pm = _lookup_optional_vnd(rows_prev_month, "Tổng huy động vốn", he_so_prev_month)
        tiet_kiem_tkvv_pm = _lookup_optional_vnd(
            rows_prev_month, "Tiền gửi tiết kiệm qua Tổ TK&VV", he_so_prev_month,
        )
        if huy_dong_pm is not None and tiet_kiem_tkvv_pm is not None:
            tien_gui_tt_pm = huy_dong_pm - tiet_kiem_tkvv_pm

    _has_pm = bool(rows_prev_month)

    for row_ht in rows_ht:
        if row_ht["la_nqh_con"]:
            continue
        indicator_lower = str(row_ht["ten"]).lower()
        if any(keyword in indicator_lower for keyword in skip_indicators):
            continue

        value_ht = _row_vnd(row_ht, he_so_ht)
        value_prev = (
            _match_prev_row_vnd(row_ht, rows_prev, he_so_prev, kh_mode)
            if rows_prev
            else 0.0
        )
        value_pm = (
            _match_prev_row_vnd(row_ht, rows_prev_month, he_so_prev_month, False)
            if rows_prev_month
            else 0.0
        )
        diff_pv = value_ht - value_prev
        diff_pm = value_ht - value_pm
        row_d: dict[str, Any] = {
            "Chỉ tiêu": row_ht["ten"],
            f"{label_prev} (triệu đồng)": _to_trieu(value_prev),
            f"{label_ht} (triệu đồng)": _to_trieu(value_ht),
            "Tăng/giảm so với năm trước (triệu đồng)": _to_trieu(diff_pv),
            "Tỷ lệ % năm trước": round(diff_pv / value_prev * 100, 2) if value_prev else 0,
        }
        if _has_pm:
            row_d["Tháng trước (triệu đồng)"] = _to_trieu(value_pm)
            row_d["Tăng/giảm so với tháng trước (triệu đồng)"] = _to_trieu(diff_pm)
            row_d["Tỷ lệ % tháng trước"] = round(diff_pm / value_pm * 100, 2) if value_pm else 0
        rows_ex1.append(row_d)

        if "tổng huy động vốn" in indicator_lower and (
            not rows_prev or tien_gui_tt_prev is not None
        ):
            value_prev_tg = tien_gui_tt_prev if tien_gui_tt_prev is not None else 0.0
            diff_pv_tg = tien_gui_tt_ht - value_prev_tg
            row_tg: dict[str, Any] = {
                "Chỉ tiêu": "TG TT TCTC & TK CN (= HĐV − TK qua Tổ TK&VV)",
                f"{label_prev} (triệu đồng)": _to_trieu(value_prev_tg),
                f"{label_ht} (triệu đồng)": _to_trieu(tien_gui_tt_ht),
                "Tăng/giảm so với năm trước (triệu đồng)": _to_trieu(diff_pv_tg),
                "Tỷ lệ % năm trước": round(diff_pv_tg / value_prev_tg * 100, 2) if value_prev_tg else 0,
            }
            if _has_pm:
                if tien_gui_tt_pm is None:
                    row_tg["Tháng trước (triệu đồng)"] = None
                    row_tg["Tăng/giảm so với tháng trước (triệu đồng)"] = None
                    row_tg["Tỷ lệ % tháng trước"] = None
                else:
                    _diff_pm_tg = tien_gui_tt_ht - tien_gui_tt_pm
                    row_tg["Tháng trước (triệu đồng)"] = _to_trieu(tien_gui_tt_pm)
                    row_tg["Tăng/giảm so với tháng trước (triệu đồng)"] = _to_trieu(_diff_pm_tg)
                    row_tg["Tỷ lệ % tháng trước"] = round(_diff_pm_tg / tien_gui_tt_pm * 100, 2) if tien_gui_tt_pm else 0
            rows_ex1.append(row_tg)

    for ten_hien, key in _CHUONG_TRINH_CANDOI:
        if key is None:
            continue
        value_ht = _lookup_vnd(rows_ht, key, he_so_ht)
        value_prev = _lookup_prev_vnd(rows_prev, key, he_so_prev, kh_mode) if rows_prev else 0.0
        nqh_ht = _nqh_con_vnd(rows_ht, key, he_so_ht)
        nqh_prev = _nqh_con_vnd(rows_prev, key, he_so_prev) if rows_prev else 0.0
        difference = value_ht - value_prev
        rows_ex2.append({
            "Chương trình": ten_hien,
            f"DN {label_prev} (triệu đồng)": _to_trieu(value_prev),
            f"DN {label_ht} (triệu đồng)": _to_trieu(value_ht),
            "Chênh lệch (triệu đồng)": _to_trieu(difference),
            "Tỷ lệ %": round(difference / value_prev * 100, 2) if value_prev else 0,
            f"NQH {label_prev} (triệu đồng)": _to_trieu(nqh_prev),
            f"NQH {label_ht} (triệu đồng)": _to_trieu(nqh_ht),
        })

    return pd.DataFrame(rows_ex1), pd.DataFrame(rows_ex2)


def _safe_export_name_part(value: object, fallback: str) -> str:
    """Chuẩn hóa một phần tên file để hợp lệ trên Windows."""
    normalized = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", str(value)).strip(" ._")
    return normalized or fallback


def _render_dienbao_lich_su(key_sfx: str) -> None:
    """Hiển thị bảng tóm tắt các điện báo đã upload để user biết trạng thái."""
    meta_ht = db.doc_kv(f"dienbao_meta_ht{key_sfx}") or {}
    meta_pv = db.doc_kv(f"dienbao_meta_prev{key_sfx}") or {}
    meta_pm = db.doc_kv(f"dienbao_meta_prev_month{key_sfx}") or {}
    if not meta_ht and not meta_pv and not meta_pm:
        return

    rows = []
    def _append_meta(meta: dict[str, Any], loai: str) -> None:
        ngay = meta.get("ngay_upload", "")
        try:
            ngay_fmt = datetime.fromisoformat(ngay).strftime("%d/%m/%Y %H:%M")
        except Exception:
            ngay_fmt = ngay or "—"
        rows.append({
            "Loại": loai,
            "File": meta.get("ten_file", "—"),
            "Kỳ số liệu": meta.get("ky") or "—",
            "Ngày upload": ngay_fmt,
            "Sheets": meta.get("n_sheets", "—"),
            "Chỉ tiêu": meta.get("n_chi_tieu", "—"),
        })
    if meta_ht:
        _append_meta(meta_ht, "📄 Hiện tại")
    if meta_pv:
        _append_meta(meta_pv, "🗓️ Kỳ trước")
    if meta_pm:
        _append_meta(meta_pm, "📅 Tháng trước")

    st.markdown("##### 📋 Điện báo đã upload")
    st.dataframe(
        pd.DataFrame(rows),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Sheets": st.column_config.NumberColumn("Sheets", format="%d"),
            "Chỉ tiêu": st.column_config.NumberColumn("Chỉ tiêu", format="%d"),
        },
    )


def _co_dienbao_lich_su(key_sfx: str) -> bool:
    """Có metadata upload Điện báo nào để hiển thị lịch sử không."""
    return any(
        db.doc_kv(f"dienbao_meta_{loai}{key_sfx}") or {}
        for loai in ("ht", "prev", "prev_month")
    )


def _render_quan_ly_tep_inline(
    store_ht: str,
    store_prev: str,
    store_prev_month: str,
    pgd_mode: bool,
    pgd_user: str | None,
    key_sfx: str,
    username: str,
    nam_ht: str,
    nam_prev: str,
) -> None:
    """Quản lý tệp inline — không popover, upload trực tiếp 1 bước."""
    with st.container(border=True):
        _meta_ht = db.doc_kv(f"dienbao_meta_ht{key_sfx}") or {}
        _ky_ht_kv = f"dienbao_ky_ht{key_sfx}"
        _ky_ht_saved = _normalize_ky_label(db.doc_kv(_ky_ht_kv))
        _default_ht = (
            _parse_ddmmyyyy(_ky_ht_saved)
            or _parse_ddmmyyyy(str(_meta_ht.get("ky", "")))
            or date.today()
        )

        _ky_pm_kv = f"dienbao_ky_pm{key_sfx}"
        _ky_pm_saved = _normalize_ky_label(db.doc_kv(_ky_pm_kv))
        _meta_pm = db.doc_kv(f"dienbao_meta_prev_month{key_sfx}") or {}

        _has_prev = os.path.exists(store_prev)
        _has_prev_month = os.path.exists(store_prev_month)

        # ── Hàng 1: Chốt ngày số liệu trước khi upload ──
        _ky_col1, _ky_col2 = st.columns(2)
        with _ky_col1:
            _ky_ht_date = st.date_input(
                "📅 Ngày số liệu HT",
                value=_default_ht,
                format="DD/MM/YYYY",
                key=f"inp_ky_ht{key_sfx}",
                help="Chọn đúng ngày trước khi upload; hệ thống sẽ lưu ngày này cùng file.",
            )
            _ky_ht_str = _ky_ht_date.strftime("%d/%m/%Y")
            _persist_ky_label_if_changed(
                _ky_ht_kv, _ky_ht_saved, _ky_ht_str, username, "kỳ số liệu HT",
            )
        with _ky_col2:
            _pm_default_date = _last_day_previous_month(_ky_ht_date)
            _default_pm = (
                _parse_ddmmyyyy(_ky_pm_saved)
                or _parse_ddmmyyyy(str(_meta_pm.get("ky", "")))
                or _pm_default_date
            )
            _ky_pm_widget_key = f"inp_ky_pm2{key_sfx}"
            _ky_pm_had_state = _ky_pm_widget_key in st.session_state
            _ky_pm_date = st.date_input(
                "📅 Ngày số liệu tháng trước",
                value=_default_pm,
                format="DD/MM/YYYY",
                key=_ky_pm_widget_key,
                help="Chọn đúng ngày trước khi upload file tháng trước.",
            )
            _ky_pm_str = _ky_pm_date.strftime("%d/%m/%Y")
            _pm_has_source = bool(_ky_pm_saved or _meta_pm.get("ky") or _has_prev_month)
            _pm_user_changed = _ky_pm_had_state and _ky_pm_date != _default_pm
            if _pm_has_source or _pm_user_changed:
                _persist_ky_label_if_changed(
                    _ky_pm_kv, _ky_pm_saved, _ky_pm_str, username, "kỳ số liệu tháng trước",
                )

        # ── Hàng 2: Trạng thái tổng quan ──
        _status_parts: list[str] = []
        _status_parts.append(f"📅 Kỳ số liệu: **{_ky_ht_str or '—'}**")
        _status_parts.append(f"🗓️ Kỳ trước: {'✅' if _has_prev else '⬜'}")
        _status_parts.append(f"📅 Tháng trước: {'✅' if _has_prev_month else '⬜'}")
        st.caption(" · ".join(_status_parts))

        # ── Hàng 3: Upload trực tiếp (3 cột) ──
        col_ht, col_prev, col_pm = st.columns(3)
        with col_ht:
            st.markdown(f"**📄 Đổi file HT** · {nam_ht}")
            _upload_one_file("ht", store_ht, "Chưa có file",
                             key_sfx, pgd_mode, pgd_user, username,
                             ky_kv=_ky_ht_kv,
                             ky_label=_ky_ht_str, ky_audit_name="kỳ số liệu HT")
        with col_prev:
            st.markdown(f"**🗓️ Kỳ trước** · {nam_prev}")
            _ky_pv_kv = f"dienbao_ky_pv{key_sfx}"
            _ky_pv_saved = _normalize_ky_label(db.doc_kv(_ky_pv_kv))
            _ky_pv_str = date(int(nam_prev), 12, 31).strftime("%d/%m/%Y")
            st.caption(f"Kỳ số liệu: **{_ky_pv_str}** (cố định)")
            _persist_ky_label_if_changed(
                _ky_pv_kv, _ky_pv_saved, _ky_pv_str, username, "kỳ số liệu kỳ trước",
            )
            _upload_one_file("prev", store_prev, "Chưa có — tùy chọn",
                             key_sfx, pgd_mode, pgd_user, username,
                             ky_kv=_ky_pv_kv,
                             ky_label=_ky_pv_str, ky_audit_name="kỳ số liệu kỳ trước")
        with col_pm:
            st.markdown("**📅 Tháng trước**")
            _upload_one_file("prev_month", store_prev_month, "Chưa có — tùy chọn",
                             key_sfx, pgd_mode, pgd_user, username,
                             ky_kv=_ky_pm_kv,
                             ky_label=_ky_pm_str, ky_audit_name="kỳ số liệu tháng trước")

        # ── Hàng 4: Lịch sử upload (gọn) ──
        if _co_dienbao_lich_su(key_sfx):
            _render_dienbao_lich_su(key_sfx)


def _upload_one_file(
    loai: str,
    store_path: str,
    empty_text: str,
    key_sfx: str,
    pgd_mode: bool,
    pgd_user: str | None,
    username: str,
    *,
    ky_kv: str | None = None,
    ky_label: str | None = None,
    ky_audit_name: str = "kỳ số liệu",
) -> None:
    """Upload 1 file Điện báo + hiển thị chip trạng thái. Dùng chung cho cả 3 loại."""
    ver_key = f"up_db_{loai}_ver{key_sfx}"
    ver = st.session_state.setdefault(ver_key, 0)
    f_up = st.file_uploader(
        f"Chọn file (.xlsx)",
        type=["xlsx", "xls"],
        key=f"up_db_{loai}{key_sfx}_{ver}",
        label_visibility="collapsed",
    )
    if f_up:
        try:
            with st.spinner("⏳ Đang xử lý..."):
                kq = luu_dienbao(
                    loai,
                    f_up.getvalue(),
                    f_up.name,
                    ten_pgd=pgd_user if pgd_mode else None,
                )
            kq.hien_thi()
            if kq.thanh_cong:
                if ky_kv and ky_label is not None:
                    ky_saved_latest = db.doc_kv(ky_kv)
                    _persist_ky_label_if_changed(
                        ky_kv, ky_saved_latest, ky_label, username, ky_audit_name,
                    )
                st.session_state[ver_key] = ver + 1
                st.cache_data.clear()
                st.rerun()
        except Exception as e:
            logger.error("Upload điện báo %s: %s", loai, e, exc_info=True)
            db.ghi_audit(
                username, "loi_he_thong",
                f"[{socket.gethostname()}] upload điện báo {loai}: {e}",
            )
            st.error(f"❌ Lỗi: {e}")
    else:
        st.markdown(_db_file_chip(store_path, empty_text), unsafe_allow_html=True)


def _render_upload_section(
    store_ht: str,
    store_prev: str,
    store_prev_month: str,
    pgd_mode: bool,
    pgd_user: str | None,
    key_sfx: str,
    username: str,
    nam_ht: str,
    nam_prev: str,
) -> None:
    """Render khu upload Điện báo — thiết kế lại 2026-08-01.

    Layout:
      1. File hiện tại (bắt buộc) — full-width, nổi bật
      2. File kỳ trước + tháng trước (tùy chọn) — 2 cột compact
      3. Kỳ số liệu — inline gọn, không HTML thừa
      4. Lịch sử upload — container trực tiếp cuối khu quản lý tệp
    """
    # ── 1. FILE HIỆN TẠI (bắt buộc) ──────────────────────────────────────
    with st.container(border=True):
        st.markdown(
            f'**📄 Điện báo hiện tại** · NĂM {nam_ht} · _bắt buộc_',
        )
        _ky_ht_kv = f"dienbao_ky_ht{key_sfx}"
        _ky_ht_saved = _normalize_ky_label(db.doc_kv(_ky_ht_kv))
        _meta_ht = db.doc_kv(f"dienbao_meta_ht{key_sfx}") or {}
        _default_ht = (
            _parse_ddmmyyyy(_ky_ht_saved)
            or _parse_ddmmyyyy(str(_meta_ht.get("ky", "")))
            or date.today()
        )
        _ky_ht_date = st.date_input(
            "📅 Ngày số liệu",
            value=_default_ht,
            format="DD/MM/YYYY",
            key=f"inp_ky_ht{key_sfx}",
            help="Chọn đúng ngày trước khi upload; hệ thống sẽ lưu ngày này cùng file.",
        )
        _ky_ht_str = _ky_ht_date.strftime("%d/%m/%Y")
        _persist_ky_label_if_changed(
            _ky_ht_kv, _ky_ht_saved, _ky_ht_str, username, "kỳ số liệu HT",
        )
        _upload_one_file("ht", store_ht, "Chưa có file — vui lòng upload",
                         key_sfx, pgd_mode, pgd_user, username,
                         ky_kv=_ky_ht_kv,
                         ky_label=_ky_ht_str, ky_audit_name="kỳ số liệu HT")

    # ── 2. FILE TÙY CHỌN (kỳ trước + tháng trước) ───────────────────────
    st.markdown(
        f'**📂 File so sánh** · _tùy chọn — bỏ qua nếu file hiện tại đã có sheet Y / KH_GIAO_DAU_NAM_',
    )
    opt_col1, opt_col2 = st.columns(2)

    with opt_col1:
        with st.container(border=True):
            st.markdown(f'**🗓️ Kỳ trước** · {nam_prev}')
            # Kỳ trước luôn = 31/12/năm trước → hiển thị text, không cần widget
            _ky_pv_kv = f"dienbao_ky_pv{key_sfx}"
            _ky_pv_saved = _normalize_ky_label(db.doc_kv(_ky_pv_kv))
            _cuoi_nam_prev = date(int(nam_prev), 12, 31)
            _ky_pv_str = _cuoi_nam_prev.strftime("%d/%m/%Y")
            st.caption(f"Kỳ số liệu: **{_ky_pv_str}** (cố định)")
            _persist_ky_label_if_changed(
                _ky_pv_kv, _ky_pv_saved, _ky_pv_str, username, "kỳ số liệu kỳ trước",
            )
            _upload_one_file("prev", store_prev, "Chưa có — không bắt buộc",
                             key_sfx, pgd_mode, pgd_user, username,
                             ky_kv=_ky_pv_kv,
                             ky_label=_ky_pv_str, ky_audit_name="kỳ số liệu kỳ trước")

    # Tháng trước = tháng liền trước kỳ hiện tại
    _pm_default_date = _last_day_previous_month(_ky_ht_date)
    _pm_nam = _pm_default_date.year

    with opt_col2:
        with st.container(border=True):
            st.markdown(f'**📅 Tháng trước** · {_pm_nam}')
            # Kỳ số liệu tháng trước
            _ky_pm_kv = f"dienbao_ky_pm{key_sfx}"
            _ky_pm_saved = _normalize_ky_label(db.doc_kv(_ky_pm_kv))
            _meta_pm = db.doc_kv(f"dienbao_meta_prev_month{key_sfx}") or {}
            _default_pm = (
                _parse_ddmmyyyy(_ky_pm_saved)
                or _parse_ddmmyyyy(str(_meta_pm.get("ky", "")))
                or _pm_default_date
            )
            _ky_pm_widget_key = f"inp_ky_pm2{key_sfx}"
            _ky_pm_had_state = _ky_pm_widget_key in st.session_state
            _ky_pm_date = st.date_input(
                "📅 Ngày số liệu",
                value=_default_pm,
                format="DD/MM/YYYY",
                key=_ky_pm_widget_key,
                help="Mặc định = ngày cuối tháng liền trước.",
            )
            _ky_pm_str = _ky_pm_date.strftime("%d/%m/%Y")
            _pm_has_source = bool(_ky_pm_saved or _meta_pm.get("ky") or os.path.exists(store_prev_month))
            _pm_user_changed = _ky_pm_had_state and _ky_pm_date != _default_pm
            if _pm_has_source or _pm_user_changed:
                _persist_ky_label_if_changed(
                    _ky_pm_kv, _ky_pm_saved, _ky_pm_str, username, "kỳ số liệu tháng trước",
                )
            _upload_one_file("prev_month", store_prev_month, "Chưa có — không bắt buộc",
                             key_sfx, pgd_mode, pgd_user, username,
                             ky_kv=_ky_pm_kv,
                             ky_label=_ky_pm_str, ky_audit_name="kỳ số liệu tháng trước")

    # ── 3. LỊCH SỬ UPLOAD ────────────────────────────────────────────────
    if _co_dienbao_lich_su(key_sfx):
        with st.container(border=True):
            _render_dienbao_lich_su(key_sfx)
    else:
        st.caption("📋 Lịch sử điện báo: chưa có file upload nào.")


from tabs.base_tab import TabContext


def render(tab: DeltaGenerator | None = None, **kwargs: dict) -> None:
    import plotly.express as px
    import plotly.graph_objects as go

    ctx = TabContext(tab, **kwargs)
    df        = kwargs.get("df")
    df_full   = ctx.df_full if ctx.df_full is not None and not ctx.df_full.empty else df
    role      = ctx.role_norm
    pgd_user  = ctx.pgd_user
    username  = ctx.username
    pgd_mode  = kwargs.get("pgd_mode", False)

    if pgd_mode and not pgd_user:
        with ctx:
            st.error("Không xác định được PGD.")
        return

    key_sfx = f"_{pgd_slug(pgd_user)}" if pgd_mode else ""

    path_dien_ht   = duong_dan_pgd(pgd_user, "dienbao_ht")   if pgd_mode else None
    path_dien_prev = duong_dan_pgd(pgd_user, "dienbao_prev") if pgd_mode else None
    path_dien_prev_month = duong_dan_pgd(pgd_user, "dienbao_prev_month") if pgd_mode else None
    store_ht   = path_dien_ht   if pgd_mode else DB_HT_CACHE
    store_prev = path_dien_prev if pgd_mode else DB_PREV_CACHE
    store_prev_month = path_dien_prev_month if pgd_mode else DB_PREV_MONTH_CACHE

    with ctx:
        nam_ht   = str(datetime.today().year)
        nam_prev = str(datetime.today().year - 1)

        if pgd_mode:
            st.subheader(f"📌 Điện báo {pgd_user}")
        else:
            st.subheader("📌 Điện báo Chi nhánh")
        st.caption("⚖️ Cân đối Nguồn vốn & Sử dụng vốn")

        # ── Format helpers ─────────────────────────────────────────────────
        def vfmt_cd(x, d=1):
            try:
                x = float(x)
                s = f"{x:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")
                return s.rstrip("0").rstrip(",") if "," in s else s
            except Exception:
                return "—"

        def fmt_pct(x):
            try:
                x = float(x)
                return (f"+{vfmt_cd(x,1)}%" if x > 0 else f"{vfmt_cd(x,1)}%") if x != 0 else "0%"
            except Exception:
                return "—"

        def _fmt_trd(x):
            try:
                if pd.isna(x):
                    return "—"
                return vfmt_cd(float(x), 0)
            except Exception:
                return "—"

        def _fmt_vnd_trieu(x):
            try:
                if pd.isna(x):
                    return "—"
                return vfmt_cd(float(x) / 1_000_000, 0)
            except Exception:
                return "—"

        # ── Xác định đường dẫn file ────────────────────────────────────────
        if pgd_mode:
            path_ht   = path_dien_ht   if path_dien_ht   and os.path.exists(path_dien_ht)   else None
            path_prev = path_dien_prev if path_dien_prev and os.path.exists(path_dien_prev) else None
            path_prev_month = path_dien_prev_month if path_dien_prev_month and os.path.exists(path_dien_prev_month) else None
        else:
            path_ht   = DB_HT_CACHE   if os.path.exists(DB_HT_CACHE)   else (FILE_PATH_DB      if os.path.exists(FILE_PATH_DB)      else None)
            path_prev = DB_PREV_CACHE if os.path.exists(DB_PREV_CACHE) else (FILE_PATH_DB_PREV if os.path.exists(FILE_PATH_DB_PREV) else None)
            path_prev_month = DB_PREV_MONTH_CACHE if os.path.exists(DB_PREV_MONTH_CACHE) else None

        # ══════════════════════════════════════════════════════════════════
        # STATE A: Chưa có file → Upload nổi bật, return sớm
        # ══════════════════════════════════════════════════════════════════
        if not path_ht:
            with st.container(border=True):
                st.markdown("### 📤 Upload file Điện báo để bắt đầu")
                st.caption(
                    "Tải file Điện báo từ Core Banking (thường có nhiều sheet: M, Y, DB, KH_GIAO_DAU_NAM…). "
                    "Upload 1 file là đủ — hệ thống sẽ đọc 2 sheet để so sánh."
                )
                _render_upload_section(store_ht, store_prev, store_prev_month, pgd_mode, pgd_user, key_sfx, username, nam_ht, nam_prev)
            return

        # ══════════════════════════════════════════════════════════════════
        # STATE B: Đã có file → Info bar + Quản lý tệp inline
        # ══════════════════════════════════════════════════════════════════
        try:
            _mtime = datetime.fromtimestamp(os.path.getmtime(path_ht)).strftime("%d/%m/%Y %H:%M")
            _kb    = os.path.getsize(path_ht) // 1024
        except Exception:
            _mtime, _kb = "—", "—"

        _has_file_prev = _has_previous_file(path_prev, path_ht)
        st.caption(f"📂 **{os.path.basename(path_ht)}** · {_kb} KB · {_mtime}")

        _render_quan_ly_tep_inline(
            store_ht,
            store_prev,
            store_prev_month,
            pgd_mode,
            pgd_user,
            key_sfx,
            username,
            nam_ht,
            nam_prev,
        )

        # ══════════════════════════════════════════════════════════════════
        # MỐC SO SÁNH + SHEET SELECTOR
        # ══════════════════════════════════════════════════════════════════
        from data.hstd import liet_ke_sheet_dienbao

        sheet_ht: str | None = None
        sheet_pv: str | None = None
        # Nhãn kỳ số liệu từ kv_store (user gắn khi upload) hoặc fallback
        _ky_ht_label = db.doc_kv(f"dienbao_ky_ht{key_sfx}") or f"{nam_ht} (HT)"
        _ky_pv_label = db.doc_kv(f"dienbao_ky_pv{key_sfx}") or f"31/12/{nam_prev}"
        _ky_pm_label = db.doc_kv(f"dienbao_ky_pm{key_sfx}") or "Tháng trước"
        _has_prev_month = bool(path_prev_month)
        label_ht = _ky_ht_label
        label_pv = _ky_pv_label
        kieu_so_sanh = "delta"        # "delta" | "thuc_hien_kh"
        _moc_val = ""                  # sẽ gán trong if ds_sheet

        try:
            ds_sheet = liet_ke_sheet_dienbao(path_ht, ts=ts_file(path_ht))
        except Exception as _e:
            logger.warning("liet_ke_sheet_dienbao: %s", _e)
            ds_sheet = []

        if ds_sheet:
            sheet_opts   = [s["sheet"] for s in ds_sheet]
            sheet_info_m = {s["sheet"]: s for s in ds_sheet}

            # Xác định sheet hiện tại mặc định (trước khi render UI)
            _default_ht = next(
                (s for s in ["M", "DB1", "DB"] if s in sheet_opts),
                sheet_opts[0],
            ) if len(ds_sheet) > 1 else sheet_opts[0]
            # Dùng session_state nếu user đã chọn trước đó
            _ss_ht_key = f"cd_sheet_ht{key_sfx}"
            _pre_ht = st.session_state.get(_ss_ht_key, _default_ht)
            if _pre_ht not in sheet_opts:
                _pre_ht = _default_ht

            # ── UI: Cấu hình so sánh (bordered, 2 cột) ─────────────────
            with st.container(border=True):
                st.markdown("##### ⚙️ Cấu hình so sánh")
                _col_ht, _col_ss = st.columns(2, gap="large")

                # Cột trái: Sheet hiện tại
                with _col_ht:
                    if len(ds_sheet) == 1:
                        sheet_ht = sheet_opts[0]
                        st.markdown(f"**📊 Kỳ hiện tại:** `{sheet_ht}`")
                    else:
                        if _ss_ht_key in st.session_state and st.session_state[_ss_ht_key] not in sheet_opts:
                            st.session_state[_ss_ht_key] = _pre_ht
                        sheet_ht = st.selectbox(
                            "📊 Kỳ hiện tại (sheet)",
                            sheet_opts,
                            index=sheet_opts.index(_pre_ht),
                            key=_ss_ht_key,
                            format_func=lambda s: (
                                f"{s} · {sheet_info_m[s]['rows']} dòng"
                                + (f" · {sheet_info_m[s].get('ngay','')[:22]}" if sheet_info_m[s].get("ngay") else "")
                            ),
                        )

                # ── Xác định các sheet so sánh khả dụng theo sheet thực tế ─
                _y_sheet = _first_comparison_sheet(sheet_opts, sheet_ht, ["Y"])
                _kh_sheet = _first_comparison_sheet(
                    sheet_opts,
                    sheet_ht,
                    ["KH_GIAO_DAU_NAM", "KH", "DIEU_CHINH_KHTD"],
                )
                _has_y_sheet = _y_sheet is not None
                _has_kh_sheet = _kh_sheet is not None
                _can_31_12 = _has_y_sheet or _has_file_prev
                _can_kh = _has_kh_sheet

                MOC_LABELS = []
                MOC_VALUES = []  # ("value", "mode")
                if _can_31_12:
                    MOC_LABELS.append(f"vs {_ky_pv_label}")
                    MOC_VALUES.append(("31_12", "delta"))
                if _can_kh:
                    MOC_LABELS.append("vs Kế hoạch giao")
                    MOC_VALUES.append(("kh_giao", "thuc_hien_kh"))
                if _has_prev_month:
                    MOC_LABELS.append(f"vs {_ky_pm_label}")
                    MOC_VALUES.append(("thang_truoc", "delta"))
                MOC_LABELS.append("Tùy chọn khác…")
                MOC_VALUES.append(("custom", "delta"))

                # Đọc mốc đã lưu từ kv_store để đặt default
                _kv_moc_key = f"candoi_moc_ss{key_sfx}"
                _saved_moc = db.doc_kv(_kv_moc_key)
                _moc_default = 0
                if _saved_moc:
                    for _i, (_v, _) in enumerate(MOC_VALUES):
                        if _v == _saved_moc:
                            _moc_default = _i
                            break

                _moc_key = f"cd_moc_ss{key_sfx}"
                _moc_changed_key = f"{_moc_key}_changed"

                if _moc_key in st.session_state and st.session_state[_moc_key] not in MOC_LABELS:
                    st.session_state[_moc_key] = MOC_LABELS[_moc_default]

                def _mark_moc_changed() -> None:
                    st.session_state[_moc_changed_key] = True

                # Cột phải: Mốc so sánh + nguồn
                with _col_ss:
                    _moc_label = st.radio(
                        "📐 So sánh với",
                        MOC_LABELS,
                        horizontal=True,
                        index=_moc_default,
                        key=_moc_key,
                        on_change=_mark_moc_changed,
                    )
                    _moc_idx = MOC_LABELS.index(_moc_label)
                    _moc_val, _moc_mode = MOC_VALUES[_moc_idx]

                    # Custom → selectbox nguồn ngay bên dưới
                    if _moc_val == "custom":
                        _custom_opts = _custom_sheet_options(sheet_opts, sheet_ht)
                        _nguon_opts = _custom_comparison_options(
                            sheet_opts,
                            sheet_ht,
                            has_previous_file=_has_file_prev,
                        )
                        if _nguon_opts:
                            _auto_pv    = _AUTO_MAP_PREV.get(sheet_ht or "", "")
                            _default_pv = _auto_pv if _auto_pv in _custom_opts else _nguon_opts[0]
                            _nguon_key = f"cd_sheet_pv{key_sfx}"
                            if _nguon_key in st.session_state and st.session_state[_nguon_key] not in _nguon_opts:
                                st.session_state[_nguon_key] = _default_pv
                            _nguon_sel = st.selectbox(
                                "Nguồn so sánh",
                                _nguon_opts,
                                index=_nguon_opts.index(_default_pv),
                                key=_nguon_key,
                                format_func=lambda s: _fmt_nguon_ss(s, sheet_info_m, path_prev),
                            )
                            sheet_pv = None if _nguon_sel == _FILE_PREV_SENTINEL else _nguon_sel
                        else:
                            st.warning("⚠️ Không có sheet/file kỳ trước để so sánh.")

            _moc_changed_by_user = bool(
                st.session_state.pop(_moc_changed_key, False)
            )

            # Không ghi default/fallback chỉ vì tab rerun hoặc danh sách mốc đổi.
            if _should_persist_moc_choice(
                _saved_moc,
                _moc_val,
                changed_by_user=_moc_changed_by_user,
            ):
                db.ghi_kv(_kv_moc_key, _moc_val, username)
                _audit_verb = "Thiết lập" if _saved_moc is None else "Đổi"
                db.ghi_audit(
                    username,
                    "candoi_moc_ss",
                    f"{_audit_verb} mốc so sánh Điện báo: {_saved_moc or 'chưa có'} → {_moc_val}",
                )

            # ── Derive sheet_pv + label từ mốc ─────────────────────────
            if _moc_val == "31_12":
                if _y_sheet:
                    sheet_pv = _y_sheet
                # else: sheet_pv = None → đọc file prev bên dưới
                label_pv = _ky_pv_label
                kieu_so_sanh = "delta"
            elif _moc_val == "kh_giao":
                sheet_pv = _kh_sheet
                label_pv = "KH giao"
                kieu_so_sanh = "thuc_hien_kh"
            elif _moc_val == "thang_truoc":
                sheet_pv = None  # đọc từ file prev_month bên dưới
                label_pv = _ky_pm_label
                kieu_so_sanh = "delta"
            elif _moc_val == "custom":
                kieu_so_sanh = "delta"

            # ── Cảnh báo nếu mốc không có sheet ─────────────────────────
            if _moc_val == "31_12" and not _has_y_sheet and not _has_file_prev:
                st.warning("⚠️ Không có sheet Y hoặc file kỳ trước để so sánh 31/12.")
            if _moc_val == "kh_giao" and not _has_kh_sheet:
                st.warning("⚠️ Không tìm thấy sheet Kế hoạch giao (KH_GIAO_DAU_NAM/KH).")

            # Label từ metadata sheet
            _si_ht = sheet_info_m.get(sheet_ht or "", {})
            _si_pv = sheet_info_m.get(sheet_pv or "", {})
            if _si_ht.get("ngay"):
                label_ht = _si_ht["ngay"][:30]
            if _si_pv.get("ngay") and _moc_val == "custom":
                label_pv = _si_pv["ngay"][:30]
            # custom + chọn file kỳ trước → dùng nhãn kỳ đã lưu
            if _moc_val == "custom" and sheet_pv is None and _has_file_prev:
                label_pv = _ky_pv_label

            # ── Tóm tắt trực quan: A ↔ B ──────────────────────────────
            _ss_src = sheet_pv or (label_pv if _moc_val != "custom" or _has_file_prev else "—")
            st.caption(
                f"📊 **{sheet_ht}** ({label_ht})  ↔  📐 **{_ss_src}** ({label_pv})"
            )

        # ── Đọc dữ liệu với sheet được chọn ──────────────────────────────
        db_ht_rows:   list | None = None
        db_prev_rows: list | None = None

        try:
            db_ht_rows = doc_dienbao(path_ht, ts_file(path_ht), sheet_name=sheet_ht)
        except Exception as e:
            logger.error("Đọc Điện báo ht sheet=%s: %s", sheet_ht, e, exc_info=True)
            st.error(f"❌ Lỗi đọc file Điện báo hiện tại: {e}")

        # Nguồn so sánh: ưu tiên sheet_pv từ cùng file; fallback file prev_month / path_prev
        if sheet_pv and sheet_pv != sheet_ht:
            try:
                db_prev_rows = doc_dienbao(path_ht, ts_file(path_ht), sheet_name=sheet_pv)
            except Exception as e:
                logger.error("Đọc Điện báo pv sheet=%s: %s", sheet_pv, e, exc_info=True)
        elif _moc_val == "thang_truoc" and path_prev_month:
            try:
                db_prev_rows = doc_dienbao(path_prev_month, ts_file(path_prev_month), sheet_name=None)
            except Exception as e:
                logger.error("Đọc Điện báo file prev_month (mốc tháng trước): %s", e, exc_info=True)
        elif _has_file_prev:
            try:
                db_prev_rows = doc_dienbao(path_prev, ts_file(path_prev), sheet_name=None)
            except Exception as e:
                logger.error("Đọc Điện báo file prev: %s", e, exc_info=True)
        # else: db_prev_rows = None → hiển thị KPI không có delta

        # Nguồn tháng trước (file riêng, không bắt buộc)
        db_prev_month_rows: list[dict] | None = None
        if _moc_val != "thang_truoc" and path_prev_month:
            try:
                db_prev_month_rows = doc_dienbao(path_prev_month, ts_file(path_prev_month), sheet_name=None)
            except Exception as e:
                logger.error("Đọc Điện báo file prev_month: %s", e, exc_info=True)

        # ── Helpers phụ thuộc dữ liệu ─────────────────────────────────────
        def _he_so_vnd(rows: list[dict] | None) -> int:
            if not rows:
                return 1_000_000
            for _r in rows:
                if _r.get("he_so_vnd"):
                    return int(_r["he_so_vnd"])
            for _r in rows:
                if "don_vi_nguon" in _r:
                    return {"trieu": 1_000_000, "nghin": 1_000, "dong": 1}.get(str(_r["don_vi_nguon"]), 1_000_000)
            return 1_000_000 if any(_r.get("don_vi_trieu") for _r in rows) else 1

        def _don_vi_label(rows: list[dict] | None) -> str:
            he_so = _he_so_vnd(rows)
            if not rows:
                return "triệu đồng"
            for _r in rows:
                if _r.get("don_vi_label"):
                    return str(_r["don_vi_label"])
                if _r.get("don_vi_nguon"):
                    return {"trieu": "triệu đồng", "nghin": "nghìn đồng", "dong": "đồng"}.get(str(_r["don_vi_nguon"]), "triệu đồng")
            return {1_000_000: "triệu đồng", 1_000: "nghìn đồng", 1: "đồng"}.get(he_so, "đồng")

        _he_so_ht = _he_so_vnd(db_ht_rows)
        _he_so_pv = _he_so_vnd(db_prev_rows) if db_prev_rows else _he_so_ht
        _he_so_pm = _he_so_vnd(db_prev_month_rows) if db_prev_month_rows else _he_so_ht
        _don_vi_ht = _don_vi_label(db_ht_rows)
        _don_vi_pv = _don_vi_label(db_prev_rows) if db_prev_rows else _don_vi_ht

        if db_prev_rows and _he_so_ht != _he_so_pv:
            st.caption(f"Đơn vị nguồn khác nhau: {label_ht} = {_don_vi_ht}, {label_pv} = {_don_vi_pv}. Số liệu đã quy đổi về VND để so sánh.")

        def _to_ty(x: float) -> float:
            """VND → tỷ đồng."""
            return round(float(x or 0) / 1_000_000_000, 2)

        def _pct(ht: float, pv: float) -> float | None:
            return round((ht - pv) / pv * 100, 1) if pv else None

        def build_row(ten_hien: str, val_ht: float, val_pv: float, la_con: bool = False, val_pm: float | None = 0.0) -> dict[str, Any]:
            cl_pv = val_ht - val_pv if db_prev_rows is not None else None
            cl_pm = val_ht - val_pm if db_prev_month_rows is not None and val_pm is not None else None
            tl_pv = (cl_pv / val_pv * 100) if (cl_pv is not None and val_pv and val_pv != 0) else None
            tl_pm = (cl_pm / val_pm * 100) if (cl_pm is not None and val_pm and val_pm != 0) else None
            ind = "　　" if la_con else ""
            return {
                "Chỉ tiêu":  ind + ten_hien,
                label_pv:    val_pv if db_prev_rows else 0,
                label_ht:    val_ht,
                "Tăng/giảm so với năm trước": cl_pv if cl_pv is not None else 0,
                "Tỷ lệ % năm trước":   tl_pv if tl_pv is not None else 0,
                "Tháng trước": val_pm if db_prev_month_rows else 0,
                "Tăng/giảm so với tháng trước": cl_pm if cl_pm is not None else 0,
                "Tỷ lệ % tháng trước":   tl_pm if tl_pm is not None else 0,
                "_ht": val_ht, "_pv": val_pv or 0, "_cl": cl_pv or 0, "_pm": val_pm or 0,
            }

        # ══════════════════════════════════════════════════════════════════
        # 3 SUB-TABS (lazy: chỉ render tab đang active)
        # ══════════════════════════════════════════════════════════════════
        _cd_sub_labels = ["📊 Tổng quan", "📌 Theo chương trình", "📊 Biểu đồ"]
        _cd_sub = st.radio(
            "Sub-tab", range(len(_cd_sub_labels)),
            format_func=lambda i: _cd_sub_labels[i],
            horizontal=True, key=f"candoi_sub_tab{key_sfx}", label_visibility="collapsed",
        )
        st.divider()

        _la_kh = kieu_so_sanh == "thuc_hien_kh"

        # ──────────────────────────────────────────────────────────────────
        # TAB 1: TỔNG QUAN — KPI + bảng chi tiết hiển thị trực tiếp
        # ──────────────────────────────────────────────────────────────────
        if _cd_sub == 0:
            if db_ht_rows is None:
                st.info("⚠️ Không đọc được dữ liệu từ file. Kiểm tra lại file hoặc chọn sheet khác.")
            else:
                tong_dn_ht  = _lookup_vnd(db_ht_rows, "Tổng dư nợ", _he_so_ht)
                huy_dong_ht = _lookup_vnd(db_ht_rows, "Tổng huy động vốn", _he_so_ht)
                tiet_kiem_to_tkvv_ht = _lookup_vnd(db_ht_rows, "Tiền gửi tiết kiệm qua Tổ TK&VV", _he_so_ht)
                tien_gui_tt_ht = huy_dong_ht - tiet_kiem_to_tkvv_ht
                utdt_ht     = _lookup_vnd(db_ht_rows, "Nguồn vốn nhận UTĐT tại ĐP", _he_so_ht)
                nqh_ht      = _lookup_vnd(db_ht_rows, "Dư nợ Quá hạn KHA", _he_so_ht) + _lookup_vnd(db_ht_rows, "Dư nợ Quá hạn KHB", _he_so_ht)
                kha_ht      = _lookup_vnd(db_ht_rows, "Dư nợ Kế hoạch A", _he_so_ht)
                khb_ht      = _lookup_vnd(db_ht_rows, "Dư nợ Kế hoạch B", _he_so_ht)
                khoanh_ht   = _lookup_khoanh_vnd(db_ht_rows, _he_so_ht)
                tl_nqh      = round(nqh_ht / tong_dn_ht * 100, 2) if tong_dn_ht else 0

                _title = f"📊 {pgd_user}" if pgd_mode else "📊 Toàn Chi nhánh"
                st.markdown(f"### {_title}")

                tien_gui_tt_pv: float | None = 0.0
                tien_gui_tt_pm: float | None = None
                if db_prev_month_rows:
                    _hd_pm = _lookup_optional_vnd(db_prev_month_rows, "Tổng huy động vốn", _he_so_pm)
                    _tk_pm = _lookup_optional_vnd(
                        db_prev_month_rows, "Tiền gửi tiết kiệm qua Tổ TK&VV", _he_so_pm,
                    )
                    if _hd_pm is not None and _tk_pm is not None:
                        tien_gui_tt_pm = _hd_pm - _tk_pm
                if db_prev_rows:
                    if _la_kh:
                        tong_dn_pv  = _lookup_kh_vnd(db_prev_rows, "Tổng dư nợ", _he_so_pv)
                        _huy_dong_pv_optional = _lookup_kh_optional_vnd(
                            db_prev_rows, "Tổng huy động vốn", _he_so_pv,
                        )
                        _tiet_kiem_to_tkvv_pv_optional = _lookup_kh_optional_vnd(
                            db_prev_rows, "Tiền gửi tiết kiệm qua Tổ TK&VV", _he_so_pv,
                        )
                        huy_dong_pv = _huy_dong_pv_optional or 0.0
                        tien_gui_tt_pv = (
                            _huy_dong_pv_optional - _tiet_kiem_to_tkvv_pv_optional
                            if _huy_dong_pv_optional is not None
                            and _tiet_kiem_to_tkvv_pv_optional is not None
                            else None
                        )
                        utdt_pv     = _lookup_kh_vnd(db_prev_rows, "Nguồn vốn nhận UTĐT tại ĐP", _he_so_pv)
                        nqh_pv      = _lookup_kh_vnd(db_prev_rows, "Dư nợ Quá hạn KHA", _he_so_pv) + _lookup_kh_vnd(db_prev_rows, "Dư nợ Quá hạn KHB", _he_so_pv)
                        kha_pv      = _lookup_kh_vnd(db_prev_rows, "Dư nợ Kế hoạch A", _he_so_pv)
                        khb_pv      = _lookup_kh_vnd(db_prev_rows, "Dư nợ Kế hoạch B", _he_so_pv)
                        khoanh_pv   = _lookup_khoanh_vnd(db_prev_rows, _he_so_pv, kh_mode=True)
                    else:
                        tong_dn_pv  = _lookup_vnd(db_prev_rows, "Tổng dư nợ", _he_so_pv)
                        huy_dong_pv = _lookup_vnd(db_prev_rows, "Tổng huy động vốn", _he_so_pv)
                        tiet_kiem_to_tkvv_pv = _lookup_vnd(db_prev_rows, "Tiền gửi tiết kiệm qua Tổ TK&VV", _he_so_pv)
                        tien_gui_tt_pv = huy_dong_pv - tiet_kiem_to_tkvv_pv
                        utdt_pv     = _lookup_vnd(db_prev_rows, "Nguồn vốn nhận UTĐT tại ĐP", _he_so_pv)
                        nqh_pv      = _lookup_vnd(db_prev_rows, "Dư nợ Quá hạn KHA", _he_so_pv) + _lookup_vnd(db_prev_rows, "Dư nợ Quá hạn KHB", _he_so_pv)
                        kha_pv      = _lookup_vnd(db_prev_rows, "Dư nợ Kế hoạch A", _he_so_pv)
                        khb_pv      = _lookup_vnd(db_prev_rows, "Dư nợ Kế hoạch B", _he_so_pv)
                        khoanh_pv   = _lookup_khoanh_vnd(db_prev_rows, _he_so_pv)

                    if _la_kh:
                        # KH mode: hiển thị % Hoàn thành KH
                        _delta_fn = lambda ht, pv: round(ht / pv * 100, 1) if pv else None
                        _delta_label = "% KH"
                        _delta_color = "normal"
                    else:
                        _delta_fn = _pct
                        _delta_label = f"vs {label_pv}"
                        _delta_color = "normal"

                    tl_nqh_pv = round(nqh_pv / tong_dn_pv * 100, 2) if tong_dn_pv else None

                    _cap_pv = "KH giao" if _la_kh else label_pv

                    _kpi_top_cards = [
                        {"label": "Tổng dư nợ", "icon": "💰", "value": _to_ty(tong_dn_ht), "precision": 1,
                         "delta": _delta_fn(tong_dn_ht, tong_dn_pv), "delta_label": _delta_label, "delta_color": _delta_color,
                         "tone": "accent",
                         "stats": [_stat_ty(tong_dn_pv, _cap_pv), _stat_cl(tong_dn_ht, tong_dn_pv),
                                   {"v": _fmt_so_vn(tl_nqh, 2) + "%", "c": "NQH"}]},
                    ]
                    if tien_gui_tt_pv is not None:
                        _kpi_top_cards.append(
                            {"label": "TG TT TCTC & TK CN", "icon": "🏧", "value": _to_ty(tien_gui_tt_ht), "precision": 1,
                             "delta": _delta_fn(tien_gui_tt_ht, tien_gui_tt_pv), "delta_label": _delta_label, "delta_color": _delta_color,
                             "tone": "info",
                             "stats": [_stat_ty(tien_gui_tt_pv, _cap_pv), _stat_cl(tien_gui_tt_ht, tien_gui_tt_pv),
                                       _stat_pct(tien_gui_tt_ht, huy_dong_ht, "HĐV")]},
                        )
                    _kpi_top_cards.append(
                        {"label": "Vốn UTĐT ĐP", "icon": "🤝", "value": _to_ty(utdt_ht), "precision": 1,
                         "delta": _delta_fn(utdt_ht, utdt_pv), "delta_label": _delta_label, "delta_color": _delta_color,
                         "tone": "info",
                         "stats": [_stat_ty(utdt_pv, _cap_pv), _stat_cl(utdt_ht, utdt_pv),
                                   _stat_pct(utdt_ht, tong_dn_ht, "tổng DN")]},
                    )
                    _render_kpi_grid(_kpi_top_cards, num_columns=len(_kpi_top_cards))

                    if _la_kh and tien_gui_tt_pv is None:
                        st.warning(
                            "⚠️ Không hiển thị KPI TG TT TCTC & TK CN khi so sánh Kế hoạch giao "
                            "vì sheet KH thiếu Tổng huy động vốn hoặc Tiền gửi tiết kiệm qua Tổ TK&VV.",
                        )
                    if db_prev_month_rows and tien_gui_tt_pm is None:
                        st.warning(
                            "⚠️ Không tính cột tháng trước cho dòng TG TT TCTC & TK CN "
                            "vì file tháng trước thiếu Tổng huy động vốn hoặc Tiền gửi tiết kiệm qua Tổ TK&VV.",
                        )

                    _render_kpi_grid([
                        {"label": "Dư nợ KHA", "icon": "📋", "value": _to_ty(kha_ht), "precision": 1,
                         "delta": _delta_fn(kha_ht, kha_pv), "delta_label": _delta_label, "delta_color": _delta_color,
                         "tone": "accent",
                         "stats": [_stat_ty(kha_pv, _cap_pv), _stat_cl(kha_ht, kha_pv),
                                   _stat_pct(kha_ht, tong_dn_ht, "tổng DN")]},
                        {"label": "Dư nợ KHB", "icon": "📋", "value": _to_ty(khb_ht), "precision": 1,
                         "delta": _delta_fn(khb_ht, khb_pv), "delta_label": _delta_label, "delta_color": _delta_color,
                         "tone": "accent",
                         "stats": [_stat_ty(khb_pv, _cap_pv), _stat_cl(khb_ht, khb_pv),
                                   _stat_pct(khb_ht, tong_dn_ht, "tổng DN")]},
                        {"label": "NQH (KHA+KHB)", "icon": "⚠️", "value": _to_ty(nqh_ht), "precision": 2,
                         "delta": tl_nqh, "delta_label": "% tổng DN", "delta_color": "inverse",
                         "tone": "error",
                         "stats": [_stat_ty(nqh_pv, _cap_pv), _stat_cl(nqh_ht, nqh_pv),
                                   {"v": (f"{tl_nqh_pv}%" if tl_nqh_pv is not None else "—"), "c": f"NQH {_cap_pv}"}]},
                        {"label": "Nợ khoanh", "icon": "🔒", "value": _to_ty(khoanh_ht), "precision": 1,
                         "delta": _delta_fn(khoanh_ht, khoanh_pv), "delta_label": _delta_label, "delta_color": _delta_color,
                         "tone": "warn",
                         "stats": [_stat_ty(khoanh_pv, _cap_pv), _stat_cl(khoanh_ht, khoanh_pv),
                                   _stat_pct(khoanh_ht, tong_dn_ht, "tổng DN")]},
                    ], num_columns=4)

                    # ── Cảnh báo khi so sánh KH mà không tìm thấy KH ────
                    if _la_kh and tong_dn_pv == 0:
                        st.warning(
                            "⚠️ Không tìm thấy chỉ tiêu khớp trong sheet Kế hoạch giao. "
                            "Kiểm tra lại tên chỉ tiêu trong sheet KH hoặc chọn mốc khác.",
                        )

                else:
                    _render_kpi_grid([
                        {"label": "Tổng dư nợ", "icon": "💰", "value": _to_ty(tong_dn_ht), "precision": 1,
                         "tone": "accent",
                         "stats": [{"v": _fmt_so_vn(tl_nqh, 2) + "%", "c": "NQH"}]},
                        {"label": "TG TT TCTC & TK CN", "icon": "🏧", "value": _to_ty(tien_gui_tt_ht), "precision": 1,
                         "tone": "info",
                         "stats": [_stat_pct(tien_gui_tt_ht, huy_dong_ht, "HĐV")]},
                        {"label": "Vốn UTĐT ĐP", "icon": "🤝", "value": _to_ty(utdt_ht), "precision": 1,
                         "tone": "info",
                         "stats": [_stat_pct(utdt_ht, tong_dn_ht, "tổng DN")]},
                    ], num_columns=3)

                    _render_kpi_grid([
                        {"label": "Dư nợ KHA", "icon": "📋", "value": _to_ty(kha_ht), "precision": 1,
                         "tone": "accent",
                         "stats": [_stat_pct(kha_ht, tong_dn_ht, "tổng DN")]},
                        {"label": "Dư nợ KHB", "icon": "📋", "value": _to_ty(khb_ht), "precision": 1,
                         "tone": "accent",
                         "stats": [_stat_pct(khb_ht, tong_dn_ht, "tổng DN")]},
                        {"label": "NQH (KHA+KHB)", "icon": "⚠️", "value": _to_ty(nqh_ht), "precision": 2,
                         "delta": tl_nqh, "delta_label": "% tổng DN", "delta_color": "inverse",
                         "tone": "error"},
                        {"label": "Nợ khoanh", "icon": "🔒", "value": _to_ty(khoanh_ht), "precision": 1,
                         "tone": "warn",
                         "stats": [_stat_pct(khoanh_ht, tong_dn_ht, "tổng DN")]},
                    ], num_columns=4)

                # ── Bảng chi tiết tất cả chỉ tiêu (hiển thị trực tiếp) ───
                with st.container(border=True):
                    st.markdown("#### 📋 Bảng chi tiết tất cả chỉ tiêu")
                    NHOM_KEYS_LOC = {
                        "Nguồn vốn":         ["Nguồn vốn","Tổng huy động","Tiền gửi","UTĐT","Vốn Trung ương","Vốn TW","HĐV"],
                        "Dư nợ KHA":         ["KHA","Kế hoạch A","GQVL KHA","NSVSMT NT","HSSV",
                                              "hộ nghèo KHA","cận nghèo KHA","thoát nghèo KHA",
                                              "SXKD VKK","XKLĐ","KFW","nhà ở","DTTS","NOXH",
                                              "TN VKK","nhà ở gđ","Quá hạn KHA","Khoanh KHA"],
                        "Dư nợ KHB":         ["KHB","Kế hoạch B","GQVL KHB","NSVSMT NT KHB",
                                              "hộ nghèo KHB","cận nghèo KHB","thoát nghèo KHB",
                                              "DTTS ĐBKK KHB","NOXH100 KHB",
                                              "Quá hạn KHB","Khoanh KHB","Khác KHB","DTTS 2085"],
                        "Vốn an toàn & quỹ": ["Vốn An toàn","Tồn quỹ","Tiền gửi tại NHNN"],
                    }
                    nhom_loc = st.radio(
                        "Lọc nhóm",
                        ["Tất cả"] + list(NHOM_KEYS_LOC.keys()),
                        horizontal=True,
                        key=f"cd_nhom{key_sfx}",
                    )
                    rows_detail: list[dict] = []
                    _match_count = 0  # đếm số chỉ tiêu khớp
                    _SKIP_TIEN_GUI = ("tiền gửi của tổ chức", "tiền gửi tiết kiệm dân cư")
                    for r in db_ht_rows:
                        if r["la_nqh_con"]:
                            continue  # dòng NQH con xử lý riêng
                        _ten_lower = r["ten"].lower()
                        if any(kw in _ten_lower for kw in _SKIP_TIEN_GUI):
                            continue  # bỏ 2 dòng riêng lẻ — gộp thành dòng tính toán
                        val_pv_r = 0.0
                        if db_prev_rows:
                            val_pv_r = _match_prev_row_vnd(r, db_prev_rows, _he_so_pv, _la_kh)
                        val_pm_r = 0.0
                        if db_prev_month_rows:
                            val_pm_r = _match_prev_row_vnd(r, db_prev_month_rows, _he_so_pm, False)
                        if nhom_loc != "Tất cả":
                            kws = NHOM_KEYS_LOC.get(nhom_loc, [])
                            ten_check = (r["cha"] or r["ten"]) if r["la_nqh_con"] else r["ten"]
                            if not any(kw.lower() in ten_check.lower() for kw in kws):
                                continue
                        if val_pv_r > 0:
                            _match_count += 1
                        rows_detail.append(build_row(
                            r["ten"].replace("  NQH: ", "  └ NQH: "),
                            _row_vnd(r, _he_so_ht), val_pv_r, r["la_nqh_con"], val_pm_r,
                        ))
                        # Chèn dòng tính toán ngay sau "Tổng huy động vốn"
                        if (
                            "tổng huy động vốn" in _ten_lower
                            and (not db_prev_rows or tien_gui_tt_pv is not None)
                        ):
                            _val_pv_tg = tien_gui_tt_pv if tien_gui_tt_pv is not None else 0.0
                            _val_pm_tg = tien_gui_tt_pm if db_prev_month_rows else 0.0
                            rows_detail.append(build_row(
                                "TG TT TCTC & TK CN (= HĐV − TK qua Tổ TK&VV)",
                                tien_gui_tt_ht, _val_pv_tg, False, _val_pm_tg,
                            ))
                            if db_prev_rows and _val_pv_tg > 0:
                                _match_count += 1
                    if rows_detail:
                        cols_s = ["Chỉ tiêu", label_pv, label_ht,
                                  "Tăng/giảm so với năm trước", "Tỷ lệ % năm trước",
                                  "Tháng trước", "Tăng/giảm so với tháng trước", "Tỷ lệ % tháng trước"]
                        # Chỉ giữ cột tháng trước khi có dữ liệu
                        if not db_prev_month_rows:
                            cols_s = [c for c in cols_s if "tháng trước" not in c.lower() and "Tháng trước" not in c]
                        df_s = pd.DataFrame(rows_detail)[cols_s].copy()
                        for _col in [label_pv, label_ht, "Tăng/giảm so với năm trước", "Tháng trước", "Tăng/giảm so với tháng trước"]:
                            if _col in df_s.columns:
                                df_s[_col] = df_s[_col].apply(_fmt_vnd_trieu)
                        for _pcol in ["Tỷ lệ % năm trước", "Tỷ lệ % tháng trước"]:
                            if _pcol in df_s.columns:
                                df_s[_pcol] = df_s[_pcol].apply(fmt_pct)
                        hien_thi_dataframe_phan_trang(
                            df_s,
                            key=f"candoi_ss_chitieu{key_sfx}",
                            height=480,
                        )
                        # Badge tỷ lệ khớp dữ liệu so sánh
                        _total = len(rows_detail)
                        if db_prev_rows and _total > 0:
                            _pct_match = round(_match_count / _total * 100)
                            _badge_color = "green" if _pct_match >= 80 else ("orange" if _pct_match >= 40 else "red")
                            st.caption(
                                f"🔄 Khớp dữ liệu so sánh: **{_match_count}/{_total}** chỉ tiêu "
                                f"({_pct_match}%) — "
                                f":{_badge_color}[{'✅ Tốt' if _pct_match >= 80 else ('⚠️ Trung bình' if _pct_match >= 40 else '❌ Thấp — kiểm tra tên chỉ tiêu giữa 2 sheet')}]"
                            )
                    else:
                        st.info("Không có dữ liệu phù hợp.")

        # ──────────────────────────────────────────────────────────────────
        # TAB 2: THEO CHƯƠNG TRÌNH
        # ──────────────────────────────────────────────────────────────────
        elif _cd_sub == 1:
            if db_ht_rows is None:
                st.info("⚠️ Không có dữ liệu.")
            else:
                st.markdown(f"**So sánh dư nợ từng chương trình: {label_pv} vs {label_ht}**")
                rows_ct = []
                for ten_hien, key_ct in _CHUONG_TRINH_CANDOI:
                    if key_ct is None:
                        rows_ct.append({
                            "Chương trình": ten_hien,
                            label_pv: float("nan"), label_ht: float("nan"),
                            "Chênh lệch": float("nan"), "Tỷ lệ %": float("nan"),
                            "NQH hiện tại": float("nan"), "NQH kỳ trước": float("nan"),
                            "_is_header": True, "_ht": 0, "_pv": 0,
                        })
                        continue
                    val_ht_ct  = _lookup_vnd(db_ht_rows, key_ct, _he_so_ht)
                    val_pv_ct  = (
                        _lookup_kh_vnd(db_prev_rows, key_ct, _he_so_pv)
                        if _la_kh and db_prev_rows
                        else _lookup_vnd(db_prev_rows, key_ct, _he_so_pv) if db_prev_rows
                        else 0.0
                    )
                    nqh_ht_ct  = _nqh_con_vnd(db_ht_rows, key_ct, _he_so_ht)
                    nqh_pv_ct  = _nqh_con_vnd(db_prev_rows, key_ct, _he_so_pv) if db_prev_rows else 0.0
                    cl_ct      = val_ht_ct - val_pv_ct
                    tl_ct      = (cl_ct / val_pv_ct * 100) if val_pv_ct else None
                    rows_ct.append({
                        "Chương trình":  ten_hien,
                        label_pv:        val_pv_ct,
                        label_ht:        val_ht_ct,
                        "Chênh lệch":    cl_ct,
                        "Tỷ lệ %":       tl_ct if tl_ct is not None else 0,
                        "NQH hiện tại":  nqh_ht_ct,
                        "NQH kỳ trước":  nqh_pv_ct,
                        "_is_header": False, "_ht": val_ht_ct, "_pv": val_pv_ct,
                    })

                df_ct = pd.DataFrame(rows_ct)
                cols_ct = ["Chương trình", label_pv, label_ht, "Chênh lệch", "Tỷ lệ %", "NQH hiện tại", "NQH kỳ trước"]
                df_ct_view = df_ct[cols_ct].copy()
                for _col in [label_pv, label_ht, "Chênh lệch", "NQH hiện tại", "NQH kỳ trước"]:
                    df_ct_view[_col] = df_ct_view[_col].apply(_fmt_vnd_trieu)
                df_ct_view["Tỷ lệ %"] = df_ct_view["Tỷ lệ %"].apply(fmt_pct)
                hien_thi_dataframe_phan_trang(
                    df_ct_view,
                    key=f"candoi_ct_chuong_trinh{key_sfx}",
                    height=560,
                )

                if db_prev_rows:
                    st.divider()
                    df_ct_loc = df_ct[~df_ct["_is_header"] & (df_ct["_ht"] > 0)]
                    c_tang, c_giam = st.columns(2)
                    with c_tang:
                        st.markdown("**📈 Tăng mạnh nhất (top 8)**")
                        top_tang = (
                            df_ct_loc[df_ct_loc["_ht"] > df_ct_loc["_pv"]]
                            .assign(_cl=lambda x: x["_ht"] - x["_pv"])
                            .nlargest(8, "_cl")
                        )
                        if not top_tang.empty:
                            top_tang["_tl"] = (top_tang["_cl"] / top_tang["_pv"] * 100).round(1)
                            fig_t = px.bar(
                                top_tang, x="_cl", y="Chương trình", orientation="h",
                                text=top_tang["_tl"].apply(lambda x: f"+{x:.1f}%"),
                                color="_cl", color_continuous_scale="Blues",
                            )
                            fig_t.update_traces(textposition="outside")
                            fig_t.update_layout(
                                height=300, margin=dict(l=0, r=60, t=5, b=5),
                                xaxis_title="", yaxis=dict(title="", autorange="reversed"),
                                coloraxis_showscale=False,
                                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                            )
                            st.plotly_chart(fig_t, use_container_width=True)
                    with c_giam:
                        st.markdown("**📉 Giảm mạnh nhất (top 8)**")
                        top_giam = (
                            df_ct_loc[df_ct_loc["_ht"] < df_ct_loc["_pv"]]
                            .assign(_cl=lambda x: x["_ht"] - x["_pv"])
                            .nsmallest(8, "_cl")
                        )
                        if not top_giam.empty:
                            top_giam["_tl"] = (top_giam["_cl"] / top_giam["_pv"] * 100).round(1)
                            fig_g = px.bar(
                                top_giam, x="_cl", y="Chương trình", orientation="h",
                                text=top_giam["_tl"].apply(lambda x: f"{x:.1f}%"),
                                color="_cl", color_continuous_scale="Reds_r",
                            )
                            fig_g.update_traces(textposition="outside")
                            fig_g.update_layout(
                                height=300, margin=dict(l=0, r=60, t=5, b=5),
                                xaxis_title="", yaxis=dict(title="", autorange="reversed"),
                                coloraxis_showscale=False,
                                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                            )
                            st.plotly_chart(fig_g, use_container_width=True)

        # ──────────────────────────────────────────────────────────────────
        # TAB 3: BIỂU ĐỒ SO SÁNH
        # ──────────────────────────────────────────────────────────────────
        elif _cd_sub == 2:
            if db_ht_rows is None:
                st.info("⚠️ Không có dữ liệu.")
            elif not db_prev_rows:
                st.info(
                    "💡 Chọn sheet SO SÁNH khác với sheet HIỆN TẠI (ví dụ M vs Y) "
                    "hoặc upload file kỳ trước để xem biểu đồ so sánh."
                )
            else:
                BD_GROUPS = {
                    "Nguồn vốn": [
                        ("Vốn TW (KHA)",  "Nguồn vốn cân đối từ TW (KHA)"),
                        ("Huy động vốn",  "Tổng huy động vốn"),
                        ("Vốn UTĐT ĐP",  "Nguồn vốn nhận UTĐT tại ĐP"),
                    ],
                    "Dư nợ tổng & phân kỳ": [
                        ("Tổng dư nợ",    "Tổng dư nợ"),
                        ("Dư nợ KHA",     "Dư nợ Kế hoạch A"),
                        ("Dư nợ KHB",     "Dư nợ Kế hoạch B"),
                    ],
                    "Chương trình lớn nhất": [
                        ("GQVL KHA",      "Dư nợ GQVL KHA"),
                        ("NSVSMT NT",     "Dư nợ NSVSMT NT"),
                        ("HSSV HCKK",     "Dư nợ HSSV"),
                        ("SXKD VKK",      "Dư nợ SXKD VKK"),
                        ("GQVL KHB",      "Dư nợ GQVL KHB"),
                        ("NOXH KHA",      "Dư nợ NOXH100 KHA"),
                        ("NOXH KHB",      "Dư nợ NOXH100 KHB"),
                        ("Hộ MTN KHA",    "Dư nợ hộ mới thoát nghèo KHA"),
                        ("Cận nghèo KHA", "Dư nợ hộ cận nghèo KHA"),
                    ],
                }
                chon_bd = st.radio(
                    "Nhóm biểu đồ", list(BD_GROUPS.keys()),
                    horizontal=True, key=f"cd_bd_nhom{key_sfx}",
                )
                items    = BD_GROUPS[chon_bd]
                ten_ng   = [i[0] for i in items]
                val_ht_b = [_to_ty(_lookup_vnd(db_ht_rows, i[1], _he_so_ht)) for i in items]
                val_pv_b = [_to_ty(_lookup_prev_vnd(db_prev_rows, i[1], _he_so_pv, _la_kh)) for i in items]

                def _vn(v: float) -> str:
                    return f"{v:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")

                fig_bd = go.Figure()
                fig_bd.add_bar(
                    name=label_pv, x=ten_ng, y=val_pv_b,
                    marker_color="#90CAF9",
                    text=[_vn(v) for v in val_pv_b],
                    textposition="outside",
                )
                fig_bd.add_bar(
                    name=label_ht, x=ten_ng, y=val_ht_b,
                    marker_color="#1565C0",
                    text=[_vn(v) for v in val_ht_b],
                    textposition="outside",
                )
                fig_bd.update_layout(
                    barmode="group", height=420, yaxis_title="Tỷ đồng",
                    margin=dict(l=0, r=20, t=10, b=10),
                    legend=dict(orientation="h", y=1.08),
                    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                )
                st.plotly_chart(fig_bd, use_container_width=True)



        # ══════════════════════════════════════════════════════════════════
        # XUẤT EXCEL / PDF / IN — SO SÁNH CÂN ĐỐI
        # ══════════════════════════════════════════════════════════════════
        st.divider()
        state = SCMStateManager()
        if db_ht_rows is None:
            st.caption("Xuất file: cần có dữ liệu Điện báo.")
        else:
            df_ex1, df_ex2 = _build_export_frames(
                db_ht_rows,
                db_prev_rows,
                _he_so_ht,
                _he_so_pv,
                _la_kh,
                label_pv,
                label_ht,
                rows_prev_month=db_prev_month_rows,
                he_so_prev_month=_he_so_pm,
            )
            _fn_pv = _safe_export_name_part(label_pv[:20], "Moc_truoc")
            _fn_ht = _safe_export_name_part(label_ht[:20], "Hien_tai")
            _fn_base = f"CanDoi_{_fn_pv}_vs_{_fn_ht}_{datetime.today().strftime('%d%m%Y')}"

            # ── 3 nút: Excel | PDF | In ──
            _bx1, _bx2, _bx3 = st.columns(3)

            # --- Excel ---
            with _bx1:
                if st.button("📥 Xuất Excel", key=f"btn_xuat_cd{key_sfx}", use_container_width=True):
                    try:
                        buf = BytesIO()
                        with pd.ExcelWriter(buf, engine="openpyxl") as _w:
                            df_ex1.to_excel(_w, index=False, sheet_name="Tổng hợp chỉ tiêu")
                            df_ex2.to_excel(_w, index=False, sheet_name="Theo chương trình")
                        state.downloads.set(f"cd_excel{key_sfx}", buf.getvalue(), f"{_fn_base}.xlsx")
                    except Exception as _e:
                        logger.error("xuat_excel_candoi: %s", _e, exc_info=True)
                        st.error(f"Lỗi tạo Excel: {_e}")
                if state.downloads.has(f"cd_excel{key_sfx}"):
                    if st.download_button(
                        "⬇ Tải Excel",
                        data=state.downloads.get_bytes(f"cd_excel{key_sfx}"),
                        file_name=state.downloads.get_filename(f"cd_excel{key_sfx}") or "CanDoi.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key=f"dl_cd_excel{key_sfx}", use_container_width=True,
                    ):
                        state.downloads.clear(f"cd_excel{key_sfx}")

            # --- PDF ---
            with _bx2:
                if st.button("📄 Xuất PDF", key=f"btn_pdf_cd{key_sfx}", use_container_width=True):
                    try:
                        from services.bc_tongquan_service import xuat_pdf_bc
                        _pdf_bytes = xuat_pdf_bc(
                            {"Tổng hợp chỉ tiêu": df_ex1, "Theo chương trình": df_ex2},
                            f"So sánh Cân đối: {label_pv} vs {label_ht}",
                            username,
                        )
                        if not _pdf_bytes:
                            raise RuntimeError("Dịch vụ PDF không trả về dữ liệu.")
                        state.downloads.set(f"cd_pdf{key_sfx}", _pdf_bytes, f"{_fn_base}.pdf")
                    except Exception as _e:
                        logger.error("xuat_pdf_candoi: %s", _e, exc_info=True)
                        st.error(f"Lỗi tạo PDF: {_e}")
                if state.downloads.has(f"cd_pdf{key_sfx}"):
                    if st.download_button(
                        "⬇ Tải PDF",
                        data=state.downloads.get_bytes(f"cd_pdf{key_sfx}"),
                        file_name=state.downloads.get_filename(f"cd_pdf{key_sfx}") or "CanDoi.pdf",
                        mime="application/pdf",
                        key=f"dl_cd_pdf{key_sfx}", use_container_width=True,
                    ):
                        state.downloads.clear(f"cd_pdf{key_sfx}")

            # --- In (HTML print-friendly) ---
            with _bx3:
                if st.button("🖨️ In bảng", key=f"btn_in_cd{key_sfx}", use_container_width=True):
                    try:
                        _html = _build_print_html(df_ex1, df_ex2, label_pv, label_ht, pgd_user, pgd_mode)
                        state.downloads.set(f"cd_html{key_sfx}", _html.encode("utf-8"), f"{_fn_base}.html")
                    except Exception as _e:
                        logger.error("xuat_html_candoi: %s", _e, exc_info=True)
                        st.error(f"Lỗi tạo bản in: {_e}")
                if state.downloads.has(f"cd_html{key_sfx}"):
                    if st.download_button(
                        "⬇ Tải HTML để in",
                        data=state.downloads.get_bytes(f"cd_html{key_sfx}"),
                        file_name=state.downloads.get_filename(f"cd_html{key_sfx}") or "CanDoi.html",
                        mime="text/html",
                        key=f"dl_cd_html{key_sfx}", use_container_width=True,
                    ):
                        state.downloads.clear(f"cd_html{key_sfx}")

        st.divider()
        with st.popover(
            "📖 Hướng dẫn Điện báo",
            help="Mở hướng dẫn sử dụng mà không làm dài trang phân tích.",
        ):
            from pathlib import Path
            _guide = Path(__file__).resolve().parent.parent / "docs" / "HUONG_DAN_DIEN_BAO.md"
            if _guide.exists():
                st.markdown(_guide.read_text(encoding="utf-8"))
