from __future__ import annotations

from datetime import date, datetime

import pandas as pd

import db
from data.pgd import pgd_slug
from logger import get_logger
from config import (
    COT_DU_NO_QH,
    COT_DVUT,
    COT_LAI_TON,
    COT_LAI_TON_QH,
    COT_MA_KH,
    COT_NGAY_VAY,
    COT_SO_DU_TG,
    COT_SO_KU,
    COT_TEN_CT,
    COT_TEN_KH,
    COT_TEN_PGD,
    COT_TEN_TO,
    COT_TEN_XA,
    COT_TONG_DU_NO,
    COT_MUC_VAY,
)

logger = get_logger(__name__)


def _chuan_hoa_df_uy_thac(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    df_src = df.copy()
    cols_text = [
        COT_DVUT,
        COT_TEN_PGD,
        COT_TEN_XA,
        COT_TEN_TO,
        COT_SO_KU,
        COT_MA_KH,
        COT_TEN_CT,
        COT_TEN_KH,
    ]
    for col in cols_text:
        if col in df_src.columns:
            try:
                s = df_src[col].astype("string").str.strip()
                df_src[col] = s.replace("", pd.NA)
            except Exception:
                df_src[col] = df_src[col]

    cols_num = [
        COT_TONG_DU_NO,
        COT_DU_NO_QH,
        COT_LAI_TON,
        COT_LAI_TON_QH,
        COT_SO_DU_TG,
        COT_MUC_VAY,
    ]
    for col in cols_num:
        if col in df_src.columns:
            df_src[col] = pd.to_numeric(df_src[col], errors="coerce").fillna(0)

    # Báo cáo ủy thác chỉ gồm hồ sơ có Hội đoàn thể nhận ủy thác.
    if COT_DVUT in df_src.columns:
        df_src = df_src[df_src[COT_DVUT].notna()].copy()

    return df_src


def _chon_cot_khach_hang(df: pd.DataFrame) -> str | None:
    if COT_MA_KH in df.columns:
        return COT_MA_KH
    if COT_SO_KU in df.columns:
        return COT_SO_KU
    return None


def _dem_to_theo_nhom(df: pd.DataFrame, group_cols: list[str]) -> pd.Series | None:
    if COT_TEN_TO not in df.columns:
        return None

    to_cols = list(group_cols)
    for col in [COT_TEN_PGD, COT_TEN_XA, COT_TEN_TO]:
        if col in df.columns and col not in to_cols:
            to_cols.append(col)
    if COT_TEN_TO not in to_cols:
        return None

    df_to = df[to_cols].dropna(subset=[c for c in group_cols if c in to_cols] + [COT_TEN_TO])
    if df_to.empty:
        return None

    return (
        df_to.drop_duplicates()
        .groupby(group_cols)
        .size()
        .rename("so_to")
    )


def _dem_to_unique(df: pd.DataFrame) -> int:
    """Đếm Tổ không phụ thuộc Hội, tránh double-count khi một Tổ mang nhiều Hội."""
    if COT_TEN_TO not in df.columns:
        return 0
    id_cols = [c for c in [COT_TEN_PGD, COT_TEN_XA, COT_TEN_TO] if c in df.columns]
    if not id_cols:
        return 0
    return int(df[id_cols].dropna(subset=[COT_TEN_TO]).drop_duplicates().shape[0])


def tong_quan_uy_thac(df: pd.DataFrame) -> dict[str, float | int]:
    df_src = _chuan_hoa_df_uy_thac(df)
    if df_src.empty:
        return {
            "so_hoi": 0,
            "so_pgd": 0,
            "so_xa": 0,
            "so_to": 0,
            "so_kh": 0,
            "tong_dn": 0.0,
            "nqh": 0.0,
            "lai_ton": 0.0,
            "so_du_tg": 0.0,
            "ty_le_nqh": 0.0,
        }

    kh_col = _chon_cot_khach_hang(df_src)
    so_to = _dem_to_unique(df_src)

    tong_dn = float(df_src[COT_TONG_DU_NO].sum()) if COT_TONG_DU_NO in df_src.columns else 0.0
    nqh = float(df_src[COT_DU_NO_QH].sum()) if COT_DU_NO_QH in df_src.columns else 0.0
    lai_ton = 0.0
    if COT_LAI_TON in df_src.columns:
        lai_ton += float(df_src[COT_LAI_TON].sum())
    if COT_LAI_TON_QH in df_src.columns:
        lai_ton += float(df_src[COT_LAI_TON_QH].sum())
    so_du_tg = float(df_src[COT_SO_DU_TG].sum()) if COT_SO_DU_TG in df_src.columns else 0.0

    return {
        "so_hoi": int(df_src[COT_DVUT].dropna().nunique()) if COT_DVUT in df_src.columns else 0,
        "so_pgd": int(df_src[COT_TEN_PGD].dropna().nunique()) if COT_TEN_PGD in df_src.columns else 0,
        "so_xa": int(df_src[COT_TEN_XA].dropna().nunique()) if COT_TEN_XA in df_src.columns else 0,
        "so_to": so_to,
        "so_kh": int(df_src[kh_col].dropna().nunique()) if kh_col else 0,
        "tong_dn": tong_dn,
        "nqh": nqh,
        "lai_ton": lai_ton,
        "so_du_tg": so_du_tg,
        "ty_le_nqh": round((nqh / tong_dn * 100.0), 2) if tong_dn else 0.0,
    }


def danh_sach_to_co_lai_ton(df: pd.DataFrame) -> pd.DataFrame:
    """Liệt kê Tổ/Hội có lãi tồn, tổng hợp từ lãi tồn thường và quá hạn."""
    df_src = _chuan_hoa_df_uy_thac(df)
    if df_src.empty or COT_TEN_TO not in df_src.columns:
        return pd.DataFrame()

    group_cols = [
        col for col in [COT_TEN_PGD, COT_TEN_XA, COT_DVUT, COT_TEN_TO]
        if col in df_src.columns
    ]
    result = tong_hop_uy_thac_theo(df_src, group_cols)
    if result.empty or "lai_ton" not in result.columns:
        return pd.DataFrame()

    result = result[pd.to_numeric(result["lai_ton"], errors="coerce").fillna(0) > 0].copy()
    cols = group_cols + [
        col for col in ["so_kh", "tong_dn", "lai_ton"]
        if col in result.columns
    ]
    return result[cols].sort_values("lai_ton", ascending=False).reset_index(drop=True)


def danh_sach_to_da_hoi(df: pd.DataFrame) -> pd.DataFrame:
    """Liệt kê Tổ xuất hiện ở nhiều Hội theo định danh PGD + Xã + Tổ."""
    df_src = _chuan_hoa_df_uy_thac(df)
    if df_src.empty or COT_TEN_TO not in df_src.columns or COT_DVUT not in df_src.columns:
        return pd.DataFrame()

    id_cols = [
        col for col in [COT_TEN_PGD, COT_TEN_XA, COT_TEN_TO]
        if col in df_src.columns
    ]
    if COT_TEN_TO not in id_cols:
        return pd.DataFrame()

    df_chk = df_src[id_cols + [COT_DVUT]].dropna(subset=id_cols + [COT_DVUT]).drop_duplicates()
    if df_chk.empty:
        return pd.DataFrame()

    result = (
        df_chk.groupby(id_cols, dropna=False)
        .agg(
            so_hoi=(COT_DVUT, "nunique"),
            ds_hoi=(COT_DVUT, lambda s: " · ".join(sorted(set(s.astype(str))))),
        )
        .reset_index()
    )
    result = result[result["so_hoi"] > 1].copy()
    return result.sort_values(["so_hoi"] + id_cols, ascending=[False] + [True] * len(id_cols)).reset_index(drop=True)


def tong_quan_dieu_hanh_uy_thac(df: pd.DataFrame) -> dict[str, float | int]:
    """Tổng quan điều hành với số Tổ có vấn đề đếm unique toàn phạm vi."""
    base = tong_quan_uy_thac(df)
    df_src = _chuan_hoa_df_uy_thac(df)
    if df_src.empty:
        return {
            **base,
            "so_to_nqh": 0,
            "so_to_lai_ton": 0,
            "ty_le_to_nqh": 0.0,
            "ty_le_to_lai_ton": 0.0,
            "tg_bq_kh": 0.0,
            "dn_bq_to": 0.0,
            "dn_bq_kh": 0.0,
        }

    tong_to = int(base.get("so_to", 0) or 0)
    tong_kh = int(base.get("so_kh", 0) or 0)
    tong_dn = float(base.get("tong_dn", 0.0) or 0.0)
    tong_tg = float(base.get("so_du_tg", 0.0) or 0.0)

    so_to_nqh = 0
    if COT_DU_NO_QH in df_src.columns:
        nqh_mask = pd.to_numeric(df_src[COT_DU_NO_QH], errors="coerce").fillna(0) > 0
        to_nqh = _dem_to_co_van_de_theo_nhom(df_src, [], nqh_mask, "so_to_nqh")
        if to_nqh is not None and not to_nqh.empty:
            so_to_nqh = int(to_nqh.iloc[0])

    so_to_lai_ton = 0
    if COT_LAI_TON in df_src.columns or COT_LAI_TON_QH in df_src.columns:
        lai_series = pd.Series(0.0, index=df_src.index, dtype="float64")
        if COT_LAI_TON in df_src.columns:
            lai_series = lai_series + pd.to_numeric(df_src[COT_LAI_TON], errors="coerce").fillna(0)
        if COT_LAI_TON_QH in df_src.columns:
            lai_series = lai_series + pd.to_numeric(df_src[COT_LAI_TON_QH], errors="coerce").fillna(0)
        to_lai_ton = _dem_to_co_van_de_theo_nhom(df_src, [], lai_series > 0, "so_to_lai_ton")
        if to_lai_ton is not None and not to_lai_ton.empty:
            so_to_lai_ton = int(to_lai_ton.iloc[0])

    return {
        **base,
        "so_to_nqh": so_to_nqh,
        "so_to_lai_ton": so_to_lai_ton,
        "ty_le_to_nqh": round((so_to_nqh / tong_to * 100.0), 2) if tong_to else 0.0,
        "ty_le_to_lai_ton": round((so_to_lai_ton / tong_to * 100.0), 2) if tong_to else 0.0,
        "tg_bq_kh": (tong_tg / tong_kh) if tong_kh else 0.0,
        "dn_bq_to": (tong_dn / tong_to) if tong_to else 0.0,
        "dn_bq_kh": (tong_dn / tong_kh) if tong_kh else 0.0,
    }


def tong_hop_uy_thac_theo(
    df: pd.DataFrame,
    group_cols: list[str],
    dvut_order: list[str] | None = None,
) -> pd.DataFrame:
    df_src = _chuan_hoa_df_uy_thac(df)
    if df_src.empty:
        return pd.DataFrame()

    group_cols = [c for c in group_cols if c in df_src.columns]
    if not group_cols:
        return pd.DataFrame()

    df_grp = df_src.dropna(subset=group_cols).copy()
    if df_grp.empty:
        return pd.DataFrame()

    out_parts: list[pd.Series] = []

    if COT_DVUT in df_grp.columns and COT_DVUT not in group_cols:
        out_parts.append(df_grp.groupby(group_cols)[COT_DVUT].nunique().rename("so_hoi"))

    so_to = _dem_to_theo_nhom(df_grp, group_cols)
    if so_to is not None:
        out_parts.append(so_to)

    kh_col = _chon_cot_khach_hang(df_grp)
    if kh_col:
        out_parts.append(
            df_grp.dropna(subset=[kh_col])
            .groupby(group_cols)[kh_col]
            .nunique()
            .rename("so_kh")
        )

    if COT_TONG_DU_NO in df_grp.columns:
        out_parts.append(df_grp.groupby(group_cols)[COT_TONG_DU_NO].sum().rename("tong_dn"))
    if COT_DU_NO_QH in df_grp.columns:
        out_parts.append(df_grp.groupby(group_cols)[COT_DU_NO_QH].sum().rename("nqh"))
    if COT_LAI_TON in df_grp.columns or COT_LAI_TON_QH in df_grp.columns:
        df_lai = df_grp[group_cols].copy()
        df_lai["lai_ton"] = 0.0
        if COT_LAI_TON in df_grp.columns:
            df_lai["lai_ton"] = df_lai["lai_ton"] + df_grp[COT_LAI_TON]
        if COT_LAI_TON_QH in df_grp.columns:
            df_lai["lai_ton"] = df_lai["lai_ton"] + df_grp[COT_LAI_TON_QH]
        out_parts.append(df_lai.groupby(group_cols)["lai_ton"].sum())
    if COT_SO_DU_TG in df_grp.columns:
        out_parts.append(df_grp.groupby(group_cols)[COT_SO_DU_TG].sum().rename("so_du_tg"))

    if not out_parts:
        return pd.DataFrame()

    result = pd.concat(out_parts, axis=1).reset_index()
    for col in ["so_hoi", "so_to", "so_kh", "tong_dn", "nqh", "lai_ton", "so_du_tg"]:
        if col not in result.columns:
            result[col] = 0
        result[col] = pd.to_numeric(result[col], errors="coerce").fillna(0)

    result["ty_le_nqh"] = result.apply(
        lambda row: round((float(row["nqh"]) / float(row["tong_dn"]) * 100.0), 2)
        if float(row["tong_dn"]) else 0.0,
        axis=1,
    )

    if len(group_cols) == 1 and group_cols[0] == COT_DVUT and dvut_order:
        result["_ord"] = result[COT_DVUT].apply(lambda x: dvut_order.index(x) if x in dvut_order else 99)
        result = result.sort_values(["_ord", "tong_dn"], ascending=[True, False]).drop(columns="_ord")
    else:
        sort_cols = ["tong_dn"] + group_cols
        asc = [False] + [True] * len(group_cols)
        result = result.sort_values(sort_cols, ascending=asc)
    return result.reset_index(drop=True)


def _dem_to_co_van_de_theo_nhom(
    df: pd.DataFrame,
    group_cols: list[str],
    mask: pd.Series,
    metric_name: str,
) -> pd.Series | None:
    """Đếm số Tổ unique có phát sinh vấn đề trong từng nhóm."""
    if COT_TEN_TO not in df.columns or mask is None:
        return None

    id_cols = [c for c in [COT_TEN_PGD, COT_TEN_XA, COT_TEN_TO] if c in df.columns]
    if COT_TEN_TO not in id_cols:
        return None

    use_cols = list(dict.fromkeys(group_cols + id_cols))
    required_cols = [c for c in group_cols if c in use_cols] + [COT_TEN_TO]
    df_problem = df.loc[mask, use_cols].dropna(subset=required_cols).copy()
    if df_problem.empty:
        return None

    df_problem = df_problem.drop_duplicates()
    if not group_cols:
        return pd.Series([int(df_problem.shape[0])], index=pd.Index(["__all__"]), name=metric_name)

    return df_problem.groupby(group_cols).size().rename(metric_name)


def tao_bao_cao_dieu_hanh_uy_thac(
    df: pd.DataFrame,
    group_cols: list[str],
    dvut_order: list[str] | None = None,
) -> pd.DataFrame:
    """Mở rộng báo cáo Ủy thác với chỉ tiêu điều hành và số Tổ có vấn đề."""
    df_src = _chuan_hoa_df_uy_thac(df)
    if df_src.empty:
        return pd.DataFrame()

    group_cols = [c for c in group_cols if c in df_src.columns]
    if not group_cols:
        return pd.DataFrame()

    result = tong_hop_uy_thac_theo(df_src, group_cols, dvut_order=dvut_order)
    if result.empty:
        return pd.DataFrame()

    indexed = result.set_index(group_cols)
    extra_parts: list[pd.Series] = []

    if COT_DU_NO_QH in df_src.columns:
        nqh_mask = pd.to_numeric(df_src[COT_DU_NO_QH], errors="coerce").fillna(0) > 0
        so_to_nqh = _dem_to_co_van_de_theo_nhom(df_src, group_cols, nqh_mask, "so_to_nqh")
        if so_to_nqh is not None:
            extra_parts.append(so_to_nqh)

    if COT_LAI_TON in df_src.columns or COT_LAI_TON_QH in df_src.columns:
        lai_series = pd.Series(0.0, index=df_src.index, dtype="float64")
        if COT_LAI_TON in df_src.columns:
            lai_series = lai_series + pd.to_numeric(df_src[COT_LAI_TON], errors="coerce").fillna(0)
        if COT_LAI_TON_QH in df_src.columns:
            lai_series = lai_series + pd.to_numeric(df_src[COT_LAI_TON_QH], errors="coerce").fillna(0)
        so_to_lai_ton = _dem_to_co_van_de_theo_nhom(
            df_src,
            group_cols,
            lai_series > 0,
            "so_to_lai_ton",
        )
        if so_to_lai_ton is not None:
            extra_parts.append(so_to_lai_ton)

    for part in extra_parts:
        indexed = indexed.join(part, how="left")

    result = indexed.reset_index()
    for col in ["so_to_nqh", "so_to_lai_ton"]:
        if col not in result.columns:
            result[col] = 0
        result[col] = pd.to_numeric(result[col], errors="coerce").fillna(0)

    tong_dn_all = float(pd.to_numeric(result["tong_dn"], errors="coerce").fillna(0).sum())
    result["ty_trong_dn"] = result["tong_dn"].apply(
        lambda x: round(float(x) / tong_dn_all * 100.0, 2) if tong_dn_all else 0.0
    )
    result["dn_bq_to"] = result.apply(
        lambda r: float(r["tong_dn"]) / float(r["so_to"]) if float(r["so_to"]) > 0 else 0.0,
        axis=1,
    )
    result["dn_bq_kh"] = result.apply(
        lambda r: float(r["tong_dn"]) / float(r["so_kh"]) if float(r["so_kh"]) > 0 else 0.0,
        axis=1,
    )
    result["kh_bq_to"] = result.apply(
        lambda r: float(r["so_kh"]) / float(r["so_to"]) if float(r["so_to"]) > 0 else 0.0,
        axis=1,
    )
    result["tg_bq_kh"] = result.apply(
        lambda r: float(r["so_du_tg"]) / float(r["so_kh"]) if float(r["so_kh"]) > 0 else 0.0,
        axis=1,
    )
    result["ty_le_to_nqh"] = result.apply(
        lambda r: float(r["so_to_nqh"]) / float(r["so_to"]) * 100.0 if float(r["so_to"]) > 0 else 0.0,
        axis=1,
    )
    result["ty_le_to_lai_ton"] = result.apply(
        lambda r: float(r["so_to_lai_ton"]) / float(r["so_to"]) * 100.0 if float(r["so_to"]) > 0 else 0.0,
        axis=1,
    )
    return result


def loc_chi_tiet_uy_thac(df: pd.DataFrame, bo_loc: dict[str, object] | None = None) -> pd.DataFrame:
    df_src = _chuan_hoa_df_uy_thac(df)
    if df_src.empty:
        return pd.DataFrame()

    bo_loc = bo_loc or {}
    for col, value in bo_loc.items():
        if col not in df_src.columns or value in (None, "", "(Tất cả)"):
            continue
        if isinstance(value, (list, tuple, set)):
            values = [v for v in value if v not in (None, "", "(Tất cả)")]
            if values:
                df_src = df_src[df_src[col].isin(values)]
        else:
            df_src = df_src[df_src[col] == value]

    if COT_LAI_TON in df_src.columns or COT_LAI_TON_QH in df_src.columns:
        lai_ton = pd.Series(0, index=df_src.index, dtype="float64")
        if COT_LAI_TON in df_src.columns:
            lai_ton = lai_ton + df_src[COT_LAI_TON]
        if COT_LAI_TON_QH in df_src.columns:
            lai_ton = lai_ton + df_src[COT_LAI_TON_QH]
        df_src["Nợ lãi"] = lai_ton

    cols = [
        COT_TEN_PGD,
        COT_DVUT,
        COT_TEN_XA,
        COT_TEN_TO,
        COT_TEN_KH,
        COT_SO_KU,
        COT_TEN_CT,
        COT_TONG_DU_NO,
        COT_DU_NO_QH,
        "Nợ lãi",
        COT_SO_DU_TG,
    ]
    cols = [c for c in cols if c in df_src.columns]
    if not cols:
        return pd.DataFrame()

    sort_cols = [c for c in [COT_TEN_PGD, COT_TEN_XA, COT_DVUT, COT_TEN_TO, COT_TEN_KH] if c in df_src.columns]
    result = df_src[cols].copy()
    if sort_cols:
        result = result.sort_values(sort_cols)
    return result.reset_index(drop=True)


def xep_hang_chat_luong_uy_thac(
    df: pd.DataFrame,
    group_cols: list[str],
) -> pd.DataFrame:
    """Xếp hạng rủi ro tương đối; điểm cao hơn nghĩa là cần ưu tiên rà soát hơn."""
    result = tong_hop_uy_thac_theo(df, group_cols)
    if result.empty:
        return result

    result = result.copy()
    result["lai_ton_tren_dn"] = result.apply(
        lambda r: float(r["lai_ton"]) / float(r["tong_dn"]) * 100
        if float(r["tong_dn"]) > 0 else 0.0,
        axis=1,
    )
    result["dn_bq_to"] = result.apply(
        lambda r: float(r["tong_dn"]) / float(r["so_to"])
        if float(r["so_to"]) > 0 else 0.0,
        axis=1,
    )
    result["kh_bq_to"] = result.apply(
        lambda r: float(r["so_kh"]) / float(r["so_to"])
        if float(r["so_to"]) > 0 else 0.0,
        axis=1,
    )
    # Percentile giúp so sánh công bằng giữa các cấp; không phải điểm xếp loại pháp lý.
    n = max(len(result), 1)
    for source, target in [
        ("ty_le_nqh", "_p_nqh"),
        ("lai_ton_tren_dn", "_p_lai"),
        ("kh_bq_to", "_p_kh"),
    ]:
        result[target] = result[source].rank(method="average", pct=True) * 100 if n > 1 else 0.0
    result["diem_rui_ro"] = (
        result["_p_nqh"] * 0.50 + result["_p_lai"] * 0.30 + result["_p_kh"] * 0.20
    ).round(1)
    result = result.sort_values(
        ["diem_rui_ro", "ty_le_nqh", "lai_ton"], ascending=[False, False, False]
    ).reset_index(drop=True)
    result.insert(0, "xep_hang", range(1, len(result) + 1))
    return result.drop(columns=["_p_nqh", "_p_lai", "_p_kh"])


def tao_canh_bao_trong_diem(
    df: pd.DataFrame,
    records: list[dict] | None = None,
    ngay_ref: date | None = None,
) -> pd.DataFrame:
    """Dựng danh sách hành động từ NQH, lãi tồn, Tổ đa hội và kiến nghị quá hạn."""
    ngay_ref = ngay_ref or date.today()
    df_src = _chuan_hoa_df_uy_thac(df)
    rows: list[dict] = []

    if not df_src.empty:
        dims = [c for c in [COT_TEN_PGD, COT_TEN_XA, COT_DVUT] if c in df_src.columns]
        if dims:
            agg = tong_hop_uy_thac_theo(df_src, dims)
            for _, row in agg.iterrows():
                don_vi = " · ".join(str(row[c]) for c in dims)
                if float(row.get("nqh", 0)) > 0:
                    rows.append({
                        "Mức độ": "🔴 Cao",
                        "Nhóm cảnh báo": "Nợ quá hạn",
                        "Đơn vị/Đối tượng": don_vi,
                        "Giá trị": float(row["nqh"]),
                        "Tỷ lệ (%)": float(row.get("ty_le_nqh", 0)),
                        "Hành động đề xuất": "Rà soát nguyên nhân và kế hoạch thu hồi NQH",
                    })
                if float(row.get("lai_ton", 0)) > 0:
                    rows.append({
                        "Mức độ": "🟠 Trung bình",
                        "Nhóm cảnh báo": "Lãi tồn",
                        "Đơn vị/Đối tượng": don_vi,
                        "Giá trị": float(row["lai_ton"]),
                        "Tỷ lệ (%)": 0.0,
                        "Hành động đề xuất": "Đối chiếu và xây dựng kế hoạch thu lãi",
                    })

        id_cols = [c for c in [COT_TEN_PGD, COT_TEN_XA, COT_TEN_TO] if c in df_src.columns]
        if COT_DVUT in df_src.columns and COT_TEN_TO in id_cols:
            multi = (
                df_src[id_cols + [COT_DVUT]].dropna().drop_duplicates()
                .groupby(id_cols)[COT_DVUT].nunique().reset_index(name="Số hội")
            )
            for _, row in multi[multi["Số hội"] > 1].iterrows():
                rows.append({
                    "Mức độ": "🟡 Cần kiểm tra",
                    "Nhóm cảnh báo": "Tổ đa hội",
                    "Đơn vị/Đối tượng": " · ".join(str(row[c]) for c in id_cols),
                    "Giá trị": float(row["Số hội"]),
                    "Tỷ lệ (%)": 0.0,
                    "Hành động đề xuất": "Kiểm tra lại Hội nhận ủy thác của Tổ trong HSTD",
                })

    for rec in records or []:
        if str(rec.get("trang_thai", "cho_xu_ly") or "cho_xu_ly") != "cho_xu_ly":
            continue
        try:
            han = datetime.fromisoformat(str(rec.get("han_hoan_thanh", "") or "")).date()
        except Exception:
            han = None
        if han is not None and han < ngay_ref:
            rows.append({
                "Mức độ": "🔴 Cao",
                "Nhóm cảnh báo": "Kiến nghị quá hạn",
                "Đơn vị/Đối tượng": rec.get("ten_don_vi", ""),
                "Giá trị": float((ngay_ref - han).days),
                "Tỷ lệ (%)": 0.0,
                "Hành động đề xuất": "Đôn đốc khép kiến nghị và cập nhật kết quả xử lý",
            })

    if not rows:
        return pd.DataFrame()
    result = pd.DataFrame(rows)
    ord_map = {"🔴 Cao": 0, "🟠 Trung bình": 1, "🟡 Cần kiểm tra": 2}
    result["_ord"] = result["Mức độ"].map(ord_map).fillna(9)
    return result.sort_values(["_ord", "Giá trị"], ascending=[True, False]).drop(columns="_ord").reset_index(drop=True)


def tinh_bien_dong_snapshot(df_snapshot: pd.DataFrame) -> pd.DataFrame:
    """Chuẩn hóa chuỗi snapshot và tính chênh lệch so với kỳ liền trước."""
    if df_snapshot is None or df_snapshot.empty or "ky" not in df_snapshot.columns:
        return pd.DataFrame()
    result = df_snapshot.copy().sort_values("ky").drop_duplicates("ky", keep="last")
    aliases = {"so_kh": "so_ho"}
    for source, target in aliases.items():
        if target not in result.columns and source in result.columns:
            result[target] = result[source]
    for col in ["tong_du_no", "du_no_qh", "lai_ton", "so_du_tg", "so_ho", "so_ku", "so_to"]:
        if col not in result.columns:
            result[col] = 0
        result[col] = pd.to_numeric(result[col], errors="coerce").fillna(0)
        result[f"delta_{col}"] = result[col].diff()
    result["ty_le_nqh"] = result.apply(
        lambda r: float(r["du_no_qh"]) / float(r["tong_du_no"]) * 100
        if float(r["tong_du_no"]) > 0 else 0.0,
        axis=1,
    )
    return result.reset_index(drop=True)


def tinh_theo_dvut(df: pd.DataFrame, dvut_order: list[str] | None = None) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    if COT_DVUT not in df.columns:
        return pd.DataFrame()

    df_src = df.copy()
    for col in [COT_DVUT, COT_TEN_PGD, COT_TEN_XA, COT_TEN_TO, COT_SO_KU, COT_MA_KH]:
        if col in df_src.columns:
            try:
                s = df_src[col].astype("string").str.strip()
                df_src[col] = s.replace("", pd.NA)
            except Exception:
                df_src[col] = df_src[col]

    for col in [COT_TONG_DU_NO, COT_DU_NO_QH, COT_LAI_TON]:
        if col in df_src.columns:
            df_src[col] = pd.to_numeric(df_src[col], errors="coerce").fillna(0)

    out_parts: list[pd.Series] = []

    if COT_TEN_TO in df_src.columns:
        if COT_TEN_PGD in df_src.columns and COT_TEN_XA in df_src.columns:
            dims = [COT_DVUT, COT_TEN_PGD, COT_TEN_XA, COT_TEN_TO]
        elif COT_TEN_PGD in df_src.columns:
            dims = [COT_DVUT, COT_TEN_PGD, COT_TEN_TO]
        elif COT_TEN_XA in df_src.columns:
            dims = [COT_DVUT, COT_TEN_XA, COT_TEN_TO]
        else:
            dims = [COT_DVUT, COT_TEN_TO]
        so_to = (
            df_src[dims]
            .dropna(subset=[COT_DVUT, COT_TEN_TO])
            .drop_duplicates()
            .groupby(COT_DVUT)
            .size()
            .rename("so_to")
        )
        out_parts.append(so_to)

    kh_col = COT_MA_KH if COT_MA_KH in df_src.columns else (
        COT_SO_KU if COT_SO_KU in df_src.columns else None
    )
    if kh_col:
        so_kh = (
            df_src.dropna(subset=[COT_DVUT, kh_col])
            .groupby(COT_DVUT)[kh_col]
            .nunique()
            .rename("so_kh")
        )
        out_parts.append(so_kh)

    if COT_TONG_DU_NO in df_src.columns:
        out_parts.append(df_src.groupby(COT_DVUT)[COT_TONG_DU_NO].sum().rename("tong_dn"))
    if COT_DU_NO_QH in df_src.columns:
        out_parts.append(df_src.groupby(COT_DVUT)[COT_DU_NO_QH].sum().rename("nqh"))
    if COT_LAI_TON in df_src.columns:
        out_parts.append(df_src.groupby(COT_DVUT)[COT_LAI_TON].sum().rename("lai_ton"))

    if not out_parts:
        return pd.DataFrame()

    t = pd.concat(out_parts, axis=1).reset_index()
    if dvut_order:
        t["_ord"] = t[COT_DVUT].apply(lambda x: dvut_order.index(x) if x in dvut_order else 99)
        return t.sort_values("_ord").drop(columns="_ord")
    return t


def loc_mau06(df: pd.DataFrame, ngay_tu: str, ngay_den: str) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    if COT_NGAY_VAY not in df.columns:
        return pd.DataFrame()

    ngay_vay = pd.to_datetime(df[COT_NGAY_VAY], errors="coerce")
    mask = (ngay_vay >= pd.Timestamp(ngay_tu)) & (ngay_vay <= pd.Timestamp(ngay_den))
    cols = [
        c
        for c in [
            COT_TEN_TO,
            COT_DVUT,
            COT_TEN_XA,
            COT_TEN_KH,
            COT_SO_KU,
            COT_TEN_CT,
            COT_NGAY_VAY,
            COT_MUC_VAY,
            COT_TONG_DU_NO,
            COT_DU_NO_QH,
            COT_LAI_TON,
        ]
        if c in df.columns
    ]
    result = df.loc[mask, cols].copy()
    if COT_NGAY_VAY in result.columns:
        return result.sort_values(COT_NGAY_VAY, ascending=False)
    return result


def loc_mau15(df: pd.DataFrame, ten_to: str) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    if COT_TEN_TO not in df.columns:
        return pd.DataFrame()

    df_to = df[df[COT_TEN_TO] == ten_to].copy()
    if COT_LAI_TON in df_to.columns and COT_LAI_TON_QH in df_to.columns:
        df_to["Nợ lãi"] = df_to[COT_LAI_TON].fillna(0) + df_to[COT_LAI_TON_QH].fillna(0)
    elif COT_LAI_TON in df_to.columns:
        df_to["Nợ lãi"] = df_to[COT_LAI_TON].fillna(0)
    else:
        df_to["Nợ lãi"] = 0

    cols = [c for c in [COT_TEN_KH, COT_TEN_CT, COT_SO_KU, COT_TONG_DU_NO, "Nợ lãi", COT_SO_DU_TG] if c in df_to.columns or c == "Nợ lãi"]
    return df_to[cols].reset_index(drop=True)


def co_du_lieu_to(df: pd.DataFrame) -> bool:
    if df is None or df.empty:
        return False
    if COT_TEN_TO not in df.columns:
        return False
    s = df[COT_TEN_TO]
    if s is None:
        return False
    try:
        return s.dropna().astype(str).str.strip().replace("", pd.NA).dropna().size > 0
    except Exception as e:
        logger.error("co_du_lieu_to: lỗi kiểm tra cột Tổ — %s", e, exc_info=True)
        return False


def kv_key_bb_ct_cx(cap: str, scope: str | None, nam: int) -> str:
    kv_prefix = "ut_bbct" if cap == "tinh" else "ut_bbcx"
    slug = pgd_slug(scope) if scope else "cn"
    return f"{kv_prefix}_{slug}_{int(nam)}"


def doc_ds_bien_ban(kv_key: str) -> list[dict]:
    ds = db.doc_kv(kv_key) or []
    return ds if isinstance(ds, list) else []


def luu_bien_ban(kv_key: str, ds_hien_tai: list, record: dict, username: str) -> None:
    if not isinstance(ds_hien_tai, list):
        ds_hien_tai = []
    db.ghi_kv(kv_key, ds_hien_tai + [record], username)

    cap = record.get("loai_cap") or ("tinh" if record.get("loai") == "CT" else "xa")
    ten_don_vi = record.get("ten_don_vi", "")
    ngay_kt_raw = record.get("ngay_kt", "")
    ngay_kt_hien_thi = str(ngay_kt_raw or "")
    try:
        if isinstance(ngay_kt_raw, date):
            ngay_kt_hien_thi = ngay_kt_raw.strftime("%d/%m/%Y")
        elif isinstance(ngay_kt_raw, str) and ngay_kt_raw:
            ngay_kt_hien_thi = datetime.fromisoformat(ngay_kt_raw).strftime("%d/%m/%Y")
    except Exception as e:
        logger.error("Lỗi trong khối except: %s", e, exc_info=True)
        ngay_kt_hien_thi = str(ngay_kt_raw or "")
    loai_str = "bb_ct" if cap == "tinh" else "bb_cx"
    mau = "02/BB-CT" if cap == "tinh" else "03/BB-CX"
    db.ghi_audit(username, f"luu_{loai_str}", f"Mẫu {mau} — {ten_don_vi} ngày {ngay_kt_hien_thi}")


def doc_bien_ban_theo_nam(nam: int, pgd_user: str | None = None) -> list[dict]:
    nam_int = int(nam)
    all_records: list[dict] = []
    if pgd_user:
        slug = pgd_slug(pgd_user)
        for pref in ["ut_bbct", "ut_bbcx"]:
            recs = db.doc_kv(f"{pref}_{slug}_{nam_int}") or []
            if isinstance(recs, list):
                all_records.extend(recs)
        return all_records

    for pref in ["ut_bbct", "ut_bbcx"]:
        all_kv: dict = db.doc_kv_prefix(f"{pref}_") or {}
        for key, recs in all_kv.items():
            if key.endswith(f"_{nam_int}") and isinstance(recs, list):
                all_records.extend(recs)
    return all_records


def cap_nhat_trang_thai_bien_ban(
    kv_key: str,
    rec_id: str,
    ket_qua_xu_ly: str,
    username: str,
    ten_don_vi: str = "",
    ngay_cap_nhat: date | None = None,
) -> bool:
    ds_cur = db.doc_kv(kv_key) or []
    if not isinstance(ds_cur, list) or not rec_id:
        return False

    found = False
    ngay_cap_nhat = ngay_cap_nhat or date.today()
    updated: list[dict] = []
    for rec in ds_cur:
        if isinstance(rec, dict) and rec.get("id") == rec_id:
            found = True
            updated.append(
                {
                    **rec,
                    "trang_thai": "da_xu_ly",
                    "ket_qua_xu_ly": ket_qua_xu_ly,
                    "ngay_cap_nhat": ngay_cap_nhat.strftime("%Y-%m-%d"),
                    "nguoi_cap_nhat": username,
                }
            )
        else:
            updated.append(rec)

    if not found:
        return False

    db.ghi_kv(kv_key, updated, username)
    if ten_don_vi:
        db.ghi_audit(username, "cap_nhat_trang_thai_bb", f"ID {rec_id} — {ten_don_vi} → Đã xử lý")
    else:
        db.ghi_audit(username, "cap_nhat_trang_thai_bb", f"ID {rec_id} → Đã xử lý")
    return True


def tong_hop_kien_nghi(records: list[dict], ngay_ref: date | None = None) -> dict[str, int]:
    ngay_ref = ngay_ref or date.today()
    tong = len(records or [])
    cho_xu_ly = 0
    da_xu_ly = 0
    khong_ton_tai = 0
    qua_han = 0
    sap_den_han = 0

    for rec in records or []:
        tt = str(rec.get("trang_thai", "cho_xu_ly") or "cho_xu_ly")
        if tt == "da_xu_ly":
            da_xu_ly += 1
            continue
        if tt == "khong_ton_tai":
            khong_ton_tai += 1
            continue
        cho_xu_ly += 1
        try:
            han = datetime.fromisoformat(str(rec.get("han_hoan_thanh", "") or "")).date()
        except Exception:
            han = None
        if han is None:
            continue
        if han < ngay_ref:
            qua_han += 1
        elif (han - ngay_ref).days <= 7:
            sap_den_han += 1

    return {
        "tong": tong,
        "cho_xu_ly": cho_xu_ly,
        "da_xu_ly": da_xu_ly,
        "khong_ton_tai": khong_ton_tai,
        "qua_han": qua_han,
        "sap_den_han": sap_den_han,
    }


def tao_bang_theo_doi_kien_nghi(
    records: list[dict],
    ngay_ref: date | None = None,
) -> pd.DataFrame:
    ngay_ref = ngay_ref or date.today()
    rows: list[dict] = []
    for rec in sorted(records or [], key=lambda x: x.get("ngay_kt", ""), reverse=True):
        tt = str(rec.get("trang_thai", "cho_xu_ly") or "cho_xu_ly")
        try:
            han = datetime.fromisoformat(str(rec.get("han_hoan_thanh", "") or "")).date()
        except Exception:
            han = None

        canh_bao = ""
        if tt == "da_xu_ly":
            canh_bao = "✅ Đã xử lý"
        elif tt == "khong_ton_tai":
            canh_bao = "⚪ Không tồn tại"
        elif han is not None and han < ngay_ref:
            canh_bao = "🔴 Quá hạn"
        elif han is not None and (han - ngay_ref).days <= 7:
            canh_bao = "🟠 Sắp đến hạn"
        elif tt == "cho_xu_ly":
            canh_bao = "🟢 Trong hạn"

        rows.append(
            {
                "ID": rec.get("id", ""),
                "KV Key": rec.get("kv_key", ""),
                "Loại": rec.get("loai", ""),
                "Mẫu số": "02/BB-CT" if rec.get("loai") == "CT" else "03/BB-CX",
                "Ngày KT": rec.get("ngay_kt", ""),
                "Đơn vị được KT": rec.get("ten_don_vi", ""),
                "Kiến nghị": rec.get("kien_nghi", ""),
                "Hạn hoàn thành": rec.get("han_hoan_thanh", ""),
                "Trạng thái": tt,
                "Cảnh báo hạn": canh_bao,
                "Kết quả xử lý": rec.get("ket_qua_xu_ly", ""),
            }
        )
    return pd.DataFrame(rows)


# ══════════════════════════════════════════════════════════════════════════════
# BUILDER PAYLOAD FUNCTIONS — Thuần, không đụng UI
# ══════════════════════════════════════════════════════════════════════════════

def build_payload_ke_hoach(
    don_vi_kt: str, so_vb: str, dia_danh: str,
    nam_kh: int, ngay_ky: date, chu_tich: str,
    muc_dich: str, yeu_cau: str, noi_dung_kt: str,
    thanh_phan: str, noi_dung_gs: str, phan_cong_gs: str,
    to_chuc: str, ds_to: list,
) -> tuple[dict, str]:
    context = {
        "don_vi_kt": don_vi_kt, "so_vb": so_vb,
        "dia_danh": dia_danh, "nam_kh": nam_kh,
        "ngay_ky": ngay_ky.strftime("%d/%m/%Y"),
        "ngay": ngay_ky.day, "thang": ngay_ky.month, "nam": ngay_ky.year,
        "muc_dich": muc_dich, "yeu_cau": yeu_cau,
        "noi_dung_kt": noi_dung_kt, "thanh_phan": thanh_phan,
        "noi_dung_gs": noi_dung_gs, "phan_cong_gs": phan_cong_gs,
        "to_chuc": to_chuc, "chu_tich": chu_tich,
        "so_to": len(ds_to), "ds_to": ds_to,
        "ngay_ky": ngay_ky,
    }
    ten_file = (
        f"KH_KiemTra_UyThac_{nam_kh}_"
        f"{don_vi_kt[:20].replace(' ','_')}"
    )
    return context, ten_file


def build_payload_mau06(
    don_vi_kt: str, ten_xa: str, ten_to: str,
    can_bo_1: str, chuc_vu_1: str, can_bo_2: str, chuc_vu_2: str,
    dia_ban: str, ngay_kt: date,
    nhan_xet_chung: str,
    so_kh_dung: str, so_tien_dung: str, ty_trong_dung: str,
    so_kh_sai: str, so_tien_sai: str, ty_trong_sai: str,
    bien_phap: str,
    df_m06: pd.DataFrame, pgd_scope: str,
) -> tuple[dict, pd.DataFrame, str]:
    df_xuat = df_m06.copy()
    if ten_to and COT_TEN_TO in df_xuat.columns:
        df_xuat = df_xuat[df_xuat[COT_TEN_TO] == ten_to]
    if COT_LAI_TON in df_xuat.columns and COT_LAI_TON_QH in df_xuat.columns:
        df_xuat["Nợ lãi"] = df_xuat[COT_LAI_TON].fillna(0) + df_xuat[COT_LAI_TON_QH].fillna(0)
    du_lieu_word = {
        "don_vi_kt": don_vi_kt,
        "ten_xa": ten_xa, "ten_to": ten_to,
        "can_bo_1": can_bo_1, "chuc_vu_1": chuc_vu_1,
        "can_bo_2": can_bo_2, "chuc_vu_2": chuc_vu_2,
        "dia_ban": dia_ban, "ngay_kt": ngay_kt,
        "nhan_xet_chung": nhan_xet_chung,
        "so_kh_dung": so_kh_dung, "so_tien_dung": so_tien_dung,
        "ty_trong_dung": ty_trong_dung,
        "so_kh_sai": so_kh_sai, "so_tien_sai": so_tien_sai,
        "ty_trong_sai": ty_trong_sai,
        "bien_phap": bien_phap,
    }
    slug = pgd_slug(pgd_scope) if pgd_scope else "cn"
    ten_file = f"Mau06TD_{slug}_{ngay_kt.strftime('%d%m%Y')}"
    return du_lieu_word, df_xuat, ten_file


def build_payload_mau15(
    pgd: str, ten_xa: str, ten_to: str, to_truong: str,
    ma_to: str, dia_chi: str, can_bo_kt: str,
    ngay_chot: date, pgd_scope: str,
) -> tuple[dict, str]:
    du_lieu_word = {
        "pgd": pgd, "ten_xa": ten_xa, "ten_to": ten_to,
        "to_truong": to_truong, "ma_to": ma_to,
        "dia_chi": dia_chi, "can_bo_kt": can_bo_kt,
        "ngay_chot": ngay_chot,
    }
    ten_file = (
        f"Mau15TD_{ten_to.replace(' ','_')}_"
        f"{ngay_chot.strftime('%d%m%Y')}"
    )
    return du_lieu_word, ten_file


def build_payload_mau16(
    don_vi_kt: str, ten_xa: str, ten_thon: str, ten_to: str,
    hoi_doan_the: str, to_truong: str, to_pho: str,
    can_bo_1: str, chuc_vu_1: str, can_bo_2: str, chuc_vu_2: str,
    ngay_kt: date,
    ty_le_nqh: str, xep_loai_to: str, so_kh_kt_thuc_te: str,
    uu_diem: str, ton_tai: str, kien_nghi: str, so_phieu_kem_theo: str,
    df_src: pd.DataFrame,
) -> tuple[dict, pd.DataFrame, str]:
    df_xuat = df_src.copy()
    if ten_xa and COT_TEN_XA in df_xuat.columns:
        df_xuat = df_xuat[df_xuat[COT_TEN_XA] == ten_xa]
    if ten_to and COT_TEN_TO in df_xuat.columns:
        df_xuat = df_xuat[df_xuat[COT_TEN_TO] == ten_to]
    du_lieu = {
        "don_vi_kt": don_vi_kt,
        "ten_xa": ten_xa, "ten_thon": ten_thon,
        "ten_to": ten_to, "hoi_doan_the": hoi_doan_the,
        "to_truong": to_truong, "to_pho": to_pho,
        "can_bo_1": can_bo_1, "chuc_vu_1": chuc_vu_1,
        "can_bo_2": can_bo_2, "chuc_vu_2": chuc_vu_2,
        "ngay_kt": ngay_kt,
        "ty_le_nqh": ty_le_nqh, "xep_loai_to": xep_loai_to,
        "so_kh_kt_thuc_te": so_kh_kt_thuc_te,
        "uu_diem": uu_diem, "ton_tai": ton_tai,
        "kien_nghi": kien_nghi,
        "so_phieu_kem_theo": so_phieu_kem_theo,
    }
    to_slug = (ten_to or "TatCa").replace(" ", "_")
    ten_file = f"Mau16TD_{to_slug}_{ngay_kt.strftime('%d%m%Y')}"
    return du_lieu, df_xuat, ten_file


def build_payload_bb_xac_minh(
    ten_kh: str, so_ku: str, so_tien: float,
    ly_do: str, bien_phap: str, can_bo_lap: str,
    ngay_lap: date, pgd_scope: str,
) -> tuple[dict, str]:
    du_lieu = {
        "ten_kh": ten_kh, "so_ku": so_ku,
        "so_tien": f"{so_tien:,.1f}",
        "ly_do": ly_do, "bien_phap": bien_phap,
        "can_bo_lap": can_bo_lap,
        "ngay_lap": ngay_lap,
        "ngay": ngay_lap.day, "thang": ngay_lap.month, "nam": ngay_lap.year,
    }
    slug = pgd_slug(pgd_scope) if pgd_scope else "cn"
    ten_file = (
        f"BBXacMinh_{so_ku}_{slug}_"
        f"{ngay_lap.strftime('%d%m%Y')}"
    )
    return du_lieu, ten_file


def build_payload_bc_th(
    don_vi_kt: str, truong_doan: str, cap_uy: str,
    dia_danh: str, ngay_bc: date, noi_dung_kt: str,
    nx_ctxh: str, nx_to: str, nx_to_vien: str,
    kn_ctxh: str, kn_nhcs: str, kn_cap_tren: str,
    nam_td: int,
) -> tuple[dict, str]:
    du_lieu_bc = {
        "don_vi_kt": don_vi_kt, "truong_doan": truong_doan,
        "dia_danh": dia_danh, "ngay_bc": ngay_bc, "cap_uy": cap_uy,
        "noi_dung_kt": noi_dung_kt,
        "nx_ctxh": nx_ctxh, "nx_to": nx_to, "nx_to_vien": nx_to_vien,
        "kn_ctxh": kn_ctxh, "kn_nhcs": kn_nhcs, "kn_cap_tren": kn_cap_tren,
    }
    ten_file = f"BaoCaoTH_UyThac_{nam_td}"
    return du_lieu_bc, ten_file

