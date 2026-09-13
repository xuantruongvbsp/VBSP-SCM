"""
Tab Mẫu 03/KHNV — Báo cáo Chất lượng tín dụng.

Báo cáo tổng hợp theo từng PGD (Hội sở + 21 PGD) các chỉ tiêu:
  • Tổng dư nợ
  • Nợ quá hạn + Nợ khoanh (tổng): Số tiền, Tỷ lệ %, Chênh lệch tháng trước, Chênh lệch 31/12/năm trước
  • Trong đó Nợ quá hạn: Số tiền, Tỷ lệ %, Chênh lệch tháng trước, Chênh lệch 31/12/năm trước
  • Trong đó Nợ khoanh:  Số tiền, Tỷ lệ %, Chênh lệch tháng trước, Chênh lệch 31/12/năm trước

Đơn vị hiển thị: Triệu đồng (2 số lẻ), % (2 số lẻ).
Chênh lệch TĂNG = màu XANH LÁ. Chênh lệch GIẢM = màu ĐỎ.
"""

from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Tuple, Optional

import pandas as pd
import streamlit as st
from streamlit.delta_generator import DeltaGenerator

from logger import get_logger
logger = get_logger(__name__)

from config import (
    COT_DU_NO_KHOANH,
    COT_DU_NO_QH,
    COT_TEN_PGD,
    COT_TONG_DU_NO,
    DON_VI_CHI_NHANH,
    DS_PGD,
    TEN_CHI_NHANH_HIEN_THI,
)
from utils import xuat_excel, ten_file_xuat
from snapshot_service import (
    doc_snapshot,
    danh_sach_ky,
    snapshot_la_cuoi_thang,
)
from data.hstd import doc_baseline_merged, ts_baseline_merged


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS — Xác định 3 kỳ báo cáo & đọc dữ liệu
# ══════════════════════════════════════════════════════════════════════════════

def _tim_ba_ky(ds_ky: list[str]) -> Tuple[Optional[str], Optional[str]]:
    """Trả về (ky_hien_tai, ky_thang_truoc) từ snapshot.
    ds_ky phải sort DESC (mới → cũ).
    Chỉ nhận đúng tháng liền trước; nếu thiếu thì trả None để tránh so nhầm kỳ cũ.
    Mốc "năm trước" KHÔNG dùng snapshot — lấy từ baseline 31/12 (xem _lay_du_lieu_3_ky).
    """
    if not ds_ky:
        return None, None

    ky_ht = ds_ky[0]

    # Kỳ tháng trước: lùi 1 tháng so với ky_ht
    try:
        y, m = map(int, ky_ht.split("-"))
        if m == 1:
            kt = f"{y - 1}-12"
        else:
            kt = f"{y}-{m - 1:02d}"
        ky_thang_truoc = kt if kt in ds_ky else None
    except Exception:
        ky_thang_truoc = None

    return ky_ht, ky_thang_truoc


def _ngay_so_lieu_cn(df_snapshot: pd.DataFrame) -> str:
    """Lấy ngày thật từ dòng tổng CN; không tự suy diễn ngày khi metadata thiếu."""
    if df_snapshot is None or df_snapshot.empty or "ngay_so_lieu" not in df_snapshot.columns:
        return ""
    df_cn = (
        df_snapshot[df_snapshot["ten_pgd"].eq("__CN__")]
        if "ten_pgd" in df_snapshot.columns
        else pd.DataFrame()
    )
    ngay = df_cn["ngay_so_lieu"] if not df_cn.empty else df_snapshot["ngay_so_lieu"]
    ngay = ngay.dropna()
    return str(ngay.iloc[0]).strip() if not ngay.empty else ""


