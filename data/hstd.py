"""Đọc file dữ liệu gốc: HSTD, NQ11, GQVL, Điện báo."""
import os
from pathlib import Path

import pandas as pd
import streamlit as st

from data.core import ts_file, excel_to_parquet, _should_force_str, _normalize_code_series
from config import (
    CACHE_HSTD, CACHE_NQ11,
    GQVL_COT_MAP, CACHE_GQVL, CACHE_SK_GQVL,
)


# ── HSTD ─────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def doc_file(fp: str, _ts) -> pd.DataFrame:
    """Đọc file HSTD (BCQUERY sheet, header dòng 4).
    Không chạy kiem_tra_chat_luong ở đây — merge_du_lieu_toan_cn đã chạy DQ rồi.
    """
    def clean(df): return df.iloc[:, 1:].dropna(how="all")
    try:
        return excel_to_parquet(fp, CACHE_HSTD, "BCQUERY", 4, clean)
    except Exception:
        return pd.read_excel(fp, sheet_name="BCQUERY", header=4).iloc[:, 1:].dropna(how="all")


@st.cache_data(ttl=7200, show_spinner="Đang tải dữ liệu mốc 31/12...")
def doc_baseline(nam: int, _ts=0) -> pd.DataFrame | None:
    """Đọc HSTD mốc 31/12 theo năm. Trả None nếu chưa có file."""
    from config import baseline_path, baseline_cache
    fp = baseline_path(nam)
    cp = baseline_cache(nam)
    if not os.path.exists(fp):
        return None
    try:
        return excel_to_parquet(fp, cp, "BCQUERY", 4)
    except Exception:
        return pd.read_excel(fp, sheet_name="BCQUERY", header=4).iloc[:, 1:].dropna(how="all")


@st.cache_data(ttl=7200, show_spinner=False)
def doc_baseline_pgd(ten_pgd: str, nam: int, _ts=0) -> pd.DataFrame | None:
    """Đọc HSTD mốc 31/12 của một PGD cụ thể."""
    from config import baseline_path_pgd, CACHE_DIR
    from data.pgd import pgd_slug
    fp = baseline_path_pgd(ten_pgd, nam)
    if not os.path.exists(fp):
        return None
    try:
        cp = str(Path(CACHE_DIR) / f"hstd_bl_{pgd_slug(ten_pgd)}_{nam}.parquet")
        return excel_to_parquet(fp, cp, "BCQUERY", 4)
    except Exception:
        return pd.read_excel(fp, sheet_name="BCQUERY", header=4).iloc[:, 1:].dropna(how="all")


