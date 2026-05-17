"""Ma trận chuyển dịch nhóm nợ — Loan-level snapshots + Migration Matrix."""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import pandas as pd

import db
from config import (
    COT_SO_KU, COT_MA_KH, COT_TONG_DU_NO, COT_DU_NO_QH,
    COT_PHAN_LOAI, COT_TEN_PGD, COT_TEN_CT, COT_NGAY_SL, CACHE_DIR,
)

_SNAPSHOT_DIR = Path(CACHE_DIR) / "snapshots_loan"
_KY_COLS = [COT_SO_KU, COT_MA_KH, COT_TONG_DU_NO, COT_DU_NO_QH,
            COT_PHAN_LOAI, COT_TEN_PGD, COT_TEN_CT]


def _thu_muc() -> Path:
    _SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    return _SNAPSHOT_DIR


def luu_snapshot(df: pd.DataFrame, username: str) -> str:
    """
    Lưu loan-level snapshot dạng parquet. Trả về tên kỳ (YYYY-MM).
    """
    ky = _ky_tu_df(df)
    cols_co = [c for c in _KY_COLS if c in df.columns]
    df_save = df[cols_co].copy()
    df_save["_ky"] = ky

    path = _thu_muc() / f"snapshot_{ky}.parquet"
    df_save.to_parquet(path, index=False)

    db.ghi_audit(username, "luu_snapshot_loan", f"Kỳ {ky} — {len(df_save)} dòng")

    # Đồng thời gọi snapshot tổng hợp
    try:
        from snapshot_service import luu_snapshot as _ls
        _ls(df, username)
    except Exception:
        pass

    return ky


def danh_sach_ky() -> list[str]:
    """Danh sách kỳ đã có loan snapshot, mới → cũ."""
    tm = _thu_muc()
    files = sorted(tm.glob("snapshot_*.parquet"), reverse=True)
    kys = []
    for f in files:
        try:
            ky = f.stem.replace("snapshot_", "")
            if len(ky) == 7 and ky[4] == "-":
                kys.append(ky)
        except Exception:
            pass
    return kys


def doc_snapshot(ky: str) -> pd.DataFrame:
    """Đọc loan-level snapshot của 1 kỳ."""
    path = _thu_muc() / f"snapshot_{ky}.parquet"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


def migration_matrix(ky_truoc: str, ky_sau: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Ma trận chuyển dịch nhóm nợ giữa 2 kỳ.

    Returns:
        (matrix_df, detail_df) — ma trận 4×4 + danh sách chi tiết món chuyển nhóm
    """
    df_truoc = doc_snapshot(ky_truoc)
    df_sau = doc_snapshot(ky_sau)

    if df_truoc.empty or df_sau.empty:
        return pd.DataFrame(), pd.DataFrame()

    cot_pl = COT_PHAN_LOAI if COT_PHAN_LOAI in df_truoc.columns else ""
    cot_so_ku = COT_SO_KU if COT_SO_KU in df_truoc.columns else ""
    cot_ma_kh = COT_MA_KH if COT_MA_KH in df_truoc.columns else ""

    if not all([cot_pl, cot_so_ku, cot_ma_kh]):
        return pd.DataFrame(), pd.DataFrame()

    def _key(df: pd.DataFrame) -> pd.Series:
        return df[cot_so_ku].astype(str).str.strip() + "\u0000" + df[cot_ma_kh].astype(str).str.strip()

    df_truoc["_key"] = _key(df_truoc)
    df_sau["_key"] = _key(df_sau)

    merged = df_truoc.merge(
        df_sau[["_key", cot_pl]],
        on="_key", how="inner", suffixes=("_truoc", "_sau")
    )

    nhan_gom = _nhan_nhom_no(merged[f"{cot_pl}_truoc"], merged[f"{cot_pl}_sau"])

    matrix = pd.crosstab(
        nhan_gom["nhom_truoc"],
        nhan_gom["nhom_sau"],
        values=merged[cot_so_ku],
        aggfunc="count",
        margins=True,
        margins_name="Tổng",
    ).fillna(0).astype(int)

    cot_order = ["Trong hạn", "Quá hạn", "Khoanh", "Tất toán"]
    idx_order = ["Trong hạn", "Quá hạn", "Khoanh", "Tất toán"]

    matrix = matrix.reindex(index=idx_order, columns=cot_order, fill_value=0)
    if "Tổng" not in matrix.index:
        matrix.loc["Tổng"] = matrix.sum()
    matrix["Tổng"] = matrix.sum(axis=1)

    chi_tiet = merged.copy()
    chi_tiet["Nhóm nợ kỳ trước"] = nhan_gom["nhom_truoc"]
    chi_tiet["Nhóm nợ kỳ sau"] = nhan_gom["nhom_sau"]
    chi_tiet["Chênh dư nợ"] = (
        merged.get(f"{COT_TONG_DU_NO}_sau", 0)
        - merged.get(f"{COT_TONG_DU_NO}_truoc", 0)
    ) if COT_TONG_DU_NO in merged.columns else 0

    cot_xuat = [
        COT_SO_KU, COT_MA_KH, COT_TEN_PGD, COT_TEN_CT,
        "Nhóm nợ kỳ trước", "Nhóm nợ kỳ sau",
    ]
    chi_tiet = chi_tiet[[c for c in cot_xuat if c in chi_tiet.columns]]

    return matrix, chi_tiet


def _nhan_nhom_no(pl_truoc: pd.Series, pl_sau: pd.Series) -> pd.DataFrame:
    """Chuẩn hóa Phân loại về 4 nhóm: Trong hạn, Quá hạn, Khoanh, Tất toán."""

    def _chuan(s: pd.Series) -> pd.Series:
        out = s.astype(str).str.strip().str.upper()
        result = pd.Series("Khác", index=s.index)
        result[out.isin(["", "NAN", "NONE", "NULL"])] = "Tất toán"
        result[out.isin(["E", "ĐỦ TIÊU CHUẨN"])] = "Trong hạn"
        result[out.isin(["D", "CẦN CHÚ Ý"])] = "Quá hạn"
        result[out.isin(["C", "DƯỚI TIÊU CHUẨN", "B", "NGHI NGỜ MẤT VỐN", "A", "MẤT VỐN"])] = "Khoanh"
        return result

    return pd.DataFrame({
        "nhom_truoc": _chuan(pl_truoc),
        "nhom_sau": _chuan(pl_sau),
    })


def _ky_tu_df(df: pd.DataFrame) -> str:
    if COT_NGAY_SL in df.columns:
        sl = df[COT_NGAY_SL].dropna()
        if len(sl):
            try:
                val = str(sl.iloc[0])
                if "/" in val:
                    parts = val.split("/")
                    return f"{parts[2][:4]}-{parts[1].zfill(2)}"
                dt = pd.to_datetime(val, errors="coerce")
                if pd.notna(dt):
                    return dt.strftime("%Y-%m")
            except Exception:
                pass
    return datetime.now().strftime("%Y-%m")
