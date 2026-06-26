"""Service: các hàm thuần túy cho tab KHTD Nhập (không có st.* calls)."""
from __future__ import annotations

import json
import re
from io import BytesIO
from datetime import datetime
from pathlib import Path

import pandas as pd

import db
from config import CHUONG_TRINH_KHTD, COT_MA_CHUONG_TRINH, COT_NGUON_VON, COT_TONG_DU_NO, COT_DU_NO_TH, COT_SO_KU
try:
    from logger import get_logger
    logger = get_logger(__name__)
except Exception as e:
    logger.error("Lỗi trong khối except: %s", e, exc_info=True)
    import logging
    logger = logging.getLogger(__name__)


def clean_sheet_name(name: str) -> str:
    """Giới hạn 31 ký tự và loại bỏ ký tự đặc biệt cho tên sheet Excel."""
    cleaned = re.sub(r'[\\/*?[\]:]', '', name.strip())
    return cleaned[:31]


def _norm_so_ku(v) -> str:
    """Chuẩn hóa Số khế ước để join HSTD <-> GQVL ổn định."""
    if pd.isna(v):
        return ""
    s = str(v).strip()
    if re.fullmatch(r"\d+\.0", s):
        return s[:-2]
    return s


def _fallback_gqvl_tu_hstd(df_hstd: pd.DataFrame) -> dict[str, float]:
    """Fallback cũ: chia đều TH HSTD của mã CT=3 theo từng nguồn vốn."""
    result = {
        "3_TW_NHCSXH": 0.0,
        "3_TW_NSNN": 0.0,
        "3_DP_TINH": 0.0,
        "3_DP_XA": 0.0,
    }
    if df_hstd is None or df_hstd.empty:
        return result
    col_dn = COT_TONG_DU_NO if COT_TONG_DU_NO in df_hstd.columns else (
        COT_DU_NO_TH if COT_DU_NO_TH in df_hstd.columns else None
    )
    if not col_dn or COT_MA_CHUONG_TRINH not in df_hstd.columns or COT_NGUON_VON not in df_hstd.columns:
        return result

    ma_ct = pd.to_numeric(df_hstd[COT_MA_CHUONG_TRINH], errors="coerce").fillna(0).astype(int)
    nv = pd.to_numeric(df_hstd[COT_NGUON_VON], errors="coerce").fillna(0).astype(int)
    dn = pd.to_numeric(df_hstd[col_dn], errors="coerce").fillna(0).astype(float)

    tong_tw = float(dn[(ma_ct == 3) & (nv == 1)].sum())
    tong_dp = float(dn[(ma_ct == 3) & (nv == 2)].sum())
    result["3_TW_NHCSXH"] = tong_tw / 2.0
    result["3_TW_NSNN"] = tong_tw / 2.0
    result["3_DP_TINH"] = tong_dp / 2.0
    result["3_DP_XA"] = tong_dp / 2.0
    return result