@st.cache_resource(show_spinner="Đang tổng hợp mốc 31/12...")
def doc_baseline_merged(nam: int) -> pd.DataFrame | None:
    """
    Đọc và merge HSTD mốc 31/12 từ tất cả đơn vị đã upload.
    Sử dụng parquet cache sau lần merge đầu tiên để load nhanh ở lần sau.
    Ưu tiên baseline_pgd_path; fallback về baseline_path cũ nếu không có đơn vị nào.
    Trả None nếu không có dữ liệu.
    """
    from config import BASELINE_PGD_DIR, baseline_pgd_path, baseline_path, baseline_cache_loai
    from config import DS_PGD, DON_VI_CHI_NHANH
    from config import COT_TEN_PGD as _COT_TEN_PGD   # cần trước cache-check block
    ds = [DON_VI_CHI_NHANH] + DS_PGD

    cache_path = baseline_cache_loai(nam, "hstd")
    _MIN_COLS = 15

    from logger import get_logger as _get_logger
    _rb_logger = _get_logger(__name__)

    # Check cache hợp lệ: mtime trước, rồi mới đọc full parquet (tránh đọc file lớn khi không cần)
    if os.path.exists(cache_path) and os.path.getsize(cache_path) >= 1000:
        cache_mtime = os.path.getmtime(cache_path)
        _stale = any(
            os.path.exists(baseline_pgd_path(dv, nam))
            and os.path.getmtime(baseline_pgd_path(dv, nam)) > cache_mtime
            for dv in ds
        )
        if not _stale:
            try:
                df_cache = pd.read_parquet(cache_path)
                if not df_cache.empty and len(df_cache.columns) >= _MIN_COLS:
                    _ds_co_file = [dv for dv in ds if os.path.exists(baseline_pgd_path(dv, nam))]
                    if _COT_TEN_PGD in df_cache.columns:
                        _pgd_cache = set(df_cache[_COT_TEN_PGD].dropna().unique())
                        _pgd_disk = set(_ds_co_file)
                        _thieu = _pgd_disk - _pgd_cache
                        if _thieu:
                            _rb_logger.warning(
                                "doc_baseline_merged: cache thiếu %d PGD (%d/%d đơn vị có file) → rebuild",
                                len(_thieu), len(_ds_co_file), len(ds),
                            )
                        else:
                            return df_cache
                    else:
                        return df_cache
            except Exception:
                pass

    # Rebuild: cache từng PGD bằng parquet → merge (song song để tăng tốc)
    from concurrent.futures import ThreadPoolExecutor

    def _clean_fn(df_: pd.DataFrame) -> pd.DataFrame:
        return df_.iloc[:, 1:].dropna(how="all")

    def _load_one(dv_: str):
        fp_ = baseline_pgd_path(dv_, nam)
        if not os.path.exists(fp_):
            return None
        try:
            path_pq_ = str(Path(fp_).with_suffix(".parquet"))
            df_ = excel_to_parquet(fp_, path_pq_, "BCQUERY", 4, _clean_fn)
            if df_ is not None and not df_.empty and len(df_.columns) >= _MIN_COLS:
                if _COT_TEN_PGD not in df_.columns:
                    df_ = df_.copy()
                    df_[_COT_TEN_PGD] = dv_
                return df_
        except Exception as e_:
            _rb_logger.error(
                "doc_baseline_merged: lỗi đọc baseline %s (%d) — %s",
                dv_, nam, e_, exc_info=True,
            )
        return None

    dfs = []
    with ThreadPoolExecutor(max_workers=min(8, len(ds))) as _pool:
        for _df in _pool.map(_load_one, ds):
            if _df is not None:
                dfs.append(_df)

    if dfs:
        result = pd.concat(dfs, ignore_index=True)
        # Sanitize bytes → str: tránh PyArrow "Expected bytes, got float" khi có cột
        # object chứa bytes từ cache cũ lẫn với NaN sau concat nhiều PGD
        for _col in list(result.columns):
            if result[_col].dtype == object:
                try:
                    _non_null = result[_col].dropna()
                    # Kiểm tra 100 phần tử đầu — không chỉ iloc[0] vì bytes có thể xuất hiện
                    # ở PGD thứ 2+ trong khi PGD đầu (Hội sở) có thể là string
                    if len(_non_null) > 0 and any(
                        isinstance(v, bytes) for v in _non_null.iloc[:100]
                    ):
                        result[_col] = result[_col].apply(
                            lambda x: x.decode("utf-8", errors="replace") if isinstance(x, bytes) else x
                        )
                except Exception:
                    pass
        for c in list(result.columns):
            if _should_force_str(c):
                result[c] = _normalize_code_series(result[c])
        # Sanitize object columns: bytes→str, mixed float/str → str
        # Phòng ArrowTypeError khi cột object chứa hỗn hợp bytes+float (e.g. "Số ATM")
        import math as _math
        for _sc in list(result.columns):
            if result[_sc].dtype == object:
                def _to_safe(v):
                    if v is None:
                        return None
                    if isinstance(v, bytes):
                        return v.decode("utf-8", errors="replace")
                    if isinstance(v, float) and _math.isnan(v):
                        return None
                    return v
                result[_sc] = result[_sc].map(_to_safe)
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        result.to_parquet(cache_path, index=False, engine="pyarrow", compression="zstd", compression_level=3)
        return result

    # fallback: file tổng cũ
    return doc_baseline(nam)


# ── NQ11 — kv_store approach (upload 1 lần) ──────────────────────────────────

def doc_so_khe_uoc_nq11() -> set[str]:
    """Đọc danh sách mã khế ước NQ11 từ kv_store."""
    import db as _db
    ids = _db.doc_kv("nq11_so_khe_uoc")
    return set(ids) if ids else set()


def luu_so_khe_uoc_nq11(file_bytes: bytes, username: str) -> tuple[int, str | None]:
    """Đọc file NQ11, lấy Số khế ước, lưu vào kv_store.

    Trả về (so_luong, None) nếu OK, (0, error_msg) nếu lỗi.
    """
    import db as _db
    from io import BytesIO
    from datetime import date
    try:
        df = pd.read_excel(BytesIO(file_bytes), sheet_name="BCQUERY", header=4)
        df = df.iloc[:, 1:].dropna(how="all")
        ku_col = next(
            (c for c in df.columns if "khế ước" in str(c).lower() or "khe uoc" in str(c).lower()),
            None,
        )
        if ku_col is None:
            return 0, "Không tìm thấy cột 'Số khế ước' trong file."
        # Chỉ lấy KU có DNO NQ11 > 0 — tránh đánh badge nhầm cho khoản đã tất toán
        dno_col = next(
            (c for c in df.columns if "dno nq11" in str(c).lower()),
            None,
        )
        if dno_col:
            _dno = pd.to_numeric(df[dno_col], errors="coerce").fillna(0)
            df = df[_dno > 0]
        ids = [
            x for x in df[ku_col].dropna().astype(str).str.strip().tolist()
            if x and x.lower() != "nan"
        ]
        if not ids:
            return 0, "File không có mã khế ước nào hợp lệ."
        _db.ghi_kv("nq11_so_khe_uoc", ids, username)
        _db.ghi_kv("nq11_meta", {
            "ngay_upload": date.today().strftime("%d/%m/%Y"),
            "so_luong": len(ids),
            "nguoi_upload": username,
        }, username)
        _db.ghi_audit(username, "luu_nq11_ids", f"Lưu {len(ids)} mã khế ước NQ11 vào kv_store")
        return len(ids), None
    except Exception as e:
        return 0, str(e)