def _doc_baseline_theo_pgd(nam: int) -> pd.DataFrame:
    """Tổng hợp HSTD mốc 31/12/{nam} theo PGD → cột ten_pgd + tong_du_no + du_no_qh + du_no_khoanh."""
    if nam is None:
        return pd.DataFrame()
    try:
        df_bl = doc_baseline_merged(nam, ts=ts_baseline_merged(nam))
    except Exception as e:
        logger.error("tab_mau03_khnv: lỗi đọc baseline 31/12/%s — %s", nam, e, exc_info=True)
        return pd.DataFrame()
    if df_bl is None or df_bl.empty:
        return pd.DataFrame()

    df = df_bl.copy()
    for c in (COT_TONG_DU_NO, COT_DU_NO_QH, COT_DU_NO_KHOANH):
        if c not in df.columns:
            df[c] = 0.0
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
    if COT_TEN_PGD not in df.columns:
        return pd.DataFrame()

    return (
        df.groupby(COT_TEN_PGD, dropna=False)
        .agg(
            tong_du_no=(COT_TONG_DU_NO, "sum"),
            du_no_qh=(COT_DU_NO_QH, "sum"),
            du_no_khoanh=(COT_DU_NO_KHOANH, "sum"),
        )
        .reset_index()
        .rename(columns={COT_TEN_PGD: "ten_pgd"})
    )


def _lay_du_lieu_3_ky() -> Tuple[
    Optional[str], Optional[str], Optional[str],
    pd.DataFrame, pd.DataFrame, pd.DataFrame,
]:
    """Trả về (ky_ht, ky_tt, moc_cuoi_nam, df_ht, df_tt, df_cn).
    df_ht/df_tt từ snapshot; df_cn từ baseline 31/12 năm trước.
    """
    ds = danh_sach_ky()
    ky_ht, ky_tt = _tim_ba_ky(ds)

    def _doc(ky, *, yeu_cau_cuoi_thang=False):
        if ky is None:
            return pd.DataFrame()
        df = doc_snapshot(ky)
        if df.empty:
            return df
        if yeu_cau_cuoi_thang and not snapshot_la_cuoi_thang(df, ky):
            return pd.DataFrame()
        keep = ["ten_pgd", "tong_du_no", "du_no_qh", "du_no_khoanh"]
        df = df[[c for c in keep if c in df.columns]].copy()
        for c in ["tong_du_no", "du_no_qh", "du_no_khoanh"]:
            if c not in df.columns:
                df[c] = 0.0
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
        return df

    # Mốc "năm trước" = 31/12/{nam-1} → đọc từ baseline (KHÔNG từ snapshot)
    nam_ht = int(str(ky_ht).split("-")[0]) if ky_ht else datetime.now().year
    nam_bl = nam_ht - 1
    moc_cn = f"31/12/{nam_bl}"
    df_cn = _doc_baseline_theo_pgd(nam_bl)

    df_tt = _doc(ky_tt, yeu_cau_cuoi_thang=True)
    if df_tt.empty:
        ky_tt = None
    return ky_ht, ky_tt, moc_cn, _doc(ky_ht), df_tt, df_cn


# ══════════════════════════════════════════════════════════════════════════════
# BUSINESS LOGIC — Xây dựng bảng báo cáo
# ══════════════════════════════════════════════════════════════════════════════

