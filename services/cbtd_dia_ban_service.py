"""
Hàm xử lý dữ liệu (không có st.*) phục vụ Dashboard CBTD & Địa bàn.

Cung cấp:
  - lay_to_theo_cbtd()           : cross-join CBTD → ĐGD → Tổ TK&VV
  - canh_bao_cbtd_dia_ban()      : tổng hợp cảnh báo thông minh
  - tom_tat_kpi()                : dict KPI cho Dashboard
  - danh_gia_workload_cbtd()     : đánh giá tải CBTD (quá tải / thiếu tải / cân bằng)
  - xep_hang_cbtd()              : bảng xếp hạng CBTD theo nhiều tiêu chí
  - phan_tich_xu_huong_to()      : xu hướng chất lượng Tổ qua các kỳ
  - so_huu_cbtd_full()           : vector-optimised map (xa, thon) → (ma_cb, ten_cb, ten_xa_dgd)
  - lay_kpi_cbtd_theo_thang()    : [MỚI v4] KPI 1 CBTD theo tháng N (dùng cho Dashboard + Đèn GD)
  - tong_hop_hstd_theo_cbtd()    : [MỚI v4] bảng số liệu HSTD theo từng CBTD
  - top_3_viec_uu_tien()         : [MỚI v4] Top 3 việc ưu tiên hôm nay (TN / NQH / Chờ duyệt GN)
  - cham_diem_cbtd_thang()       : [MỚI v4] Wrapper scorecard clamp 0-100 cho 1 CBTD 1 tháng
"""
from __future__ import annotations

from datetime import datetime, date
from typing import TYPE_CHECKING, Any

import pandas as pd
import numpy as np

from config import (
    COT_DU_NO_QH,
    COT_DU_NO_TH,
    COT_TONG_DU_NO,
    COT_TEN_THON,
    COT_TEN_XA,
    COT_TEN_CT,
    COT_MA_KH,
    COT_SO_KU,
    COT_NGAY_VAY,
    COT_NGAY_DEN_HAN,
    COT_NGAY_GN_DAU_TIEN,
    COT_HINH_THUC_VAY,
)

try:
    from logger import get_logger
    logger = get_logger(__name__)
except Exception:
    import logging
    logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    pass


# ── Thresholds (có thể override khi gọi hàm) ─────────────────────────────────
_NGUONG_DGD_QUA_TAI: int = 5
_NGUONG_AP_QUA_TAI: int = 30
_NGUONG_DGD_THIEU_TAI: int = 1
_NGUONG_TO_XEP_LOAI_2KY: int = 2


# ── helpers ──────────────────────────────────────────────────────────────────

def _normalize(s) -> str:
    """Chuẩn hóa text join/groupby, an toàn với None, NaN và pd.NA."""
    if s is None:
        return ""
    try:
        if pd.isna(s):
            return ""
    except (TypeError, ValueError):
        pass
    try:
        text = str(s).strip().lower()
    except Exception:
        return ""
    return "" if text in {"nan", "none", "<na>"} else text


def _count_ap(pgd: str, ds_dgd: list, dgd_map: dict) -> int:
    """Đếm tổng số ấp phụ trách của CBTD từ ds_dgd."""
    cnt = 0
    xa_block = (dgd_map or {}).get(pgd, {})
    if not isinstance(xa_block, dict):
        return 0
    for dgd_name in ds_dgd:
        for xa_k, dgd_block in xa_block.items():
            if not isinstance(dgd_block, dict) or dgd_name not in dgd_block:
                continue
            entry = dgd_block[dgd_name]
            thon_list = entry.get("thon", []) if isinstance(entry, dict) else (entry or [])
            cnt += len([t for t in thon_list if str(t).strip()])
    return cnt


# ─────────────────────────────────────────────────────────────────────────────
# Cross-join CBTD → Tổ TK&VV (original, kept for compat)
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
# Vector-optimised: (xa, thon) → (ma_cb, ten_cb)
# ─────────────────────────────────────────────────────────────────────────────

def so_huu_cbtd_full(cbtd_data: dict, dgd_map: dict) -> dict:
    """
    Xây lookup toàn diện phục vụ vector join với HSTD/Tổ.
    Trả về: {
        "ap_map":      {(norm_xa, norm_thon): (ma_cb, ten_cb, pgd, dgd_name)},
        "cb_meta":     {ma_cb: {ho_ten, pgd, so_dgd, so_ap, chuc_vu, ngay_bo_nhiem}},
    }
    """
    ap_map: dict[tuple[str, str], tuple[str, str, str, str]] = {}
    cb_meta: dict[str, dict] = {}

    for ma_cb, info in (cbtd_data or {}).items():
        pgd = info.get("pgd", "")
        ds_dgd = info.get("ds_dgd", []) or []
        meta = {
            "ho_ten":          info.get("ho_ten", ""),
            "pgd":             pgd,
            "so_dgd":          len(ds_dgd),
            "so_ap":           _count_ap(pgd, ds_dgd, dgd_map),
            "chuc_vu":         info.get("chuc_vu", ""),
            "ngay_bo_nhiem":   info.get("ngay_bo_nhiem", ""),
            "dien_thoai":      info.get("dien_thoai", ""),
            "ghi_chu":         info.get("ghi_chu", ""),
            "ngay_cap":        info.get("ngay_cap", ""),
        }
        cb_meta[ma_cb] = meta
        if not pgd or not ds_dgd:
            continue
        from data.khtd import lay_ap_tu_dgd_list
        for ten_xa, ten_ap in lay_ap_tu_dgd_list(pgd, ds_dgd, dgd_map):
            xa_n = _normalize(ten_xa)
            ap_n = _normalize(ten_ap)
            dgd_name = _tim_dgd_cua_xa(pgd, ten_xa, ds_dgd, dgd_map)
            key = (xa_n, ap_n)
            if key not in ap_map:
                ap_map[key] = (ma_cb, meta["ho_ten"], pgd, dgd_name)

    return {"ap_map": ap_map, "cb_meta": cb_meta}


# ─────────────────────────────────────────────────────────────────────────────
# Cảnh báo thông minh — MỞ RỘNG (4 loại mới)
# ─────────────────────────────────────────────────────────────────────────────

