"""Service đọc Google Sheets kế hoạch/kết quả công việc nội bộ Phòng KH-NV."""

from __future__ import annotations

import sys
import time
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import quote

import pandas as pd

import db
from config import (
    BASE_DIR,
    KE_HOACH_CV_KHNV_SHEET_ID,
    KE_HOACH_CV_KHNV_SHEET_KH,
    KE_HOACH_CV_KHNV_SHEET_KQ,
)
from logger import get_logger

logger = get_logger(__name__)

KV_CONFIG = "khnv_ke_hoach_cv_config"

COT_KH = [
    "thoi_gian",
    "ho_ten",
    "tuan_ke_hoach",
    "nhom_cong_tac",
    "dau_viec",
    "mo_ta",
    "thoi_gian_du_kien",
    "uu_tien",
    "ghi_chu",
]

COT_KQ = [
    "thoi_gian",
    "ho_ten",
    "tuan_bao_cao",
    "nhom_cong_tac",
    "dau_viec",
    "mo_ta_cv",
    "trang_thai",
    "ket_qua",
]

_GSHEET_READ_RETRIES = 3
_GSHEET_READ_BACKOFF_S = 1.5
_LAST_ERROR: str | None = None


def doc_config() -> dict[str, Any]:
    """Đọc cấu hình runtime từ kv_store."""
    raw = db.doc_kv(KV_CONFIG) or {}
    if not isinstance(raw, dict):
        return {}
    cfg = dict(raw)
    cfg.setdefault("sheet_id", "")
    cfg.setdefault("form_ke_hoach_url", "")
    cfg.setdefault("form_ket_qua_url", "")
    cfg.setdefault("dau_viec_custom", [])
    if not isinstance(cfg["dau_viec_custom"], list):
        cfg["dau_viec_custom"] = []
    return cfg


def luu_config(cfg: dict[str, Any], username: str) -> None:
    """Lưu cấu hình runtime vào kv_store và audit."""
    payload = {
        "sheet_id": str(cfg.get("sheet_id", "") or "").strip(),
        "form_ke_hoach_url": str(cfg.get("form_ke_hoach_url", "") or "").strip(),
        "form_ket_qua_url": str(cfg.get("form_ket_qua_url", "") or "").strip(),
        "dau_viec_custom": [
            str(item).strip()
            for item in cfg.get("dau_viec_custom", [])
            if str(item).strip()
        ],
    }
    db.ghi_kv(KV_CONFIG, payload, username)
    db.ghi_audit(
        username,
        "luu_khnv_ke_hoach_cv_config",
        f"Cập nhật cấu hình KH/KQ công việc KH-NV; sheet_id={bool(payload['sheet_id'])}",
    )


def _lay_sheet_id() -> str | None:
    """Lấy Sheet ID ưu tiên kv_store, fallback constant config."""
    cfg = doc_config()
    sheet_id = str(cfg.get("sheet_id", "") or "").strip()
    if sheet_id:
        return sheet_id
    fallback = str(KE_HOACH_CV_KHNV_SHEET_ID or "").strip()
    return fallback or None


def lay_loi_doc_gsheet_gan_nhat() -> str | None:
    return _LAST_ERROR


def _tim_credentials() -> Path:
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


def _la_loi_gsheet_tam_thoi(exc: BaseException) -> bool:
    msg = str(exc).lower()
    markers = (
        "500",
        "502",
        "503",
        "504",
        "429",
        "internal error",
        "backend error",
        "rate limit",
        "service unavailable",
        "temporarily unavailable",
    )
    return any(marker in msg for marker in markers)


def _goi_y_loi_gsheet(exc: BaseException) -> str:
    if _la_loi_gsheet_tam_thoi(exc):
        return " — lỗi tạm thời phía Google, thử làm mới sau 1–2 phút"
    return ""