# ── NQ11 — đọc file gốc (legacy / fallback) ──────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def doc_file_nq11(fp: str, _ts) -> pd.DataFrame:
    """Đọc file sao kê NQ11 (BCQUERY sheet, header dòng 4)."""
    def clean(df): return df.iloc[:, 1:].dropna(how="all")
    from services.data_quality import kiem_tra_chat_luong
    try:
        df = excel_to_parquet(fp, CACHE_NQ11, "BCQUERY", 4, clean)
    except Exception:
        df = pd.read_excel(fp, sheet_name="BCQUERY", header=4).iloc[:, 1:].dropna(how="all")
    return kiem_tra_chat_luong(df, "nq11").df


# ── GQVL ─────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def doc_file_gqvl(fp: str, _ts) -> pd.DataFrame:
    """Đọc file sao kê GQVL, chuẩn hoá tên cột."""
    from services.data_quality import kiem_tra_chat_luong
    try:
        os.makedirs(os.path.dirname(CACHE_GQVL), exist_ok=True)
        if ts_file(CACHE_GQVL) < ts_file(fp):
            df = pd.read_excel(fp, sheet_name="Sheet1", header=7)
            df = df.iloc[:, 1:].dropna(how="all").iloc[1:]
            df = df.rename(columns=GQVL_COT_MAP).reset_index(drop=True)
            df = kiem_tra_chat_luong(df, "gqvl").df
            df.to_parquet(CACHE_GQVL, index=False, compression='zstd', compression_level=9)
        return pd.read_parquet(CACHE_GQVL)
    except Exception:
        df = pd.read_excel(fp, sheet_name="Sheet1", header=7)
        df = df.iloc[:, 1:].dropna(how="all").iloc[1:]
        df = df.rename(columns=GQVL_COT_MAP).reset_index(drop=True)
        return kiem_tra_chat_luong(df, "gqvl").df


# ── SK GQVL (tra NQ11 cho món vay dư nợ = 0) ─────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def doc_file_sk_gqvl(fp: str, _ts) -> pd.DataFrame:
    """
    Đọc file sao kê GQVL chi tiết (SK_GQVL_du_lieu_tho.xlsx).
    Header ở dòng 7, bỏ dòng đầu tiên sau header (dòng tổng cộng).
    Chuẩn hoá tên cột theo GQVL_COT_MAP — kết quả có cột 'Số khế ước' và 'NQ11'.
    """
    def _doc(path: str) -> pd.DataFrame:
        df = pd.read_excel(path, sheet_name="Sheet1", header=7)
        df = df.iloc[:, 1:].dropna(how="all").iloc[1:].reset_index(drop=True)
        return df.rename(columns=GQVL_COT_MAP)

    try:
        os.makedirs(os.path.dirname(CACHE_SK_GQVL), exist_ok=True)
        if ts_file(CACHE_SK_GQVL) < ts_file(fp):
            _doc(fp).to_parquet(CACHE_SK_GQVL, index=False, compression='zstd', compression_level=9)
        return pd.read_parquet(CACHE_SK_GQVL)
    except Exception:
        return _doc(fp)


