"""Service: các hàm thuần túy cho tab KHTD Nhập (không có st.* calls)."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

import pandas as pd

import db
from config import CHUONG_TRINH_KHTD


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
    except Exception:
        pass
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
