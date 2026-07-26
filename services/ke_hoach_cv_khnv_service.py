"""Service đọc Google Sheets kế hoạch/kết quả công việc nội bộ Phòng KH-NV."""

from __future__ import annotations

import sys
import time
import uuid
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import quote

import pandas as pd

import db
from config import (
    BASE_DIR,
    KE_HOACH_CV_KHNV_SHEET_GV,
    KE_HOACH_CV_KHNV_SHEET_ID,
    KE_HOACH_CV_KHNV_SHEET_KH,
    KE_HOACH_CV_KHNV_SHEET_KQ,
    KE_HOACH_CV_KHNV_SHEET_NV,
)
from logger import get_logger

logger = get_logger(__name__)

KV_CONFIG = "khnv_ke_hoach_cv_config"
KV_NHIEM_VU_GIAO = "khnv_nhiem_vu_giao_list"

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

COT_NV_GIAO = [
    "thoi_gian",
    "ma_nhiem_vu",
    "ngay_giao",
    "nguoi_giao",
    "can_bo_nhan",
    "nhom_cong_tac",
    "noi_dung",
    "san_pham",
    "han_hoan_thanh",
    "uu_tien",
    "trang_thai",
    "ghi_chu",
]

# Cột của tab GiaoViec (Google Form giao việc lãnh đạo)
COT_GV = [
    "thoi_gian",
    "nguoi_nhan",
    "tuan_thuc_hien",
    "nhom_cong_tac",
    "dau_viec",
    "noi_dung",
    "ket_qua_can_dat",
    "thoi_han",
    "uu_tien",
]

TRANG_THAI_NHIEM_VU = ["Mới giao", "Đang thực hiện", "Hoàn thành", "Tạm dừng"]
UU_TIEN_NHIEM_VU = ["Khẩn cấp", "Quan trọng", "Bình thường"]

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
    cfg.setdefault("form_nhiem_vu_url", "")
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
        "form_nhiem_vu_url": str(cfg.get("form_nhiem_vu_url", "") or "").strip(),
        "nhom_custom": [
            str(item).strip()
            for item in cfg.get("nhom_custom", [])
            if str(item).strip()
        ],
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


def _la_loi_tab_khong_ton_tai(err: BaseException | None) -> bool:
    """Nhận diện lỗi Google Sheets do tên tab không khớp sheet nào.

    Khi truyền chỉ tên tab vào endpoint values/{range} mà tab chưa được tạo
    (hoặc sai tên), Google trả 400 "Unable to parse range: <tên>". Đây là lỗi
    cấu hình nhẹ của tab TUỲ CHỌN, không phải lỗi kết nối/auth toàn cục.
    """
    if err is None:
        return False
    msg = str(err).lower()
    return "unable to parse range" in msg or (
        "400" in str(err) and "range" in msg
    )


def _doc_raw_values_sheet(
    tab: str, sheet_id: str | None = None, *, optional: bool = False,
) -> list[list[str]]:
    """Đọc toàn bộ ô của một tab Google Sheets.

    optional=True: tab tuỳ chọn (vd NhiemVuGiao). Nếu tab chưa tồn tại thì trả
    danh sách rỗng ÊM — không ghi _LAST_ERROR toàn cục, không raise — để một
    tab thiếu không làm banner lỗi che mất các tab còn đọc tốt.
    """
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
            # Tab tuỳ chọn chưa tạo → trả rỗng êm, không làm bẩn lỗi toàn cục.
            if optional and _la_loi_tab_khong_ton_tai(last_err):
                logger.warning(
                    "_doc_raw_values_sheet(%s): tab chưa tồn tại (tuỳ chọn) — bỏ qua",
                    tab,
                )
                return []
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


def _chuan_hoa_nhiem_vu_gsheet(df: pd.DataFrame) -> pd.DataFrame:
    """Chuẩn hóa dữ liệu nhiệm vụ lãnh đạo giao đọc từ Google Sheets."""
    if df.empty:
        return pd.DataFrame(columns=COT_NV_GIAO + ["han", "nguon"])
    result = df.copy()
    for col in result.columns:
        if col not in {"thoi_gian", "ngay_giao", "han_hoan_thanh"}:
            result[col] = result[col].apply(_clean_text)
    for col in ["thoi_gian", "ngay_giao", "han_hoan_thanh"]:
        result[col] = pd.to_datetime(result[col], dayfirst=True, errors="coerce")
    result["han"] = result["han_hoan_thanh"].dt.date
    result["nguon"] = "Google Sheet"
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