# ── ĐIỆN BÁO ─────────────────────────────────────────────────────────────────
@st.cache_data(ttl=7200, show_spinner=False)
def doc_dienbao(fp: str, ts: float = 0, sheet_name: str | None = None) -> list:
    """
    Đọc file Điện báo — tự động nhận diện format:
    Tham số ts (timestamp) dùng để cache bust — truyền ts_file(fp) khi gọi.

    Format 1 (cũ - dọc): Cột B = tên chỉ tiêu, Cột C = giá trị tổng.
    Format 2 (mới - ma trận): Cột B = tên chỉ tiêu, Cột C = Cộng (tổng),
                              từ Cột D trở đi = giá trị từng PGD.

    Trả về list[dict]: {ten, val, la_nqh_con, cha}
    val luôn là TỔNG (nếu nhiều cột PGD thì tự cộng).

    Nếu sheet_name được chỉ định, chỉ đọc sheet đó.
    """
    if sheet_name:
        df_raw = pd.read_excel(fp, sheet_name=sheet_name, header=None)
    else:
        df_raw = pd.read_excel(fp, header=None)

    # Tự động nhận diện: col[2] là "Cộng"/"Tổng" → đọc 1 cột, nếu không → cộng tất cả
    n_cols = len(df_raw.columns)
    col2_is_tong = False
    sum_all_cols = False
    if n_cols >= 5 and len(df_raw) >= 5:
        v2 = str(df_raw.iloc[4, 2]).strip().lower() if pd.notna(df_raw.iloc[4, 2]) else ""
        if "cộng" in v2 or "tong" in v2 or "tổng" in v2:
            col2_is_tong = True
        else:
            # col[2] là tên PGD (vd: "Hội sở CN Đồng Nai") → cần cộng tất cả cột
            sum_all_cols = True

    # ── Phát hiện đơn vị (triệu đồng hay đồng) ──
    # Mặc định coi là triệu đồng (VBSP dùng đơn vị này)
    don_vi_trieu = True
    # Kiểm tra text "đồng" mà không có "triệu" → đơn vị là đồng
    for i in range(min(8, len(df_raw))):
        for j in range(min(30, n_cols)):
            v = str(df_raw.iloc[i, j]).lower() if pd.notna(df_raw.iloc[i, j]) else ""
            if "triệu đồng" in v:
                don_vi_trieu = True
                break
            if "nghìn đồng" in v or ("đồng" in v and "triệu" not in v and "tỷ" not in v):
                don_vi_trieu = False

    rows, ten_cha = [], None
    skip_keywords = ("", "nan", "chỉ tiêu", "điện báo ngày", "stt", "b.", "a.", "i", "ii", "iii")
    nqh_prefixes = ("trđ:", "nqh:", "trd:")

    for _, row in df_raw.iterrows():
        ten = str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else ""

        # Bỏ qua dòng tiêu đề / trống
        if ten.lower() in skip_keywords or ten == "":
            continue
        # Bỏ qua dòng header của bảng
        if any(kw in ten.lower() for kw in ("điện báo", "ngân hàng", "chi nhánh", "cân đối")):
            continue

        # Đọc giá trị
        if sum_all_cols:
            # Cộng tất cả cột số từ col[2] trở đi
            val = 0.0
            for j in range(2, n_cols):
                try:
                    val += float(row.iloc[j]) if pd.notna(row.iloc[j]) else 0.0
                except (ValueError, TypeError):
                    pass
        else:
            # Đọc col[2] như cũ (Cộng/Tổng)
            try:
                val = float(row.iloc[2]) if pd.notna(row.iloc[2]) else 0.0
            except (ValueError, TypeError):
                val = 0.0

        # Phát hiện dòng NQH con
        if ten.startswith("-") or ten.startswith("+"):
            ten_clean = ten.lstrip("-+ ").strip()
            rows.append({"ten": f"  NQH: {ten_clean}", "val": val,
                         "la_nqh_con": True, "cha": ten_cha})
            continue
        elif any(ten.lower().startswith(p) for p in nqh_prefixes):
            rows.append({"ten": f"  NQH: {ten_cha}", "val": val,
                         "la_nqh_con": True, "cha": ten_cha})
            continue

        rows.append({"ten": ten, "val": val,
                     "la_nqh_con": False, "cha": None,
                     "don_vi_trieu": don_vi_trieu})
        ten_cha = ten

    return rows


