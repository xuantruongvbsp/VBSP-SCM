"""Service: các hàm thuần túy cho tab KHTD Nhập (không có st.* calls)."""
from __future__ import annotations

import json
import re
from io import BytesIO
from datetime import datetime
from pathlib import Path

import pandas as pd

import db
from config import CHUONG_TRINH_KHTD
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


def tinh_th_gqvl_phan_tang(df_gqvl: pd.DataFrame) -> dict[str, float]:
    """
    Tính TH GQVL phân tầng 4 nhóm từ gqvl.parquet.
    Dùng config.GQVL_PHAN_TANG, config.COT_PL_NV, config.MA_NDT_CAP_TINH_DUOI.

    Trả về dict: {sub_key: tong_du_no_VND}
    sub_key theo GQVL_PHAN_TANG[i][3]:
      "cap_tinh_tw_nhcsxh", "cap_tinh_tw_nsnn", "cap_tinh", "cap_xa"

    Logic phân loại:
    - TW + PL NV=2 (NHCSXH HĐ) → "cap_tinh_tw_nhcsxh"
    - TW + PL NV=1 (NSNN/Quỹ QG) → "cap_tinh_tw_nsnn"
    - DP + Mã NĐT endswith bất kỳ trong MA_NDT_CAP_TINH_DUOI → "cap_tinh"
    - DP + còn lại → "cap_xa"
    """
    from config import GQVL_PHAN_TANG, COT_PL_NV, MA_NDT_CAP_TINH_DUOI
    from config import COT_NGUON_VON, COT_TONG_DU_NO, COT_DU_NO_TH, COT_MA_NHA_DAU_TU

    result = {row[3]: 0.0 for row in GQVL_PHAN_TANG}
    result.setdefault("3_TW_NHCSXH", 0.0)
    result.setdefault("3_TW_NSNN", 0.0)
    result.setdefault("3_DP_TINH", 0.0)
    result.setdefault("3_DP_XA", 0.0)

    if df_gqvl is None or df_gqvl.empty:
        return result

    col_dn = COT_TONG_DU_NO if COT_TONG_DU_NO in df_gqvl.columns else (
        COT_DU_NO_TH if COT_DU_NO_TH in df_gqvl.columns else None
    )
    if not col_dn:
        return result

    df = df_gqvl.copy()
    nv_raw = df.get(COT_NGUON_VON, pd.Series(dtype=object))
    nv = pd.to_numeric(nv_raw, errors="coerce")
    if nv.isna().all():
        nv_str = nv_raw.fillna("").astype(str).str.strip().str.upper()
        nv = nv_str.map({"TW": 1, "ĐP": 2, "DP": 2}).fillna(0)
    else:
        nv = nv.fillna(0)

    plnv = pd.to_numeric(df.get(COT_PL_NV, pd.Series(dtype=object)), errors="coerce").fillna(0)
    mandt = df.get(COT_MA_NHA_DAU_TU, pd.Series(dtype=str)).fillna("").astype(str)
    dn = pd.to_numeric(df[col_dn], errors="coerce").fillna(0)

    mask_tw = nv == 1
    result["cap_tinh_tw_nhcsxh"] = float(dn[mask_tw & (plnv == 2)].sum())
    result["cap_tinh_tw_nsnn"] = float(dn[mask_tw & (plnv == 1)].sum())

    mask_dp = nv == 2
    mask_cap_tinh = mandt.apply(lambda x: any(str(x).endswith(m) for m in MA_NDT_CAP_TINH_DUOI))
    result["cap_tinh"] = float(dn[mask_dp & mask_cap_tinh].sum())
    result["cap_xa"] = float(dn[mask_dp & ~mask_cap_tinh].sum())

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
