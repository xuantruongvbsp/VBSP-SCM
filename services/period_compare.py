"""Logic so sánh hai kỳ cấp độ khế ước — port từ period-compare.ts."""
from __future__ import annotations

from datetime import timedelta
from typing import Optional

import pandas as pd

from config import (
    COT_DU_NO_QH,
    COT_DU_NO_TH,
    COT_MA_KH,
    COT_NGAY_DH,
    COT_NGAY_DH_HD,
    COT_NGAY_SL,
    COT_NGAY_VAY,
    COT_SO_KU,
    COT_TEN_KH,
    COT_TONG_DU_NO,
)

_COT_KHOANH = "Dư nợ khoanh"
_NULL_SEP = "\x00"


# ─── Phân loại tình trạng khế ước ─────────────────────────────────────────────

def _derive_status(dn_th: float, dn_qh: float, dn_khoanh: float) -> str:
    """Ưu tiên: khoanh > quá hạn > trong hạn > none."""
    if dn_khoanh > 0:
        return "kh"
    if dn_qh > 0:
        return "qh"
    if dn_th > 0:
        return "th"
    return "none"


_STATUS_RANK = {"th": 0, "qh": 1, "kh": 2, "none": 3}
_STATUS_LABEL = {"th": "Trong hạn", "qh": "Quá hạn", "kh": "Khoanh", "none": "Không dư nợ"}


def _status_series(df: pd.DataFrame) -> pd.Series:
    """Trả về Series tình trạng ('th'/'qh'/'kh'/'none') cho từng dòng."""
    dn_th = df[COT_DU_NO_TH].fillna(0) if COT_DU_NO_TH in df.columns else pd.Series(0.0, index=df.index)
    dn_qh = df[COT_DU_NO_QH].fillna(0) if COT_DU_NO_QH in df.columns else pd.Series(0.0, index=df.index)
    dn_kh = df[_COT_KHOANH].fillna(0) if _COT_KHOANH in df.columns else pd.Series(0.0, index=df.index)

    s = pd.Series("none", index=df.index)
    s[dn_th > 0] = "th"
    s[dn_qh > 0] = "qh"
    s[dn_kh > 0] = "kh"
    return s


def _loan_key_series(df: pd.DataFrame) -> pd.Series:
    so_ku = df[COT_SO_KU].astype(str).str.strip() if COT_SO_KU in df.columns else pd.Series("", index=df.index)
    ma_kh = df[COT_MA_KH].astype(str).str.strip() if COT_MA_KH in df.columns else pd.Series("", index=df.index)
    return so_ku + _NULL_SEP + ma_kh


# ─── Ghép cặp khế ước ─────────────────────────────────────────────────────────

def join_by_loan(df_prev: pd.DataFrame, df_curr: pd.DataFrame) -> pd.DataFrame:
    """
    Ghép hai DataFrame theo khóa (soKU + maKH).

    Trả về DataFrame với:
    - Cột _key, _bucket ('both'/'closed'/'new')
    - Cột gốc có suffix _prev và _curr
    - _status_prev, _status_curr — 'th'/'qh'/'kh'/'none'
    """
    if df_prev.empty and df_curr.empty:
        return pd.DataFrame()

    df_p = df_prev.copy()
    df_c = df_curr.copy()

    df_p["_key"] = _loan_key_series(df_p)
    df_c["_key"] = _loan_key_series(df_c)

    # Dedup — lấy dòng cuối cùng nếu trùng key
    df_p = df_p.drop_duplicates("_key", keep="last")
    df_c = df_c.drop_duplicates("_key", keep="last")

    df_p["_status"] = _status_series(df_p)
    df_c["_status"] = _status_series(df_c)

    merged = df_p.merge(
        df_c,
        on="_key",
        how="outer",
        suffixes=("_prev", "_curr"),
        indicator=True,
    )
    bucket_map = {"left_only": "closed", "right_only": "new", "both": "both"}
    merged["_bucket"] = merged["_merge"].map(bucket_map)
    merged.drop(columns=["_merge"], inplace=True)

    return merged


# ─── Roll rate / Cure rate ─────────────────────────────────────────────────────

