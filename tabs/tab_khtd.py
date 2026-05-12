"""Tab Kế hoạch Tín dụng — Phòng KH-NV quản lý, phân cấp đến Xã.

KV store:
  khtd_cn  → {ma_ct: gia_tri_dong}         kế hoạch tổng chi nhánh
  khtd_xa  → {ten_xa|ma_ct: gia_tri_dong}  kế hoạch phân bổ theo xã
"""
from __future__ import annotations

import os
import re
import json
import logging
from io import BytesIO
from pathlib import Path
from datetime import datetime
from typing import TYPE_CHECKING, Any

import streamlit as st
import pandas as pd
from openpyxl.styles import Font, PatternFill

import db
from utils import (
    xuat_excel,
    ten_file_xuat,
    fmt,
    fmt_so,
    vn,
    hien_thi_dataframe_phan_trang,
)
from pdf_service import xuat_pdf
from config import (
    CHUONG_TRINH_KHTD, TEN_CHINH_THUC_CT,
    COT_MA_CHUONG_TRINH, COT_NGUON_VON, COT_TONG_DU_NO, COT_DU_NO_TH,
    COT_TEN_CT, COT_TEN_PGD,
    DS_PGD, PGD_XA_MAP,
)

if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator

_LOG = logging.getLogger(__name__)

# ── Hằng số ──────────────────────────────────────────────────────────────────
KV_KEY_CN  = "khtd_cn"
KV_KEY_XA  = "khtd_xa"
DS_MA_CT   = [row[0] for row in CHUONG_TRINH_KHTD]
CT_TW      = [(mk, ten) for mk, _, ten, nv, _ in CHUONG_TRINH_KHTD if nv == "TW"]
CT_DP      = [(mk, ten) for mk, _, ten, nv, _ in CHUONG_TRINH_KHTD if nv == "DP"]
NGUON_VON_MA = {mk: nv for mk, _, _, nv, _ in CHUONG_TRINH_KHTD}
MA_CT_BY_MAKEY = {mk: int(ma_ct) for mk, ma_ct, _, _, _ in CHUONG_TRINH_KHTD}
MA_KEYS_CO_KHTD = {row[0] for row in CHUONG_TRINH_KHTD}
# Nhóm giao diện nhập thủ công KHTD Chi nhánh (theo ma_ct HSTD)
KHTD_CN_NHOM_MA_CT: list[tuple[str, list[int]]] = [
    ("Hộ nghèo · Cận nghèo · Thoát nghèo", [1, 9, 19]),
    ("HSSV · GQVL", [2, 3]),
    ("Nhà ở · DTTS · Xuất khẩu lao động", [4, 7, 17, 21, 25]),
    ("Vùng khó khăn", [10, 15]),
    ("Nước sạch · SXKD · Khác", [6, 12, 26, 99]),
]
# Sub-nhóm GQVL phân tầng 4 nhóm (TW: PL NV, ĐP: Mã NĐT)
GQVL_SUB_NHOM = [
    # (sub_key, ten_hien_thi, nguon_von)
    # nguon_von: "TW" → hiện ở cột KH TW, "ĐP" → hiện ở cột KH ĐP
    ("3_TW_NHCSXH", "↳ TW — NHCSXH huy động",   "TW"),
    ("3_TW_NSNN",   "↳ TW — NSNN (Quỹ QG TW)",  "TW"),
    ("3_DP_TINH",   "↳ ĐP — Cấp tỉnh",          "ĐP"),
    ("3_DP_XA",     "↳ ĐP — Cấp xã/khác",       "ĐP"),
]
MAKEY_BY_MACT_NV: dict[tuple[int, int], str] = {}
TEN_BASE_BY_MACT: dict[int, str] = {}
for mk, ma_ct, ten, nv, _ in CHUONG_TRINH_KHTD:
    ma_ct_i = int(ma_ct)
    nv_int = 1 if nv == "TW" else 2
    MAKEY_BY_MACT_NV[(ma_ct_i, nv_int)] = mk
    TEN_BASE_BY_MACT.setdefault(ma_ct_i, str(ten))

# Thư mục gốc dữ liệu
DATA_DIR = Path(__file__).parent.parent / "data"

# Thư mục lưu văn bản QĐ cấp Chi nhánh
QD_DIR_CN = DATA_DIR / "qd"


# ── Trợ lý đọc/ghi kv_store ──────────────────────────────────────────────────
def _doc_kv(key: str) -> dict[str, Any]:
    """
    Đọc dict từ kv_store theo key.
    
    Args:
        key: Khóa trong kv_store
    
    Returns:
        Dict chứa dữ liệu hoặc dict rỗng nếu không tìm thấy
    """
    val = db.doc_kv(key)
    if isinstance(val, dict):
        return val
    return {}