def canh_bao_cbtd_dia_ban(
    cbtd_data: dict,
    dgd_map: dict,
    df_hstd: "pd.DataFrame | None",
    df_cdtotkvv: "pd.DataFrame | None",
    df_cdtotkvv_truoc: "pd.DataFrame | None" = None,
    nguong_qh_pct: float = 2.0,
    nguong_dgd_quatai: int = _NGUONG_DGD_QUA_TAI,
    nguong_ap_quatai: int = _NGUONG_AP_QUA_TAI,
    nguong_dgd_thieutai: int = _NGUONG_DGD_THIEU_TAI,
) -> list[dict]:
    """
    Tổng hợp cảnh báo. Trả về list[dict]:
        {
            "loai":   "dgd_thieu_cbtd" | "cbtd_qh_cao" | "to_yeu_lien_tiep"
                    | "cbtd_quatai" | "cbtd_thieutai" | "to_giam_diem_2ky" | "dgd_khong_co_hs",
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

    # ── 1b. CBTD quá tải / thiếu tải ────────────────────────────────────────
    try:
        wl = danh_gia_workload_cbtd(cbtd_data, dgd_map,
                                     nguong_dgd_quatai=nguong_dgd_quatai,
                                     nguong_ap_quatai=nguong_ap_quatai,
                                     nguong_dgd_thieutai=nguong_dgd_thieutai)
        for ma_cb, info in wl.items():
            loai_wl = info.get("loai")
            if loai_wl == "quatai":
                canh_baos.append({
                    "loai": "cbtd_quatai",
                    "muc_do": "🔴",
                    "noi_dung": (
                        f"CBTD **{ma_cb} — {info['ho_ten']}** ({info['pgd']}) "
                        f"quá tải: {info['so_dgd']} ĐGD / {info['so_ap']} ấp"
                    ),
                    "chi_tiet": {"ma_cb": ma_cb, **{k: v for k, v in info.items() if k != "loai"}},
                })
            elif loai_wl == "thieutai":
                canh_baos.append({
                    "loai": "cbtd_thieutai",
                    "muc_do": "⚠️",
                    "noi_dung": (
                        f"CBTD **{ma_cb} — {info['ho_ten']}** ({info['pgd']}) "
                        f"thiếu tải: chỉ {info['so_dgd']} ĐGD / {info['so_ap']} ấp"
                    ),
                    "chi_tiet": {"ma_cb": ma_cb, **{k: v for k, v in info.items() if k != "loai"}},
                })
    except Exception as e:
        logger.error("canh_bao workload: %s", e, exc_info=True)

    # ── 2. CBTD có tỷ lệ QH cao ──────────────────────────────────────────────
    if df_hstd is not None and not df_hstd.empty and cbtd_data:
        try:
            from data.khtd import gan_cbtd_vao_df
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
                        "chi_tiet": {"ma_cb": ma_cb, "ho_ten": info["ho_ten"], "ty_le_qh": round(ty_le, 2),
                                     "tong_du_no": float(tdn), "du_no_qh": float(dqh)},
                    })
        except Exception as e:
            logger.error("canh_bao QH: %s", e, exc_info=True)

    # ── 3. Tổ TB/Yếu liên tiếp 2+ tháng ─────────────────────────────────────
    if (df_cdtotkvv is not None and not df_cdtotkvv.empty
            and df_cdtotkvv_truoc is not None and not df_cdtotkvv_truoc.empty):
        try:
            _XEP_LOAI_YEU = "Yếu"
            _XEP_LOAI_TB = "Trung bình"
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
                            f"Tổ **{ma_to}** ({r.get('ten_xa', '?')}) xếp loại "
                            f"{r.get('xep_loai', '?')} từ TB/Yếu 2+ tháng liên tiếp"
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

    # ── 4. Tổ điểm GIẢM 2 kỳ liên tiếp ──────────────────────────────────────
    if (df_cdtotkvv is not None and not df_cdtotkvv.empty
            and df_cdtotkvv_truoc is not None and not df_cdtotkvv_truoc.empty
            and "tong_diem" in df_cdtotkvv.columns
            and "tong_diem" in df_cdtotkvv_truoc.columns):
        try:
            d1 = df_cdtotkvv[["ma_to", "tong_diem", "ten_xa", "ten_dv", "xep_loai"]].copy()
            d2 = df_cdtotkvv_truoc[["ma_to", "tong_diem"]].copy()
            d1["ma_to"] = d1["ma_to"].astype(str).str.strip()
            d2["ma_to"] = d2["ma_to"].astype(str).str.strip()
            d1["tong_diem"] = pd.to_numeric(d1["tong_diem"], errors="coerce")
            d2 = d2.rename(columns={"tong_diem": "tong_diem_ky_truoc"})
            d2["tong_diem_ky_truoc"] = pd.to_numeric(d2["tong_diem_ky_truoc"], errors="coerce")
            merged = d1.merge(d2, on="ma_to", how="inner")
            merged = merged.dropna(subset=["tong_diem", "tong_diem_ky_truoc"])
            merged["delta"] = merged["tong_diem"] - merged["tong_diem_ky_truoc"]
            giam = merged[merged["delta"] < -2.0]
            for _, r in giam.iterrows():
                canh_baos.append({
                    "loai": "to_giam_diem_2ky",
                    "muc_do": "⚠️",
                    "noi_dung": (
                        f"Tổ **{r['ma_to']}** ({r.get('ten_xa', '?')}) điểm giảm "
                        f"{abs(float(r['delta'])):.1f} điểm (từ {float(r['tong_diem_ky_truoc']):.1f} → {float(r['tong_diem']):.1f})"
                    ),
                    "chi_tiet": {
                        "ma_to": r["ma_to"],
                        "ten_xa": r.get("ten_xa"),
                        "ten_dv": r.get("ten_dv"),
                        "delta": float(r["delta"]),
                        "diem_hien": float(r["tong_diem"]),
                        "diem_truoc": float(r["tong_diem_ky_truoc"]),
                    },
                })
        except Exception as e:
            logger.error("canh_bao Tổ giảm điểm: %s", e, exc_info=True)

    # ── 5. ĐGD không có hồ sơ vay (empty HSTD) ──────────────────────────────
    if df_hstd is not None and not df_hstd.empty and dgd_map and cbtd_data:
        try:
            from data.khtd import gan_cbtd_vao_df
            df_j = gan_cbtd_vao_df(df_hstd, cbtd_data, dgd_map)
            if COT_TEN_XA in df_j.columns and COT_TEN_THON in df_j.columns:
                # Build set of (norm_xa, norm_thon) present in HSTD
                hstd_xa_thon = set(
                    zip(
                        df_j[COT_TEN_XA].fillna("").astype(str).str.strip().str.lower(),
                        df_j[COT_TEN_THON].fillna("").astype(str).str.strip().str.lower(),
                    )
                )
                # Check each configured ĐGD: nếu có ≥3 ấp trong config nhưng KHÔNG có ấp nào có hồ sơ → cảnh báo
                for pgd_k, xa_block in dgd_map.items():
                    if not isinstance(xa_block, dict):
                        continue
                    for xa_k, dgd_block in xa_block.items():
                        if not isinstance(dgd_block, dict):
                            continue
                        for dgd_name, entry in dgd_block.items():
                            thon_list = entry.get("thon", []) if isinstance(entry, dict) else (entry or [])
                            if len(thon_list) < 3:
                                continue
                            da_co = 0
                            for t in thon_list:
                                if (_normalize(xa_k), _normalize(t)) in hstd_xa_thon:
                                    da_co += 1
                            if da_co == 0:
                                canh_baos.append({
                                    "loai": "dgd_khong_co_hs",
                                    "muc_do": "⚠️",
                                    "noi_dung": (
                                        f"ĐGD **{dgd_name}** ({pgd_k} / {xa_k}) có {len(thon_list)} ấp "
                                        f"nhưng chưa có hồ sơ vay nào trong HSTD"
                                    ),
                                    "chi_tiet": {"pgd": pgd_k, "xa": xa_k, "dgd": dgd_name,
                                                 "so_thon": len(thon_list)},
                                })
        except Exception as e:
            logger.error("canh_bao DGD không có HS: %s", e, exc_info=True)

    return canh_baos


# ─────────────────────────────────────────────────────────────────────────────
# KPI tóm tắt (mở rộng)
# ─────────────────────────────────────────────────────────────────────────────

def tom_tat_kpi(
    cbtd_data: dict,
    dgd_map: dict,
    df_cdtotkvv: "pd.DataFrame | None",
) -> dict:
    """
    Trả về dict KPI:
        so_cbtd, so_dgd_tong, so_dgd_chua_phan,
        so_to_tong, diem_tb, pct_to_dat, so_to_yeu, so_to_tb_yeu,
        so_cbtd_quatai, so_cbtd_thieutai
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

    # Workload CBTD
    so_cbtd_quatai = 0
    so_cbtd_thieutai = 0
    try:
        wl = danh_gia_workload_cbtd(cbtd_data, dgd_map)
        for info in wl.values():
            l = info.get("loai")
            if l == "quatai":
                so_cbtd_quatai += 1
            elif l == "thieutai":
                so_cbtd_thieutai += 1
    except Exception:
        pass

    return {
        "so_cbtd":          len(cbtd_data),
        "so_dgd_tong":      so_dgd_tong,
        "so_dgd_chua_phan": so_dgd_chua_phan,
        "so_to_tong":       so_to_tong,
        "diem_tb":          diem_tb,
        "pct_to_dat":       pct_to_dat,
        "so_to_yeu":        so_to_yeu,
        "so_to_tb_yeu":     so_to_tb_yeu,
        "so_cbtd_quatai":   so_cbtd_quatai,
        "so_cbtd_thieutai": so_cbtd_thieutai,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Workload CBTD đánh giá
# ─────────────────────────────────────────────────────────────────────────────

def danh_gia_workload_cbtd(
    cbtd_data: dict,
    dgd_map: dict,
    nguong_dgd_quatai: int = _NGUONG_DGD_QUA_TAI,
    nguong_ap_quatai: int = _NGUONG_AP_QUA_TAI,
    nguong_dgd_thieutai: int = _NGUONG_DGD_THIEU_TAI,
) -> dict[str, dict]:
    """
    Đánh giá mỗi CBTD là quá tải / cân bằng / thiếu tải.
    Trả về {ma_cb: {ho_ten, pgd, so_dgd, so_ap, loai}} — loai ∈ {"quatai","canbang","thieutai"}.
    """
    ket_qua: dict[str, dict] = {}
    for ma_cb, info in (cbtd_data or {}).items():
        pgd = info.get("pgd", "")
        ds_dgd = info.get("ds_dgd", []) or []
        so_dgd = len(ds_dgd)
        so_ap = _count_ap(pgd, ds_dgd, dgd_map)

        if so_dgd >= nguong_dgd_quatai or so_ap >= nguong_ap_quatai:
            loai = "quatai"
        elif so_dgd <= nguong_dgd_thieutai and so_ap > 0:
            loai = "thieutai"
        else:
            loai = "canbang"

        ket_qua[ma_cb] = {
            "ho_ten": info.get("ho_ten", ""),
            "pgd":    pgd,
            "so_dgd": so_dgd,
            "so_ap":  so_ap,
            "loai":   loai,
        }
    return ket_qua


# ─────────────────────────────────────────────────────────────────────────────
# Xếp hạng CBTD (scorecard)
# ─────────────────────────────────────────────────────────────────────────────

def xep_hang_cbtd(
    cbtd_data: dict,
    dgd_map: dict,
    df_hstd: "pd.DataFrame | None",
    df_cdtotkvv: "pd.DataFrame | None",
    to_theo_cbtd: "dict[str, list[dict]] | None" = None,
) -> pd.DataFrame:
    """
    Bảng xếp hạng CBTD theo scorecard (điểm tổng hợp 0-100).
    Trả về DataFrame có cột:
        Hang, Ma_CBTD, Ho_ten, PGD, So_DGD, So_ap, So_KH, Du_no_TY, TL_QH_pct,
        So_to, Pct_to_dat, Diem_TB_to, Diem_Tong, Xep_Loai
    """
    rows: list[dict] = []

    if to_theo_cbtd is None:
        to_theo_cbtd = lay_to_theo_cbtd(cbtd_data, dgd_map, df_cdtotkvv)

    # Build joined HSTD (once)
    df_joined = None
    if df_hstd is not None and not df_hstd.empty:
        try:
            from data.khtd import gan_cbtd_vao_df
            df_joined = gan_cbtd_vao_df(df_hstd, cbtd_data, dgd_map)
        except Exception:
            df_joined = None

    for ma_cb, info in (cbtd_data or {}).items():
        ho_ten = info.get("ho_ten", "")
        pgd = info.get("pgd", "")
        ds_dgd = info.get("ds_dgd", []) or []
        so_dgd = len(ds_dgd)
        so_ap = _count_ap(pgd, ds_dgd, dgd_map)

        # --- HSTD metrics ---
        so_kh = 0
        du_no_ty = 0.0
        tl_qh_pct = 0.0
        if df_joined is not None and not df_joined.empty:
            df_cb = df_joined[df_joined["CBTD"] == ma_cb]
            if not df_cb.empty:
                if COT_MA_KH in df_cb.columns:
                    so_kh = int(pd.Series(df_cb[COT_MA_KH]).nunique())
                dn_num = pd.to_numeric(df_cb.get(COT_TONG_DU_NO, pd.Series(dtype=float)),
                                        errors="coerce").fillna(0)
                qh_num = pd.to_numeric(df_cb.get(COT_DU_NO_QH, pd.Series(dtype=float)),
                                        errors="coerce").fillna(0)
                tdn = float(dn_num.sum())
                dqh = float(qh_num.sum())
                du_no_ty = tdn / 1_000_000_000.0
                tl_qh_pct = (dqh / tdn * 100) if tdn > 0 else 0.0

        # --- Tổ metrics ---
        tos = to_theo_cbtd.get(ma_cb, []) or []
        so_to = len(tos)
        pct_to_dat = 0.0
        diem_tb_to = None
        if so_to > 0:
            loai_xl = [t.get("xep_loai") for t in tos if t.get("xep_loai")]
            diems = [t.get("tong_diem") for t in tos
                     if t.get("tong_diem") is not None and isinstance(t.get("tong_diem"), (int, float))]
            if loai_xl:
                dat = sum(1 for x in loai_xl if x in ("Tốt", "Khá"))
                pct_to_dat = round(dat / len(loai_xl) * 100, 1)
            if diems:
                diem_tb_to = round(sum(diems) / len(diems), 1)

        # --- Scorecard (0-100) ---
        # Baseline 30 + TL QH 25 + % Tổ đạt 20 + Điểm TB Tổ 15 + Workload 10 = TOTAL 100
        s = 30.0  # baseline

        # TL QH (trọng số 25): 0% = 25đ, 5%+ = 0đ
        if tl_qh_pct <= 0:
            s += 25
        elif tl_qh_pct >= 5:
            s += 0
        else:
            s += 25 * (1 - tl_qh_pct / 5)

        # % Tổ đạt (trọng số 20): 100% = 20đ, 0% = 0đ
        s += pct_to_dat / 100 * 20

        # Điểm TB Tổ (trọng số 15): max 100đ → 15đ, chia 100 *15
        if diem_tb_to is not None:
            scaled = max(0.0, min(100.0, float(diem_tb_to)))
            s += scaled / 100 * 15

        # Workload balance (trọng số 10): ĐGD 2-4 cân bằng = 10đ
        if so_dgd == 0:
            pass
        elif so_dgd <= 4:
            s += 10
        elif so_dgd <= 6:
            s += 6
        else:
            s += 2

        s = round(max(0, min(100, s)), 1)

        # Xếp loại theo điểm tổng
        if s >= 85:
            xep_loai = "Xuất sắc"
        elif s >= 70:
            xep_loai = "Tốt"
        elif s >= 55:
            xep_loai = "Khá"
        elif s >= 40:
            xep_loai = "Trung bình"
        else:
            xep_loai = "Yếu"

        rows.append({
            "Ma_CBTD":     ma_cb,
            "Ho_ten":      ho_ten,
            "PGD":         pgd,
            "So_DGD":      so_dgd,
            "So_ap":       so_ap,
            "So_KH":       so_kh,
            "Du_no_TY":    round(du_no_ty, 2),
            "TL_QH_pct":   round(tl_qh_pct, 2),
            "So_to":       so_to,
            "Pct_to_dat":  pct_to_dat,
            "Diem_TB_to":  diem_tb_to if diem_tb_to is not None else 0.0,
            "Diem_Tong":   s,
            "Xep_Loai":    xep_loai,
        })

    if not rows:
        return pd.DataFrame(columns=[
            "Hang", "Ma_CBTD", "Ho_ten", "PGD", "So_DGD", "So_ap", "So_KH",
            "Du_no_TY", "TL_QH_pct", "So_to", "Pct_to_dat", "Diem_TB_to",
            "Diem_Tong", "Xep_Loai",
        ])

    df = pd.DataFrame(rows).sort_values("Diem_Tong", ascending=False).reset_index(drop=True)
    df.insert(0, "Hang", df.index + 1)
    return df


def tong_hop_hstd_theo_cbtd(
    cbtd_data: dict,
    dgd_map: dict,
    df_hstd: pd.DataFrame | None,
    *,
    yyyy: int | None = None,
    mm: int | None = None,
    scope_pgd: str | None = None,
    scope_ma_cb: str | None = None,
) -> pd.DataFrame:
    """
    Tổng hợp số liệu HSTD theo từng CBTD.

    Mỗi dòng ứng với một CBTD trong phạm vi được xem, kể cả CBTD chưa có HSTD
    khớp địa bàn để UI còn thấy rõ cán bộ nào thiếu phân công/dữ liệu.
    """
    columns = [
        "Ma_CBTD", "Ho_ten", "PGD", "So_DGD", "So_ap", "So_KH", "So_mon_vay",
        "Tong_du_no", "Du_no_trong_han", "Du_no_qh", "TL_QH_pct", "So_CT",
        "CT_du_no_lon_nhat", "Du_no_ct_lon_nhat", "So_KH_moi_thang",
        "So_giai_ngan_thang", "Canh_bao",
    ]
    try:
        scoped: dict[str, dict] = {}
        for ma_cb, info in (cbtd_data or {}).items():
            if scope_ma_cb and ma_cb != scope_ma_cb:
                continue
            pgd_cb = (info or {}).get("pgd") or ""
            if scope_pgd and pgd_cb.strip().lower() != scope_pgd.strip().lower():
                continue
            scoped[ma_cb] = info or {}

        rows: list[dict[str, Any]] = []
        df_joined: pd.DataFrame | None = None
        can_join = df_hstd is not None and not df_hstd.empty and scoped
        if can_join:
            try:
                from data.khtd import gan_cbtd_vao_df
                df_joined = gan_cbtd_vao_df(df_hstd, scoped, dgd_map)
                if COT_HINH_THUC_VAY in df_joined.columns:
                    htv = pd.to_numeric(df_joined[COT_HINH_THUC_VAY], errors="coerce")
                    df_joined = df_joined[htv != 1]
            except Exception as e:
                logger.error("tong_hop_hstd_theo_cbtd join HSTD: %s", e, exc_info=True)
                df_joined = None

        def _sum_col(df_part: pd.DataFrame, col: str) -> float:
            if col not in df_part.columns:
                return 0.0
            return float(pd.to_numeric(df_part[col], errors="coerce").fillna(0).sum() or 0.0)

        def _nunique_nonempty(df_part: pd.DataFrame, col: str) -> int:
            if col not in df_part.columns:
                return 0
            s = df_part[col].dropna().astype("string").str.strip()
            s = s[(s != "") & ~s.str.lower().isin(["nan", "none", "<na>"])]
            return int(s.nunique() or 0)

        for ma_cb, info in scoped.items():
            pgd = info.get("pgd") or ""
            ds_dgd = info.get("ds_dgd", []) or []
            df_cb = pd.DataFrame()
            if df_joined is not None and "CBTD" in df_joined.columns:
                df_cb = df_joined[df_joined["CBTD"] == ma_cb].copy()

            tong_du_no = _sum_col(df_cb, COT_TONG_DU_NO)
            du_no_qh = _sum_col(df_cb, COT_DU_NO_QH)
            du_no_th = _sum_col(df_cb, COT_DU_NO_TH)
            so_kh = _nunique_nonempty(df_cb, COT_MA_KH)
            so_mon = _nunique_nonempty(df_cb, COT_SO_KU)
            tl_qh = round(du_no_qh / tong_du_no * 100, 2) if tong_du_no > 0 else 0.0
            so_ct = _nunique_nonempty(df_cb, COT_TEN_CT)

            ct_lon_nhat = ""
            du_no_ct_lon_nhat = 0.0
            if COT_TEN_CT in df_cb.columns and COT_TONG_DU_NO in df_cb.columns and not df_cb.empty:
                tmp_ct = df_cb[[COT_TEN_CT, COT_TONG_DU_NO]].copy()
                tmp_ct[COT_TONG_DU_NO] = pd.to_numeric(tmp_ct[COT_TONG_DU_NO], errors="coerce").fillna(0)
                by_ct = tmp_ct.groupby(COT_TEN_CT, dropna=True)[COT_TONG_DU_NO].sum().sort_values(ascending=False)
                if not by_ct.empty:
                    ct_lon_nhat = str(by_ct.index[0])
                    du_no_ct_lon_nhat = float(by_ct.iloc[0] or 0.0)

            so_kh_moi = 0
            so_gn_thang = 0
            if yyyy and mm and not df_cb.empty:
                if COT_NGAY_VAY in df_cb.columns:
                    ng_vay = _parse_dt_series(df_cb[COT_NGAY_VAY])
                    mask_vay = (ng_vay.dt.year.astype("Int64") == int(yyyy)) & (
                        ng_vay.dt.month.astype("Int64") == int(mm)
                    )
                    so_kh_moi = _nunique_nonempty(df_cb.loc[mask_vay.fillna(False)], COT_MA_KH)
                if COT_NGAY_GN_DAU_TIEN in df_cb.columns:
                    ng_gn = _parse_dt_series(df_cb[COT_NGAY_GN_DAU_TIEN])
                    mask_gn = (ng_gn.dt.year.astype("Int64") == int(yyyy)) & (
                        ng_gn.dt.month.astype("Int64") == int(mm)
                    )
                    so_gn_thang = int(mask_gn.fillna(False).sum())

            canh_bao: list[str] = []
            if not ds_dgd:
                canh_bao.append("Chưa gán ĐGD")
            if df_hstd is None or df_hstd.empty:
                canh_bao.append("Chưa có HSTD")
            elif df_joined is None:
                canh_bao.append("Không join được HSTD")
            elif df_cb.empty:
                canh_bao.append("Không có hồ sơ khớp địa bàn")
            if du_no_qh > 0:
                canh_bao.append("Có nợ quá hạn")

            rows.append({
                "Ma_CBTD": ma_cb,
                "Ho_ten": info.get("ho_ten", ""),
                "PGD": pgd,
                "So_DGD": len(ds_dgd),
                "So_ap": _count_ap(pgd, ds_dgd, dgd_map),
                "So_KH": so_kh,
                "So_mon_vay": so_mon,
                "Tong_du_no": tong_du_no,
                "Du_no_trong_han": du_no_th,
                "Du_no_qh": du_no_qh,
                "TL_QH_pct": tl_qh,
                "So_CT": so_ct,
                "CT_du_no_lon_nhat": ct_lon_nhat,
                "Du_no_ct_lon_nhat": du_no_ct_lon_nhat,
                "So_KH_moi_thang": so_kh_moi,
                "So_giai_ngan_thang": so_gn_thang,
                "Canh_bao": "; ".join(canh_bao),
            })

        if not rows:
            return pd.DataFrame(columns=columns)
        return pd.DataFrame(rows, columns=columns).sort_values(
            ["Tong_du_no", "Du_no_qh"], ascending=[False, False]
        ).reset_index(drop=True)
    except Exception as e:
        logger.error("tong_hop_hstd_theo_cbtd: %s", e, exc_info=True)
        return pd.DataFrame(columns=columns)


# ─────────────────────────────────────────────────────────────────────────────
# Phân tích xu hướng chất lượng Tổ theo kỳ
# ─────────────────────────────────────────────────────────────────────────────

def phan_tich_xu_huong_to(
    ds_df_ky: "list[pd.DataFrame]",
    ds_nhan_ky: "list[str]",
) -> dict:
    """
    Phân tích xu hướng chất lượng Tổ qua nhiều kỳ.
    Args:
        ds_df_ky: list DataFrame CDTOTKVV theo từng kỳ (từ cũ → mới)
        ds_nhan_ky: list label kỳ (ví dụ ["06/2026", "07/2026", "08/2026"])
    Returns: dict:
        {
            "summary": {"ky": [..], "so_to": [..], "pct_dat": [..], "diem_tb": [..]},
            "to_duoi_tb_lien_tiep": list[{ma_to, ten_xa, ten_dv, so_ky_duoi_tb, ky_gan_nhat}],
            "to_tang_ty_le": list[{ma_to, ten_xa, so_ky_tang, delta}],
        }
    """
    summary: dict = {
        "ky": list(ds_nhan_ky),
        "so_to": [],
        "pct_dat": [],
        "diem_tb": [],
    }
    series: dict[str, list[tuple[str, float, str, str]]] = {}  # ma_to → [(ky, diem, ten_xa, ten_dv)]

    for ky_label, df_ky in zip(ds_nhan_ky, ds_df_ky):
        if df_ky is None or df_ky.empty:
            summary["so_to"].append(0)
            summary["pct_dat"].append(0.0)
            summary["diem_tb"].append(0.0)
            continue
        so_to = len(df_ky)
        summary["so_to"].append(so_to)
        if "xep_loai" in df_ky.columns:
            dat = int(df_ky["xep_loai"].astype(str).isin({"Tốt", "Khá"}).sum())
            summary["pct_dat"].append(round(dat / so_to * 100, 1) if so_to else 0.0)
        else:
            summary["pct_dat"].append(0.0)
        if "tong_diem" in df_ky.columns:
            diem = round(float(pd.to_numeric(df_ky["tong_diem"], errors="coerce").mean() or 0), 1)
            summary["diem_tb"].append(diem)
        else:
            summary["diem_tb"].append(0.0)
        # Series per to
        if "ma_to" in df_ky.columns:
            for _, r in df_ky.iterrows():
                ma = str(r.get("ma_to", "")).strip()
                if not ma:
                    continue
                d = pd.to_numeric(r.get("tong_diem"), errors="coerce")
                diem_val = float(d) if pd.notna(d) else None
                ten_xa = str(r.get("ten_xa", ""))
                ten_dv = str(r.get("ten_dv", ""))
                series.setdefault(ma, []).append((ky_label, diem_val, ten_xa, ten_dv))

    # Tổ dưới TB liên tiếp ≥ 2 kỳ
    to_duoi_tb: list[dict] = []
    to_tang: list[dict] = []
    for ma, lst in series.items():
        if len(lst) < 2:
            continue
        # Chỉ xét kỳ cuối N = min(len,6)
        recent = lst[-min(len(lst), 6):]
        cnt_duoi = 0
        ten_xa_lc = ""
        ten_dv_lc = ""
        for _ky, d, xa, dv in recent:
            ten_xa_lc = xa or ten_xa_lc
            ten_dv_lc = dv or ten_dv_lc
            if d is not None and d < 60:
                cnt_duoi += 1
        if cnt_duoi >= 2:
            to_duoi_tb.append({
                "ma_to": ma,
                "ten_xa": ten_xa_lc,
                "ten_dv": ten_dv_lc,
                "so_ky_duoi_tb": cnt_duoi,
                "ky_gan_nhat": recent[-1][0],
                "diem_gan_nhat": recent[-1][1],
            })
        # Tang tỷ lệ
        with_d = [(ky, d, xa, dv) for ky, d, xa, dv in recent if d is not None]
        if len(with_d) >= 2:
            delta = with_d[-1][1] - with_d[0][1]
            if delta >= 5:
                to_tang.append({
                    "ma_to": ma,
                    "ten_xa": with_d[-1][2],
                    "so_ky_tang": len(with_d),
                    "delta": round(delta, 1),
                })

    return {
        "summary":            summary,
        "to_duoi_tb_lien_tiep": to_duoi_tb,
        "to_tang_ty_le":       to_tang,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# [MỚI v4] Các helper phục vụ 6 nhóm nghiệp vụ CBTD tab mới
#   - lay_kpi_cbtd_theo_thang  : KPI tháng N cho 1 CBTD (Dashboard + Đèn giao dịch)
#   - top_3_viec_uu_tien       : Top 3 việc hôm nay (TN / NQH / Tổ yếu / Chờ GN)
#   - cham_diem_cbtd_thang     : Wrapper scorecard clamp 0-100 cho 1 CBTD (reuse xep_hang_cbtd)
# ═══════════════════════════════════════════════════════════════════════════════

def _parse_dt_series(s: pd.Series) -> pd.Series:
    """Helper parse date series an toàn (không raise, trả về NaT khi lỗi)."""
    try:
        parsed = pd.to_datetime(s, errors="coerce", dayfirst=True, format="mixed")
    except TypeError:
        parsed = pd.to_datetime(s, errors="coerce", dayfirst=True)
    try:
        text = s.astype("string").str.strip()
        iso_mask = text.str.match(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}", na=False)
        if bool(iso_mask.any()):
            parsed.loc[iso_mask] = pd.to_datetime(s.loc[iso_mask], errors="coerce", yearfirst=True)
    except Exception as e:
        logger.error("_parse_dt_series iso fallback: %s", e, exc_info=True)
    return parsed


def _scope_guard_cb(ma_cb: str, cbtd_data: dict, scope_pgd: str | None, scope_ma_cb: str | None) -> tuple[bool, str | None, dict | None]:
    """Check scope CBTD trước khi truy vấn dữ liệu. Trả (ok, reason, info_cb)."""
    if not ma_cb:
        return False, "ma_cb trống", None
    if scope_ma_cb and ma_cb != scope_ma_cb:
        return False, f"scope_ma_cb khớp (yêu cầu {scope_ma_cb}, nhận {ma_cb})", None
    info = (cbtd_data or {}).get(ma_cb)
    if not info:
        return False, f"{ma_cb} không trong cbtd_data", None
    pgd_cb = info.get("pgd") or ""
    if scope_pgd and pgd_cb and pgd_cb.strip().lower() != scope_pgd.strip().lower():
        return False, f"CBTD {ma_cb} thuộc PGD {pgd_cb} khác scope {scope_pgd}", None
    return True, None, info


def lay_kpi_cbtd_theo_thang(
    ma_cb: str,
    yyyy: int,
    mm: int,
    *,
    cbtd_data: dict,
    dgd_map: dict,
    df_hstd: pd.DataFrame | None = None,
    scope_pgd: str | None = None,
    scope_ma_cb: str | None = None,
) -> dict:
    """
    KPI tháng cho 1 CBTD (phục vụ Dashboard + Đèn giao dịch tháng).

    Returns dict keys:
      meta: {ma_cb, ho_ten, pgd, yyyy, mm, fallback_all_time, schema_missing_cols: list}
      so_kh: int | 0
      so_mon_vay: int | 0
      tong_du_no_ty: float (tỷ đồng) | 0.0
      du_no_qh_ty: float (tỷ đồng) | 0.0
      tl_qh_pct: float % | 0.0
      so_kh_moi_thang: int (số KH có ngày vay trong tháng N) | 0
      so_giai_ngan_mon: int (số món GN trong tháng N, nếu có cột ngày GN) | 0
    """
    result: dict[str, Any] = {
        "meta": {
            "ma_cb": ma_cb, "ho_ten": "", "pgd": "",
            "yyyy": yyyy, "mm": mm,
            "fallback_all_time": False,
            "schema_missing_cols": [],
        },
        "so_kh": 0, "so_mon_vay": 0,
        "tong_du_no_ty": 0.0, "du_no_qh_ty": 0.0, "tl_qh_pct": 0.0,
        "so_kh_moi_thang": 0, "so_giai_ngan_mon": 0,
    }
    try:
        ok, reason, info = _scope_guard_cb(ma_cb, cbtd_data, scope_pgd, scope_ma_cb)
        if not ok:
            result["meta"]["error"] = reason or "scope guard failed"
            return result
        assert info is not None
        result["meta"]["ho_ten"] = info.get("ho_ten", "")
        result["meta"]["pgd"] = info.get("pgd", "")

        if df_hstd is None or df_hstd.empty:
            result["meta"]["warning"] = "df_hstd rỗng — chưa có dữ liệu"
            return result

        # Rule 6.16 — Kiểm tra schema parquet trước khi access cột
        cols_req = [COT_TEN_XA, COT_TEN_THON, COT_MA_KH, COT_TONG_DU_NO]
        missing = [c for c in cols_req if c not in df_hstd.columns]
        result["meta"]["schema_missing_cols"] = list(missing)
        if missing:
            result["meta"]["warning"] = (f"Thiếu cột HSTD: {', '.join(missing)} — "
                                         f"thống kê có thể không đầy đủ")

        # Join CBTD → HSTD
        try:
            from data.khtd import gan_cbtd_vao_df
        except Exception as e:
            logger.error("lay_kpi_cbtd_theo_thang import gan_cbtd_vao_df: %s", e, exc_info=True)
            return result
        df_joined = gan_cbtd_vao_df(df_hstd, {ma_cb: info}, dgd_map)
        if COT_HINH_THUC_VAY in df_joined.columns:
            df_joined = df_joined[df_joined[COT_HINH_THUC_VAY] != 1]
        df_cb = df_joined[df_joined["CBTD"] == ma_cb] if "CBTD" in df_joined.columns else df_joined.iloc[0:0]
        if df_cb.empty:
            return result

        # --- Toàn thời gian (baseline luôn có dù thiếu cột tháng) ---
        if COT_MA_KH in df_cb.columns:
            result["so_kh"] = int(pd.to_numeric(df_cb[COT_MA_KH], errors="coerce").dropna().nunique() or 0)
        if COT_SO_KU in df_cb.columns:
            result["so_mon_vay"] = int(pd.to_numeric(df_cb[COT_SO_KU], errors="coerce").dropna().nunique() or 0)
        if COT_TONG_DU_NO in df_cb.columns:
            tdn = float(pd.to_numeric(df_cb[COT_TONG_DU_NO], errors="coerce").fillna(0).sum() or 0.0)
            result["tong_du_no_ty"] = round(tdn / 1_000_000_000.0, 2)
        if COT_DU_NO_QH in df_cb.columns:
            dqh = float(pd.to_numeric(df_cb[COT_DU_NO_QH], errors="coerce").fillna(0).sum() or 0.0)
            result["du_no_qh_ty"] = round(dqh / 1_000_000_000.0, 2)
            result["tl_qh_pct"] = round(dqh / tdn * 100, 2) if tdn > 0 else 0.0

        # --- Tháng N (nếu có cột ngày) ---
        has_thang = False
        mask_thang = pd.Series(False, index=df_cb.index)
        if COT_NGAY_VAY in df_cb.columns:
            ng_vay = _parse_dt_series(df_cb[COT_NGAY_VAY])
            mask = (ng_vay.dt.year.astype("Int64") == int(yyyy)) & (
                ng_vay.dt.month.astype("Int64") == int(mm)
            )
            # Số KH mới trong tháng = KH có Ngày vay trong tháng N
            if COT_MA_KH in df_cb.columns:
                mask_kh = mask.fillna(False)
                result["so_kh_moi_thang"] = int(
                    pd.to_numeric(df_cb.loc[mask_kh, COT_MA_KH], errors="coerce").dropna().nunique() or 0
                )
            mask_thang |= mask.fillna(False)
            has_thang = True
        if COT_NGAY_GN_DAU_TIEN in df_cb.columns:
            ng_gn = _parse_dt_series(df_cb[COT_NGAY_GN_DAU_TIEN])
            mask_gn = (ng_gn.dt.year.astype("Int64") == int(yyyy)) & (
                ng_gn.dt.month.astype("Int64") == int(mm)
            )
            result["so_giai_ngan_mon"] = int(mask_gn.fillna(False).sum())
            mask_thang |= mask_gn.fillna(False)
            has_thang = True
        if not has_thang:
            result["meta"]["fallback_all_time"] = True
            result["meta"]["warning"] = (result["meta"].get("warning", "") +
                                         " | HSTD thiếu cột Ngày vay / Ngày GN → "
                                         "KPI hiển thị toàn thời gian thay vì tháng").strip(" |")
        return result
    except Exception as e:
        logger.error("lay_kpi_cbtd_theo_thang(%s, %s-%02d): %s", ma_cb, yyyy, mm, e, exc_info=True)
        result["meta"]["error"] = f"exception: {type(e).__name__}: {e}"
        return result


def top_3_viec_uu_tien(
    ma_cb: str,
    today: date | None = None,
    *,
    cbtd_data: dict,
    dgd_map: dict,
    df_hstd: pd.DataFrame | None = None,
    scope_pgd: str | None = None,
) -> list[dict]:
    """
    Top 3 việc CBTD cần ưu tiên làm hôm nay.

    Priority: 1 (cao nhất) → Đến hạn trả nợ hôm nay
              2 → NQH trên 30 ngày
              3 → Đơn giải ngân chờ duyệt > 3 ngày (placeholder)
    Returns list[dict] tối đa 3 phần tử, sắp xếp priority tăng dần.
    """
    today = today or date.today()
    viecs: list[dict] = []
    try:
        ok, reason, info = _scope_guard_cb(ma_cb, cbtd_data, scope_pgd, None)
        if not ok:
            return [{"priority": 99, "loai": "error", "noi_dung": f"⚠️ {reason or 'scope guard'}", "chi_tiet": {}}]
        assert info is not None

        if df_hstd is None or df_hstd.empty:
            return [{"priority": 5, "loai": "chua_co_du_lieu",
                     "noi_dung": "ℹ️ Chưa có dữ liệu HSTD — upload file HSTD để có việc ưu tiên.",
                     "chi_tiet": {}}]

        # Join HSTD → CBTD
        try:
            from data.khtd import gan_cbtd_vao_df
        except Exception:
            return viecs
        df_joined = gan_cbtd_vao_df(df_hstd, {ma_cb: info}, dgd_map)
        if COT_HINH_THUC_VAY in df_joined.columns:
            df_joined = df_joined[df_joined[COT_HINH_THUC_VAY] != 1]
        df_cb = df_joined[df_joined["CBTD"] == ma_cb] if "CBTD" in df_joined.columns else df_joined.iloc[0:0]
        if df_cb.empty:
            return viecs

        # 1) Đến hạn hôm nay (Ngày đến hạn == today)
        if COT_NGAY_DEN_HAN in df_cb.columns:
            ng_dh = _parse_dt_series(df_cb[COT_NGAY_DEN_HAN])
            mask_today = (ng_dh.dt.date == today).fillna(False)
            cnt_today = int(mask_today.sum())
            if cnt_today > 0:
                kh_hint = "—"
                if COT_MA_KH in df_cb.columns:
                    kq = df_cb.loc[mask_today, COT_MA_KH].dropna().astype(str).head(3).tolist()
                    kh_hint = ", ".join(kq) + ("..." if cnt_today > 3 else "")
                viecs.append({
                    "priority": 1, "loai": "den_han_hom_nay",
                    "noi_dung": f"🔴 Có {cnt_today} hợp đồng ĐẾN HẠN trả nợ hôm nay ({today.strftime('%d/%m/%Y')})",
                    "chi_tiet": {"so_hd": cnt_today, "ma_kh_mau": kh_hint, "ngay": today.isoformat()},
                })

        # 2) NQH > 30 ngày (tỷ lệ % hoặc có dư nợ QH)
        if COT_DU_NO_QH in df_cb.columns and COT_TONG_DU_NO in df_cb.columns:
            dn_qh_num = pd.to_numeric(df_cb[COT_DU_NO_QH], errors="coerce").fillna(0)
            tdn_num = pd.to_numeric(df_cb[COT_TONG_DU_NO], errors="coerce").fillna(0)
            mask_nqh = (dn_qh_num > 0) & (tdn_num > 0)
            if mask_nqh.any():
                pct_nqh = (dn_qh_num[mask_nqh].sum() / tdn_num[mask_nqh].sum() * 100) if tdn_num[mask_nqh].sum() > 0 else 0.0
                so_mon = int(mask_nqh.sum())
                viecs.append({
                    "priority": 2, "loai": "nqh_cao",
                    "noi_dung": (f"⚠️ Có {so_mon} hợp đồng NQH (tỷ lệ {pct_nqh:,.1f}% trên dư nợ) — "
                                "cần rà soát & đôn đốc khách hàng."),
                    "chi_tiet": {"so_mon": so_mon, "ty_le_pct": round(float(pct_nqh), 2),
                                 "so_tien_qh_ty": round(float(dn_qh_num.sum() / 1_000_000_000), 2)},
                })

        # 3) Số hợp đồng mới vay < 7 ngày (giả định = đơn GN sắp hoàn tất → ưu tiên đóng hồ sơ)
        if COT_NGAY_VAY in df_cb.columns:
            ng_v = _parse_dt_series(df_cb[COT_NGAY_VAY]).dt.date
            cutoff = None
            # So sánh bằng date scalar để tránh lỗi timedelta trên Series object.
            try:
                cutoff = (pd.Timestamp(today) - pd.Timedelta(days=7)).date()
                mask_gn_gan = (ng_v >= cutoff).fillna(False)
            except Exception:
                mask_gn_gan = pd.Series(False, index=df_cb.index)
            so_hd_gan = int(mask_gn_gan.sum())
            if so_hd_gan > 0:
                viecs.append({
                    "priority": 3, "loai": "don_gn_moi",
                    "noi_dung": f"📝 {so_hd_gan} hồ sơ vay mới trong 7 ngày qua → kiểm tra hồ sơ & thanh lý thủ tục.",
                    "chi_tiet": {"so_hd": so_hd_gan, "ngay_cutoff": cutoff.isoformat() if cutoff else None},
                })

        # Sort & head 3
        viecs.sort(key=lambda x: (int(x.get("priority", 99)), x.get("noi_dung", "")))
        return viecs[:3]
    except Exception as e:
        logger.error("top_3_viec_uu_tien(%s, %s): %s", ma_cb, today, e, exc_info=True)
        return viecs


def cham_diem_cbtd_thang(
    ma_cb: str,
    yyyy: int,
    mm: int,
    *,
    cbtd_data: dict,
    dgd_map: dict,
    df_hstd: pd.DataFrame | None = None,
    df_cdtotkvv: pd.DataFrame | None = None,
    scope_pgd: str | None = None,
) -> dict:
    """
    Wrapper scorecard clamp 0-100 cho 1 CBTD (reuse logic xep_hang_cbtd).
    Nếu có KPI tháng N từ `lay_kpi_cbtd_theo_thang` sẽ ưu tiên; fallback toàn thời gian.
    BUGMAP C49: luôn clamp cuối 0-100.
    """
    result: dict[str, Any] = {
        "meta": {"ma_cb": ma_cb, "yyyy": yyyy, "mm": mm, "source": "fallback",
                 "ho_ten": "", "pgd": ""},
        "ma_cb": ma_cb,
        "ho_ten": "", "pgd": "",
        "diem_tong": 0.0, "xep_loai": "Yếu",
    }
    try:
        ok, reason, info = _scope_guard_cb(ma_cb, cbtd_data, scope_pgd, None)
        if not ok:
            result["meta"]["error"] = reason or "scope guard"
            return result
        assert info is not None
        result["meta"]["ho_ten"] = result["ho_ten"] = info.get("ho_ten", "")
        result["meta"]["pgd"]  = result["pgd"]  = info.get("pgd", "")

        # Filter CBTD dataset chứa 1 CBTD cho xep_hang_cbtd
        cbtd_1 = {ma_cb: info}
        try:
            df_xh = xep_hang_cbtd(cbtd_1, dgd_map, df_hstd, df_cdtotkvv)
        except Exception as e:
            logger.error("cham_diem_cbtd_thang xep_hang_cbtd wrapper: %s", e, exc_info=True)
            df_xh = pd.DataFrame()

        if df_xh is not None and not df_xh.empty:
            row = df_xh.iloc[0].to_dict()
            s_raw = float(row.get("Diem_Tong", 0.0) or 0.0)
            # BUGMAP C49 clamp
            s_clamped = round(max(0.0, min(100.0, s_raw)), 1)
            xl = str(row.get("Xep_Loai", "Yếu")) or "Yếu"
            hang = int(row.get("Hang", 1) or 1)
            result.update({
                "diem_tong": s_clamped,
                "xep_loai": xl,
                "hang_cbtd_all_cn": hang,
                "so_kh": int(row.get("So_KH", 0) or 0),
                "du_no_ty": float(row.get("Du_no_TY", 0.0) or 0.0),
                "tl_qh_pct": float(row.get("TL_QH_pct", 0.0) or 0.0),
                "so_to": int(row.get("So_to", 0) or 0),
                "pct_to_dat": float(row.get("Pct_to_dat", 0.0) or 0.0),
                "diem_tb_to": float(row.get("Diem_TB_to", 0.0) or 0.0),
                "so_dgd": int(row.get("So_DGD", 0) or 0),
                "so_ap":  int(row.get("So_ap", 0) or 0),
            })
            result["meta"]["source"] = "xep_hang_cbtd (toàn thời gian)"
            return result

        # Fallback: KPI tháng N + công thức thủ công 0-100 clamp
        kpi = lay_kpi_cbtd_theo_thang(ma_cb, yyyy, mm, cbtd_data=cbtd_data, dgd_map=dgd_map,
                                      df_hstd=df_hstd, scope_pgd=scope_pgd) or {}
        tl_qh = float(kpi.get("tl_qh_pct", 0.0) or 0.0)
        so_kh = int(kpi.get("so_kh", 0) or 0)
        s = 30.0
        if tl_qh <= 0:
            s += 25
        elif tl_qh >= 5:
            s += 0
        else:
            s += 25 * (1 - tl_qh / 5)
        # Workload 2-4 ĐGD cân bằng → 10đ
        so_dgd = len(info.get("ds_dgd", []) or [])
        if 2 <= so_dgd <= 4:
            s += 10
        elif 5 <= so_dgd <= 6:
            s += 6
        elif so_dgd > 6:
            s += 2
        # Số KH > 0 → 15đ (tiểu chuẩn đại diện)
        if so_kh > 0:
            s += min(15.0, so_kh / 20.0 * 15.0)
        # BUGMAP C49 clamp
        s = round(max(0.0, min(100.0, s)), 1)
        if s >= 85:
            xl = "Xuất sắc"
        elif s >= 70:
            xl = "Tốt"
        elif s >= 55:
            xl = "Khá"
        elif s >= 40:
            xl = "Trung bình"
        else:
            xl = "Yếu"
        result["meta"]["source"] = "fallback_kpi_thang + cong_thuc_can_ban"
        result.update({"diem_tong": s, "xep_loai": xl, "so_kh": so_kh, "tl_qh_pct": tl_qh, "so_dgd": so_dgd})
        return result
    except Exception as e:
        logger.error("cham_diem_cbtd_thang(%s,%s-%02d): %s", ma_cb, yyyy, mm, e, exc_info=True)
        result["meta"]["error"] = f"exception: {type(e).__name__}: {e}"
        # Final clamp (BUGMAP C49)
        result["diem_tong"] = round(max(0.0, min(100.0, float(result["diem_tong"] or 0.0))), 1)
        return result