def roll_cure_rate(df_joined: pd.DataFrame) -> dict:
    """
    Tính roll rate và cure rate từ DataFrame đã ghép cặp.

    rollRate = Σ duNoQH_curr (KƯ TH ở kỳ trước) / Σ duNoTH_prev (KƯ TH)
    cureRate = Σ duNoTH_curr (KƯ QH ở kỳ trước) / Σ duNoQH_prev (KƯ QH)
    """
    if df_joined.empty:
        return {"roll_rate": 0.0, "cure_rate": 0.0,
                "roll_count": 0, "cure_count": 0,
                "base_th_prev": 0.0, "base_qh_prev": 0.0}

    prev_status = df_joined.get("_status_prev", pd.Series(dtype=str))
    curr_qh = df_joined.get(f"{COT_DU_NO_QH}_curr", pd.Series(0.0, index=df_joined.index)).fillna(0)
    curr_th = df_joined.get(f"{COT_DU_NO_TH}_curr", pd.Series(0.0, index=df_joined.index)).fillna(0)
    prev_th = df_joined.get(f"{COT_DU_NO_TH}_prev", pd.Series(0.0, index=df_joined.index)).fillna(0)
    prev_qh = df_joined.get(f"{COT_DU_NO_QH}_prev", pd.Series(0.0, index=df_joined.index)).fillna(0)

    # Chỉ tính cho khế ước "both"
    both = df_joined.get("_bucket", pd.Series(dtype=str)) == "both"

    mask_th = both & (prev_status == "th")
    mask_qh = both & (prev_status == "qh")

    base_th = float(prev_th[mask_th].sum())
    base_qh = float(prev_qh[mask_qh].sum())

    roll_num = float(curr_qh[mask_th].sum())
    cure_num = float(curr_th[mask_qh].sum())

    roll_count = int((curr_qh[mask_th] > 0).sum())
    cure_count = int((curr_th[mask_qh] > 0).sum())

    return {
        "roll_rate": roll_num / base_th if base_th > 0 else 0.0,
        "cure_rate": cure_num / base_qh if base_qh > 0 else 0.0,
        "roll_count": roll_count,
        "cure_count": cure_count,
        "base_th_prev": base_th,
        "base_qh_prev": base_qh,
    }


# ─── Phân loại biến động khế ước ──────────────────────────────────────────────

_CHANGE_LABEL = {
    "new":       "🆕 Mới",
    "closed":    "✅ Tất toán",
    "worsened":  "🔴 Chuyển xấu",
    "improved":  "🟢 Cải thiện",
    "extended":  "📅 Gia hạn",
    "increased": "📈 Tăng DN",
    "decreased": "📉 Giảm DN",
    "unchanged": "⬜ Không đổi",
}

CHANGE_TYPES = list(_CHANGE_LABEL.keys())
CHANGE_LABELS = list(_CHANGE_LABEL.values())


def classify_changes(df_joined: pd.DataFrame) -> pd.DataFrame:
    """
    Phân loại từng khế ước theo loại biến động.

    Trả về DataFrame với cột _change_type, _status_prev, _status_curr,
    _du_no_delta, _status_rank_delta (cùng các cột gốc).
    """
    if df_joined.empty:
        return df_joined

    df = df_joined.copy()
    bucket = df.get("_bucket", pd.Series(dtype=str))
    sp = df.get("_status_prev", pd.Series("none", index=df.index))
    sc = df.get("_status_curr", pd.Series("none", index=df.index))

    dn_prev = df.get(f"{COT_TONG_DU_NO}_prev", pd.Series(0.0, index=df.index)).fillna(0)
    dn_curr = df.get(f"{COT_TONG_DU_NO}_curr", pd.Series(0.0, index=df.index)).fillna(0)

    rank_prev = sp.map(_STATUS_RANK).fillna(3).astype(int)
    rank_curr = sc.map(_STATUS_RANK).fillna(3).astype(int)
    rank_delta = rank_curr - rank_prev

    # Ngày ĐH gia hạn — phát hiện gia hạn
    dh_prev_col = f"{COT_NGAY_DH}_prev" if f"{COT_NGAY_DH}_prev" in df.columns else None
    dh_curr_col = f"{COT_NGAY_DH}_curr" if f"{COT_NGAY_DH}_curr" in df.columns else None

    change = pd.Series("unchanged", index=df.index)

    change[bucket == "new"] = "new"
    change[bucket == "closed"] = "closed"
    change[(bucket == "both") & (rank_delta > 0)] = "worsened"
    change[(bucket == "both") & (rank_delta < 0)] = "improved"

    # Gia hạn: rank_delta == 0, ngayDH thay đổi
    if dh_prev_col and dh_curr_col:
        dh_changed = df[dh_curr_col] != df[dh_prev_col]
        change[(bucket == "both") & (rank_delta == 0) & dh_changed] = "extended"

    both_stable = (bucket == "both") & (rank_delta == 0) & (change == "unchanged")
    change[both_stable & (dn_curr > dn_prev)] = "increased"
    change[both_stable & (dn_curr < dn_prev)] = "decreased"

    df["_change_type"] = change
    df["_change_label"] = change.map(_CHANGE_LABEL)
    df["_du_no_delta"] = dn_curr - dn_prev
    df["_status_rank_delta"] = rank_delta

    return df


