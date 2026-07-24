"""report_submission_service.py — Service lõi cho luồng PGD nộp báo cáo về Chi nhánh.

Là nơi DUY NHẤT xử lý logic nghiệp vụ:
  - Đọc dữ liệu từ Google Sheets.
  - Chuẩn hóa tên PGD và dữ liệu.
  - Đọc/ghi deadline config và manual override.
  - Phân loại trạng thái nộp báo cáo.
  - Sinh ma trận tiến độ và danh sách cần nhắc.
  - Kiểm tra sức khỏe nguồn dữ liệu.

Dùng chung giữa:
  - tabs/tab_tien_do_nop.py  (UI)
  - scripts/nhac_deadline.py (scheduler Telegram)
"""

from __future__ import annotations

import re
import sys
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

import pandas as pd

import db
from config import DS_PGD, DON_VI_CHI_NHANH, TIENDO_BAOCAO_SHEET_ID, TIENDO_BAOCAO_SHEET_TAB
from logger import get_logger

logger = get_logger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

SHEET_ID = TIENDO_BAOCAO_SHEET_ID
SHEET_TAB = TIENDO_BAOCAO_SHEET_TAB
COT = ["thoi_gian", "email", "ten_pgd", "loai_bao_cao",
       "ky_bao_cao", "noi_dung", "file_dinh_kem", "ho_ten"]

DS_PGD_ALL = [DON_VI_CHI_NHANH] + DS_PGD

EMOJI = {"dung_han": "🟢", "tre": "🟡", "chua_nop": "🔴", "da_nop": "⚪", "thieu_file": "⚠️"}
LABEL = {"dung_han": "Đúng hạn", "tre": "Trễ hạn", "chua_nop": "Chưa nộp", "da_nop": "Đã nộp", "thieu_file": "Thiếu file"}

# KV keys
KV_DEADLINE = "bao_cao_deadline_config"
KV_MANUAL = "manual_nop_tdn"
KV_MANUAL_AUDIT = "manual_nop_tdn_audit"
KV_ALLOWLIST = "telegram_deadline_bc_allowlist"
KV_ARCHIVE = "bao_cao_archive_config"

_YEAR_RANGE_RE = re.compile(r"\b\d{4}\s*[-–]\s*\d{4}\b", re.IGNORECASE)

BASE_DIR = Path(__file__).resolve().parent.parent

_GSHEET_READ_RETRIES = 3
_GSHEET_READ_BACKOFF_S = 1.5
_LAST_GSHEET_ERROR: str | None = None

# ── Kết nối Google Sheets ─────────────────────────────────────────────────────

def _tim_credentials() -> Path:
    """Tìm file credentials.json cho Google Sheets."""
    candidates = [
        BASE_DIR / "credentials.json",
        BASE_DIR.parent / "credentials.json",
        Path.cwd() / "credentials.json",
        Path("credentials.json"),
    ]
    for cand in candidates:
        if cand.exists():
            return cand.resolve()
    raise FileNotFoundError(
        f"Không tìm thấy credentials.json. Đã thử: {[str(c) for c in candidates]}"
    )


def _ket_noi_gsheet():
    """Kết nối Google Sheets bằng Service Account, có fallback oauth2client."""
    try:
        import gspread
    except ImportError:
        raise RuntimeError("Thiếu thư viện gspread. Cài: pip install gspread google-auth")

    creds_path = str(_tim_credentials())
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    try:
        return gspread.service_account(filename=creds_path, scopes=scope)
    except Exception as e:
        logger.warning("_ket_noi_gsheet: fallback oauth2client — %s", e, exc_info=True)
        try:
            from oauth2client.service_account import ServiceAccountCredentials
        except ImportError:
            raise RuntimeError(
                "Không thể kết nối GSheet: cần cài google-auth hoặc oauth2client."
            )
        creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)
        return gspread.authorize(creds)


def chuan_hoa_ten_pgd(raw: str) -> str:
    """Chuẩn hóa tên PGD từ Google Form: bỏ prefix 'Phòng giao dịch' / 'PGD'."""
    if not isinstance(raw, str) or not raw.strip():
        return raw
    s = raw.strip()
    for prefix in ("Phòng giao dịch ", "Phong giao dich ", "PGD ", "pgd "):
        if s.lower().startswith(prefix.lower()):
            return "PGD " + s[len(prefix):].strip()
    return s


# ── Đọc dữ liệu GSheet ───────────────────────────────────────────────────────

def lay_loi_doc_gsheet_gan_nhat() -> str | None:
    """Lỗi đọc GSheet lần gần nhất — dùng khi DataFrame trả về rỗng."""
    return _LAST_GSHEET_ERROR


def _la_loi_gsheet_tam_thoi(exc: BaseException) -> bool:
    msg = str(exc).lower()
    markers = (
        "500", "502", "503", "504", "429",
        "internal error", "backend error", "rate limit",
        "service unavailable", "temporarily unavailable",
    )
    return any(m in msg for m in markers)


def _goi_y_loi_gsheet(exc: BaseException) -> str:
    if _la_loi_gsheet_tam_thoi(exc):
        return " — lỗi tạm thời phía Google, thử 🔄 Làm mới sau 1–2 phút"
    return ""