def _build_report_data(df_ht, df_tt, df_cn) -> pd.DataFrame:
    """Merge 3 kỳ → DataFrame 1 hàng = 1 PGD.
    Tên cột ngắn gọn phục vụ render bảng & xuất Excel.
    """
    if df_ht.empty:
        return pd.DataFrame()

    ds_hien_thi = [DON_VI_CHI_NHANH] + list(DS_PGD)

    def _to_map(df):
        if df.empty:
            return {}
        return df.set_index("ten_pgd").to_dict("index")

    m_ht = _to_map(df_ht)
    m_tt = _to_map(df_tt)
    m_cn = _to_map(df_cn)

    def _VND_to_trieu(v): return float(v) / 1_000_000.0
    def _tong_no_xau_trieu(row: dict) -> float:
        return _VND_to_trieu(row.get("du_no_qh", 0)) + _VND_to_trieu(row.get("du_no_khoanh", 0))
    def _delta(curr: float, comp: float | None):
        if comp is None:
            return pd.NA
        return round(curr - comp, 2)

    rows = []
    for pgd in ds_hien_thi:
        r_ht = m_ht.get(pgd, {})
        r_tt = m_tt.get(pgd, {})
        r_cn = m_cn.get(pgd, {})

        tdn     = _VND_to_trieu(r_ht.get("tong_du_no",   0))
        nqh_ht  = _VND_to_trieu(r_ht.get("du_no_qh",     0))
        nkh_ht  = _VND_to_trieu(r_ht.get("du_no_khoanh", 0))
        nqhk_ht = nqh_ht + nkh_ht

        tl_qhk_ht  = (nqhk_ht / tdn * 100)   if tdn > 0 else 0.0
        tl_qh_ht   = (nqh_ht  / tdn * 100)   if tdn > 0 else 0.0
        tl_kh_ht   = (nkh_ht  / tdn * 100)   if tdn > 0 else 0.0

        rows.append({
            "ten_pgd":      pgd,
            "tong_du_no":   round(tdn, 2),
            "nqhk":         round(nqhk_ht, 2),
            "tl_nqhk":      round(tl_qhk_ht, 2),
            "d_nqhk_tt":    _delta(nqhk_ht, _tong_no_xau_trieu(r_tt) if r_tt else None),
            "d_nqhk_cn":    _delta(nqhk_ht, _tong_no_xau_trieu(r_cn) if r_cn else None),
            "nqh":          round(nqh_ht, 2),
            "tl_nqh":       round(tl_qh_ht, 2),
            "d_nqh_tt":     _delta(nqh_ht, _VND_to_trieu(r_tt.get("du_no_qh", 0)) if r_tt else None),
            "d_nqh_cn":     _delta(nqh_ht, _VND_to_trieu(r_cn.get("du_no_qh", 0)) if r_cn else None),
            "nkh":          round(nkh_ht, 2),
            "tl_nkh":       round(tl_kh_ht, 2),
            "d_nkh_tt":     _delta(nkh_ht, _VND_to_trieu(r_tt.get("du_no_khoanh", 0)) if r_tt else None),
            "d_nkh_cn":     _delta(nkh_ht, _VND_to_trieu(r_cn.get("du_no_khoanh", 0)) if r_cn else None),
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        tong = {"ten_pgd": f"⬛ Tổng {TEN_CHI_NHANH_HIEN_THI}"}
        tdn_sum = float(df["tong_du_no"].sum())
        tong["tong_du_no"] = round(tdn_sum, 2)
        for grp, prefix in [("nqhk", "nqhk"), ("nqh", "nqh"), ("nkh", "nkh")]:
            s = float(df[prefix].sum())
            tong[prefix] = round(s, 2)
            tong[f"tl_{prefix}"] = round(s / tdn_sum * 100, 2) if tdn_sum > 0 else 0.0
            for suffix in ("tt", "cn"):
                delta_series = pd.to_numeric(df[f"d_{prefix}_{suffix}"], errors="coerce")
                tong[f"d_{prefix}_{suffix}"] = (
                    round(float(delta_series.sum()), 2)
                    if delta_series.notna().any()
                    else pd.NA
                )
        df = pd.concat([df, pd.DataFrame([tong])], ignore_index=True)

    return df


# ══════════════════════════════════════════════════════════════════════════════
# RENDER BẢNG HTML — Multi-level header giống mẫu 03/KHNV
# ══════════════════════════════════════════════════════════════════════════════

def _fmt_tien(v: float) -> str:
    try:
        v = float(v)
        return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "—"


def _fmt_pct(v: float) -> str:
    try:
        v = float(v)
        return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "—"


def _fmt_delta(v: float) -> str:
    """Chênh lệch: Dương = tăng → XANH LÁ, Âm = giảm → ĐỎ."""
    try:
        v = float(v)
        if abs(v) < 0.005:
            s = "0,00"
            clr = "var(--text-secondary,#94A3B8)"
        else:
            sign = "+" if v > 0 else "−"
            s = f"{sign}{abs(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            clr = "#2E7D32" if v > 0 else "#C62828"
        return f'<span style="color:{clr};font-weight:600">{s}</span>'
    except Exception:
        return "—"


def _html_text(v: object) -> str:
    """Escape nội dung text động trước khi ghép vào HTML."""
    return escape(str(v), quote=True)


def _render_bang_html(df: pd.DataFrame, ngay_bc: str) -> None:
    """Render bảng báo cáo Mẫu 03 bằng HTML với header 3 tầng."""
    if df.empty:
        return

    BD = "#37474F"
    HD_BG = "#0D47A1"
    HD_BG_2 = "#1565C0"
    HD_TXT = "#FFFFFF"
    TX = "var(--text-primary,#ECEFF1)"
    TONG_BG = "rgba(13,71,161,0.10)"

    def td(v, al="right", cl="", bg="", fw="", raw_html=False):
        stl = (
            f"padding:6px 9px;border:1px solid {BD};"
            f"font-size:0.82rem;white-space:nowrap;"
            f"text-align:{al};color:{TX};vertical-align:middle"
        )
        if cl:
            stl += f";{cl}"
        if bg:
            stl += f";background:{bg}"
        if fw:
            stl += f";font-weight:{fw}"
        content = str(v) if raw_html else _html_text(v)
        return f"<td style='{stl}'>{content}</td>"

    header = f"""
    <thead>
    <tr>
      <th rowspan="3" style="background:{HD_BG};color:{HD_TXT};border:1px solid {BD};padding:7px 10px;text-align:center;width:40px">STT</th>
      <th rowspan="3" style="background:{HD_BG};color:{HD_TXT};border:1px solid {BD};padding:7px 10px;text-align:left;min-width:170px">Chi nhánh<br>tỉnh/thành phố</th>
      <th rowspan="3" style="background:{HD_BG};color:{HD_TXT};border:1px solid {BD};padding:7px 10px;text-align:right;min-width:110px">Tổng dư nợ</th>
      <th colspan="4" style="background:{HD_BG_2};color:{HD_TXT};border:1px solid {BD};padding:7px 10px;text-align:center">Nợ quá hạn và nợ khoanh</th>
      <th colspan="8" style="background:{HD_BG};color:{HD_TXT};border:1px solid {BD};padding:7px 10px;text-align:center">Trong đó</th>
    </tr>
    <tr>
      <th colspan="4" style="background:{HD_BG_2};color:{HD_TXT};border:1px solid {BD};padding:6px 10px;text-align:center">&nbsp;</th>
      <th colspan="4" style="background:{HD_BG_2};color:{HD_TXT};border:1px solid {BD};padding:6px 10px;text-align:center">Nợ quá hạn</th>
      <th colspan="4" style="background:{HD_BG_2};color:{HD_TXT};border:1px solid {BD};padding:6px 10px;text-align:center">Nợ khoanh</th>
    </tr>
    <tr>
      <!-- Nợ QH+Khoanh -->
      <th style="background:{HD_BG_2};color:{HD_TXT};border:1px solid {BD};padding:6px 8px;text-align:right;min-width:96px">Số tiền</th>
      <th style="background:{HD_BG_2};color:{HD_TXT};border:1px solid {BD};padding:6px 8px;text-align:right;min-width:64px">Tỷ lệ %</th>
      <th style="background:{HD_BG_2};color:{HD_TXT};border:1px solid {BD};padding:6px 8px;text-align:right;min-width:88px">± tháng trước</th>
      <th style="background:{HD_BG_2};color:{HD_TXT};border:1px solid {BD};padding:6px 8px;text-align:right;min-width:72px">± 31/12</th>
      <!-- Nợ QH -->
      <th style="background:{HD_BG_2};color:{HD_TXT};border:1px solid {BD};padding:6px 8px;text-align:right;min-width:96px">Số tiền</th>
      <th style="background:{HD_BG_2};color:{HD_TXT};border:1px solid {BD};padding:6px 8px;text-align:right;min-width:64px">Tỷ lệ %</th>
      <th style="background:{HD_BG_2};color:{HD_TXT};border:1px solid {BD};padding:6px 8px;text-align:right;min-width:88px">± tháng trước</th>
      <th style="background:{HD_BG_2};color:{HD_TXT};border:1px solid {BD};padding:6px 8px;text-align:right;min-width:72px">± 31/12</th>
      <!-- Nợ Khoanh -->
      <th style="background:{HD_BG_2};color:{HD_TXT};border:1px solid {BD};padding:6px 8px;text-align:right;min-width:96px">Số tiền</th>
      <th style="background:{HD_BG_2};color:{HD_TXT};border:1px solid {BD};padding:6px 8px;text-align:right;min-width:64px">Tỷ lệ %</th>
      <th style="background:{HD_BG_2};color:{HD_TXT};border:1px solid {BD};padding:6px 8px;text-align:right;min-width:88px">± tháng trước</th>
      <th style="background:{HD_BG_2};color:{HD_TXT};border:1px solid {BD};padding:6px 8px;text-align:right;min-width:72px">± 31/12</th>
    </tr>
    </thead>
    """

    body_rows = []
    for i, (_, r) in enumerate(df.iterrows()):
        is_tong = str(r["ten_pgd"]).startswith("⬛")
        bg = TONG_BG if is_tong else ("" if i % 2 == 0 else "rgba(255,255,255,0.03)")
        fw = "700" if is_tong else ""
        stt = "" if is_tong else str(i + 1)
        stt_al = "center"

        cells = (
            td(stt, stt_al, bg=bg, fw=fw)
            + td(r["ten_pgd"], "left", bg=bg, fw=fw)
            + td(_fmt_tien(r["tong_du_no"]), bg=bg, fw=fw)
            + td(_fmt_tien(r["nqhk"]), bg=bg, fw=fw)
            + td(_fmt_pct(r["tl_nqhk"]), bg=bg, fw=fw)
            + td(_fmt_delta(r["d_nqhk_tt"]), bg=bg, raw_html=True)
            + td(_fmt_delta(r["d_nqhk_cn"]), bg=bg, raw_html=True)
            + td(_fmt_tien(r["nqh"]), bg=bg, fw=fw)
            + td(_fmt_pct(r["tl_nqh"]), bg=bg, fw=fw)
            + td(_fmt_delta(r["d_nqh_tt"]), bg=bg, raw_html=True)
            + td(_fmt_delta(r["d_nqh_cn"]), bg=bg, raw_html=True)
            + td(_fmt_tien(r["nkh"]), bg=bg, fw=fw)
            + td(_fmt_pct(r["tl_nkh"]), bg=bg, fw=fw)
            + td(_fmt_delta(r["d_nkh_tt"]), bg=bg, raw_html=True)
            + td(_fmt_delta(r["d_nkh_cn"]), bg=bg, raw_html=True)
        )
        body_rows.append(f"<tr>{cells}</tr>")

    st.html(
        f"""
        <div style="overflow-x:auto;margin:2px 0">
        <table style="border-collapse:collapse;width:100%;font-family:'Inter','Segoe UI',sans-serif">
          {header}
          <tbody>{"".join(body_rows)}</tbody>
        </table>
        </div>
        """
    )


# ══════════════════════════════════════════════════════════════════════════════
# XUẤT EXCEL — 2 sheet: Dữ liệu & Meta
# ══════════════════════════════════════════════════════════════════════════════

def _xuat_excel_mau03(df: pd.DataFrame, ky_ht, ky_tt, ky_cn) -> bytes:
    """Xuất báo cáo Mẫu 03 ra Excel 2 sheet."""
    df_xl = df.copy()
    df_xl["ten_pgd"] = df_xl["ten_pgd"].astype(str).str.replace("⬛ ", "", regex=False)
    stt_vals = list(range(1, len(df_xl))) + [""]  # dòng tổng cuối không có STT
    df_xl.insert(0, "STT", stt_vals)

    df_xl = df_xl.rename(columns={
        "ten_pgd":    "Chi nhánh/tỉnh/thành phố",
        "tong_du_no": "Tổng dư nợ (triệu đồng)",
        "nqhk":       "Nợ QH+Khoanh - Số tiền (triệu đồng)",
        "tl_nqhk":    "Nợ QH+Khoanh - Tỷ lệ (%)",
        "d_nqhk_tt":  "Nợ QH+Khoanh - Chênh lệch tháng trước (triệu đồng)",
        "d_nqhk_cn":  "Nợ QH+Khoanh - Chênh lệch 31/12/năm trước (triệu đồng)",
        "nqh":        "Nợ quá hạn - Số tiền (triệu đồng)",
        "tl_nqh":     "Nợ quá hạn - Tỷ lệ (%)",
        "d_nqh_tt":   "Nợ quá hạn - Chênh lệch tháng trước (triệu đồng)",
        "d_nqh_cn":   "Nợ quá hạn - Chênh lệch 31/12/năm trước (triệu đồng)",
        "nkh":        "Nợ khoanh - Số tiền (triệu đồng)",
        "tl_nkh":     "Nợ khoanh - Tỷ lệ (%)",
        "d_nkh_tt":   "Nợ khoanh - Chênh lệch tháng trước (triệu đồng)",
        "d_nkh_cn":   "Nợ khoanh - Chênh lệch 31/12/năm trước (triệu đồng)",
    })

    df_meta = pd.DataFrame([
        {"Thông tin": "Tên báo cáo",      "Giá trị": "Báo cáo Chất lượng tín dụng (Mẫu 03/KHNV)"},
        {"Thông tin": "Đơn vị",           "Giá trị": TEN_CHI_NHANH_HIEN_THI},
        {"Thông tin": "Kỳ báo cáo",       "Giá trị": str(ky_ht or "")},
        {"Thông tin": "Mốc tháng trước",  "Giá trị": str(ky_tt or "(không có dữ liệu)")},
        {"Thông tin": "Mốc cuối năm",     "Giá trị": str(ky_cn or "(không có dữ liệu)")},
        {"Thông tin": "Đơn vị tiền tệ",   "Giá trị": "Triệu đồng (2 số lẻ)"},
        {"Thông tin": "Đơn vị tỷ lệ",     "Giá trị": "% (2 số lẻ)"},
        {"Thông tin": "Ngày xuất file",   "Giá trị": datetime.now().strftime("%d/%m/%Y %H:%M")},
        {"Thông tin": "Ghi chú",          "Giá trị": "Nguồn: kỳ hiện tại & tháng trước từ hstd_snapshot; mốc 31/12 từ baseline HSTD. Chênh lệch dương = TĂNG (xanh lá), âm = GIẢM (đỏ)."},
    ])

    return xuat_excel({
        "BaoCao_ChatLuongTD": df_xl,
        "ThongTinCauHinh":    df_meta,
    })

# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def render(tab: DeltaGenerator | None = None, **kwargs) -> None:
    """Render tab Báo cáo Chất lượng tín dụng (Mẫu 03/KHNV)."""
    ctx = tab if tab is not None else st.container()
    with ctx:
        st.markdown("### 📊 Báo cáo Chất lượng tín dụng")
        st.caption("🟢 Tăng · 🔴 Giảm  ·  Đơn vị: triệu đồng, % (2 số lẻ)")

        ky_ht, ky_tt, ky_cn, df_ht, df_tt, df_cn = _lay_du_lieu_3_ky()

        if ky_ht is None or df_ht.empty:
            st.warning("⚠️ Chưa có dữ liệu HSTD snapshot. Vui lòng upload HSTD và lưu snapshot trong tab Quản trị.")
            return

        nam_ht = int(str(ky_ht).split("-")[0])
        ngay_so_lieu = ""
        try:
            _tmp = doc_snapshot(ky_ht)
            ngay_so_lieu = _ngay_so_lieu_cn(_tmp)
        except Exception as e:
            logger.error("tab_mau03_khnv: lỗi đọc ngày số liệu snapshot kỳ %s — %s", ky_ht, e, exc_info=True)
        if not ngay_so_lieu:
            ngay_so_lieu = "Không xác định"

        ic1, ic2, ic3, ic4 = st.columns(4)
        ic1.info(f"**Kỳ báo cáo**\n\n{ky_ht}")
        ic2.info(f"**So với tháng trước**\n\n{ky_tt or '—'}")
        ic3.info(f"**So với mốc 31/12**\n\n{ky_cn or '—'}")
        ic4.success(f"**Ngày số liệu**\n\n{ngay_so_lieu}")

        df_bc = _build_report_data(df_ht, df_tt, df_cn)

        if df_bc.empty:
            st.warning("⚠️ Không xây dựng được dữ liệu báo cáo.")
            return

        st.html(
            f"""
            <div style="text-align:center;margin:6px 0 14px">
              <div style="font-size:0.85rem;font-weight:600;letter-spacing:0.02em;color:var(--text-primary,#ECEFF1)">
                NGÂN HÀNG CHÍNH SÁCH XÃ HỘI VIỆT NAM
              </div>
              <div style="font-size:0.8rem;color:var(--text-secondary,#94A3B8);margin-top:2px">
                {_html_text(TEN_CHI_NHANH_HIEN_THI)}
              </div>
              <div style="font-size:1.3rem;font-weight:700;margin-top:8px;color:var(--text-primary,#ECEFF1)">
                BÁO CÁO CHẤT LƯỢNG TÍN DỤNG
              </div>
              <div style="font-size:0.78rem;color:var(--text-secondary,#94A3B8);font-style:italic;margin-top:3px">
                Số liệu ngày {_html_text(ngay_so_lieu)} · Mẫu 03/KHNV
              </div>
            </div>
            """
        )

        ec1, ec2 = st.columns([8, 2])
        with ec2:
            xl_bytes = _xuat_excel_mau03(df_bc, ky_ht, ky_tt, ky_cn)
            st.download_button(
                label="📥 Xuất Excel Báo cáo Chất lượng tín dụng",
                data=xl_bytes,
                file_name=ten_file_xuat(f"BaoCao_ChatLuongTinDung_{ky_ht}"),
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                key="mau03_xuat_xl",
            )

        _render_bang_html(df_bc, ngay_so_lieu)

        with st.expander("📌 Ghi chú giải thích cột & nghiệp vụ", expanded=False):
            st.markdown(
                f"""
| Cột | Giải thích |
|---|---|
| **Tổng dư nợ** | Tổng dư nợ toàn bộ các khoản vay còn lại của PGD (triệu đồng, 2 số lẻ) |
| **Nợ QH+Khoanh** | Tổng cộng Dư nợ quá hạn + Dư nợ khoanh QĐ62 |
| **Tỷ lệ %** | (Số nợ / Tổng dư nợ) × 100, 2 số lẻ |
| **Chênh lệch tháng trước** | Giá trị kỳ báo cáo − Giá trị tháng trước (`+/−` triệu đồng) |
| **Chênh lệch 31/12/{nam_ht - 1}** | Giá trị kỳ báo cáo − Giá trị mốc 31/12 năm trước (baseline HSTD) |
| **Trong đó Nợ quá hạn** | Khoản vay đã quá hạn thanh toán (chưa khoanh) |
| **Trong đó Nợ khoanh** | Khoản vay được khoanh nợ theo Quyết định 62/NHCS |

> 💡 **Màu số chênh lệch:** 🟢 **Xanh lá** = TĂNG ; 🔴 **Đỏ** = GIẢM.
> Nguồn số liệu: bảng `hstd_snapshot` trong SQLite — được cập nhật khi chạy **Lưu snapshot** sau upload HSTD ở tab Quản trị.
> Thứ tự PGD trong bảng: Hội sở + 21 PGD theo danh sách cố định từ `config.DS_PGD`.
                """,
                unsafe_allow_html=False,
            )