# ─── Vintage NQH ──────────────────────────────────────────────────────────────

def vintage_nqh(df: pd.DataFrame) -> pd.DataFrame:
    """
    Phân tích NQH theo năm vay (vintage).

    Trả về DataFrame: nam_vay, so_ku, tong_du_no, du_no_qh, ty_le_nqh
    """
    if df.empty or COT_NGAY_VAY not in df.columns:
        return pd.DataFrame()

    df2 = df.copy()
    ngay_vay = pd.to_datetime(df2[COT_NGAY_VAY], errors="coerce", dayfirst=True)
    df2["_nam_vay"] = ngay_vay.dt.year.fillna(-1).astype(int)

    agg = (
        df2.groupby("_nam_vay")
        .agg(
            so_ku=(COT_SO_KU, "count"),
            tong_du_no=(COT_TONG_DU_NO, "sum") if COT_TONG_DU_NO in df2.columns else (COT_SO_KU, "count"),
            du_no_qh=(COT_DU_NO_QH, "sum") if COT_DU_NO_QH in df2.columns else (COT_SO_KU, "count"),
        )
        .reset_index()
        .rename(columns={"_nam_vay": "Năm vay"})
    )

    agg["Tỷ lệ NQH"] = (agg["du_no_qh"] / agg["tong_du_no"]).where(agg["tong_du_no"] > 0, 0)

    # Đổi -1 về "N/A"
    agg["Năm vay"] = agg["Năm vay"].apply(lambda x: "N/A" if x == -1 else str(x))

    return agg.sort_values("Năm vay")


# ─── PAR theo ngày quá hạn ────────────────────────────────────────────────────

def par_breakdown(df: pd.DataFrame) -> dict:
    """
    Tính PAR30/PAR90/PAR180 dựa trên ngày đáo hạn.

    Dùng COT_NGAY_DH (gia hạn) ưu tiên, fallback COT_NGAY_DH_HD.
    """
    if df.empty:
        return {"par30": 0, "par90": 0, "par180": 0,
                "par30_pct": 0.0, "par90_pct": 0.0, "par180_pct": 0.0,
                "tong_du_no": 0}

    ref_col = COT_NGAY_SL
    tong = float(df[COT_TONG_DU_NO].sum()) if COT_TONG_DU_NO in df.columns else 0.0

    # Tính ngày quá hạn
    ngay_sl = None
    if ref_col in df.columns:
        sl = pd.to_datetime(df[ref_col], errors="coerce", dayfirst=True).dropna()
        if len(sl):
            ngay_sl = sl.iloc[0]

    if ngay_sl is None or COT_TONG_DU_NO not in df.columns:
        return {"par30": 0, "par90": 0, "par180": 0,
                "par30_pct": 0.0, "par90_pct": 0.0, "par180_pct": 0.0,
                "tong_du_no": tong}

    # Chọn cột ngày đáo hạn
    due_col = COT_NGAY_DH if COT_NGAY_DH in df.columns else (COT_NGAY_DH_HD if COT_NGAY_DH_HD in df.columns else None)

    if due_col:
        due_dates = pd.to_datetime(df[due_col], errors="coerce", dayfirst=True)
        overdue_days = ((ngay_sl - due_dates).dt.days).clip(lower=0).fillna(0)
    else:
        # Fallback: dùng cột dư nợ quá hạn làm proxy
        has_qh = (df[COT_DU_NO_QH] > 0) if COT_DU_NO_QH in df.columns else pd.Series(False, index=df.index)
        overdue_days = pd.Series(0, index=df.index)
        overdue_days[has_qh] = 31  # ít nhất 31 ngày

    dn = df[COT_TONG_DU_NO].fillna(0)
    par30 = float(dn[overdue_days > 30].sum())
    par90 = float(dn[overdue_days > 90].sum())
    par180 = float(dn[overdue_days > 180].sum())

    return {
        "par30": par30,
        "par90": par90,
        "par180": par180,
        "par30_pct": par30 / tong if tong > 0 else 0.0,
        "par90_pct": par90 / tong if tong > 0 else 0.0,
        "par180_pct": par180 / tong if tong > 0 else 0.0,
        "tong_du_no": tong,
    }