def _gsheet_request_json(
    client_like: Any,
    method: str,
    url: str,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Gọi Google Sheets REST API qua adapter tương thích nhiều version gspread."""
    candidates = [client_like]
    nested = getattr(client_like, "client", None)
    if nested is not None:
        candidates.append(nested)

    for candidate in candidates:
        if candidate is None:
            continue

        request_fn = getattr(candidate, "request", None)
        if callable(request_fn):
            return request_fn(method, url, params=params).json()

        http_client = getattr(candidate, "http_client", None)
        http_request = getattr(http_client, "request", None)
        if callable(http_request):
            return http_request(method, url, params=params).json()

        session = getattr(candidate, "session", None)
        session_request = getattr(session, "request", None)
        if callable(session_request):
            resp = session_request(method=method, url=url, params=params)
            resp.raise_for_status()
            return resp.json()

    raise AttributeError("GSpread client không hỗ trợ request/http_client/session.request")


def _doc_raw_values_sheet(
    sheet_id: str = SHEET_ID,
    tab: str = SHEET_TAB,
) -> list[list[str]]:
    """Đọc toàn bộ ô trên 1 tab — REST API v4 + retry khi Google trả 5xx/429."""
    global _LAST_GSHEET_ERROR
    last_err: Exception | None = None
    for attempt in range(_GSHEET_READ_RETRIES):
        try:
            client = _ket_noi_gsheet()
            range_path = quote(tab, safe="!")
            payload = _gsheet_request_json(
                client,
                "get",
                f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}/values/{range_path}",
            )
            _LAST_GSHEET_ERROR = None
            return payload.get("values", []) or []
        except Exception:
            last_err = sys.exc_info()[1]
            if (
                isinstance(last_err, BaseException)
                and _la_loi_gsheet_tam_thoi(last_err)
                and attempt < _GSHEET_READ_RETRIES - 1
            ):
                logger.warning(
                    "_doc_raw_values_sheet: attempt %d/%d tạm thời — %s",
                    attempt + 1,
                    _GSHEET_READ_RETRIES,
                    last_err,
                )
                time.sleep(_GSHEET_READ_BACKOFF_S * (attempt + 1))
                continue
            logger.error(
                "_doc_raw_values_sheet: đọc sheet thất bại — %s",
                last_err,
                exc_info=True,
            )
            break
    _LAST_GSHEET_ERROR = (
        "{}: {}{}".format(type(last_err).__name__, last_err, _goi_y_loi_gsheet(last_err))
        if last_err
        else "Không đọc được GSheet"
    )
    if last_err:
        raise last_err
    return []


def kiem_tra_ket_noi_gsheet() -> tuple[bool, str]:
    """Kiểm tra credentials + đọc thử sheet TIENDO_BAOCAO."""
    try:
        cred_path = _tim_credentials()
    except FileNotFoundError as e:
        return False, str(e)
    except Exception as e:
        logger.error("kiem_tra_ket_noi_gsheet: credentials — %s", e, exc_info=True)
        return False, f"Lỗi credentials: {e}"

    try:
        data = _doc_raw_values_sheet()
        return True, f"OK — {cred_path.name}/{SHEET_TAB}: {len(data)} dòng"
    except Exception as e:
        logger.error("kiem_tra_ket_noi_gsheet: %s", e, exc_info=True)
        return False, f"{type(e).__name__}: {e}{_goi_y_loi_gsheet(e)}"


def doc_du_lieu_gsheet() -> pd.DataFrame:
    """Đọc dữ liệu nộp báo cáo từ Google Sheets (không cache).

    Dùng cho cả UI và scheduler.
    """
    try:
        data = _doc_raw_values_sheet()
        if len(data) <= 1:
            return pd.DataFrame(columns=COT)
        df = pd.DataFrame([r[:len(COT)] for r in data[1:]], columns=COT)
        df["ten_pgd"] = df["ten_pgd"].apply(chuan_hoa_ten_pgd)
        df["thoi_gian"] = pd.to_datetime(df["thoi_gian"], dayfirst=True, errors="coerce")
        return df
    except Exception as e:
        logger.error("doc_du_lieu_gsheet: %s", e, exc_info=True)
        global _LAST_GSHEET_ERROR
        if not _LAST_GSHEET_ERROR:
            _LAST_GSHEET_ERROR = f"{type(e).__name__}: {e}{_goi_y_loi_gsheet(e)}"
        return pd.DataFrame(columns=COT)


# ── Deadline config ───────────────────────────────────────────────────────────

def doc_deadline_config() -> dict[str, str]:
    """Đọc cấu hình deadline: {loai_bao_cao: 'YYYY-MM-DD'}.

    Tự normalize từ định dạng cũ (dict lồng).
    """
    raw = db.doc_kv(KV_DEADLINE) or {}
    normalized: dict[str, str] = {}
    for key, val in raw.items():
        if isinstance(val, dict):
            vals = [v for v in val.values() if isinstance(v, str)]
            if vals:
                normalized[key] = vals[0]
        elif isinstance(val, str):
            normalized[key] = val
    return normalized


def luu_deadline_config(cfg: dict, username: str) -> None:
    """Lưu cấu hình deadline vào kv_store."""
    db.ghi_kv(KV_DEADLINE, cfg, username)
    db.ghi_audit(username, "luu_deadline_bao_cao", f"{len(cfg)} deadline đã lưu")


def doc_luu_tru_config() -> dict[str, dict[str, Any]]:
    """Đọc danh mục loại báo cáo đã hoàn thành và đưa vào lưu trữ."""
    raw = db.doc_kv(KV_ARCHIVE) or {}
    if not isinstance(raw, dict):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for key, value in raw.items():
        ten = _chuan_hoa_ten_loai(key)
        if not ten:
            continue
        meta = dict(value) if isinstance(value, dict) else {}
        meta.setdefault("ten_hien_thi", ten)
        meta.setdefault("ten_theo_doi", ten)
        result[ten] = meta
    return result


def _tap_ten_luu_tru(config: dict[str, dict[str, Any]] | None = None) -> set[str]:
    cfg = config if config is not None else doc_luu_tru_config()
    names: set[str] = set()
    for key, meta in cfg.items():
        for value in (
            key,
            meta.get("ten_hien_thi", "") if isinstance(meta, dict) else "",
            meta.get("ten_theo_doi", "") if isinstance(meta, dict) else "",
        ):
            normalized = _chuan_hoa_ten_loai(value).casefold()
            if normalized:
                names.add(normalized)
    return names


def la_loai_bao_cao_luu_tru(
    ten_loai: str,
    config: dict[str, dict[str, Any]] | None = None,
) -> bool:
    """Kiểm tra một tên Form/tracked key có thuộc danh mục lưu trữ không."""
    return _chuan_hoa_ten_loai(ten_loai).casefold() in _tap_ten_luu_tru(config)


def loc_du_lieu_luu_tru(
    df: pd.DataFrame,
    config: dict[str, dict[str, Any]] | None = None,
    *,
    archived: bool,
) -> pd.DataFrame:
    """Lọc dòng Google Form đang hoạt động hoặc đã lưu trữ mà không xóa dữ liệu gốc."""
    if df is None or df.empty or "loai_bao_cao" not in df.columns:
        return df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame(columns=COT)
    names = _tap_ten_luu_tru(config)
    mask = df["loai_bao_cao"].apply(
        lambda value: _chuan_hoa_ten_loai(value).casefold() in names
    )
    return df.loc[mask if archived else ~mask].copy()


def loc_deadline_dang_hoat_dong(
    deadline_cfg: dict[str, str],
    config: dict[str, dict[str, Any]] | None = None,
) -> dict[str, str]:
    """Loại deadline thuộc báo cáo lưu trữ không được tham gia ma trận/nhắc hạn."""
    return {
        key: value
        for key, value in deadline_cfg.items()
        if not la_loai_bao_cao_luu_tru(key, config)
    }


def luu_tru_loai_bao_cao(
    ten_hien_thi: str,
    username: str,
    ten_theo_doi: str | None = None,
) -> dict[str, Any]:
    """Lưu trữ một loại báo cáo, đồng thời gỡ deadline để dừng nhắc tự động."""
    ten_hien = _chuan_hoa_ten_loai(ten_hien_thi)
    ten_track = _chuan_hoa_ten_loai(ten_theo_doi or ten_hien)
    if not ten_hien:
        raise ValueError("Tên loại báo cáo không được để trống.")

    deadline_cfg = doc_deadline_config()
    deadline_cu = deadline_cfg.pop(ten_track, None)
    if ten_hien != ten_track:
        deadline_cu = deadline_cfg.pop(ten_hien, None) or deadline_cu

    archive_cfg = doc_luu_tru_config()
    archive_cfg[ten_hien] = {
        "ten_hien_thi": ten_hien,
        "ten_theo_doi": ten_track,
        "deadline_cu": deadline_cu or "",
        "luu_tru_luc": datetime.now().isoformat(),
        "luu_tru_boi": username,
    }

    db.ghi_kv(KV_DEADLINE, deadline_cfg, username)
    db.ghi_kv(KV_ARCHIVE, archive_cfg, username)
    db.ghi_audit(
        username,
        "luu_tru_bao_cao",
        f"Lưu trữ '{ten_hien}'; gỡ deadline={bool(deadline_cu)}",
    )
    return archive_cfg[ten_hien]


def khoi_phuc_loai_bao_cao(ten_luu_tru: str, username: str) -> bool:
    """Bỏ trạng thái lưu trữ; deadline cũ không tự bật lại để tránh nhắc quá hạn."""
    archive_cfg = doc_luu_tru_config()
    target_norm = _chuan_hoa_ten_loai(ten_luu_tru).casefold()
    key = next(
        (
            item_key
            for item_key, meta in archive_cfg.items()
            if target_norm
            in {
                _chuan_hoa_ten_loai(item_key).casefold(),
                _chuan_hoa_ten_loai(meta.get("ten_hien_thi", "")).casefold(),
                _chuan_hoa_ten_loai(meta.get("ten_theo_doi", "")).casefold(),
            }
        ),
        None,
    )
    if key is None:
        return False
    meta = archive_cfg.pop(key)
    db.ghi_kv(KV_ARCHIVE, archive_cfg, username)
    db.ghi_audit(
        username,
        "khoi_phuc_bao_cao",
        f"Khôi phục '{meta.get('ten_hien_thi', key)}'; chưa bật lại deadline",
    )
    return True


def _chuan_hoa_ten_loai(ten: str) -> str:
    """Chuẩn hóa tên loại báo cáo để so sánh (không đổi giá trị lưu)."""
    return re.sub(r"\s+", " ", str(ten or "").strip())


def _ten_loai_khong_nam(ten: str) -> str:
    """Bỏ mọi giai đoạn năm trong chuỗi để so khớp tên báo cáo."""
    s = _chuan_hoa_ten_loai(ten)
    return _chuan_hoa_chuoi_so_khop(_YEAR_RANGE_RE.sub(" ", s))


def _chuan_hoa_chuoi_so_khop(ten: str) -> str:
    """Chuẩn hóa chuỗi để so khớp mềm: uppercase, bỏ dấu câu, gộp khoảng trắng."""
    s = _chuan_hoa_ten_loai(ten).upper()
    s = re.sub(r"[^\w\s]", " ", s, flags=re.UNICODE)
    return re.sub(r"\s+", " ", s).strip()


def _tim_ten_form_goi_y(
    ten_theo_doi: str,
    ds_loai_gsheet: list[str],
) -> tuple[str, str]:
    """Tìm tên trên Form tương ứng với loại đang theo dõi.

    Ưu tiên:
      1. Khớp exact sau khi bỏ giai đoạn năm.
      2. Khớp containment sau khi bỏ giai đoạn năm và chuẩn hóa dấu câu.
    Chỉ trả gợi ý khi có đúng 1 candidate rõ ràng để tránh match nhầm.
    """
    ten_norm = _chuan_hoa_ten_loai(ten_theo_doi)
    base = _ten_loai_khong_nam(ten_theo_doi)
    if not base:
        return "", "khong_co_tren_form"

    gsheet_map: dict[str, str] = {}
    for item in ds_loai_gsheet:
        raw = _chuan_hoa_ten_loai(item)
        if raw and raw not in gsheet_map:
            gsheet_map[raw] = raw

    exact_matches: list[str] = []
    loose_matches: list[str] = []
    for g_norm, g_display in gsheet_map.items():
        if g_norm == ten_norm:
            continue
        base_g = _ten_loai_khong_nam(g_norm)
        if not base_g:
            continue
        if base_g == base:
            exact_matches.append(g_display)
            continue
        if base in base_g or base_g in base:
            loose_matches.append(g_display)

    if len(exact_matches) == 1:
        return exact_matches[0], "khac_giai_doan_nam"
    if len(loose_matches) == 1:
        return loose_matches[0], "gan_dung_ten_goc"
    return "", "khong_co_tren_form"


def xay_dung_danh_muc_theo_doi(
    deadline_cfg: dict[str, str],
    ds_loai_gsheet: list[str],
) -> dict[str, Any]:
    """Xây danh mục theo dõi hiệu lực, ưu tiên tên đang xuất hiện trên Form.

    Không tự ghi vào kv_store. Chỉ tạo mapping runtime để:
      - match đúng dữ liệu GSheet dù tên đã đổi giai đoạn năm,
      - hiển thị UI theo tên Form khi có thể,
      - không đòi user phải bấm "Liên kết" thì hệ thống mới chạy đúng.
    """
    tracked_keys = sorted(deadline_cfg.keys())
    alias_to_tracked: dict[str, str] = {}
    tracked_to_display: dict[str, str] = {}

    for tracked in tracked_keys:
        alias_to_tracked[_chuan_hoa_ten_loai(tracked)] = tracked
        tracked_to_display[tracked] = tracked

    ds_lech = phat_hien_ten_lech_ten(deadline_cfg, ds_loai_gsheet)
    for item in ds_lech:
        tracked = item["ten_theo_doi"]
        ten_form = item.get("ten_form") or ""
        if not ten_form:
            continue
        form_norm = _chuan_hoa_ten_loai(ten_form)
        # Tránh ghi đè alias đang trỏ đến tracked key khác.
        # VD: cả "KHTD 2023-2026" và "KHTD 2027-2030" đều được theo dõi —
        #     auto-link không được map "KHTD 2027-2030" → "KHTD 2023-2026".
        existing = alias_to_tracked.get(form_norm)
        if existing is not None and existing != tracked:
            continue
        alias_to_tracked[form_norm] = tracked
        tracked_to_display[tracked] = ten_form

    display_to_tracked: dict[str, str] = {}
    for tracked in tracked_keys:
        display = tracked_to_display.get(tracked, tracked)
        if display in display_to_tracked and display_to_tracked[display] != tracked:
            tracked_to_display[tracked] = tracked
            display = tracked
        display_to_tracked[display] = tracked

    ds_loai_chua_cai: list[str] = []
    for loai in sorted({_chuan_hoa_ten_loai(x): x for x in ds_loai_gsheet if x}.values()):
        if _chuan_hoa_ten_loai(loai) not in alias_to_tracked:
            ds_loai_chua_cai.append(loai)

    display_cfg = {
        tracked_to_display.get(tracked, tracked): deadline_cfg[tracked]
        for tracked in tracked_keys
    }

    return {
        "tracked_keys": tracked_keys,
        "display_keys": sorted(display_to_tracked.keys()),
        "alias_to_tracked": alias_to_tracked,
        "tracked_to_display": tracked_to_display,
        "display_to_tracked": display_to_tracked,
        "display_cfg": display_cfg,
        "ds_loai_chua_cai": ds_loai_chua_cai,
        "ds_lech": ds_lech,
    }


def _gan_khoa_theo_doi(df: pd.DataFrame, deadline_cfg: dict[str, str]) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Thêm khóa theo dõi nội bộ để match dữ liệu GSheet với deadline config."""
    if df is None:
        df = pd.DataFrame(columns=COT)
    df = df.copy()
    ds_loai_gsheet = sorted(df["loai_bao_cao"].dropna().unique().tolist()) if "loai_bao_cao" in df.columns else []
    dm = xay_dung_danh_muc_theo_doi(deadline_cfg, ds_loai_gsheet)
    alias_to_tracked = dm["alias_to_tracked"]

    if "loai_bao_cao" not in df.columns:
        df["_loai_theo_doi"] = pd.Series(dtype="object")
        df["_loai_hien_thi"] = pd.Series(dtype="object")
        return df, dm

    df["_loai_theo_doi"] = df["loai_bao_cao"].apply(
        lambda x: alias_to_tracked.get(_chuan_hoa_ten_loai(x), _chuan_hoa_ten_loai(x))
    )
    df["_loai_hien_thi"] = df["_loai_theo_doi"].map(dm["tracked_to_display"]).fillna(df["loai_bao_cao"])
    return df, dm


def phat_hien_ten_lech_ten(
    deadline_cfg: dict[str, str],
    ds_loai_gsheet: list[str],
) -> list[dict[str, str]]:
    """Tìm loại đang theo dõi không khớp tên trên Google Form.

    Returns:
        list dict: ten_theo_doi, ten_form (gợi ý hoặc ""), ly_do
    """
    if not deadline_cfg:
        return []

    gsheet_set = {_chuan_hoa_ten_loai(x) for x in ds_loai_gsheet if x}
    ket_qua: list[dict[str, str]] = []

    for ten_theo_doi in sorted(deadline_cfg.keys()):
        ten_norm = _chuan_hoa_ten_loai(ten_theo_doi)
        if ten_norm in gsheet_set:
            continue

        goi_y, ly_do = _tim_ten_form_goi_y(ten_theo_doi, ds_loai_gsheet)

        ket_qua.append({
            "ten_theo_doi": ten_theo_doi,
            "ten_form": goi_y,
            "ly_do": ly_do,
        })

    return ket_qua


def _migrate_allowlist_loai(ten_cu: str, ten_moi: str, username: str) -> bool:
    """Đổi tên loại trong telegram_deadline_bc_allowlist nếu có."""
    raw = db.doc_kv(KV_ALLOWLIST)
    if raw is None:
        return False
    if not isinstance(raw, list):
        return False

    da_doi = False
    ds_moi: list[str] = []
    for item in raw:
        loai = _chuan_hoa_ten_loai(str(item))
        if loai == _chuan_hoa_ten_loai(ten_cu):
            ds_moi.append(ten_moi)
            da_doi = True
        else:
            ds_moi.append(item)  # giữ nguyên item gốc, không chuẩn hóa
    if da_doi:
        db.ghi_kv(KV_ALLOWLIST, ds_moi, username)
        db.ghi_audit(
            username,
            "telegram_deadline_bc_allowlist",
            f"Đổi tên allowlist: {ten_cu} → {ten_moi}",
        )
    return da_doi


def doi_ten_loai_theo_doi(
    ten_cu: str,
    ten_moi: str,
    username: str,
) -> dict[str, Any]:
    """Đổi key loại báo cáo trong deadline + manual log + Telegram allowlist.

    Dùng khi tên trên Form khác tên đã cài theo dõi (VD: đổi giai đoạn năm).
  """
    ten_cu = _chuan_hoa_ten_loai(ten_cu)
    ten_moi = _chuan_hoa_ten_loai(ten_moi)
    ket_qua: dict[str, Any] = {
        "ok": False,
        "msg": "",
        "so_manual_cap_nhat": 0,
        "allowlist_cap_nhat": False,
    }

    if not ten_cu or not ten_moi:
        ket_qua["msg"] = "Tên cũ và tên mới không được để trống."
        return ket_qua
    if ten_cu == ten_moi:
        ket_qua["msg"] = "Tên cũ và tên mới giống nhau."
        return ket_qua

    cfg = doc_deadline_config()
    if ten_cu not in cfg:
        ket_qua["msg"] = f"Không tìm thấy loại đang theo dõi: {ten_cu}"
        return ket_qua
    if ten_moi in cfg:
        ket_qua["msg"] = f"Tên mới đã tồn tại trong danh mục theo dõi: {ten_moi}"
        return ket_qua

    dl = cfg.pop(ten_cu)
    cfg[ten_moi] = dl
    luu_deadline_config(cfg, username)

    manual_raw = doc_manual_log_raw()
    so_manual = 0
    for entry in manual_raw:
        if not isinstance(entry, dict):
            continue
        if _chuan_hoa_ten_loai(str(entry.get("loai", ""))) == ten_cu:
            entry["loai"] = ten_moi
            so_manual += 1
    if so_manual:
        luu_manual_log(manual_raw, username)

    allowlist_ok = _migrate_allowlist_loai(ten_cu, ten_moi, username)

    db.ghi_audit(
        username,
        "doi_ten_loai_bao_cao",
        f"{ten_cu} → {ten_moi} (manual={so_manual}, allowlist={allowlist_ok})",
    )

    ket_qua["ok"] = True
    ket_qua["so_manual_cap_nhat"] = so_manual
    ket_qua["allowlist_cap_nhat"] = allowlist_ok
    ket_qua["msg"] = f"Đã liên kết: {ten_cu} → {ten_moi}"
    return ket_qua


def dong_bo_tat_ca_ten_theo_form(
    deadline_cfg: dict[str, str],
    ds_loai_gsheet: list[str],
    username: str,
) -> dict[str, Any]:
    """Đồng bộ hàng loạt các tên theo dõi có gợi ý rõ ràng từ Google Form."""
    ds_lech = phat_hien_ten_lech_ten(deadline_cfg, ds_loai_gsheet)
    ds_can_doi = [x for x in ds_lech if x.get("ten_form")]
    ket_qua = {
        "ok": False,
        "so_doi": 0,
        "so_loi": 0,
        "chi_tiet": [],
        "msg": "",
    }
    if not ds_can_doi:
        ket_qua["msg"] = "Không có tên nào cần chuẩn hóa theo Form."
        return ket_qua

    for item in ds_can_doi:
        kq = doi_ten_loai_theo_doi(
            item["ten_theo_doi"],
            item["ten_form"],
            username,
        )
        ket_qua["chi_tiet"].append(kq)
        if kq.get("ok"):
            ket_qua["so_doi"] += 1
        else:
            ket_qua["so_loi"] += 1

    ket_qua["ok"] = ket_qua["so_doi"] > 0 and ket_qua["so_loi"] == 0
    ket_qua["msg"] = (
        f"Đã chuẩn hóa {ket_qua['so_doi']} tên theo Form"
        + (f", lỗi {ket_qua['so_loi']} mục" if ket_qua["so_loi"] else "")
    )
    return ket_qua


# ── Phân loại trạng thái ─────────────────────────────────────────────────────

def phan_loai_trang_thai(ngay_nop, deadline_str: str | None) -> str:
    """Phân loại một lượt nộp: 'dung_han' | 'tre' | 'chua_nop' | 'da_nop'.

    - chua_nop: không có ngày nộp (NaN/None)
    - da_nop:  có ngày nộp nhưng loại BC chưa cài deadline
    - dung_han: ngày nộp <= deadline
    - tre:      ngày nộp > deadline
    """
    if pd.isna(ngay_nop):
        return "chua_nop"
    if not deadline_str:
        return "da_nop"
    try:
        dl = pd.to_datetime(deadline_str).date()
        nop = ngay_nop.date() if hasattr(ngay_nop, "date") else pd.to_datetime(ngay_nop).date()
        return "dung_han" if nop <= dl else "tre"
    except Exception as e:
        logger.error("phan_loai_trang_thai: parse ngay loi — %s", e, exc_info=True)
        # deadline_str không parse được → không thể so sánh → coi như chưa nộp
        return "chua_nop"


def gan_trang_thai(
    df: pd.DataFrame, deadline_cfg: dict[str, str]
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Gán cột 'tt' cho DataFrame dựa trên deadline config.

    Returns:
        (df, dm) — DataFrame đã gán trạng thái + danh mục theo dõi.
    """
    df, dm = _gan_khoa_theo_doi(df, deadline_cfg)
    df["tt"] = df.apply(
        lambda r: phan_loai_trang_thai(r["thoi_gian"], deadline_cfg.get(r["_loai_theo_doi"])),
        axis=1,
    )
    return df, dm


# ── Manual override ───────────────────────────────────────────────────────────

def doc_manual_log() -> dict[tuple[str, str], dict]:
    """Đọc danh sách đánh dấu thủ công: {(pgd, loai): entry_dict}."""
    raw = db.doc_kv(KV_MANUAL)
    if not isinstance(raw, list):
        return {}
    result: dict[tuple[str, str], dict] = {}
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        pgd = entry.get("pgd")
        loai = entry.get("loai")
        if pgd and loai:
            result[(pgd, loai)] = entry
    return result


def doc_manual_log_raw() -> list[dict]:
    """Đọc danh sách đánh dấu thủ công dạng list nguyên gốc."""
    raw = db.doc_kv(KV_MANUAL)
    if isinstance(raw, list):
        return raw
    return []


def luu_manual_log(ds: list[dict], username: str) -> None:
    """Lưu danh sách đánh dấu thủ công vào kv_store."""
    db.ghi_kv(KV_MANUAL, ds, username)
    db.ghi_audit(username, "tdn_manual_submit", f"{len(ds)} đánh dấu thủ công")


def doc_manual_audit_log() -> list[dict]:
    """Đọc nhật ký thao tác override thủ công."""
    raw = db.doc_kv(KV_MANUAL_AUDIT)
    if isinstance(raw, list):
        return raw
    return []


def _manual_entry_key(entry: dict[str, Any]) -> tuple[str, str]:
    return (
        str(entry.get("pgd", "") or "").strip(),
        _chuan_hoa_ten_loai(str(entry.get("loai", "") or "")),
    )


def _append_manual_audit(
    hanh_dong: str,
    entry: dict[str, Any],
    username: str,
    ly_do: str = "",
) -> None:
    """Ghi 1 dòng audit chi tiết cho thao tác manual override."""
    now = datetime.now().isoformat()
    ds_audit = doc_manual_audit_log()
    audit_entry = {
        "hanh_dong": hanh_dong,
        "pgd": entry.get("pgd", ""),
        "loai": entry.get("loai", ""),
        "ngay_nop": entry.get("ngay_nop", ""),
        "ghi_chu": entry.get("ghi_chu", ""),
        "ghi_de": bool(entry.get("ghi_de", True)),
        "ly_do": ly_do or entry.get("ghi_chu", "") or hanh_dong,
        "username": username,
        "thoi_gian": now,
    }
    ds_audit.append(audit_entry)
    db.ghi_kv(KV_MANUAL_AUDIT, ds_audit, username)
    db.ghi_audit(
        username,
        f"tdn_manual_{hanh_dong}",
        f"{audit_entry['pgd']} — {audit_entry['loai']} — {audit_entry['ly_do']}",
    )


def luu_manual_override(
    entry: dict[str, Any],
    username: str,
    ds_hien_tai: list[dict] | None = None,
    ly_do: str = "",
) -> list[dict]:
    """Thêm/cập nhật một override thủ công và ghi nhật ký chi tiết."""
    if ds_hien_tai is None:
        ds_hien_tai = doc_manual_log_raw()

    key = _manual_entry_key(entry)
    old_entry = next((e for e in ds_hien_tai if _manual_entry_key(e) == key), None)
    ds_moi = [e for e in ds_hien_tai if _manual_entry_key(e) != key]

    now = datetime.now().isoformat()
    entry_moi = dict(entry)
    if old_entry:
        entry_moi.setdefault("username_tao", old_entry.get("username_tao", username))
        entry_moi.setdefault("tao_luc", old_entry.get("tao_luc", now))
        hanh_dong = "cap_nhat"
    else:
        entry_moi.setdefault("username_tao", username)
        entry_moi.setdefault("tao_luc", now)
        hanh_dong = "them"
    entry_moi["username_cap_nhat"] = username
    entry_moi["cap_nhat_luc"] = now
    entry_moi["ly_do"] = ly_do or entry_moi.get("ghi_chu", "") or "Đánh dấu thủ công"

    ds_moi.append(entry_moi)
    db.ghi_kv(KV_MANUAL, ds_moi, username)
    db.ghi_audit(
        username,
        "tdn_manual_submit",
        f"{hanh_dong}: {entry_moi.get('pgd', '')} — {entry_moi.get('loai', '')}",
    )
    _append_manual_audit(hanh_dong, entry_moi, username, entry_moi["ly_do"])
    return ds_moi


def xoa_manual_override(
    index: int,
    username: str,
    ds_hien_tai: list[dict] | None = None,
    ly_do: str = "Bỏ đánh dấu thủ công",
) -> list[dict]:
    """Xóa một override thủ công theo index hiển thị và ghi nhật ký chi tiết."""
    if ds_hien_tai is None:
        ds_hien_tai = doc_manual_log_raw()
    if index < 0 or index >= len(ds_hien_tai):
        raise IndexError("Index đánh dấu thủ công không hợp lệ.")

    ds_moi = list(ds_hien_tai)
    entry = ds_moi.pop(index)
    db.ghi_kv(KV_MANUAL, ds_moi, username)
    db.ghi_audit(
        username,
        "tdn_manual_delete",
        f"{entry.get('pgd', '')} — {entry.get('loai', '')}",
    )
    _append_manual_audit("xoa", entry, username, ly_do)
    return ds_moi


# ── Tổng hợp nghiệp vụ ───────────────────────────────────────────────────────

def lay_pgd_chua_nop(
    loai_bao_cao: str,
    df: pd.DataFrame | None = None,
) -> tuple[list[str], str | None]:
    """Trả về (ds_pgd_chua_nop, deadline_str) cho 1 loại báo cáo.

    Xét cả manual override: PGD có ghi đè = xem như đã nộp.
    """
    deadline_cfg = doc_deadline_config()

    if la_loai_bao_cao_luu_tru(loai_bao_cao):
        return [], None

    if df is None:
        df = doc_du_lieu_gsheet()
    df, dm = _gan_khoa_theo_doi(df, deadline_cfg)

    loai_norm = _chuan_hoa_ten_loai(loai_bao_cao)
    tracked_loai = (
        deadline_cfg.get(loai_bao_cao) and loai_bao_cao
    ) or dm["display_to_tracked"].get(loai_bao_cao) or dm["alias_to_tracked"].get(loai_norm)
    if tracked_loai is None and loai_bao_cao in deadline_cfg:
        tracked_loai = loai_bao_cao
    deadline_str = deadline_cfg.get(tracked_loai) if tracked_loai else None

    manual_map = doc_manual_log()
    ds_chua_nop: list[str] = []
    for pgd in DS_PGD_ALL:
        entry = manual_map.get((pgd, tracked_loai))
        if entry and entry.get("ghi_de", True):
            continue  # có ghi đè thủ công → xem như đã nộp
        match = df[(df["ten_pgd"] == pgd) & (df["_loai_theo_doi"] == tracked_loai)]
        if match.empty:
            ds_chua_nop.append(pgd)

    return ds_chua_nop, deadline_str


def lay_danh_sach_can_nhac(
    df: pd.DataFrame | None = None,
    allowlist: set[str] | None = None,
) -> list[dict]:
    """Trả danh sách các loại báo cáo cần nhắc Telegram.

    Mỗi phần tử: {"loai": str, "deadline_str": str, "deadline_date": date,
                   "days_left": int, "ds_chua_nop": list[str]}

    Chỉ trả các loại:
      - Có deadline đã qua hoặc trong 3 ngày tới.
      - Nằm trong allowlist (nếu allowlist không None).
      - Còn ít nhất 1 PGD chưa nộp.
    """
    deadline_cfg = doc_deadline_config()
    if not deadline_cfg:
        return []

    if df is None:
        df = doc_du_lieu_gsheet()
    if df.empty:
        return []

    df, dm = _gan_khoa_theo_doi(df, deadline_cfg)
    manual_map = doc_manual_log()
    today = date.today()
    result: list[dict] = []

    for loai, deadline_str in sorted(deadline_cfg.items()):
        loai_hien = dm["tracked_to_display"].get(loai, loai)
        if la_loai_bao_cao_luu_tru(loai) or la_loai_bao_cao_luu_tru(loai_hien):
            continue
        # Lọc allowlist
        if allowlist is not None and loai not in allowlist and loai_hien not in allowlist:
            continue

        # Parse deadline
        try:
            dl_date = pd.to_datetime(deadline_str).date()
        except Exception:
            logger.warning("Bỏ qua deadline '%s': không parse được '%s'", loai, deadline_str)
            continue

        days_left = (dl_date - today).days
        if days_left > 3:
            continue

        # Tìm PGD chưa nộp
        chua_nop: list[str] = []
        for pgd in DS_PGD_ALL:
            manual_entry = manual_map.get((pgd, loai))
            if manual_entry and manual_entry.get("ghi_de", True):
                ngay = pd.to_datetime(manual_entry.get("ngay_nop"))
                try:
                    nop_date = ngay.date() if hasattr(ngay, "date") else pd.to_datetime(ngay).date()
                    if nop_date <= dl_date:
                        continue
                except Exception:
                    pass

            match = df[(df["ten_pgd"] == pgd) & (df["_loai_theo_doi"] == loai)]
            if match.empty:
                chua_nop.append(pgd)
            else:
                last = match.sort_values("thoi_gian").iloc[-1]
                ngay_nop = last["thoi_gian"]
                if pd.isna(ngay_nop):
                    chua_nop.append(pgd)

        if chua_nop:
            result.append({
                "loai": loai_hien,
                "loai_theo_doi": loai,
                "deadline_str": deadline_str,
                "deadline_date": dl_date,
                "days_left": days_left,
                "ds_chua_nop": chua_nop,
            })

    return result


def tao_ma_tran_tien_do(
    df: pd.DataFrame,
    deadline_cfg: dict[str, str],
    ds_pgd_scope: list[str] | None = None,
) -> tuple[list[dict], dict[str, int]]:
    """Tạo ma trận PGD × Loại báo cáo và metrics.

    Returns:
        (rows, metrics)
        rows: list[dict] mỗi dòng = {"Đơn vị": pgd, loai_1: emoji_status, ...}
        metrics: {"dung_han": int, "tre": int, "chua_nop": int, "da_nop": int}
    """
    if ds_pgd_scope is None:
        ds_pgd_scope = DS_PGD_ALL

    df, dm = gan_trang_thai(df, deadline_cfg)
    tracked_keys = sorted(deadline_cfg.keys(), key=lambda x: dm["tracked_to_display"].get(x, x))
    manual_map = doc_manual_log()

    rows = []
    for pgd in ds_pgd_scope:
        row: dict = {"Đơn vị": pgd}
        for loai in tracked_keys:
            loai_hien = dm["tracked_to_display"].get(loai, loai)
            manual_key = (pgd, loai)
            entry = manual_map.get(manual_key)
            ghi_de = entry.get("ghi_de", True) if entry else False

            if entry and ghi_de:
                ngay = pd.to_datetime(entry.get("ngay_nop"))
                tt = phan_loai_trang_thai(ngay, deadline_cfg.get(loai))
                row[loai_hien] = f"{EMOJI[tt]} {LABEL[tt]} *"
            else:
                match = df[(df["ten_pgd"] == pgd) & (df["_loai_theo_doi"] == loai)]
                if match.empty:
                    row[loai_hien] = "🔴 Chưa nộp" if loai in deadline_cfg else "⚪ Chưa nộp"
                else:
                    last = match.sort_values("thoi_gian").iloc[-1]
                    co_file = str(last.get("file_dinh_kem", "")).strip()
                    badge_note = " 📝" if entry and not ghi_de else ""
                    if not co_file:
                        # Đã nộp form nhưng không có file đính kèm → Thiếu file
                        row[loai_hien] = f"{EMOJI['thieu_file']} {LABEL['thieu_file']}{badge_note}"
                    else:
                        tt = last["tt"]
                        row[loai_hien] = f"{EMOJI[tt]} {LABEL[tt]}{badge_note}"
        rows.append(row)

    ds_loai_hien = [dm["tracked_to_display"].get(loai, loai) for loai in tracked_keys]
    dung_han = sum(1 for r in rows for l in ds_loai_hien if "🟢" in str(r.get(l, "")))
    tre = sum(1 for r in rows for l in ds_loai_hien if "🟡" in str(r.get(l, "")))
    chua_nop = sum(1 for r in rows for l in ds_loai_hien if "🔴" in str(r.get(l, "")))
    thieu_file = sum(1 for r in rows for l in ds_loai_hien if "⚠️" in str(r.get(l, "")))
    da_nop = dung_han + tre

    metrics = {"dung_han": dung_han, "tre": tre, "chua_nop": chua_nop, "thieu_file": thieu_file, "da_nop": da_nop}
    return rows, metrics


def _fmt_ngay_vn(value) -> str:
    """Format ngày theo DD/MM/YYYY; giá trị rỗng trả về '—'."""
    if pd.isna(value):
        return "—"
    try:
        return pd.to_datetime(value).strftime("%d/%m/%Y")
    except Exception:
        return str(value or "—")


def _parse_deadline(deadline_str: str | None) -> date | None:
    """Parse deadline từ chuỗi YYYY-MM-DD."""
    if not deadline_str:
        return None
    try:
        return pd.to_datetime(deadline_str).date()
    except Exception:
        return None


def lap_bang_nghia_vu_bao_cao(
    df: pd.DataFrame,
    deadline_cfg: dict[str, str],
    ds_pgd_scope: list[str] | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Sinh bảng nghĩa vụ nộp báo cáo theo PGD × loại deadline."""
    if ds_pgd_scope is None:
        ds_pgd_scope = DS_PGD_ALL

    if not deadline_cfg:
        return pd.DataFrame(), {
            "danh_muc": {"tracked_keys": [], "tracked_to_display": {}},
            "metrics": {
                "tong_nghia_vu": 0,
                "tong_loai": 0,
                "tong_don_vi": len(ds_pgd_scope),
                "da_hoan_thanh": 0,
                "chua_hoan_thanh": 0,
            },
        }

    df, dm = gan_trang_thai(df, deadline_cfg)
    tracked_keys = sorted(deadline_cfg.keys(), key=lambda x: dm["tracked_to_display"].get(x, x))
    manual_map = doc_manual_log()
    hom_nay = date.today()
    rows: list[dict[str, Any]] = []

    for pgd in ds_pgd_scope:
        for loai in tracked_keys:
            loai_hien = dm["tracked_to_display"].get(loai, loai)
            deadline_str = deadline_cfg.get(loai)
            deadline_dt = _parse_deadline(deadline_str)
            match = df[(df["ten_pgd"] == pgd) & (df["_loai_theo_doi"] == loai)].sort_values("thoi_gian")
            manual_entry = manual_map.get((pgd, loai))
            ghi_de = manual_entry.get("ghi_de", True) if manual_entry else False

            nguon = "Chưa có dữ liệu"
            ghi_chu = ""
            ky_bao_cao = ""
            file_dinh_kem = ""
            ngay_nop = pd.NaT
            co_file = False

            if manual_entry and ghi_de:
                ngay_nop = pd.to_datetime(manual_entry.get("ngay_nop"), errors="coerce")
                ma_tt = phan_loai_trang_thai(ngay_nop, deadline_str)
                nguon = "Thủ công"
                ghi_chu = str(manual_entry.get("ghi_chu", "") or "").strip()
            elif match.empty:
                ma_tt = "chua_nop"
                if manual_entry:
                    ghi_chu = str(manual_entry.get("ghi_chu", "") or "").strip()
                    nguon = "Chưa có dữ liệu + ghi chú"
            else:
                lan_cuoi = match.iloc[-1]
                ngay_nop = lan_cuoi.get("thoi_gian")
                ky_bao_cao = str(lan_cuoi.get("ky_bao_cao", "") or "").strip()
                file_dinh_kem = str(lan_cuoi.get("file_dinh_kem", "") or "").strip()
                co_file = bool(file_dinh_kem)
                ma_tt = "thieu_file" if not co_file else str(lan_cuoi.get("tt", "chua_nop"))
                nguon = "Google Form"
                if manual_entry and not ghi_de:
                    ghi_chu = str(manual_entry.get("ghi_chu", "") or "").strip()
                    nguon = "Google Form + ghi chú"

            hoan_thanh = ma_tt in {"dung_han", "tre"}
            can_xu_ly = ma_tt in {"chua_nop", "thieu_file"}
            sap_den_han = bool(deadline_dt and not hoan_thanh and 0 <= (deadline_dt - hom_nay).days <= 3)

            if deadline_dt is None:
                so_ngay_tre = 0
            elif ma_tt == "tre" and not pd.isna(ngay_nop):
                nop_date = pd.to_datetime(ngay_nop).date()
                so_ngay_tre = max((nop_date - deadline_dt).days, 0)
            elif ma_tt in {"chua_nop", "thieu_file"}:
                so_ngay_tre = max((hom_nay - deadline_dt).days, 0)
            else:
                so_ngay_tre = 0

            if ma_tt == "thieu_file":
                nhom_hanh_dong = "Thiếu file"
            elif ma_tt == "chua_nop" and so_ngay_tre > 0:
                nhom_hanh_dong = "Quá hạn chưa nộp"
            elif ma_tt == "chua_nop":
                nhom_hanh_dong = "Sắp đến hạn"
            elif ma_tt == "tre":
                nhom_hanh_dong = "Đã nộp trễ"
            else:
                nhom_hanh_dong = "Hoàn thành"

            rows.append(
                {
                    "Đơn vị": pgd,
                    "Loại báo cáo": loai_hien,
                    "Trạng thái": f"{EMOJI.get(ma_tt, '')} {LABEL.get(ma_tt, ma_tt)}".strip(),
                    "Mã trạng thái": ma_tt,
                    "Thời hạn": _fmt_ngay_vn(deadline_str),
                    "Ngày nộp cuối": _fmt_ngay_vn(ngay_nop),
                    "Kỳ báo cáo": ky_bao_cao or "—",
                    "Nguồn trạng thái": nguon,
                    "Có file": "Có" if co_file else "Không",
                    "Quá hạn (ngày)": int(so_ngay_tre),
                    "Cần xử lý": can_xu_ly,
                    "Sắp đến hạn": sap_den_han,
                    "Hoàn thành": hoan_thanh,
                    "Nhóm hành động": nhom_hanh_dong,
                    "Ghi chú": ghi_chu or "—",
                    "_deadline_raw": deadline_str or "",
                    "_ngay_nop_raw": ngay_nop,
                    "_file_dinh_kem": file_dinh_kem,
                }
            )

    df_nghia_vu = pd.DataFrame(rows)
    metrics = {
        "tong_nghia_vu": int(len(df_nghia_vu)),
        "tong_loai": int(len(tracked_keys)),
        "tong_don_vi": int(len(ds_pgd_scope)),
        "da_hoan_thanh": int(df_nghia_vu["Hoàn thành"].sum()) if not df_nghia_vu.empty else 0,
        "chua_hoan_thanh": int((~df_nghia_vu["Hoàn thành"]).sum()) if not df_nghia_vu.empty else 0,
    }
    return df_nghia_vu, {"danh_muc": dm, "metrics": metrics}


def tong_hop_bao_cao_dieu_hanh(
    df: pd.DataFrame,
    deadline_cfg: dict[str, str],
    ds_pgd_scope: list[str] | None = None,
) -> dict[str, Any]:
    """Tổng hợp dữ liệu điều hành từ bảng nghĩa vụ nộp báo cáo."""
    df_nghia_vu, extra = lap_bang_nghia_vu_bao_cao(df, deadline_cfg, ds_pgd_scope)
    metrics = dict(extra.get("metrics", {}))

    if df_nghia_vu.empty:
        metrics.update(
            {
                "ty_le_hoan_thanh": 0.0,
                "so_don_vi_hoan_thanh_100": 0,
                "so_don_vi_con_thieu": 0,
                "so_tre_han": 0,
                "so_thieu_file": 0,
                "so_sap_den_han": 0,
                "so_qua_han_chua_nop": 0,
                "so_luot_nop": int(len(df)) if df is not None else 0,
            }
        )
        return {
            "df_chi_tiet": df_nghia_vu,
            "df_da_hoan_thanh": df_nghia_vu,
            "df_chua_hoan_thanh": df_nghia_vu,
            "df_can_xu_ly": df_nghia_vu,
            "df_sap_den_han": df_nghia_vu,
            "df_top_don_vi": pd.DataFrame(),
            "df_top_loai": pd.DataFrame(),
            "metrics": metrics,
            "nhan_dinh": [],
        }

    tong_nghia_vu = max(int(metrics.get("tong_nghia_vu", 0)), 1)
    metrics.update(
        {
            "ty_le_hoan_thanh": metrics.get("da_hoan_thanh", 0) / tong_nghia_vu,
            "so_tre_han": int((df_nghia_vu["Mã trạng thái"] == "tre").sum()),
            "so_thieu_file": int((df_nghia_vu["Mã trạng thái"] == "thieu_file").sum()),
            "so_sap_den_han": int(df_nghia_vu["Sắp đến hạn"].sum()),
            "so_qua_han_chua_nop": int(
                (
                    (df_nghia_vu["Mã trạng thái"] == "chua_nop")
                    & (df_nghia_vu["Quá hạn (ngày)"] > 0)
                ).sum()
            ),
            "so_luot_nop": int(len(df)) if df is not None else 0,
        }
    )

    unit_stats = (
        df_nghia_vu.groupby("Đơn vị")
        .agg(
            tong_nghia_vu=("Đơn vị", "size"),
            da_hoan_thanh=("Hoàn thành", "sum"),
            chua_hoan_thanh=("Cần xử lý", "sum"),
            tre_han=("Mã trạng thái", lambda s: int((s == "tre").sum())),
            thieu_file=("Mã trạng thái", lambda s: int((s == "thieu_file").sum())),
            qua_han_max=("Quá hạn (ngày)", "max"),
        )
        .reset_index()
    )
    unit_stats["ty_le_hoan_thanh"] = (
        unit_stats["da_hoan_thanh"] / unit_stats["tong_nghia_vu"]
    ).fillna(0.0)
    metrics["so_don_vi_hoan_thanh_100"] = int((unit_stats["chua_hoan_thanh"] == 0).sum())
    metrics["so_don_vi_con_thieu"] = int((unit_stats["chua_hoan_thanh"] > 0).sum())

    loai_stats = (
        df_nghia_vu.groupby("Loại báo cáo")
        .agg(
            tong_nghia_vu=("Loại báo cáo", "size"),
            da_hoan_thanh=("Hoàn thành", "sum"),
            chua_hoan_thanh=("Cần xử lý", "sum"),
            tre_han=("Mã trạng thái", lambda s: int((s == "tre").sum())),
            thieu_file=("Mã trạng thái", lambda s: int((s == "thieu_file").sum())),
            qua_han_max=("Quá hạn (ngày)", "max"),
        )
        .reset_index()
    )
    loai_stats["ty_le_hoan_thanh"] = (
        loai_stats["da_hoan_thanh"] / loai_stats["tong_nghia_vu"]
    ).fillna(0.0)

    df_chua_hoan_thanh = df_nghia_vu[~df_nghia_vu["Hoàn thành"]].copy()
    df_can_xu_ly = df_nghia_vu[df_nghia_vu["Cần xử lý"]].copy()
    df_sap_den_han = df_nghia_vu[df_nghia_vu["Sắp đến hạn"]].copy()
    df_da_hoan_thanh = df_nghia_vu[df_nghia_vu["Hoàn thành"]].copy()

    df_top_don_vi = unit_stats.sort_values(
        ["chua_hoan_thanh", "thieu_file", "qua_han_max", "Đơn vị"],
        ascending=[False, False, False, True],
    )
    df_top_loai = loai_stats.sort_values(
        ["chua_hoan_thanh", "thieu_file", "qua_han_max", "Loại báo cáo"],
        ascending=[False, False, False, True],
    )
    df_can_xu_ly = df_can_xu_ly.sort_values(
        ["Quá hạn (ngày)", "_deadline_raw", "Đơn vị", "Loại báo cáo"],
        ascending=[False, True, True, True],
    )
    df_sap_den_han = df_sap_den_han.sort_values(
        ["_deadline_raw", "Đơn vị", "Loại báo cáo"],
        ascending=[True, True, True],
    )

    nhan_dinh: list[str] = []
    if metrics["so_qua_han_chua_nop"]:
        nhan_dinh.append(
            f"Còn {metrics['so_qua_han_chua_nop']} nghĩa vụ đã quá hạn nhưng chưa nộp."
        )
    if metrics["so_thieu_file"]:
        nhan_dinh.append(
            f"Có {metrics['so_thieu_file']} báo cáo đã gửi Form nhưng chưa có file đính kèm."
        )
    if metrics["so_sap_den_han"]:
        nhan_dinh.append(
            f"Có {metrics['so_sap_den_han']} nghĩa vụ sắp đến hạn trong 3 ngày tới."
        )
    if not nhan_dinh:
        nhan_dinh.append("Tiến độ đang ổn định, chưa thấy điểm nghẽn cần đôn đốc gấp.")

    return {
        "df_chi_tiet": df_nghia_vu,
        "df_da_hoan_thanh": df_da_hoan_thanh,
        "df_chua_hoan_thanh": df_chua_hoan_thanh,
        "df_can_xu_ly": df_can_xu_ly,
        "df_sap_den_han": df_sap_den_han,
        "df_top_don_vi": df_top_don_vi,
        "df_top_loai": df_top_loai,
        "metrics": metrics,
        "nhan_dinh": nhan_dinh,
    }


# ── Health-check nguồn dữ liệu ────────────────────────────────────────────────

def kiem_tra_suc_khoe_nguon() -> dict[str, Any]:
    """Kiểm tra sức khỏe kết nối GSheet và chất lượng dữ liệu.

    Returns:
        {
            "ok": bool,
            "credentials_ok": bool,
            "ket_noi_ok": bool,
            "so_dong": int,
            "so_pgd": int,
            "so_loai_bc": int,
            "lan_cap_nhat_cuoi": str | None,
            "loi": str | None,
        }
    """
    result: dict[str, Any] = {
        "ok": False,
        "credentials_ok": False,
        "ket_noi_ok": False,
        "so_dong": 0,
        "so_pgd": 0,
        "so_loai_bc": 0,
        "lan_cap_nhat_cuoi": None,
        "loi": None,
    }

    # Check credentials
    try:
        _tim_credentials()
        result["credentials_ok"] = True
    except FileNotFoundError as e:
        result["loi"] = str(e)
        return result
    except Exception as e:
        logger.error("kiem_tra_suc_khoe_nguon: credentials — %s", e, exc_info=True)
        result["loi"] = f"Lỗi credentials: {e}"
        return result

    # Check connection + data
    df = doc_du_lieu_gsheet()
    result["ket_noi_ok"] = not lay_loi_doc_gsheet_gan_nhat()
    if lay_loi_doc_gsheet_gan_nhat():
        result["loi"] = lay_loi_doc_gsheet_gan_nhat()
        return result

    if df.empty:
        result["loi"] = "GSheet trả về dữ liệu rỗng (không có dòng nào)"
        return result

    result["ok"] = True
    result["so_dong"] = len(df)
    result["so_pgd"] = df["ten_pgd"].dropna().nunique()
    result["so_loai_bc"] = df["loai_bao_cao"].dropna().nunique()

    if "thoi_gian" in df.columns and df["thoi_gian"].notna().any():
        lan_cuoi = df["thoi_gian"].max()
        try:
            result["lan_cap_nhat_cuoi"] = pd.Timestamp(lan_cuoi).strftime("%d/%m/%Y %H:%M")
        except Exception:
            result["lan_cap_nhat_cuoi"] = str(lan_cuoi)

    return result


def doc_du_lieu_gsheet_cached(ttl: int = 300):
    """Trả về callable để UI dùng với @st.cache_data."""
    import streamlit as st

    @st.cache_data(ttl=ttl)
    def _cached():
        return doc_du_lieu_gsheet()

    return _cached