def doc_dienbao_matrix(
    fp: str,
    ts: float = 0,
    sheet_name: str | None = None,
    cot_tong: int = 2,
) -> dict[str, list]:
    """
    Đọc file Điện báo format MA TRẬN (nhiều cột PGD).

    Trả về dict:
    {
        "rows": list[dict],       # như doc_dienbao() — cột Cộng
        "units": list[str],       # tên các đơn vị (HST, L.Thành, T.Bom, ...)
        "unit_codes": list[str],  # mã đơn vị (004601, 004602, ...)
        "matrix": {ten_ct: {ten_dv: float}},  # ma trận đầy đủ
        "ngay_bao_cao": str,      # ngày trên file
        "sheet_name": str,
    }
    """
    if sheet_name:
        df_raw = pd.read_excel(fp, sheet_name=sheet_name, header=None)
    else:
        df_raw = pd.read_excel(fp, header=None)

    # ── Trích xuất danh sách đơn vị (từ row 4, từ cột 3 trở đi) ──
    units = []
    unit_codes = []
    for j in range(3, len(df_raw.columns)):
        ten_dv = str(df_raw.iloc[4, j]).strip() if pd.notna(df_raw.iloc[4, j]) else ""
        raw_ma = df_raw.iloc[3, j]
        try:
            ma_dv = str(int(raw_ma)) if pd.notna(raw_ma) else ""
        except (ValueError, TypeError):
            # Row 3 chứa text (vd: "Đơn vị tính: Triệu đồng") — thử tìm ở row khác
            ma_dv = ""
            for fallback_row in (2, 4, 5):
                if fallback_row >= len(df_raw):
                    continue
                try:
                    v = df_raw.iloc[fallback_row, j]
                    if pd.notna(v):
                        ma_dv = str(int(v))
                        break
                except (ValueError, TypeError):
                    continue
        if ten_dv and ten_dv.lower() != "nan":
            units.append(ten_dv)
            unit_codes.append(ma_dv)

    # ── Trích xuất ngày báo cáo ──
    ngay_bc = ""
    for i in range(min(5, len(df_raw))):
        for j in range(len(df_raw.columns)):
            v = str(df_raw.iloc[i, j]) if pd.notna(df_raw.iloc[i, j]) else ""
            if "ngày" in v.lower():
                ngay_bc = v.replace("Ngày ", "").replace("ngày ", "").strip()
                break

    # ── Đọc chỉ tiêu + giá trị ──
    rows = []
    matrix = {}
    ten_cha = None
    skip_keywords = ("", "nan", "chỉ tiêu", "điện báo ngày", "stt",
                     "sử dụng vốn", "kế hoạch nguồn vốn", "trung ương",
                     "địa phương")

    for i in range(5, len(df_raw)):
        ten = str(df_raw.iloc[i, 1]).strip() if pd.notna(df_raw.iloc[i, 1]) else ""
        if not ten or ten.lower() in skip_keywords:
            continue
        if ten.lower() in ("i", "ii", "iii"):
            continue

        try:
            val_tong = float(df_raw.iloc[i, cot_tong]) if pd.notna(df_raw.iloc[i, cot_tong]) else 0.0
        except (ValueError, TypeError):
            val_tong = 0.0

        # Đọc giá trị từng đơn vị
        dv_vals = {}
        for j, dv_name in enumerate(units):
            col_idx = 3 + j
            try:
                dv_vals[dv_name] = float(df_raw.iloc[i, col_idx]) if pd.notna(df_raw.iloc[i, col_idx]) else 0.0
            except (ValueError, TypeError):
                dv_vals[dv_name] = 0.0

        matrix[ten] = dv_vals

        # Dòng con (bắt đầu bằng - hoặc +)
        if ten.startswith("-") or ten.startswith("+"):
            ten_clean = ten.lstrip("-+ ").strip()
            rows.append({"ten": f"  NQH: {ten_clean}", "val": val_tong,
                         "la_nqh_con": True, "cha": ten_cha})
        else:
            rows.append({"ten": ten, "val": val_tong,
                         "la_nqh_con": False, "cha": None})
            ten_cha = ten

    return {
        "rows": rows,
        "units": units,
        "unit_codes": unit_codes,
        "matrix": matrix,
        "ngay_bao_cao": ngay_bc,
        "sheet_name": sheet_name or "",
    }


def liet_ke_sheet_dienbao(fp: str) -> list[dict]:
    """Liệt kê các sheet trong file Điện báo, kèm metadata."""
    import pandas as pd
    xls = pd.ExcelFile(fp)
    result = []
    for s in xls.sheet_names:
        df = pd.read_excel(fp, sheet_name=s, header=None)
        n_rows = len(df)
        n_cols = len(df.columns)
        # Xác định format
        is_matrix = False
        if n_cols >= 5 and n_rows >= 5:
            v = str(df.iloc[4, 2]).strip().lower() if pd.notna(df.iloc[4, 2]) else ""
            if "cộng" in v or "tong" in v:
                is_matrix = True
        # Đếm đơn vị nếu là matrix
        n_dv = 0
        if is_matrix:
            for j in range(3, n_cols):
                if pd.notna(df.iloc[4, j]) and str(df.iloc[4, j]).strip().lower() != "nan":
                    n_dv += 1
        # Tìm ngày
        ngay = ""
        for i in range(min(5, n_rows)):
            for j in range(min(20, n_cols)):
                v = str(df.iloc[i, j]) if pd.notna(df.iloc[i, j]) else ""
                if "ngày" in v.lower():
                    ngay = v.strip()[:60]
                    break
        result.append({
            "sheet": s,
            "rows": n_rows,
            "cols": n_cols,
            "format": "matrix" if is_matrix else "doc",
            "n_don_vi": n_dv,
            "ngay": ngay,
        })
    return result


def db_lookup(rows: list, ten_search: str) -> float:
    """Tìm giá trị theo tên chỉ tiêu (chính xác → gần đúng)."""
    if not rows:
        return 0.0
    ten_l = ten_search.lower()
    for r in rows:
        if not r["la_nqh_con"] and r["ten"].strip() == ten_search.strip():
            return r["val"]
    for r in rows:
        if not r["la_nqh_con"] and ten_l in r["ten"].lower():
            return r["val"]
    return 0.0