def _doc_raw_values_sheet(tab: str, sheet_id: str | None = None) -> list[list[str]]:
    """Đọc toàn bộ ô của một tab Google Sheets."""
    global _LAST_ERROR
    sheet_id = str(sheet_id or _lay_sheet_id() or "").strip()
    if not sheet_id:
        _LAST_ERROR = "Chưa cấu hình Sheet ID trong tab Cài đặt"
        return []

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
            _LAST_ERROR = None
            return payload.get("values", []) or []
        except Exception:
            last_err = sys.exc_info()[1]
            if (
                isinstance(last_err, BaseException)
                and _la_loi_gsheet_tam_thoi(last_err)
                and attempt < _GSHEET_READ_RETRIES - 1
            ):
                logger.warning(
                    "_doc_raw_values_sheet(%s): attempt %d/%d tạm thời — %s",
                    tab,
                    attempt + 1,
                    _GSHEET_READ_RETRIES,
                    last_err,
                )
                time.sleep(_GSHEET_READ_BACKOFF_S * (attempt + 1))
                continue
            logger.error("_doc_raw_values_sheet(%s): %s", tab, last_err, exc_info=True)
            break

    _LAST_ERROR = (
        "{}: {}{}".format(type(last_err).__name__, last_err, _goi_y_loi_gsheet(last_err))
        if last_err
        else "Không đọc được GSheet"
    )
    if last_err:
        raise last_err
    return []


def _rows_to_df(data: list[list[str]], columns: list[str]) -> pd.DataFrame:
    if len(data) <= 1:
        return pd.DataFrame(columns=columns)
    rows = []
    for raw in data[1:]:
        row = list(raw[: len(columns)])
        row.extend([""] * (len(columns) - len(row)))
        rows.append(row)
    return pd.DataFrame(rows, columns=columns)


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _chuan_hoa_df(df: pd.DataFrame, week_col: str) -> pd.DataFrame:
    if df.empty:
        return df
    result = df.copy()
    for col in result.columns:
        if col not in {"thoi_gian", week_col}:
            result[col] = result[col].apply(_clean_text)
    result["thoi_gian"] = pd.to_datetime(result["thoi_gian"], dayfirst=True, errors="coerce")
    result[week_col] = pd.to_datetime(result[week_col], dayfirst=True, errors="coerce")
    result["tuan"] = result[week_col].dt.date
    return result


def doc_ke_hoach() -> pd.DataFrame:
    """Đọc tab KhHoach từ Google Sheets, không cache."""
    try:
        data = _doc_raw_values_sheet(KE_HOACH_CV_KHNV_SHEET_KH)
        return _chuan_hoa_df(_rows_to_df(data, COT_KH), "tuan_ke_hoach")
    except Exception as e:
        logger.error("doc_ke_hoach: %s", e, exc_info=True)
        return pd.DataFrame(columns=COT_KH + ["tuan"])


def doc_ket_qua() -> pd.DataFrame:
    """Đọc tab KetQua từ Google Sheets, không cache."""
    try:
        data = _doc_raw_values_sheet(KE_HOACH_CV_KHNV_SHEET_KQ)
        return _chuan_hoa_df(_rows_to_df(data, COT_KQ), "tuan_bao_cao")
    except Exception as e:
        logger.error("doc_ket_qua: %s", e, exc_info=True)
        return pd.DataFrame(columns=COT_KQ + ["tuan"])


def doc_ke_hoach_cached(ttl: int = 300):
    """Trả về callable để UI dùng với @st.cache_data."""
    import streamlit as st

    @st.cache_data(ttl=ttl)
    def _cached():
        return doc_ke_hoach()

    return _cached


def doc_ket_qua_cached(ttl: int = 300):
    """Trả về callable để UI dùng với @st.cache_data."""
    import streamlit as st

    @st.cache_data(ttl=ttl)
    def _cached():
        return doc_ket_qua()

    return _cached


def kiem_tra_ket_noi() -> tuple[bool, str]:
    """Kiểm tra credentials, Sheet ID và hai tab KhHoach/KetQua."""
    try:
        cred_path = _tim_credentials()
    except Exception as e:
        logger.error("kiem_tra_ket_noi: credentials — %s", e, exc_info=True)
        return False, str(e)

    sheet_id = _lay_sheet_id()
    if not sheet_id:
        return False, "Chưa cấu hình Sheet ID trong tab Cài đặt"

    try:
        kh = _doc_raw_values_sheet(KE_HOACH_CV_KHNV_SHEET_KH, sheet_id)
        kq = _doc_raw_values_sheet(KE_HOACH_CV_KHNV_SHEET_KQ, sheet_id)
        return (
            True,
            f"OK — {cred_path.name}: {KE_HOACH_CV_KHNV_SHEET_KH} {len(kh)} dòng, "
            f"{KE_HOACH_CV_KHNV_SHEET_KQ} {len(kq)} dòng",
        )
    except Exception as e:
        logger.error("kiem_tra_ket_noi: %s", e, exc_info=True)
        return False, f"{type(e).__name__}: {e}{_goi_y_loi_gsheet(e)}"