def tinh_th_gqvl_phan_tang(
    df_hstd: pd.DataFrame | None,
    df_gqvl: pd.DataFrame | None,
) -> dict[str, float]:
    """
    Tính TH GQVL phân tầng 4 nhóm.

    - Số TH luôn lấy từ HSTD.
    - GQVL chỉ dùng làm bảng tham chiếu để xác định mỗi Số khế ước thuộc nhóm nào.
    - Nếu một phần khoản vay không match được sang GQVL thì phần còn lại fallback về cách chia cũ
      theo nguồn vốn để không làm hụt tổng TH.
    """
    from config import GQVL_PHAN_TANG, COT_PL_NV, COT_MA_NHA_DAU_TU
    from db import phan_loai_ndt_dp_cap

    result = {row[3]: 0.0 for row in GQVL_PHAN_TANG}
    result.setdefault("3_TW_NHCSXH", 0.0)
    result.setdefault("3_TW_NSNN", 0.0)
    result.setdefault("3_DP_TINH", 0.0)
    result.setdefault("3_DP_XA", 0.0)

    if df_hstd is None or df_hstd.empty:
        return result

    col_dn = COT_TONG_DU_NO if COT_TONG_DU_NO in df_hstd.columns else (
        COT_DU_NO_TH if COT_DU_NO_TH in df_hstd.columns else None
    )
    if (
        not col_dn
        or COT_MA_CHUONG_TRINH not in df_hstd.columns
        or COT_NGUON_VON not in df_hstd.columns
        or COT_SO_KU not in df_hstd.columns
    ):
        return result

    fallback = _fallback_gqvl_tu_hstd(df_hstd)
    if df_gqvl is None or df_gqvl.empty or COT_SO_KU not in df_gqvl.columns:
        return fallback

    df_h = pd.DataFrame(
        {
            "so_ku": df_hstd[COT_SO_KU].map(_norm_so_ku),
            "ma_ct": pd.to_numeric(df_hstd[COT_MA_CHUONG_TRINH], errors="coerce").fillna(0).astype(int),
            "nv": pd.to_numeric(df_hstd[COT_NGUON_VON], errors="coerce").fillna(0).astype(int),
            "th": pd.to_numeric(df_hstd[col_dn], errors="coerce").fillna(0).astype(float),
        }
    )
    df_h = df_h[(df_h["ma_ct"] == 3) & (df_h["nv"].isin([1, 2])) & (df_h["th"] != 0)]
    if df_h.empty:
        return result

    df_g = pd.DataFrame(
        {
            "so_ku": df_gqvl[COT_SO_KU].map(_norm_so_ku),
            "pl_nv": pd.to_numeric(df_gqvl.get(COT_PL_NV, pd.Series(dtype=object)), errors="coerce"),
            "ma_ndt": df_gqvl.get(COT_MA_NHA_DAU_TU, pd.Series(dtype=object)).fillna("").astype(str).str.strip(),
        }
    )
    df_g = df_g[df_g["so_ku"] != ""].drop_duplicates(subset=["so_ku"], keep="first")
    if df_g.empty:
        return fallback

    df_m = df_h.merge(df_g, on="so_ku", how="left")

    mask_tw = df_m["nv"] == 1
    th_tw_nhcsxh = float(df_m.loc[mask_tw & (df_m["pl_nv"] == 2), "th"].sum())
    th_tw_nsnn = float(df_m.loc[mask_tw & (df_m["pl_nv"] == 1), "th"].sum())
    tong_tw = float(df_m.loc[mask_tw, "th"].sum())
    con_lai_tw = max(0.0, tong_tw - th_tw_nhcsxh - th_tw_nsnn)
    result["cap_tinh_tw_nhcsxh"] = th_tw_nhcsxh + con_lai_tw / 2.0
    result["cap_tinh_tw_nsnn"] = th_tw_nsnn + con_lai_tw / 2.0

    mask_dp = df_m["nv"] == 2
    cap_dp = df_m["ma_ndt"].map(lambda ma: phan_loai_ndt_dp_cap(3, ma))
    th_dp_tinh = float(df_m.loc[mask_dp & cap_dp.eq("tinh"), "th"].sum())
    th_dp_xa = float(df_m.loc[mask_dp & cap_dp.eq("xa"), "th"].sum())
    tong_dp = float(df_m.loc[mask_dp, "th"].sum())
    con_lai_dp = max(0.0, tong_dp - th_dp_tinh - th_dp_xa)
    result["cap_tinh"] = th_dp_tinh + con_lai_dp / 2.0
    result["cap_xa"] = th_dp_xa + con_lai_dp / 2.0

    result["3_TW_NHCSXH"] = result.get("cap_tinh_tw_nhcsxh", 0.0)
    result["3_TW_NSNN"] = result.get("cap_tinh_tw_nsnn", 0.0)
    result["3_DP_TINH"] = result.get("cap_tinh", 0.0)
    result["3_DP_XA"] = result.get("cap_xa", 0.0)
    return result