def db_nqh_con(rows: list, ten_cha: str) -> float:
    """Lấy giá trị NQH dòng con ngay sau ten_cha."""
    for r in rows:
        if r["la_nqh_con"] and r["cha"] == ten_cha:
            return r["val"]
    return 0.0


# ── Phân tích rủi ro: 3 tháng không hoạt động ────────────────────────────────

def danh_dau_khong_hd(df: "pd.DataFrame") -> "pd.DataFrame":
    """
    Đánh dấu món vay 3 tháng không hoạt động (KHĐ).

    Công thức: (Ngày báo cáo − Ngày giao dịch gần nhất) / 30.44 >= 3 tháng.
    Chỉ dùng cột "Ngày giao dịch gần nhất" từ HSTD — không fallback sang Ngày vay
    hay lãi tồn. Món nào GDGN trống → không bị tính vào KHĐ.

    Loại trừ: (Dư nợ TH + Dư nợ QH) ≤ 0; Dư nợ khoanh > 0;
    Học sinh sinh viên (Mã chương trình 02 hoặc tên CT chứa "sinh viên"/"học sinh").

    Thêm cột: is_3m_inactive (bool), so_thang_khong_hd (float, làm tròn 1 chữ số).
    """
    from config import (
        NGUONG_KHONG_HĐ_THANG,
        COT_NGAY_GDGN,
        COT_NGAY_SL,
        COT_DU_NO_TH,
        COT_DU_NO_QH,
        COT_MA_CHUONG_TRINH,
        COT_TEN_CT,
    )

    COT_DU_NO_KHOANH = "Dư nợ khoanh"
    df = df.copy()

    du_th = pd.to_numeric(df[COT_DU_NO_TH], errors="coerce").fillna(0) if COT_DU_NO_TH in df.columns else pd.Series(0.0, index=df.index)
    du_qh = pd.to_numeric(df[COT_DU_NO_QH], errors="coerce").fillna(0) if COT_DU_NO_QH in df.columns else pd.Series(0.0, index=df.index)
    du_kh = pd.to_numeric(df[COT_DU_NO_KHOANH], errors="coerce").fillna(0) if COT_DU_NO_KHOANH in df.columns else pd.Series(0.0, index=df.index)

    # Loại trừ: dư nợ = 0, nợ khoanh
    mask_loai_tru = ((du_th + du_qh) <= 0) | (du_kh > 0)

    # Loại trừ: Học sinh sinh viên (mã 02 hoặc tên CT chứa từ khóa)
    if COT_MA_CHUONG_TRINH in df.columns:
        ma_raw = df[COT_MA_CHUONG_TRINH]
        ma_num = pd.to_numeric(ma_raw, errors="coerce")
        ma_str = ma_raw.astype(str).str.strip()
        mask_hssv = (ma_num == 2) | (ma_str == "02") | (ma_str == "2")
        mask_loai_tru = mask_loai_tru | mask_hssv
    if COT_TEN_CT in df.columns:
        ten_ct_lower = df[COT_TEN_CT].astype(str).str.lower()
        mask_hssv_ten = ten_ct_lower.str.contains("sinh viên|học sinh|hssv|stem", na=False)
        mask_loai_tru = mask_loai_tru | mask_hssv_ten

    # Tính số tháng từ Ngày GDGN đến Ngày báo cáo
    if COT_NGAY_GDGN not in df.columns or COT_NGAY_SL not in df.columns:
        # Priority-2 fallback: lãi tồn / lãi tháng ≥ 3 → đánh dấu KHĐ
        from config import COT_LAI_TON, COT_LAI_THANG
        if COT_LAI_TON in df.columns and COT_LAI_THANG in df.columns:
            lai_ton   = pd.to_numeric(df[COT_LAI_TON],   errors="coerce").fillna(0)
            lai_thang = pd.to_numeric(df[COT_LAI_THANG], errors="coerce").fillna(0)
            so_thang_p2 = pd.Series(float("nan"), index=df.index, dtype=float)
            mask_nonzero = lai_thang > 0
            so_thang_p2[mask_nonzero] = lai_ton[mask_nonzero] / lai_thang[mask_nonzero]
            mask_p2 = mask_nonzero & (so_thang_p2 >= 3)
            df["is_3m_inactive"]    = mask_p2 & (~mask_loai_tru)
            df["so_thang_khong_hd"] = so_thang_p2.round(1)
        else:
            df["is_3m_inactive"]    = False
            df["so_thang_khong_hd"] = float("nan")
        return df

    ngay_sl   = pd.to_datetime(df[COT_NGAY_SL].astype(object),   errors="coerce", dayfirst=True)
    ngay_gdgn = pd.to_datetime(df[COT_NGAY_GDGN].astype(object), errors="coerce", dayfirst=True)

    days      = (ngay_sl - ngay_gdgn).dt.days          # NaT → NaN
    so_thang  = days.astype(float) / 30.44
    df["so_thang_khong_hd"] = so_thang.round(1)

    # GDGN trống (NaT) → so_thang = NaN → notna() = False → không tính KHĐ
    mask_khd = (so_thang >= float(NGUONG_KHONG_HĐ_THANG)) & so_thang.notna()
    df["is_3m_inactive"] = mask_khd & (~mask_loai_tru)
    return df