def _luu_kv(key: str, data: dict[str, Any], username: str) -> bool:
    """
    Ghi dict vào kv_store. Trả về True nếu thành công.
    
    Args:
        key: Khóa trong kv_store
        data: Dữ liệu cần lưu
        username: Tên người dùng thực hiện
    
    Returns:
        True nếu lưu thành công
    """
    try:
        db.ghi_kv(key, data, username)
        db.ghi_audit(username, "luu_kv", f"key={key}, {len(data)} items")
        return True
    except Exception as e:
        st.error(f"Lỗi lưu dữ liệu (key={key}): {e}")
        return False


def _fmt_vn(x, d: int = 1) -> str:
    try:
        if x is None or (isinstance(x, float) and pd.isna(x)):
            return "—"
        v = float(x)
        s = f"{v:,.{d}f}"
        return s.replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "—"


def _fvn(x: float, d: int = 1) -> str:
    """Định dạng số VN (d chữ số thập phân). KPI tỷ: d=3; KH triệu: d=1; TH triệu: d=0."""
    return f"{float(x):,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _khtd_cn_hdr_cell(
    text: str,
    bg: str,
    color: str | None = None,
    bold: bool = True,
) -> str:
    sty = (
        f"background-color:{bg};padding:8px 6px;border-radius:4px;"
        f"font-weight:{'600' if bold else '400'};font-size:0.88rem;"
        f"text-align:center;line-height:1.4"
        + (f";color:{color}" if color else "")
    )
    inner = text if text else "&nbsp;"
    return f"<div style='{sty}'>{inner}</div>"


def _fmt_vn_signed(x, d: int = 1) -> str:
    try:
        v = float(x)
        s = _fmt_vn(v, d)
        return f"+{s}" if v > 0 else s
    except Exception:
        return "—"

def _nv_int_tu_ma_key(ma_key: str) -> int | None:
    if ma_key.endswith("_TW"):
        return 1
    if ma_key.endswith("_DP"):
        return 2
    if "|" in ma_key:
        try:
            return int(ma_key.split("|", 1)[1])
        except Exception:
            return None
    nv = NGUON_VON_MA.get(ma_key)
    if nv == "TW":
        return 1
    if nv == "DP":
        return 2
    return None


def _ma_ct_tu_ma_key(ma_key: str) -> int | None:
    if "|" in ma_key:
        try:
            return int(ma_key.split("|", 1)[0])
        except Exception:
            return None
    if ma_key.endswith("_TW") or ma_key.endswith("_DP"):
        try:
            return int(ma_key.rsplit("_", 1)[0])
        except Exception:
            return None
    return MA_CT_BY_MAKEY.get(ma_key)


def _ma_key_tu_ma_ct_nv(ma_ct: int, nv_int: int) -> str:
    return MAKEY_BY_MACT_NV.get((int(ma_ct), int(nv_int)), f"{int(ma_ct)}|{int(nv_int)}")


def _ten_ct_base(ma_ct: int, ten_map: dict[str, str] | None = None) -> str:
    ten = TEN_BASE_BY_MACT.get(int(ma_ct))
    if ten:
        return ten
    ten_map = ten_map or {}
    for mk, t in ten_map.items():
        if _ma_ct_tu_ma_key(mk) == int(ma_ct):
            return t
    return str(ma_ct)


def _quet_ct_co_du_no(df: "pd.DataFrame | None") -> tuple[set[str], dict[str, str]]:
    if df is None or df.empty:
        return set(), {}
    if (
        COT_MA_CHUONG_TRINH not in df.columns
        or COT_NGUON_VON not in df.columns
    ):
        return set(), {}

    col_du_no = COT_TONG_DU_NO if COT_TONG_DU_NO in df.columns else (
        COT_DU_NO_TH if COT_DU_NO_TH in df.columns else None
    )
    if not col_du_no:
        return set(), {}

    lookup: dict[tuple[int, int], str] = {}
    for ma_key, ma_ct, _, nguon_von, _ in CHUONG_TRINH_KHTD:
        nv_int = 1 if nguon_von == "TW" else 2
        if (int(ma_ct), nv_int) not in lookup:
            lookup[(int(ma_ct), nv_int)] = ma_key

    ma_ct_s = pd.to_numeric(df[COT_MA_CHUONG_TRINH], errors="coerce").fillna(0).astype(int)
    nv_s = pd.to_numeric(df[COT_NGUON_VON], errors="coerce").fillna(0).astype(int)
    du_no_s = pd.to_numeric(df[col_du_no], errors="coerce").fillna(0).astype(float)

    ten_ct_s = df[COT_TEN_CT].astype(str).fillna("").str.strip() if COT_TEN_CT in df.columns else None

    mk_list: list[str] = []
    ten_list: list[str] = []
    for i in range(len(ma_ct_s)):
        if du_no_s.iat[i] <= 0:
            continue
        ma_ct = int(ma_ct_s.iat[i])
        nv_int = int(nv_s.iat[i])
        if ma_ct <= 0 or nv_int not in (1, 2):
            continue
        mk = lookup.get((ma_ct, nv_int), f"{ma_ct}|{nv_int}")
        mk_list.append(mk)
        if ten_ct_s is not None:
            ten_list.append(str(ten_ct_s.iat[i]))
        else:
            ten_list.append("")

    keys = set(mk_list)
    ten_map: dict[str, str] = {}
    for mk, ten in zip(mk_list, ten_list):
        if mk in ten_map:
            continue
        ten_map[mk] = TEN_CHINH_THUC_CT.get(mk, ten) or mk
    return keys, ten_map