def _monday_of(d: date) -> date:
    return d - pd.Timedelta(days=d.weekday())


def _week_label(value: Any) -> str:
    if pd.isna(value):
        return "Chưa rõ tuần"
    try:
        return pd.to_datetime(value).strftime("%d/%m/%Y")
    except Exception:
        return str(value or "Chưa rõ tuần")


def _is_done(value: Any) -> bool:
    text = _clean_text(value).casefold()
    return "hoàn thành" in text or "hoan thanh" in text


def tinh_tong_hop(df_kh: pd.DataFrame, df_kq: pd.DataFrame) -> dict[str, Any]:
    """Tính KPI tuần hiện tại, ma trận cán bộ × tuần và dữ liệu biểu đồ."""
    today_monday = _monday_of(date.today())
    kh = df_kh.copy() if isinstance(df_kh, pd.DataFrame) else pd.DataFrame(columns=COT_KH)
    kq = df_kq.copy() if isinstance(df_kq, pd.DataFrame) else pd.DataFrame(columns=COT_KQ)

    kh_tuan = kh[kh.get("tuan").eq(today_monday)] if "tuan" in kh.columns else pd.DataFrame()
    kq_tuan = kq[kq.get("tuan").eq(today_monday)] if "tuan" in kq.columns else pd.DataFrame()
    hoan_thanh = int(kq_tuan.get("trang_thai", pd.Series(dtype=str)).apply(_is_done).sum())
    tong_kh_tuan = int(len(kh_tuan))
    da_bao_cao = int(len(kq_tuan))

    ty_le = (hoan_thanh / tong_kh_tuan) if tong_kh_tuan else 0.0
    weeks = sorted(
        {
            item
            for item in list(kh.get("tuan", pd.Series(dtype=object)).dropna())
            + list(kq.get("tuan", pd.Series(dtype=object)).dropna())
        }
    )
    people = sorted(
        {
            _clean_text(item)
            for item in list(kh.get("ho_ten", pd.Series(dtype=str)).dropna())
            + list(kq.get("ho_ten", pd.Series(dtype=str)).dropna())
            if _clean_text(item)
        }
    )

    matrix_rows: list[dict[str, str]] = []
    for person in people:
        row = {"Cán bộ": person}
        for week in weeks:
            co_kh = not kh[(kh.get("ho_ten") == person) & (kh.get("tuan") == week)].empty
            kq_match = kq[(kq.get("ho_ten") == person) & (kq.get("tuan") == week)]
            co_kq = not kq_match.empty
            co_done = bool(kq_match.get("trang_thai", pd.Series(dtype=str)).apply(_is_done).any())
            label = _week_label(week)
            if co_kh and co_done:
                row[label] = "🟢 Hoàn thành"
            elif co_kh and co_kq:
                row[label] = "🟡 Đang TH"
            elif co_kh:
                row[label] = "🟡 Có KH"
            elif co_kq:
                row[label] = "🟡 Có KQ"
            else:
                row[label] = "🔴 Chưa có"
        matrix_rows.append(row)

    if not kh.empty and "dau_viec" in kh.columns:
        chart = (
            kh.groupby("dau_viec")
            .size()
            .reset_index(name="Số kế hoạch")
            .sort_values("Số kế hoạch", ascending=False)
        )
    else:
        chart = pd.DataFrame(columns=["dau_viec", "Số kế hoạch"])

    return {
        "tuan_hien_tai": today_monday,
        "metrics": {
            "tong_kh_tuan": tong_kh_tuan,
            "da_bao_cao": da_bao_cao,
            "hoan_thanh": hoan_thanh,
            "ty_le_hoan_thanh": ty_le,
        },
        "matrix": pd.DataFrame(matrix_rows),
        "chart_dau_viec": chart,
    }