@st.cache_data(show_spinner=False, ttl=300)
def danh_dau_khong_hd_cached(_df: "pd.DataFrame", ts: float = 0.0) -> "pd.DataFrame":
    """Cache by ts — không hash DataFrame để tránh chậm trên tập dữ liệu lớn."""
    _ = ts
    return danh_dau_khong_hd(_df)


@st.cache_data(show_spinner=False, ttl=300)
def tong_hop_khong_hd_cached(_df: "pd.DataFrame", nhom_theo: str = "Tên ĐVUT", ts: float = 0.0) -> "pd.DataFrame":
    _ = ts
    return tong_hop_khong_hd(_df, nhom_theo=nhom_theo)


@st.cache_data(show_spinner=False, ttl=300)
def canh_bao_migration_cached(_df: "pd.DataFrame", ts: float = 0.0) -> "pd.DataFrame":
    _ = ts
    return canh_bao_migration(_df)


def tong_hop_khong_hd(df: "pd.DataFrame",
                      nhom_theo: str = "Tên ĐVUT") -> "pd.DataFrame":
    """
    Tổng hợp số món 'không hoạt động 3 tháng' theo nhóm.

    Tham số:
        df        : DataFrame đã qua danh_dau_khong_hd()
        nhom_theo : Cột để group — "Tên ĐVUT", "Tên xã", "Tên PGD", "Tên thôn"

    Trả về DataFrame gồm:
        nhom_theo | Tổng_món | Món_3m_KHĐ | Tỷ_lệ_KHĐ_%
        | Lãi_tồn_KHĐ | Dư_nợ_KHĐ
    """
    from config import (COT_SO_KU, COT_TONG_DU_NO, COT_LAI_TON,
                        COT_DU_NO_TH, COT_DU_NO_QH)

    if "is_3m_inactive" not in df.columns:
        df = danh_dau_khong_hd(df)

    if nhom_theo not in df.columns:
        return pd.DataFrame()

    df_inactive = df[df["is_3m_inactive"]]

    # Tổng toàn bộ theo nhóm
    tong = df.groupby(nhom_theo).agg(
        Tổng_món=(COT_SO_KU, "nunique"),
    ).reset_index()

    # Tổng món không hoạt động theo nhóm
    khd = df_inactive.groupby(nhom_theo).agg(
        Món_3m_KHĐ   =(COT_SO_KU,       "nunique"),
        Lãi_tồn_KHĐ  =(COT_LAI_TON,     "sum"),
        Dư_nợ_KHĐ    =(COT_TONG_DU_NO,  "sum"),
    ).reset_index()

    result = tong.merge(khd, on=nhom_theo, how="left").fillna(0)
    result["Món_3m_KHĐ"]  = result["Món_3m_KHĐ"].astype(int)
    result["Tỷ_lệ_KHĐ_%"] = (
        result["Món_3m_KHĐ"] / result["Tổng_món"] * 100
    ).round(1).fillna(0)

    return result.sort_values("Món_3m_KHĐ", ascending=False).reset_index(drop=True)