def format_kich_thuoc(byte_count: int) -> str:
    """Định dạng dung lượng file thành chuỗi dễ đọc."""
    if byte_count >= 1_048_576:
        return f"{byte_count / 1_048_576:.1f} MB"
    return f"{byte_count / 1024:.1f} KB"


def doc_meta_qd(kv_key: str) -> list[dict]:
    """Đọc danh sách metadata file QĐ từ kv_store."""
    try:
        with db.get_conn() as conn:
            row = conn.execute(
                "SELECT value FROM kv_store WHERE key=?", (kv_key,)
            ).fetchone()
            if row:
                val = json.loads(row["value"])
                return val if isinstance(val, list) else []
    except Exception as e:
        logger.error("doc_cbtd_list: lỗi đọc kv key=%s — %s", kv_key, e, exc_info=True)
    return []


def luu_meta_qd(kv_key: str, danh_sach: list[dict], username: str) -> None:
    """Ghi danh sách metadata file QĐ vào kv_store. Raise Exception nếu lỗi."""
    with db.get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO kv_store (key, value, updated_at, updated_by) "
            "VALUES (?,?,?,?)",
            (kv_key, json.dumps(danh_sach, ensure_ascii=False),
             datetime.now().isoformat(), username),
        )
        conn.commit()


def luu_file_qd(uploaded, thu_muc: Path, kv_key: str, username: str) -> Path:
    """Lưu file mới với timestamp prefix, cập nhật metadata trong kv_store.

    Raise Exception nếu ghi DB thất bại — caller chịu trách nhiệm bắt lỗi.
    """
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    ten_goc = uploaded.name
    ten_luu = f"{ts}_{ten_goc}"
    thu_muc.mkdir(parents=True, exist_ok=True)
    duong_dan = thu_muc / ten_luu
    noi_dung = uploaded.getvalue()
    duong_dan.write_bytes(noi_dung)

    danh_sach = doc_meta_qd(kv_key)
    danh_sach.append({
        "ten_file":    ten_goc,
        "duong_dan":   str(duong_dan),
        "ngay_upload": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "nguoi_upload": username,
        "kich_thuoc":  len(noi_dung),
    })
    luu_meta_qd(kv_key, danh_sach, username)
    return duong_dan


def tao_df_mau_khtd_cn() -> pd.DataFrame:
    """DataFrame mẫu upload KHTD Chi nhánh (một dòng / ma_key trong CHUONG_TRINH_KHTD)."""
    rows: list[dict] = []
    for ma_key, _ma_ct, ten, nv, _ in CHUONG_TRINH_KHTD:
        rows.append({
            "Chương trình": ten,
            "Mã CT": ma_key,
            "Nguồn vốn": nv,
            "KH (triệu đồng)": 0.0,
        })
    return pd.DataFrame(rows)


def doc_excel_khtd_cn_upload(
    file_bytes: bytes,
    ma_keys_co_khtd: set[str],
) -> tuple[dict[str, float], int, list[str]]:
    """
    Đọc Excel upload KHTD Chi nhánh → dict ma_key → số VND.
    Return: (patch_vnd, so_dong_hop_le, ds_ma_ct_bo_qua).
    Raise ValueError với thông báo người dùng nếu thiếu cột bắt buộc hoặc không đọc được file.
    """
    try:
        df_up = pd.read_excel(BytesIO(file_bytes), header=0)
    except Exception as e:  # conv: skip
        raise ValueError(f"Không đọc được file Excel: {e}") from e

    ten_cot = {str(c).strip(): c for c in df_up.columns}
    if "Mã CT" not in ten_cot:
        raise ValueError(
            "Không tìm thấy cột Mã CT trong file. Vui lòng dùng đúng file mẫu Excel và giữ nguyên tên các cột."
        )

    col_kh = ten_cot.get("KH (triệu đồng)")
    if col_kh is None:
        for t, c in ten_cot.items():
            tl = t.lower()
            if "kh" in tl and ("triệu" in t or "trieu" in tl):
                col_kh = c
                break
    if col_kh is None:
        raise ValueError(
            "Không tìm thấy cột KH (triệu đồng). Vui lòng dùng file mẫu và không đổi tên cột KH."
        )

    col_ma = ten_cot["Mã CT"]
    out: dict[str, float] = {}
    bo_qua: list[str] = []
    for _, row in df_up.iterrows():
        ma_key = str(row[col_ma]).strip()
        if not ma_key or ma_key.lower() == "nan":
            continue
        if ma_key not in ma_keys_co_khtd:
            bo_qua.append(ma_key)
            continue
        v = row[col_kh]
        if pd.isna(v):
            continue
        try:
            kh_trieu = float(v)
        except (TypeError, ValueError):
            continue
        if kh_trieu == 0:
            continue
        out[ma_key] = kh_trieu * 1_000_000
    return out, len(out), bo_qua