def doc_nhiem_vu_gsheet() -> pd.DataFrame:
    """Đọc tab NhiemVuGiao từ Google Sheets, không cache.

    Tab này TUỲ CHỌN: nếu spreadsheet chưa tạo tab thì trả DataFrame rỗng êm,
    không làm bẩn lỗi Google Sheets toàn cục (optional=True).
    """
    try:
        data = _doc_raw_values_sheet(KE_HOACH_CV_KHNV_SHEET_NV, optional=True)
        return _chuan_hoa_nhiem_vu_gsheet(_rows_to_df(data, COT_NV_GIAO))
    except Exception as e:
        logger.error("doc_nhiem_vu_gsheet: %s", e, exc_info=True)
        return pd.DataFrame(columns=COT_NV_GIAO + ["han", "nguon"])


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


def doc_nhiem_vu_gsheet_cached(ttl: int = 300):
    """Trả về callable để UI dùng với @st.cache_data."""
    import streamlit as st

    @st.cache_data(ttl=ttl)
    def _cached():
        return doc_nhiem_vu_gsheet()

    return _cached


# ── GiaoViec (Form giao việc lãnh đạo) ──────────────────────────────────────


def _chuan_hoa_giao_viec(df: pd.DataFrame) -> pd.DataFrame:
    """Chuẩn hóa dữ liệu giao việc đọc từ tab GiaoViec."""
    if df.empty:
        return pd.DataFrame(columns=COT_GV + ["han", "tuan"])
    result = df.copy()
    for col in result.columns:
        if col not in {"thoi_gian", "tuan_thuc_hien", "thoi_han"}:
            result[col] = result[col].apply(_clean_text)
    for col in ["thoi_gian", "tuan_thuc_hien", "thoi_han"]:
        if col in result.columns:
            result[col] = pd.to_datetime(result[col], dayfirst=True, errors="coerce")
    result["han"] = result["thoi_han"].dt.date
    result["tuan"] = result["tuan_thuc_hien"].dt.date
    return result


def doc_giao_viec() -> pd.DataFrame:
    """Đọc tab GiaoViec từ Google Sheets, không cache."""
    try:
        data = _doc_raw_values_sheet(KE_HOACH_CV_KHNV_SHEET_GV)
        return _chuan_hoa_giao_viec(_rows_to_df(data, COT_GV))
    except Exception as e:
        logger.error("doc_giao_viec: %s", e, exc_info=True)
        return pd.DataFrame(columns=COT_GV + ["han", "tuan"])


def loc_giao_viec_theo_can_bo(df_gv: pd.DataFrame, ten_can_bo: str) -> pd.DataFrame:
    """Lọc nhiệm vụ được giao cho một cán bộ cụ thể."""
    if df_gv.empty or not ten_can_bo.strip():
        return df_gv
    ten = _clean_text(ten_can_bo).casefold()
    mask = df_gv.get("nguoi_nhan", pd.Series(dtype=str)).apply(
        lambda x: ten in _clean_text(x).casefold()
    )
    return df_gv[mask]


def doi_chieu_giao_viec_ket_qua(
    df_gv: pd.DataFrame,
    df_kq: pd.DataFrame,
) -> pd.DataFrame:
    """Đối chiếu nhiệm vụ giao (GiaoViec) với kết quả báo cáo (KetQua).

    Ghép theo họ tên cán bộ + đầu việc (gần đúng). Trả về DataFrame
    với cột 'trang_thai_kq' và 'da_bao_cao'.
    """
    if df_gv.empty:
        return pd.DataFrame()

    result = df_gv.copy()
    result["da_bao_cao"] = False
    result["trang_thai_kq"] = ""
    result["ket_qua_chi_tiet"] = ""

    if df_kq is None or df_kq.empty:
        return result

    for idx, row_gv in result.iterrows():
        ten = _clean_text(row_gv.get("nguoi_nhan", "")).casefold()
        dau_viec = _clean_text(row_gv.get("dau_viec", "")).casefold()
        if not ten:
            continue
        # Tìm báo cáo kết quả khớp tên + đầu việc
        mask_ten = df_kq.get("ho_ten", pd.Series(dtype=str)).apply(
            lambda x: ten in _clean_text(x).casefold()
        )
        kq_match = df_kq[mask_ten]
        if dau_viec and "dau_viec" in kq_match.columns:
            kq_dv = kq_match[
                kq_match["dau_viec"].apply(lambda x: dau_viec in _clean_text(x).casefold())
            ]
            if not kq_dv.empty:
                kq_match = kq_dv
        if not kq_match.empty:
            result.at[idx, "da_bao_cao"] = True
            trang_thai_list = kq_match.get("trang_thai", pd.Series(dtype=str)).tolist()
            result.at[idx, "trang_thai_kq"] = "; ".join(
                str(t).strip() for t in trang_thai_list if str(t).strip()
            )
            ket_qua_list = kq_match.get("ket_qua", pd.Series(dtype=str)).tolist()
            result.at[idx, "ket_qua_chi_tiet"] = "; ".join(
                str(k).strip() for k in ket_qua_list if str(k).strip()
            )
    return result