def ds_chi_tiet_khong_hd(df: "pd.DataFrame",
                          nhom_theo: str = "Tên ĐVUT",
                          gia_tri_nhom: str = None) -> "pd.DataFrame":
    """
    Danh sách chi tiết các hộ cần đôn đốc (3 tháng không hoạt động).
    Dùng để xuất Excel giao CBTD đi đôn đốc.

    Tham số:
        df            : DataFrame đã qua danh_dau_khong_hd()
        nhom_theo     : Cột lọc (mặc định "Tên ĐVUT")
        gia_tri_nhom  : Giá trị nhóm cần lấy (None = tất cả)
    """
    import logging

    from config import (
        COT_TEN_PGD,
        COT_TEN_XA,
        COT_MA_KH,
        COT_TEN_KH,
        COT_SO_KU,
        COT_NGAY_GDGN,
        COT_TEN_CT,
        COT_TONG_DU_NO,
        COT_LAI_TON,
        COT_DVUT,
        COT_NGAY_DH,
    )

    if "is_3m_inactive" not in df.columns:
        df = danh_dau_khong_hd(df)

    ds = df[df["is_3m_inactive"]].copy()

    if gia_tri_nhom and nhom_theo in ds.columns:
        ds = ds[ds[nhom_theo] == gia_tri_nhom]

    logging.debug(
        "Cột ngày hạn: %s",
        [c for c in ds.columns if "hạn" in c.lower()],
    )
    logging.debug(
        "Cột lãi tồn: %s",
        [c for c in ds.columns if "lãi" in c.lower() and "tồn" in c.lower()],
    )

    cot_lai_ton_qh = None
    for alias in ("Lãi tồn QH", "Lãi quá hạn tồn", "Lãi tồn quá hạn"):
        if alias in ds.columns:
            cot_lai_ton_qh = alias
            break

    if COT_LAI_TON in ds.columns:
        lai_th = pd.to_numeric(ds[COT_LAI_TON], errors="coerce").fillna(0)
    else:
        lai_th = pd.Series(0.0, index=ds.index, dtype="float64")

    if cot_lai_ton_qh is not None:
        lai_qh = pd.to_numeric(ds[cot_lai_ton_qh], errors="coerce").fillna(0)
    else:
        lai_qh = pd.Series(0.0, index=ds.index, dtype="float64")

    ds["Lãi tồn"] = lai_th + lai_qh

    cot_ngay_han = None
    for alias in (
        "Ngày đến hạn cuối",
        "Ngày đến hạn (sau GH)",
        "Ngày đến hạn GH",
        "Ngày ĐH cuối",
        COT_NGAY_DH,
    ):
        if alias in ds.columns:
            cot_ngay_han = alias
            break
    if cot_ngay_han is not None:
        ds["Ngày đến hạn cuối"] = ds[cot_ngay_han]

    cols_xuat = [
        c
        for c in [
            COT_TEN_PGD,
            COT_TEN_XA,
            COT_DVUT,
            "Tên tổ",
            COT_MA_KH,
            COT_TEN_KH,
            COT_SO_KU,
            COT_TEN_CT,
            "Ngày đến hạn cuối",
            COT_TONG_DU_NO,
            "Lãi tồn",
            COT_NGAY_GDGN,
        ]
        if c in ds.columns
    ]

    return ds[cols_xuat].reset_index(drop=True)


def canh_bao_migration(df: "pd.DataFrame") -> "pd.DataFrame":
    """
    Phát hiện món vay 'Đủ tiêu chuẩn' (Phân loại=E) có dấu hiệu
    sắp chuyển sang '3 tháng không lãi' — cảnh báo sớm trước NQH.

    Điều kiện:
        - Phân loại = E (Đủ tiêu chuẩn — chưa quá hạn)
        - Lãi tồn TH > 0  (đã bắt đầu tồn lãi)
        - Lãi tồn TH > 1 tháng lãi dự thu (cảnh báo từ tháng thứ 2)
        - Chưa đủ 3 tháng (is_3m_inactive = False)
        → Vùng "amber": cần chú ý, chưa vi phạm nhưng có rủi ro cao

    Trả về DataFrame chỉ gồm các món ở vùng cảnh báo, có thêm cột:
        'so_thang_ton_uoc' — số tháng lãi tồn ước tính
        'muc_canh_bao'     — "⚠️ Cảnh báo" hoặc "🔴 Khẩn cấp"
    """
    from config import (COT_LAI_TON, COT_LAI_THANG, COT_PHAN_LOAI,
                        COT_SO_KU, COT_TEN_KH, COT_TEN_PGD,
                        COT_TEN_XA, COT_DVUT)

    if "is_3m_inactive" not in df.columns:
        df = danh_dau_khong_hd(df)

    lai_ton   = pd.to_numeric(df[COT_LAI_TON],   errors="coerce").fillna(0)
    lai_thang = pd.to_numeric(df[COT_LAI_THANG], errors="coerce").fillna(1)

    mask_e = df[COT_PHAN_LOAI].astype(str).str.strip().str.upper() == "E" \
             if COT_PHAN_LOAI in df.columns else pd.Series(True, index=df.index)
    so_thang = lai_ton / lai_thang.clip(lower=1)
    mask_amber = (
        mask_e &
        (so_thang >= 2.0) &           # từ 2 tháng trở lên
        (~df["is_3m_inactive"])        # chưa đủ 3 tháng (chưa bị đánh dấu)
    )

    result = df[mask_amber].copy()
    result["so_thang_ton_uoc"] = so_thang[mask_amber].round(1)
    result["muc_canh_bao"] = result["so_thang_ton_uoc"].apply(
        lambda x: "🔴 Nguy cơ cao (2.5–3 tháng)" if x >= 2.5 else "⚠️ Sắp chuyển 3 tháng KHĐ (2–2.4 tháng)"
    )
    return result.reset_index(drop=True)