def doc_excel_khtd_xa_upload(
    file_bytes: bytes,
    ds_xa_hop_le: set[str],
    ma_keys_co_khtd: set[str],
) -> tuple[dict[str, float], int, list[str]]:
    """
    Đọc Excel upload hàng loạt KHTD theo xã.
    Cấu trúc file: cột 1=Tên xã, cột 2=Mã CT, cột 3=Giá trị (triệu đồng).
    Return: (updates_vnd, so_dong_hop_le, ds_canh_bao).
    """
    try:
        df_up = pd.read_excel(BytesIO(file_bytes), header=0)
    except Exception as e:  # conv: skip
        raise ValueError(f"Lỗi đọc file Excel: {e}") from e

    updates: dict[str, float] = {}
    canh_bao: list[str] = []
    dem = 0
    for _, row in df_up.iterrows():
        ten_xa = str(row.iloc[0]).strip() if len(row) > 0 else ""
        ma_ct = str(row.iloc[1]).strip() if len(row) > 1 else ""
        v = row.iloc[2] if len(row) > 2 else None

        if not ten_xa or ten_xa.lower() == "nan":
            continue
        if ds_xa_hop_le and ten_xa not in ds_xa_hop_le:
            canh_bao.append(f"Xã không thuộc PGD: {ten_xa}")
            continue
        if not ma_ct or ma_ct.lower() == "nan":
            continue
        if ma_ct not in ma_keys_co_khtd:
            canh_bao.append(f"Mã CT không hợp lệ: {ma_ct}")
            continue
        if v is None or pd.isna(v):
            continue
        try:
            val_trieu = float(v)
        except (TypeError, ValueError):
            continue
        if val_trieu <= 0:
            continue
        updates[f"{ten_xa}|{ma_ct}"] = val_trieu * 1_000_000
        dem += 1
    return updates, dem, canh_bao


def luu_pdf_khtd_xa(
    pdf_bytes: bytes,
    thu_muc: str,
    *,
    pgd: str,
    xa: str,
    now: datetime | None = None,
) -> Path:
    if not pdf_bytes:
        raise ValueError("PDF trống.")
    if not thu_muc:
        raise ValueError("Chưa nhập thư mục lưu PDF.")
    p = Path(str(thu_muc).strip())
    if not p.exists() or not p.is_dir():
        raise ValueError(f"Thư mục không tồn tại: {p}")

    ts = (now or datetime.now()).strftime("%Y%m%d_%H%M")
    pgd_safe = re.sub(r"[\\/*?\"<>|:]", "_", str(pgd or "").strip())[:40]
    xa_safe = re.sub(r"[\\/*?\"<>|:]", "_", str(xa or "").strip())[:40]
    ten_file = f"KHTD_{pgd_safe}_{xa_safe}_{ts}.pdf".strip("_")
    duong_dan = p / ten_file
    duong_dan.write_bytes(pdf_bytes)
    return duong_dan
