"""
Hàm xử lý dữ liệu (không có st.*) phục vụ Dashboard CBTD & Địa bàn.

Cung cấp:
  - lay_to_theo_cbtd()      : cross-join CBTD → ĐGD → Tổ TK&VV
  - canh_bao_cbtd_dia_ban() : tổng hợp cảnh báo thông minh
  - tom_tat_kpi()           : dict KPI cho Dashboard
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

from config import (
    COT_DU_NO_QH,
    COT_TONG_DU_NO,
    COT_TEN_THON,
    COT_TEN_XA,
)

try:
    from logger import get_logger
    logger = get_logger(__name__)
except Exception:
    import logging
    logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    pass


# ── helpers ──────────────────────────────────────────────────────────────────

def _normalize(s: str) -> str:
    return str(s).strip().lower()


# ─────────────────────────────────────────────────────────────────────────────
# Cross-join CBTD → Tổ TK&VV
# ─────────────────────────────────────────────────────────────────────────────

def lay_to_theo_cbtd(
    cbtd_data: dict,
    dgd_map: dict,
    df_cdtotkvv: "pd.DataFrame | None",
) -> dict[str, list[dict]]:
    """
    Trả về dict[ma_cb → list[dict]] mô tả Tổ TK&VV thuộc địa bàn CBTD.

    Mỗi phần tử list có dạng:
        {
            "ma_to":    str,
            "ten_xa":   str,
            "dgd":      str,
            "xep_loai": str | None,   # xếp loại tháng gần nhất
            "tong_diem": float | None,
            "tinh_trang": str | None,
        }

    Khớp theo logic:
        cbtd.ds_dgd  ─(dgd_map)→  danh sách thôn/ấp  ─(cdtotkvv.ten_xa+ĐVUT)→  Tổ
    """
    ket_qua: dict[str, list[dict]] = {}
    if not cbtd_data:
        return ket_qua

    # Build lookup từ cdtotkvv: key = (norm_ten_dv, norm_xa) → list[row_dict]
    cdto_lookup: dict[tuple[str, str], list[dict]] = {}
    if df_cdtotkvv is not None and not df_cdtotkvv.empty:
        for _, row in df_cdtotkvv.iterrows():
            ten_dv = _normalize(row.get("ten_dv", ""))
            ten_xa = _normalize(row.get("ten_xa", ""))
            cdto_lookup.setdefault((ten_dv, ten_xa), []).append(row.to_dict())

    # Build lookup (pgd, xa, thon) → dgd_name từ dgd_map
    thon_to_dgd: dict[tuple[str, str, str], str] = {}
    for pgd_k, xa_block in dgd_map.items():
        if not isinstance(xa_block, dict):
            continue
        for xa_k, dgd_block in xa_block.items():
            if not isinstance(dgd_block, dict):
                continue
            for dgd_name, entry in dgd_block.items():
                thon_list = entry.get("thon", []) if isinstance(entry, dict) else (entry or [])
                for thon in thon_list:
                    thon_to_dgd[(_normalize(pgd_k), _normalize(xa_k), _normalize(str(thon)))] = dgd_name

    for ma_cb, info in cbtd_data.items():
        pgd_cb = info.get("pgd", "")
        ds_dgd = info.get("ds_dgd", [])
        tos: list[dict] = []

        # Thu thập tất cả xã/thôn thuộc ĐGD của CBTD này
        xa_set: set[str] = set()
        for dgd_name in ds_dgd:
            for xa_block_k, xa_block_v in dgd_map.get(pgd_cb, {}).items():
                if isinstance(xa_block_v, dict) and dgd_name in xa_block_v:
                    xa_set.add(xa_block_k)

        # Với mỗi xã, tìm Tổ TK&VV trong cdtotkvv
        if df_cdtotkvv is not None and not df_cdtotkvv.empty:
            for xa in xa_set:
                # Tìm theo (ten_dv == pgd, ten_xa == xa)
                for (dv_k, xa_k), rows in cdto_lookup.items():
                    if xa_k == _normalize(xa) and (
                        dv_k == _normalize(pgd_cb) or dv_k == ""
                    ):
                        for row in rows:
                            tos.append({
                                "ma_to":      str(row.get("ma_to", "—")),
                                "ten_xa":     xa,
                                "dgd":        _tim_dgd_cua_xa(pgd_cb, xa, ds_dgd, dgd_map),
                                "xep_loai":   row.get("xep_loai"),
                                "tong_diem":  row.get("tong_diem"),
                                "tinh_trang": row.get("tinh_trang"),
                                "ten_to_truong": row.get("ten_to_truong", ""),
                            })

        ket_qua[ma_cb] = tos
    return ket_qua


def _tim_dgd_cua_xa(pgd: str, xa: str, ds_dgd: list[str], dgd_map: dict) -> str:
    """Trả về tên ĐGD đầu tiên trong ds_dgd nằm trong xa."""
    xa_block = dgd_map.get(pgd, {}).get(xa, {})
    if not isinstance(xa_block, dict):
        return "—"
    for dgd_name in ds_dgd:
        if dgd_name in xa_block:
            return dgd_name
    return "—"


# ─────────────────────────────────────────────────────────────────────────────
# Cảnh báo thông minh
# ─────────────────────────────────────────────────────────────────────────────

def canh_bao_cbtd_dia_ban(
    cbtd_data: dict,
    dgd_map: dict,
    df_hstd: "pd.DataFrame | None",
    df_cdtotkvv: "pd.DataFrame | None",
    df_cdtotkvv_truoc: "pd.DataFrame | None" = None,
    nguong_qh_pct: float = 2.0,
) -> list[dict]:
    """
    Tổng hợp cảnh báo. Trả về list[dict]:
        {
            "loai":   "dgd_thieu_cbtd" | "cbtd_qh_cao" | "to_yeu_lien_tiep",
            "muc_do": "🔴" | "⚠️",
            "noi_dung": str,
            "chi_tiet": dict,
        }
    """
    canh_baos: list[dict] = []

    # ── 1. ĐGD chưa có CBTD ──────────────────────────────────────────────────
    dgd_da_phan: set[tuple[str, str]] = set()
    for info in cbtd_data.values():
        pgd_cb = info.get("pgd", "")
        for dgd in info.get("ds_dgd", []):
            dgd_da_phan.add((_normalize(pgd_cb), _normalize(dgd)))

    for pgd_k, xa_block in dgd_map.items():
        if not isinstance(xa_block, dict):
            continue
        for xa_k, dgd_block in xa_block.items():
            if not isinstance(dgd_block, dict):
                continue
            for dgd_name in dgd_block:
                key = (_normalize(pgd_k), _normalize(dgd_name))
                if key not in dgd_da_phan:
                    canh_baos.append({
                        "loai": "dgd_thieu_cbtd",
                        "muc_do": "⚠️",
                        "noi_dung": f"ĐGD **{dgd_name}** ({pgd_k} / {xa_k}) chưa có CBTD phụ trách",
                        "chi_tiet": {"pgd": pgd_k, "xa": xa_k, "dgd": dgd_name},
                    })

    # ── 2. CBTD có tỷ lệ QH cao ──────────────────────────────────────────────
    if df_hstd is not None and not df_hstd.empty and cbtd_data:
        try:
            from data.khtd import gan_cbtd_vao_df, lay_ap_tu_dgd_list
            df_joined = gan_cbtd_vao_df(df_hstd, cbtd_data, dgd_map)
            for ma_cb, info in cbtd_data.items():
                if not info.get("ds_dgd"):
                    continue
                df_cb = df_joined[df_joined["CBTD"] == ma_cb]
                if df_cb.empty:
                    continue
                tdn = pd.to_numeric(df_cb[COT_TONG_DU_NO], errors="coerce").sum() if COT_TONG_DU_NO in df_cb.columns else 0
                dqh = pd.to_numeric(df_cb[COT_DU_NO_QH], errors="coerce").sum() if COT_DU_NO_QH in df_cb.columns else 0
                ty_le = (dqh / tdn * 100) if tdn > 0 else 0
                if ty_le >= nguong_qh_pct:
                    canh_baos.append({
                        "loai": "cbtd_qh_cao",
                        "muc_do": "🔴",
                        "noi_dung": f"CBTD **{ma_cb} — {info['ho_ten']}** có tỷ lệ QH {ty_le:.1f}% (≥{nguong_qh_pct}%)",
                        "chi_tiet": {"ma_cb": ma_cb, "ho_ten": info["ho_ten"], "ty_le_qh": round(ty_le, 2)},
                    })
        except Exception as e:
            logger.error("canh_bao QH: %s", e, exc_info=True)

    # ── 3. Tổ TB/Yếu liên tiếp 2+ tháng ─────────────────────────────────────
    if (df_cdtotkvv is not None and not df_cdtotkvv.empty
            and df_cdtotkvv_truoc is not None and not df_cdtotkvv_truoc.empty):
        try:
            _XEP_LOAI_YEU = "Yếu"
            _XEP_LOAI_TB  = "Trung bình"
            loai_xau = {_XEP_LOAI_YEU, _XEP_LOAI_TB}

            if "xep_loai" in df_cdtotkvv.columns and "xep_loai" in df_cdtotkvv_truoc.columns:
                ma_to_xau_hien = set(
                    df_cdtotkvv[df_cdtotkvv["xep_loai"].isin(loai_xau)]["ma_to"].astype(str)
                )
                ma_to_xau_truoc = set(
                    df_cdtotkvv_truoc[df_cdtotkvv_truoc["xep_loai"].isin(loai_xau)]["ma_to"].astype(str)
                )
                ma_to_lien_tiep = ma_to_xau_hien & ma_to_xau_truoc
                for ma_to in ma_to_lien_tiep:
                    row = df_cdtotkvv[df_cdtotkvv["ma_to"].astype(str) == ma_to]
                    if row.empty:
                        continue
                    r = row.iloc[0]
                    canh_baos.append({
                        "loai": "to_yeu_lien_tiep",
                        "muc_do": "🔴",
                        "noi_dung": (
                            f"Tổ **{ma_to}** ({r.get('ten_xa','?')}) xếp loại "
                            f"{r.get('xep_loai','?')} từ TB/Yếu 2+ tháng liên tiếp"
                        ),
                        "chi_tiet": {
                            "ma_to": ma_to,
                            "ten_xa": r.get("ten_xa"),
                            "ten_dv": r.get("ten_dv"),
                            "xep_loai": r.get("xep_loai"),
                            "tong_diem": r.get("tong_diem"),
                        },
                    })
        except Exception as e:
            logger.error("canh_bao Tổ liên tiếp: %s", e, exc_info=True)

    return canh_baos


# ─────────────────────────────────────────────────────────────────────────────
# KPI tóm tắt
# ─────────────────────────────────────────────────────────────────────────────

def tom_tat_kpi(
    cbtd_data: dict,
    dgd_map: dict,
    df_cdtotkvv: "pd.DataFrame | None",
) -> dict:
    """
    Trả về dict KPI:
        so_cbtd, so_dgd_tong, so_dgd_chua_phan,
        so_to_tong, diem_tb, pct_to_dat, so_to_yeu, so_to_tb_yeu
    """
    # ĐGD
    so_dgd_tong = sum(
        len(dgd_block)
        for xa_block in dgd_map.values()
        for dgd_block in xa_block.values()
        if isinstance(dgd_block, dict)
        if isinstance(xa_block, dict)
    )
    dgd_da_phan = {
        (_normalize(info.get("pgd", "")), _normalize(dgd))
        for info in cbtd_data.values()
        for dgd in info.get("ds_dgd", [])
    }
    so_dgd_chua_phan = max(0, so_dgd_tong - len(dgd_da_phan))

    # Tổ TK&VV
    so_to_tong = 0
    diem_tb = 0.0
    so_to_yeu = 0
    so_to_tb_yeu = 0
    pct_to_dat = 0.0

    if df_cdtotkvv is not None and not df_cdtotkvv.empty:
        so_to_tong = len(df_cdtotkvv)
        if "tong_diem" in df_cdtotkvv.columns:
            diem_tb = round(
                float(pd.to_numeric(df_cdtotkvv["tong_diem"], errors="coerce").mean() or 0), 2
            )
        if "xep_loai" in df_cdtotkvv.columns:
            so_to_yeu = int((df_cdtotkvv["xep_loai"] == "Yếu").sum())
            so_to_tb_yeu = int(df_cdtotkvv["xep_loai"].isin({"Yếu", "Trung bình"}).sum())
            so_to_dat = int(df_cdtotkvv["xep_loai"].isin({"Tốt", "Khá"}).sum())
            pct_to_dat = round(so_to_dat / so_to_tong * 100, 1) if so_to_tong else 0.0

    return {
        "so_cbtd":          len(cbtd_data),
        "so_dgd_tong":      so_dgd_tong,
        "so_dgd_chua_phan": so_dgd_chua_phan,
        "so_to_tong":       so_to_tong,
        "diem_tb":          diem_tb,
        "pct_to_dat":       pct_to_dat,
        "so_to_yeu":        so_to_yeu,
        "so_to_tb_yeu":     so_to_tb_yeu,
    }