def tinh_tong_hop_giao_viec(df_gv: pd.DataFrame) -> dict[str, int]:
    """Tính KPI cho dữ liệu giao việc từ Form."""
    if not isinstance(df_gv, pd.DataFrame) or df_gv.empty:
        return {"tong": 0, "qua_han": 0, "da_bao_cao": 0, "chua_bao_cao": 0}
    today = date.today()
    tong = len(df_gv)
    qua_han = 0
    if "han" in df_gv.columns:
        qua_han = int(
            df_gv["han"].apply(
                lambda h: isinstance(h, date) and h < today
            ).sum()
        )
    da_bao_cao = int(df_gv.get("da_bao_cao", pd.Series(dtype=bool)).fillna(False).sum())
    return {
        "tong": tong,
        "qua_han": qua_han,
        "da_bao_cao": da_bao_cao,
        "chua_bao_cao": max(0, tong - da_bao_cao),
    }


def kiem_tra_ket_noi() -> tuple[bool, str]:
    """Kiểm tra credentials, Sheet ID và ba tab KhHoach/KetQua/NhiemVuGiao."""
    global _LAST_ERROR
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
    except Exception as e:
        logger.error("kiem_tra_ket_noi: %s", e, exc_info=True)
        return False, f"{type(e).__name__}: {e}{_goi_y_loi_gsheet(e)}"

    # Tab NhiemVuGiao tuỳ chọn: thiếu thì cảnh báo nhẹ, không fail toàn bộ.
    try:
        nv = _doc_raw_values_sheet(KE_HOACH_CV_KHNV_SHEET_NV, sheet_id)
        nv_msg = f"{KE_HOACH_CV_KHNV_SHEET_NV} {len(nv)} dòng"
    except Exception as e:
        if _la_loi_tab_khong_ton_tai(e):
            # Tab tuỳ chọn chưa tạo: _doc_raw_values_sheet (không optional) đã
            # ghi _LAST_ERROR trước khi raise → phải làm sạch để không hiện banner.
            _LAST_ERROR = None
            nv_msg = f"{KE_HOACH_CV_KHNV_SHEET_NV} chưa tạo (tuỳ chọn)"
        else:
            logger.error("kiem_tra_ket_noi: %s", e, exc_info=True)
            return False, f"{type(e).__name__}: {e}{_goi_y_loi_gsheet(e)}"

    # Tab GiaoViec tuỳ chọn
    try:
        gv = _doc_raw_values_sheet(KE_HOACH_CV_KHNV_SHEET_GV, sheet_id)
        gv_msg = f"{KE_HOACH_CV_KHNV_SHEET_GV} {len(gv)} dòng"
    except Exception as e:
        if _la_loi_tab_khong_ton_tai(e):
            _LAST_ERROR = None
            gv_msg = f"{KE_HOACH_CV_KHNV_SHEET_GV} chưa tạo (tuỳ chọn)"
        else:
            logger.error("kiem_tra_ket_noi: %s", e, exc_info=True)
            return False, f"{type(e).__name__}: {e}{_goi_y_loi_gsheet(e)}"

    return (
        True,
        f"OK — {cred_path.name}: {KE_HOACH_CV_KHNV_SHEET_KH} {len(kh)} dòng, "
        f"{KE_HOACH_CV_KHNV_SHEET_KQ} {len(kq)} dòng, {nv_msg}, {gv_msg}",
    )


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


def _today_iso() -> str:
    return date.today().isoformat()


def _normal_date_iso(value: Any) -> str:
    if isinstance(value, date):
        return value.isoformat()
    if pd.isna(value):
        return ""
    try:
        ts = pd.to_datetime(value, dayfirst=True, errors="coerce")
        if pd.isna(ts):
            return ""
        return ts.date().isoformat()
    except Exception:
        return ""


def _doc_nhiem_vu_app_raw() -> list[dict[str, Any]]:
    raw = db.doc_kv(KV_NHIEM_VU_GIAO) or []
    return raw if isinstance(raw, list) else []