def _chon_ds_ct(nv_chon: str, df_hstd_loc: "pd.DataFrame | None", them_keys: set[str] | None = None) -> list[tuple[str, str]]:
    keys_du_no, ten_map = _quet_ct_co_du_no(df_hstd_loc)
    them_keys = them_keys or set()

    keys_show = set(keys_du_no) | set(them_keys)
    base = CT_TW + CT_DP
    if not keys_show:
        keys_show = {mk for mk, _ in base}
    if nv_chon == "Trung ương":
        keys_show = {k for k in keys_show if _nv_int_tu_ma_key(k) == 1}
    elif nv_chon == "Địa phương":
        keys_show = {k for k in keys_show if _nv_int_tu_ma_key(k) == 2}

    base_keys = [mk for mk, _ in base if mk in keys_show]
    extra_keys = sorted(
        (k for k in keys_show if k not in {mk for mk, _ in base}),
        key=lambda k: (
            _nv_int_tu_ma_key(k) or 9,
            int(k.split("_", 1)[0]) if "_" in k and k.split("_", 1)[0].isdigit()
            else (int(k.split("|", 1)[0]) if "|" in k and k.split("|", 1)[0].isdigit() else 9_999),
            k,
        ),
    )

    out: list[tuple[str, str]] = []
    for mk in base_keys + extra_keys:
        out.append((mk, TEN_CHINH_THUC_CT.get(mk, ten_map.get(mk, mk)) or mk))
    return out


def _tinh_thuc_hien_theo_ct(df: "pd.DataFrame") -> dict[str, float]:
    """
    Tính 'Thực hiện' theo chương trình (ma_key) từ dữ liệu HSTD.
    Thực hiện = Tổng dư nợ (fallback: Dư nợ trong hạn nếu thiếu cột Tổng dư nợ).

    Lưu ý: nếu nhiều ma_key cùng (ma_ct, nv_int),
    giá trị dư nợ được chia đều — xem CHUONG_TRINH_KHTD
    để kiểm tra trùng mã.
    """
    if df is None or df.empty:
        return {}

    if COT_MA_CHUONG_TRINH not in df.columns or COT_NGUON_VON not in df.columns:
        return {}

    col_th = COT_TONG_DU_NO if COT_TONG_DU_NO in df.columns else (
        COT_DU_NO_TH if COT_DU_NO_TH in df.columns else None
    )
    if not col_th:
        return {}

    lookup: dict[tuple[int, int], list[str]] = {}
    for ma_key, ma_ct, _, nguon_von, _ in CHUONG_TRINH_KHTD:
        nv_int = 1 if nguon_von == "TW" else 2
        lookup.setdefault((int(ma_ct), nv_int), []).append(ma_key)

    ma_ct_s = pd.to_numeric(df[COT_MA_CHUONG_TRINH], errors="coerce").fillna(0).astype(int)
    nv_s = pd.to_numeric(df[COT_NGUON_VON], errors="coerce").fillna(0).astype(int)
    th_s = pd.to_numeric(df[col_th], errors="coerce").fillna(0).astype(float)

    tmp = pd.DataFrame({"ma_ct": ma_ct_s, "nv": nv_s, "th": th_s})
    tmp = tmp[(tmp["ma_ct"] > 0) & (tmp["nv"].isin([1, 2])) & (tmp["th"] != 0)]
    if tmp.empty:
        return {}

    g = tmp.groupby(["ma_ct", "nv"])["th"].sum()
    out: dict[str, float] = {}
    for (ma_ct, nv_int), val in g.items():
        mk_list = lookup.get((int(ma_ct), int(nv_int)), [])
        if len(mk_list) == 1:
            out[mk_list[0]] = float(val)
        elif len(mk_list) > 1:
            share = float(val) / len(mk_list)
            for mk in mk_list:
                out[mk] = share

    _dbg = os.environ.get("DEBUG", "").strip().lower()
    if _dbg in ("1", "true", "yes"):
        tong_th = sum(out.values())
        tong_du_no_full = float(pd.to_numeric(df[col_th], errors="coerce").fillna(0).sum())
        if tong_du_no_full > 0:
            pct_lech = abs(tong_th - tong_du_no_full) / tong_du_no_full * 100.0
        else:
            pct_lech = 0.0
        _LOG.debug(
            "[KHTD TH] tong_th(ma_key)=%s dong | tong_du_no(df)=%s dong | "
            "chenh_lech=%.4f%% | tmp_th_sum=%s",
            tong_th,
            tong_du_no_full,
            pct_lech,
            float(tmp["th"].sum()),
        )

    return out


