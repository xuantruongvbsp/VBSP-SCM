"""Theo dõi tiến độ PGD điền khảo sát HN/HCN/HTN — đọc từ Google Sheets.

Cấu trúc Google Sheet: mỗi PGD có 1 worksheet riêng (tên = tên PGD).
Mỗi worksheet có cùng template:
  - Hàng 9 (index 8): dòng tổng của PGD
  - Hàng 10–12 (index 9–11): theo từng chương trình
  - Cột E (index 4): Số hộ đang là hộ nghèo
  - Cột F (index 5): Số hộ đang là cận nghèo
Kiểm tra: ô không None/rỗng → đã nhập (kể cả giá trị 0).

Sheet "Nhật ký" (tạo tự động bởi Apps Script onEdit):
  Cột: Thời gian | Đơn vị | Hàng | Cột | Giá trị mới | Người nhập
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st
from streamlit.delta_generator import DeltaGenerator

from logger import get_logger

logger = get_logger(__name__)

from auth import la_phan_he_cn, normalize_role
from config import DS_PGD, DON_VI_CHI_NHANH

_DS_TAT_CA = [DON_VI_CHI_NHANH] + DS_PGD  # 22 đơn vị
from tabs.base_tab import TabContext

# ── Hằng số ──────────────────────────────────────────────────────────────────

SHEET_ID        = "1BRSNwynHAO3FSq5Vsuk3u1WcvJD8asJgi3evuOaDmDw"
SHEET_NHAT_KY   = "Nhật ký"
COT_E_IDX       = 4   # 0-based — "Số hộ đang là hộ nghèo"
COT_F_IDX       = 5   # 0-based — "Số hộ đang là cận nghèo"
DATA_ROW_INDICES = [8, 9, 10, 11]   # hàng 9–12 (0-based)

TEN_COT_E = "Số hộ hộ nghèo (E)"
TEN_COT_F = "Số hộ cận nghèo (F)"

_EMOJI_DU    = "🟢"
_EMOJI_MOT   = "🟡"
_EMOJI_TRONG = "🔴"
_EMOJI_KTT   = "⚫"

# ── Kết nối Google Sheets ─────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _tim_credentials() -> Path:
    candidates = [
        PROJECT_ROOT / "credentials.json",
        PROJECT_ROOT.parent / "credentials.json",
        Path.cwd() / "credentials.json",
        Path("credentials.json"),
    ]
    from config import BASE_DIR as _bd
    candidates.append(_bd / "credentials.json")
    for cand in candidates:
        if cand.exists():
            return cand.resolve()
    raise FileNotFoundError(
        f"Không tìm thấy credentials.json. Đã thử: {[str(c) for c in candidates]}"
    )


def _ket_noi_gsheet():
    _p = _tim_credentials()
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    try:
        import gspread
    except ImportError:
        raise RuntimeError("Thiếu thư viện gspread. Cài đặt: pip install gspread google-auth")
    try:
        return gspread.service_account(filename=str(_p), scopes=scope)
    except Exception as e:
        logger.error("_ket_noi_gsheet: fallback oauth2client — %s", e, exc_info=True)
        try:
            from oauth2client.service_account import ServiceAccountCredentials
        except ImportError:
            raise RuntimeError("Không thể kết nối GSheet: cần cài google-auth hoặc oauth2client.")
        creds = ServiceAccountCredentials.from_json_keyfile_name(str(_p), scope)
        return gspread.authorize(creds)


_ALIAS_HOI_SO = {
    "hội sở cn đồng nai", "hoi so cn dong nai",
    "hội sở chi nhánh", "hội sở", "hoi so",
}

def _chuan_hoa_ten_pgd(raw: str) -> str:
    """Chuẩn hóa tên PGD về dạng 'PGD Xxx Yyy'; map alias Hội sở về DON_VI_CHI_NHANH."""
    if not isinstance(raw, str) or not raw.strip():
        return raw
    s = raw.strip()
    if s.lower() in _ALIAS_HOI_SO:
        return DON_VI_CHI_NHANH
    for prefix in ("Phòng giao dịch ", "Phong giao dich ", "PGD ", "pgd "):
        if s.lower().startswith(prefix.lower()):
            return "PGD " + s[len(prefix):].strip()
    s_upper = s.upper()
    for prefix_upper in ("PHÒNG GIAO DỊCH ", "PHONG GIAO DICH "):
        if s_upper.startswith(prefix_upper):
            return "PGD " + s[len(prefix_upper):].strip().title()
    return s


def _co_gia_tri(val) -> bool:
    """True nếu ô đã được điền (kể cả giá trị 0)."""
    if val is None:
        return False
    if isinstance(val, str):
        return val.strip() != ""
    return True


# ── Đọc dữ liệu cột E/F từng worksheet PGD ───────────────────────────────────

@st.cache_data(ttl=300)
def _doc_khao_sat() -> dict:
    """Fetch dữ liệu từng worksheet PGD.

    Trả về {"data": {pgd: (has_e, has_f, val_e, val_f)}} hoặc {"error": msg}.
    """
    try:
        client = _ket_noi_gsheet()
        spreadsheet = client.open_by_key(SHEET_ID)
        all_ws = spreadsheet.worksheets()
    except FileNotFoundError as e:
        return {"error": str(e)}
    except Exception as e:
        logger.error("_doc_khao_sat: %s", e, exc_info=True)
        return {"error": f"Lỗi kết nối Google Sheets: {e}"}

    ws_map: dict = {_chuan_hoa_ten_pgd(ws.title): ws for ws in all_ws}

    ket_qua: dict[str, tuple] = {}
    for pgd in _DS_TAT_CA:
        ws = ws_map.get(pgd) or next(
            (v for k, v in ws_map.items() if k.upper() == pgd.upper()), None
        )
        if ws is None:
            ket_qua[pgd] = (None, None, "", "")
            continue

        try:
            data = ws.get_all_values()
        except Exception as e:
            logger.warning("_doc_khao_sat: lỗi đọc sheet '%s' — %s", pgd, e)
            ket_qua[pgd] = (None, None, "", f"Lỗi đọc: {e}")
            continue

        has_e, has_f = False, False
        vals_e: list[str] = []
        vals_f: list[str] = []

        for row_idx in DATA_ROW_INDICES:
            if row_idx >= len(data):
                continue
            row = data[row_idx]
            val_e = row[COT_E_IDX] if len(row) > COT_E_IDX else None
            val_f = row[COT_F_IDX] if len(row) > COT_F_IDX else None
            if _co_gia_tri(val_e):
                has_e = True
                vals_e.append(str(val_e).strip())
            if _co_gia_tri(val_f):
                has_f = True
                vals_f.append(str(val_f).strip())

        ket_qua[pgd] = (has_e, has_f, ", ".join(vals_e), ", ".join(vals_f))

    return {"data": ket_qua}


# ── Đọc sheet Nhật ký ─────────────────────────────────────────────────────────

@st.cache_data(ttl=300)
def _doc_nhat_ky() -> dict[str, dict]:
    """Đọc sheet 'Nhật ký'; trả về {pgd: {"nguoi": str, "thoi_gian": str}}.

    Mỗi PGD giữ bản ghi mới nhất (dòng cuối cùng trong log).
    Trả về {} nếu sheet chưa tồn tại hoặc lỗi kết nối.
    """
    try:
        client = _ket_noi_gsheet()
        spreadsheet = client.open_by_key(SHEET_ID)
        try:
            log_ws = spreadsheet.worksheet(SHEET_NHAT_KY)
        except Exception:
            return {}   # sheet chưa được tạo bởi Apps Script
        data = log_ws.get_all_values()
    except Exception as e:
        logger.warning("_doc_nhat_ky: %s", e)
        return {}

    if len(data) < 2:
        return {}

    # Header: Thời gian(0) | Đơn vị(1) | Hàng(2) | Cột(3) | Giá trị(4) | Người nhập(5)
    result: dict[str, dict] = {}
    for row in data[1:]:
        if len(row) < 6:
            continue
        pgd        = _chuan_hoa_ten_pgd(row[1].strip())
        thoi_gian  = row[0].strip()
        nguoi_nhap = row[5].strip()
        if not pgd or pgd not in _DS_TAT_CA:
            continue
        # Ghi đè liên tục → dòng cuối = mới nhất
        result[pgd] = {"nguoi": nguoi_nhap, "thoi_gian": thoi_gian}

    return result


# ── Render ────────────────────────────────────────────────────────────────────

def _trang_thai(has_e, has_f) -> tuple[str, str]:
    if has_e is None and has_f is None:
        return _EMOJI_KTT, "Không tìm thấy sheet"
    if has_e and has_f:
        return _EMOJI_DU, "Đã nhập đủ"
    if has_e or has_f:
        return _EMOJI_MOT, "Nhập một phần"
    return _EMOJI_TRONG, "Chưa nhập"


def _render_metrics(rows_result: list[dict]) -> None:
    cnt_du   = sum(1 for r in rows_result if _EMOJI_DU    in r["Trạng thái"])
    cnt_mot  = sum(1 for r in rows_result if _EMOJI_MOT   in r["Trạng thái"])
    cnt_chua = sum(1 for r in rows_result if _EMOJI_TRONG in r["Trạng thái"])
    cnt_ktt  = sum(1 for r in rows_result if _EMOJI_KTT   in r["Trạng thái"])

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Tổng PGD",                    len(rows_result))
    c2.metric(f"{_EMOJI_DU}  Đã nhập đủ",    cnt_du)
    c3.metric(f"{_EMOJI_MOT}  Nhập 1 phần",  cnt_mot)
    c4.metric(f"{_EMOJI_TRONG} Chưa nhập",   cnt_chua)
    c5.metric(f"{_EMOJI_KTT}  Không tìm thấy", cnt_ktt)


def _render_bang(ket_qua: dict, nhat_ky: dict, ds_pgd: list) -> None:
    co_nhat_ky = bool(nhat_ky)
    rows_result = []

    for pgd in ds_pgd:
        has_e, has_f, val_e, val_f = ket_qua.get(pgd, (None, None, "", ""))
        emoji, label = _trang_thai(has_e, has_f)

        log = nhat_ky.get(pgd, {})
        row: dict = {
            "Đơn vị":     pgd,
            TEN_COT_E:    val_e if has_e else ("—" if has_e is False else ""),
            TEN_COT_F:    val_f if has_f else ("—" if has_f is False else ""),
            "Trạng thái": f"{emoji} {label}",
        }
        if co_nhat_ky:
            row["Người nhập"] = log.get("nguoi", "")
            row["Thời gian"]  = log.get("thoi_gian", "")

        rows_result.append(row)

    _render_metrics(rows_result)
    st.dataframe(pd.DataFrame(rows_result), hide_index=True, use_container_width=True)


def render(tab: DeltaGenerator = None, **kwargs) -> None:
    """Render tab theo dõi khảo sát HN/HCN/HTN."""
    role_raw = str(kwargs.get("role", "user") or "user")
    role     = normalize_role(role_raw)
    is_cn    = la_phan_he_cn(role)
    pgd_user = kwargs.get("pgd_user")

    ctx = tab if tab is not None else st.container()
    with ctx:
        col_title, col_btn = st.columns([8, 1])
        with col_title:
            st.subheader("📋 Theo dõi Khảo sát HN / HCN / HTN")
        with col_btn:
            if st.button("🔄", help="Làm mới dữ liệu từ Google Sheets",
                         key="khaosat_btn_refresh", use_container_width=True):
                st.cache_data.clear()
                st.rerun()

        result = _doc_khao_sat()

        if result.get("error"):
            st.error(f"❌ {result['error']}")
            with st.expander("Hướng dẫn khắc phục"):
                st.markdown(
                    "1. Đảm bảo file `credentials.json` (Service Account) có trong thư mục gốc dự án.\n"
                    "2. Chia sẻ spreadsheet với email `client_email` trong file credentials (quyền **Viewer**).\n"
                    "3. Kiểm tra kết nối mạng và thử lại."
                )
            return

        ket_qua: dict = result.get("data", {})
        nhat_ky: dict = _doc_nhat_ky()

        ds_pgd = _DS_TAT_CA if is_cn else ([pgd_user] if pgd_user else [])
        if not ds_pgd:
            st.info("ℹ️ Không xác định được đơn vị cần hiển thị.")
            return

        if not nhat_ky:
            st.info(
                "ℹ️ Chưa có dữ liệu nhật ký — cột **Người nhập** và **Thời gian** sẽ hiển thị "
                "sau khi thiết lập Apps Script trong Google Sheets."
            )

        _render_bang(ket_qua, nhat_ky, ds_pgd)
        st.caption(
            "Dữ liệu từ Google Sheets · Tự động cập nhật mỗi 5 phút · "
            f"Kiểm tra: **{TEN_COT_E}** và **{TEN_COT_F}** (hàng 9–12 mỗi worksheet PGD)"
        )