def doc_nhiem_vu_app() -> pd.DataFrame:
    """Đọc nhiệm vụ lãnh đạo giao được nhập trực tiếp trong app."""
    rows = []
    for item in _doc_nhiem_vu_app_raw():
        if not isinstance(item, dict):
            continue
        row = {
            "thoi_gian": item.get("created_at", ""),
            "ma_nhiem_vu": item.get("ma_nhiem_vu", ""),
            "ngay_giao": item.get("ngay_giao", ""),
            "nguoi_giao": item.get("nguoi_giao", ""),
            "can_bo_nhan": item.get("can_bo_nhan", ""),
            "nhom_cong_tac": item.get("nhom_cong_tac", ""),
            "noi_dung": item.get("noi_dung", ""),
            "san_pham": item.get("san_pham", ""),
            "han_hoan_thanh": item.get("han_hoan_thanh", ""),
            "uu_tien": item.get("uu_tien", ""),
            "trang_thai": item.get("trang_thai", ""),
            "ghi_chu": item.get("ghi_chu", ""),
            "nguon": "VBSP-SCM",
        }
        rows.append(row)
    if not rows:
        return pd.DataFrame(columns=COT_NV_GIAO + ["han", "nguon"])
    result = pd.DataFrame(rows)
    for col in ["thoi_gian", "ngay_giao", "han_hoan_thanh"]:
        result[col] = pd.to_datetime(result[col], errors="coerce")
    for col in result.columns:
        if col not in {"thoi_gian", "ngay_giao", "han_hoan_thanh", "han"}:
            result[col] = result[col].apply(_clean_text)
    result["han"] = result["han_hoan_thanh"].dt.date
    return result


def tao_ma_nhiem_vu(ds_hien_tai: list[dict[str, Any]] | None = None) -> str:
    """Tạo mã nhiệm vụ ngắn, đủ ổn định để cán bộ đối chiếu khi báo cáo."""
    today = date.today()
    prefix = f"NV-{today:%Y%m%d}-"
    ds = ds_hien_tai if ds_hien_tai is not None else _doc_nhiem_vu_app_raw()
    max_seq = 0
    for item in ds:
        ma = str(item.get("ma_nhiem_vu", "") if isinstance(item, dict) else "")
        if ma.startswith(prefix):
            try:
                max_seq = max(max_seq, int(ma.rsplit("-", 1)[-1]))
            except ValueError:
                continue
    return f"{prefix}{max_seq + 1:03d}"


def them_nhiem_vu_app(payload: dict[str, Any], username: str) -> dict[str, Any]:
    """Thêm nhiệm vụ lãnh đạo giao vào kv_store và ghi audit."""
    ds = _doc_nhiem_vu_app_raw()
    ma_nv = _clean_text(payload.get("ma_nhiem_vu")) or tao_ma_nhiem_vu(ds)
    now_iso = pd.Timestamp.now().isoformat(timespec="seconds")
    item = {
        "id": str(uuid.uuid4()),
        "ma_nhiem_vu": ma_nv,
        "ngay_giao": _normal_date_iso(payload.get("ngay_giao")) or _today_iso(),
        "nguoi_giao": _clean_text(payload.get("nguoi_giao")) or username,
        "can_bo_nhan": _clean_text(payload.get("can_bo_nhan")),
        "nhom_cong_tac": _clean_text(payload.get("nhom_cong_tac")),
        "noi_dung": _clean_text(payload.get("noi_dung")),
        "san_pham": _clean_text(payload.get("san_pham")),
        "han_hoan_thanh": _normal_date_iso(payload.get("han_hoan_thanh")),
        "uu_tien": _clean_text(payload.get("uu_tien")) or "Bình thường",
        "trang_thai": _clean_text(payload.get("trang_thai")) or "Mới giao",
        "ghi_chu": _clean_text(payload.get("ghi_chu")),
        "created_at": now_iso,
        "created_by": username,
        "updated_at": now_iso,
        "updated_by": username,
    }
    if not item["can_bo_nhan"]:
        raise ValueError("Thiếu cán bộ nhận nhiệm vụ")
    if not item["noi_dung"]:
        raise ValueError("Thiếu nội dung nhiệm vụ")
    if not item["han_hoan_thanh"]:
        raise ValueError("Thiếu hạn hoàn thành")
    ds.insert(0, item)
    db.ghi_kv(KV_NHIEM_VU_GIAO, ds, username)
    db.ghi_audit(
        username,
        "khnv_them_nhiem_vu_giao",
        f"{ma_nv} — {item['can_bo_nhan']} — hạn {item['han_hoan_thanh']}",
    )
    return item