def _tinh_th_gqvl_phan_tang(df_gqvl: "pd.DataFrame | None") -> dict[str, float]:
    """
    Tính TH thực tế cho 4 nhóm GQVL từ file GQVL (df sau merge toàn CN).
    Dùng cùng logic phân tầng với gen_dcgiam_sheet._phan_loai_4_nhom().
    Trả về: {"3_TW_NHCSXH": VND, "3_TW_NSNN": VND,
             "3_DP_TINH": VND, "3_DP_XA": VND}
    """
    result = {"3_TW_NHCSXH": 0.0, "3_TW_NSNN": 0.0,
              "3_DP_TINH": 0.0,   "3_DP_XA": 0.0}
    if df_gqvl is None or df_gqvl.empty:
        return result

    # Cột dư nợ: ưu tiên COT_TONG_DU_NO, fallback COT_DU_NO_TH
    col_dn = COT_TONG_DU_NO if COT_TONG_DU_NO in df_gqvl.columns \
             else (COT_DU_NO_TH if COT_DU_NO_TH in df_gqvl.columns else None)
    if col_dn is None:
        return result

    from db import doc_ndt_dp_ma_list
    ndt_list = doc_ndt_dp_ma_list()

    for _, row in df_gqvl.iterrows():
        nv  = str(row.get("Nguồn vốn", "")).strip()
        dn  = float(pd.to_numeric(row.get(col_dn, 0), errors="coerce") or 0)
        if dn == 0:
            continue
        if nv == "TW":
            try:
                pl = int(float(row.get("Phân loại NV", 0)))
            except:
                continue
            if pl == 2:
                result["3_TW_NHCSXH"] += dn
            elif pl == 1:
                result["3_TW_NSNN"]   += dn
        elif nv == "ĐP":
            ma = str(row.get("Mã nhà đầu tư", "")).strip()
            if ma in ndt_list:
                result["3_DP_TINH"] += dn
            else:
                result["3_DP_XA"]   += dn
    return result


from tabs.tab_khtd_nhap import render_nhap_cn, render_nhap_pgd
from tabs.tab_khtd_xuat import render_xuat_baocao


# ── Helper đọc GQVL parquet toàn CN ─────────────────────────────────────────
def _doc_gqvl_parquet() -> "pd.DataFrame | None":
    """Đọc GQVL từ cache parquet nếu có."""
    from pathlib import Path
    from config import CACHE_DIR
    gqvl_parquet = Path(CACHE_DIR) / "gqvl.parquet"
    if not gqvl_parquet.exists():
        return None
    try:
        return pd.read_parquet(gqvl_parquet)
    except Exception:
        return None


from utils import get_tab_context

# ── Entry point ───────────────────────────────────────────────────────────────
def render(tab: DeltaGenerator, **kwargs: dict) -> None:
    """
    Render tab Kế hoạch Tín dụng.
    
    Args:
        tab: Streamlit DeltaGenerator cho tab này
        **kwargs: Chứa role, username, df_full
    """
    role = kwargs.get("role", "user")
    username = kwargs.get("username", "unknown")
    df_full = kwargs.get("df_full")
    # Đọc GQVL toàn CN để tính TH phân tầng 4 nhóm
    df_gqvl = _doc_gqvl_parquet()

    with get_tab_context(tab):
        st.title("🏛️ Kế hoạch Tín dụng — Phòng KH-NV")
        st.caption(
            "Quản lý KHTD cấp Chi nhánh và phân bổ xuống Xã · "
            "Theo dõi chênh lệch phân bổ theo Chương trình"
        )

        tab_cn, tab_xa, tab_cb = st.tabs([
            "🏛️ KHTD Chi nhánh",
            "📍 KHTD theo Xã",
            "⚠️ Cảnh báo chênh lệch",
        ])
        with tab_cn:
            render_nhap_cn(role, username, df_full, df_gqvl)
        with tab_xa:
            render_nhap_pgd(role, username, df_full)
        with tab_cb:
            render_xuat_baocao()