def cap_nhat_trang_thai_nhiem_vu_app(
    ma_nhiem_vu: str,
    trang_thai: str,
    ghi_chu: str,
    username: str,
) -> bool:
    """Cập nhật trạng thái nhiệm vụ app theo mã nhiệm vụ."""
    ma = _clean_text(ma_nhiem_vu)
    ds = _doc_nhiem_vu_app_raw()
    changed = False
    now_iso = pd.Timestamp.now().isoformat(timespec="seconds")
    for item in ds:
        if isinstance(item, dict) and _clean_text(item.get("ma_nhiem_vu")) == ma:
            item["trang_thai"] = _clean_text(trang_thai) or item.get("trang_thai", "")
            item["ghi_chu"] = _clean_text(ghi_chu)
            item["updated_at"] = now_iso
            item["updated_by"] = username
            changed = True
            break
    if not changed:
        return False
    db.ghi_kv(KV_NHIEM_VU_GIAO, ds, username)
    db.ghi_audit(username, "khnv_cap_nhat_nhiem_vu_giao", f"{ma} — {trang_thai}")
    return True


def xoa_nhiem_vu_app(ma_nhiem_vu: str, username: str) -> bool:
    """Xóa nhiệm vụ app theo mã nhiệm vụ."""
    ma = _clean_text(ma_nhiem_vu)
    ds = _doc_nhiem_vu_app_raw()
    ds_moi = [
        item
        for item in ds
        if not (isinstance(item, dict) and _clean_text(item.get("ma_nhiem_vu")) == ma)
    ]
    if len(ds_moi) == len(ds):
        return False
    db.ghi_kv(KV_NHIEM_VU_GIAO, ds_moi, username)
    db.ghi_audit(username, "khnv_xoa_nhiem_vu_giao", ma)
    return True


def gop_nhiem_vu(df_app: pd.DataFrame, df_gsheet: pd.DataFrame) -> pd.DataFrame:
    """Gộp nhiệm vụ từ VBSP-SCM và Google Sheet, ưu tiên dòng app khi trùng mã."""
    frames = [
        frame
        for frame in [df_app, df_gsheet]
        if isinstance(frame, pd.DataFrame) and not frame.empty
    ]
    if not frames:
        return pd.DataFrame(columns=COT_NV_GIAO + ["han", "nguon", "qua_han"])
    result = pd.concat(frames, ignore_index=True, sort=False)
    if "ma_nhiem_vu" in result.columns:
        result["_source_rank"] = result.get("nguon", "").map({"VBSP-SCM": 0}).fillna(1)
        result = (
            result.sort_values(["ma_nhiem_vu", "_source_rank"])
            .drop_duplicates("ma_nhiem_vu", keep="first")
            .drop(columns=["_source_rank"])
        )
    today = date.today()
    result["qua_han"] = result.apply(
        lambda row: bool(
            isinstance(row.get("han"), date)
            and row.get("han") < today
            and not _is_done(row.get("trang_thai"))
        ),
        axis=1,
    )
    return result.sort_values(["qua_han", "han"], ascending=[False, True], na_position="last")


def tinh_tong_hop_nhiem_vu(df_nv: pd.DataFrame) -> dict[str, int]:
    """Tính KPI nhiệm vụ lãnh đạo giao."""
    if not isinstance(df_nv, pd.DataFrame) or df_nv.empty:
        return {"tong": 0, "hoan_thanh": 0, "qua_han": 0, "dang_mo": 0}
    hoan_thanh = int(df_nv.get("trang_thai", pd.Series(dtype=str)).apply(_is_done).sum())
    qua_han = int(df_nv.get("qua_han", pd.Series(dtype=bool)).fillna(False).sum())
    tong = int(len(df_nv))
    return {
        "tong": tong,
        "hoan_thanh": hoan_thanh,
        "qua_han": qua_han,
        "dang_mo": max(0, tong - hoan_thanh),
    }


def tinh_tong_hop(df_kh: pd.DataFrame, df_kq: pd.DataFrame) -> dict[str, Any]:
    """Tính KPI tuần hiện tại, ma trận cán bộ × tuần và dữ liệu biểu đồ."""
    today_monday = _monday_of(date.today())
    kh = df_kh.copy() if isinstance(df_kh, pd.DataFrame) else pd.DataFrame(columns=COT_KH)
    kq = df_kq.copy() if isinstance(df_kq, pd.DataFrame) else pd.DataFrame(columns=COT_KQ)

    kh_tuan = kh[kh.get("tuan").eq(today_monday)] if "tuan" in kh.columns else pd.DataFrame()
    kq_tuan = kq[kq.get("tuan").eq(today_monday)] if "tuan" in kq.columns else pd.DataFrame()
    hoan_thanh = int(kq_tuan.get("trang_thai", pd.Series(dtype=str)).apply(_is_done).sum() or 0)
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
