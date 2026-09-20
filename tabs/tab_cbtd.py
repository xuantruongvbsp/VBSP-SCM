"""Tab CBTD — Quản lý Cán bộ Tín dụng theo ĐGD.

Schema (v3):
    cbtd_data[ma_cb] = {
        "ho_ten":         str,
        "chuc_vu":        str,          # Cán bộ tín dụng / Trưởng nhóm / Phó nhóm / Khác
        "ngay_bo_nhiem":  str,          # định dạng DD/MM/YYYY
        "pgd":            str,          # PGD trực thuộc (không chéo PGD)
        "ds_dgd":         list[str],    # Tên ĐGD phụ trách (2-4 ĐGD)
        "dien_thoai":     str,
        "ghi_chu":        str,
        "ngay_cap":       str,
    }
Thôn/ấp được suy ra động từ dgd_map[pgd][xa][dgd] — không lưu trực tiếp.
"""
from __future__ import annotations

import re
from io import BytesIO
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

import streamlit as st
import pandas as pd

import db
from config import (
    COT_MA_KH, COT_NGAY_SL, COT_SO_KU, COT_TEN_THON,
    COT_TONG_DU_NO, COT_DU_NO_QH, COT_DU_NO_TH, COT_DU_NO_KHOANH,
    COT_TEN_PGD,
    DS_PGD, DON_VI_CHI_NHANH, lay_dgd_cho_pgd,
    TEN_CHI_NHANH_HIEN_THI,
)
from auth import la_phan_he_cn, la_phan_he_pgd, la_executive, la_quan_ly_cn, normalize_role
from logger import get_logger
from state_manager import SCMStateManager
from html import escape as _html_esc

from utils import xuat_excel, hien_thi_dataframe_phan_trang, fmt, fmt_so, fmt_ty, fmt_cl, vn, lazy_tabs
from components.delta_card import delta_card, kpi_row
from services.cbtd_dia_ban_service import (
    lay_kpi_cbtd_theo_thang, tong_hop_hstd_theo_cbtd,
    top_3_viec_uu_tien, cham_diem_cbtd_thang, lay_to_theo_cbtd,
    tong_hop_hstd_cbtd_xa_chuong_trinh, _parse_dt_series,
    chuan_bi_hstd_bao_cao_dgd, mask_noxh_truc_tiep,
)
from data.khtd import (
    doc_cbtd, luu_cbtd, lay_ap_tu_dgd_list, gan_cbtd_vao_df,
    lay_thong_tin_dgd_theo_ten,
)

if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator

logger = get_logger(__name__)


def _ky_hstd_hien_tai(df_hstd: pd.DataFrame | None) -> tuple[int, int, date | None]:
    """Trả kỳ/ngày số liệu mới nhất của HSTD; fallback ngày hiện tại khi thiếu."""
    today = date.today()
    if df_hstd is None or df_hstd.empty or COT_NGAY_SL not in df_hstd.columns:
        return today.year, today.month, None
    try:
        values = _parse_dt_series(df_hstd[COT_NGAY_SL]).dropna()
        if values.empty:
            return today.year, today.month, None
        latest = values.max().date()
        return latest.year, latest.month, latest
    except Exception as e:
        logger.error("_ky_hstd_hien_tai: lỗi đọc ngày số liệu — %s", e, exc_info=True)
        return today.year, today.month, None


# Cột snapshot thôn (snake_case) → tên cột thô trong tong_hop_hstd_theo_cbtd.
_SNAP_RENAME = {
    "ma_cb": "Ma_CBTD",
    "tong_du_no": "Tong_du_no",
    "du_no_th": "Du_no_trong_han",
    "du_no_qh": "Du_no_qh",
    "cho_vay_thang": "Cho_vay_thang",
    "thu_no_thang": "Thu_no_thang",
    "cho_vay_nam": "Cho_vay_nam",
    "thu_no_nam": "Thu_no_nam",
    "no_den_han_mon": "No_den_han_mon",
    "no_den_han_goc": "No_den_han_goc",
    "so_mon_3m_khd": "So_mon_3m_khd",
    "so_mon_rui_ro": "So_mon_rui_ro",
}


def _lay_snapshot_cbtd(ky: str, cbtd_data: dict, dgd_map: dict) -> pd.DataFrame:
    """Đọc snapshot thôn kỳ cũ → gán lại CBTD hiện tại → gộp theo CBTD (VND)."""
    if not ky:
        return pd.DataFrame()
    try:
        from snapshot_service import doc_thon_snapshot, snapshot_la_cuoi_thang
        from services.cbtd_dia_ban_service import tong_hop_thon_snapshot_theo_cbtd
        df_thon = doc_thon_snapshot(ky)
        if df_thon is None or df_thon.empty:
            return pd.DataFrame()
        if not snapshot_la_cuoi_thang(df_thon, ky):
            return pd.DataFrame()
        df_cb = tong_hop_thon_snapshot_theo_cbtd(df_thon, cbtd_data, dgd_map)
        if df_cb is None or df_cb.empty:
            return pd.DataFrame()
        return df_cb.rename(columns=_SNAP_RENAME)
    except Exception as e:
        logger.error("_lay_snapshot_cbtd: kỳ %s — %s", ky, e, exc_info=True)
        return pd.DataFrame()


def _num0(value: Any) -> float:
    parsed = pd.to_numeric(value, errors="coerce")
    return 0.0 if pd.isna(parsed) else float(parsed)


def _map_ky(df_ky: pd.DataFrame | None, col: str) -> dict[str, float]:
    """Map Ma_CBTD → giá trị cột của kỳ so sánh (rỗng nếu thiếu kỳ/cột)."""
    if df_ky is None or df_ky.empty:
        return {}
    if "Ma_CBTD" not in df_ky.columns or col not in df_ky.columns:
        return {}
    return {str(k): _num0(v) for k, v in zip(df_ky["Ma_CBTD"], df_ky[col])}


def _delta_ky(cur: float, ky_map: dict[str, float], ma: str) -> float | None:
    return (cur - ky_map[ma]) if ma in ky_map else None


def _tao_bang_tong_hop(
    df_cur: pd.DataFrame,
    df_ttr: pd.DataFrame | None,
    df_ntr: pd.DataFrame | None,
) -> pd.DataFrame:
    """Bảng dư nợ DỒN 1 bảng theo CBTD (khớp mẫu biểu VBSP): Kh vay vốn, món vay,
    tổng dư nợ, trong hạn/quá hạn/khoanh, cho vay/thu nợ tháng, TL QH
    + Δ dư nợ & Δ quá hạn so tháng trước và 31/12 năm trước."""
    if df_cur is None or df_cur.empty:
        return pd.DataFrame()

    metric_cols = ["Tong_du_no", "Du_no_trong_han", "Du_no_qh", "Cho_vay_thang", "Thu_no_thang"]
    extra_cols = ["So_KH", "So_mon_vay", "Du_no_khoanh"]
    delta_cols = (("Tong_du_no", "DN"), ("Du_no_qh", "QH"))
    maps = {c: (_map_ky(df_ttr, c), _map_ky(df_ntr, c)) for c in metric_cols}

    rows: list[dict] = []
    for _, r in df_cur.iterrows():
        ma = str(r.get("Ma_CBTD", ""))
        row: dict[str, Any] = {
            "Ma_CBTD": ma,
            "Ho_ten": r.get("Ho_ten", ""),
            "PGD": r.get("PGD", ""),
            "TL_QH_pct": _num0(r.get("TL_QH_pct")),
        }
        for c in metric_cols + extra_cols:
            row[c] = _num0(r.get(c))
        for c, pre in delta_cols:
            ttr_map, ntr_map = maps[c]
            row[f"{pre}_dTTr"] = _delta_ky(row[c], ttr_map, ma)
            row[f"{pre}_dNY"] = _delta_ky(row[c], ntr_map, ma)
        rows.append(row)

    df = pd.DataFrame(rows).sort_values("Tong_du_no", ascending=False).reset_index(drop=True)
    df.insert(0, "STT", range(1, len(df) + 1))

    tot: dict[str, Any] = {"STT": "", "Ma_CBTD": "TỔNG", "Ho_ten": "", "PGD": ""}
    for c in metric_cols + extra_cols:
        tot[c] = float(df[c].sum())
    tot["TL_QH_pct"] = round(tot["Du_no_qh"] / tot["Tong_du_no"] * 100, 1) if tot["Tong_du_no"] else 0.0
    for c, pre in delta_cols:
        ttr_map, ntr_map = maps[c]
        tot[f"{pre}_dTTr"] = (tot[c] - sum(ttr_map.values())) if ttr_map else None
        tot[f"{pre}_dNY"] = (tot[c] - sum(ntr_map.values())) if ntr_map else None
    return pd.concat([df, pd.DataFrame([tot])], ignore_index=True)


def _tao_bang_no_quan_tam(
    df_cur: pd.DataFrame,
    df_ttr: pd.DataFrame | None,
    df_ntr: pd.DataFrame | None,
) -> pd.DataFrame:
    """Bảng cụm chỉ tiêu nợ cần quan tâm: món đến hạn, 3T KHĐ, tiềm ẩn rủi ro + Δ."""
    if df_cur is None or df_cur.empty:
        return pd.DataFrame()

    metric_cols = ["No_den_han_mon", "So_mon_3m_khd", "So_mon_rui_ro"]
    pre_map = {"No_den_han_mon": "DH", "So_mon_3m_khd": "K3", "So_mon_rui_ro": "RR"}
    maps = {c: (_map_ky(df_ttr, c), _map_ky(df_ntr, c)) for c in metric_cols}

    rows: list[dict] = []
    for _, r in df_cur.iterrows():
        ma = str(r.get("Ma_CBTD", ""))
        row: dict[str, Any] = {
            "Ma_CBTD": ma,
            "Ho_ten": r.get("Ho_ten", ""),
            "PGD": r.get("PGD", ""),
        }
        for c in metric_cols:
            row[c] = _num0(r.get(c))
            ttr_map, ntr_map = maps[c]
            row[f"{pre_map[c]}_dTTr"] = _delta_ky(row[c], ttr_map, ma)
            row[f"{pre_map[c]}_dNY"] = _delta_ky(row[c], ntr_map, ma)
        rows.append(row)

    df = pd.DataFrame(rows).sort_values("No_den_han_mon", ascending=False).reset_index(drop=True)
    df.insert(0, "STT", range(1, len(df) + 1))

    tot: dict[str, Any] = {"STT": "", "Ma_CBTD": "TỔNG", "Ho_ten": "", "PGD": ""}
    for c in metric_cols:
        tot[c] = float(df[c].sum())
        ttr_map, ntr_map = maps[c]
        tot[f"{pre_map[c]}_dTTr"] = (tot[c] - sum(ttr_map.values())) if ttr_map else None
        tot[f"{pre_map[c]}_dNY"] = (tot[c] - sum(ntr_map.values())) if ntr_map else None
    return pd.concat([df, pd.DataFrame([tot])], ignore_index=True)


# ── Format ô bảng HTML (dùng class .cdp-* của utils_theme) ───────────────────

def _fmt_tr(v: Any) -> str:
    """VND → triệu đồng kiểu VN (0 số lẻ); 0 → '0'."""
    try:
        x = float(v)
    except (TypeError, ValueError):
        return "—"
    if pd.isna(x):
        return "—"
    return f"{x / 1_000_000:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _fmt_tr_dau(v: Any) -> str:
    """Chênh lệch triệu đồng có dấu +/-; |Δ| < 0.5 triệu → '0'."""
    try:
        x = float(v)
    except (TypeError, ValueError):
        return "—"
    if pd.isna(x):
        return "—"
    if abs(x) < 500_000:
        return "0"
    return ("+" if x > 0 else "-") + _fmt_tr(abs(x))


def _fmt_so_dau(v: Any) -> str:
    """Chênh lệch số món có dấu +/-; None → '—'."""
    try:
        x = float(v)
    except (TypeError, ValueError):
        return "—"
    if pd.isna(x):
        return "—"
    if abs(x) < 0.5:
        return "0"
    return ("+" if x > 0 else "-") + fmt_so(abs(x))


def _cls_delta(v: Any, tang_la_tot: bool) -> str:
    """Class màu cho ô Δ: xanh = thuận lợi, đỏ = cần chú ý."""
    try:
        x = float(v)
    except (TypeError, ValueError):
        return "cdp-zero"
    if pd.isna(x) or x == 0:
        return "cdp-zero"
    tang = x > 0
    return "cdp-pos" if tang == tang_la_tot else "cdp-neg"


def _td(content: str, bold: bool = False, align: str = "right", cls: str = "") -> str:
    attrs = f" class='{cls}'" if cls else ""
    if align == "left":
        attrs += " style='text-align:left'"
    body = f"<b>{content}</b>" if bold else content
    return f"<td{attrs}>{body}</td>"


def _td_delta(v: Any, tang_la_tot: bool, bold: bool = False, la_tien: bool = True) -> str:
    txt = _fmt_tr_dau(v) if la_tien else _fmt_so_dau(v)
    if txt == "—":
        return _td('<span class="cdp-zero">—</span>', bold)
    return _td(f'<span class="{_cls_delta(v, tang_la_tot)}">{txt}</span>', bold)


def _html_bang_du_no(df: pd.DataFrame) -> str:
    """Bảng dư nợ dồn 1 bảng — header 2 hàng nhóm giống mẫu biểu VBSP."""
    head = (
        "<thead><tr>"
        "<th rowspan='2'>STT</th><th rowspan='2'>Mã CBTD</th><th rowspan='2'>Họ tên</th>"
        "<th rowspan='2'>PGD</th><th rowspan='2'>Kh vay vốn</th><th rowspan='2'>Món vay</th>"
        "<th rowspan='2'>Tổng dư nợ</th>"
        "<th colspan='3'>Trong đó</th>"
        "<th rowspan='2'>Cho vay</th><th rowspan='2'>Thu nợ</th>"
        "<th colspan='2'>Dư nợ tăng/giảm</th><th colspan='2'>Quá hạn tăng/giảm</th>"
        "<th rowspan='2'>TL QH (%)</th>"
        "</tr><tr>"
        "<th>Trong hạn</th><th>Quá hạn</th><th>Khoanh</th>"
        "<th>So tháng trước</th><th>So 31/12 năm trước</th>"
        "<th>So tháng trước</th><th>So 31/12 năm trước</th>"
        "</tr></thead>"
    )
    body: list[str] = []
    for _, r in df.iterrows():
        b = str(r.get("Ma_CBTD", "")) == "TỔNG"
        cells = [
            _td(str(r.get("STT", "")), b, "left", "cdp-stt"),
            _td(_html_esc(str(r.get("Ma_CBTD", ""))), b, "left", "cdp-txt"),
            _td(_html_esc(str(r.get("Ho_ten", ""))), b, "left", "cdp-txt"),
            _td(_html_esc(str(r.get("PGD", ""))), b, "left", "cdp-txt"),
            _td(fmt_so(r.get("So_KH")), b),
            _td(fmt_so(r.get("So_mon_vay")), b),
            _td(_fmt_tr(r.get("Tong_du_no")), b),
            _td(_fmt_tr(r.get("Du_no_trong_han")), b),
            _td(_fmt_tr(r.get("Du_no_qh")), b),
            _td(_fmt_tr(r.get("Du_no_khoanh")), b),
            _td(_fmt_tr(r.get("Cho_vay_thang")), b),
            _td(_fmt_tr(r.get("Thu_no_thang")), b),
            _td_delta(r.get("DN_dTTr"), True, b),
            _td_delta(r.get("DN_dNY"), True, b),
            _td_delta(r.get("QH_dTTr"), False, b),
            _td_delta(r.get("QH_dNY"), False, b),
            _td(vn(r.get("TL_QH_pct"), 1), b),
        ]
        body.append(f'<tr class="cdp-row">{"".join(cells)}</tr>')
    return (
        '<div class="cdp-wrap cdp-fit"><table class="cdp-table cdp-fit-t">'
        f"{head}<tbody>{''.join(body)}</tbody></table></div>"
    )


def _chuan_bi_pdf_bang_du_no(df_th_x: pd.DataFrame) -> tuple[pd.DataFrame, list[str], list[str], list[str]]:
    """Chuẩn bị bảng PDF dư nợ CBTD: tiền quy triệu, delta thiếu kỳ giữ dấu thiếu dữ liệu."""
    df_pdf = df_th_x.copy()
    cols_tien = [c for c in [
        "Tổng dư nợ", "Trong hạn", "Quá hạn", "Khoanh",
        "Cho vay", "Thu nợ",
        "Dư nợ Δ so tháng trước", "Dư nợ Δ so 31/12 năm trước",
        "QH Δ so tháng trước", "QH Δ so 31/12 năm trước",
    ] if c in df_pdf.columns]
    delta_cols = {
        "Dư nợ Δ so tháng trước", "Dư nợ Δ so 31/12 năm trước",
        "QH Δ so tháng trước", "QH Δ so 31/12 năm trước",
    }
    for c in cols_tien:
        values = pd.to_numeric(df_pdf[c], errors="coerce").div(1_000_000).round(0)
        if c in delta_cols:
            df_pdf[c] = values.astype(object)
            df_pdf.loc[values.isna(), c] = "—"
        else:
            df_pdf[c] = values.fillna(0)

    cols_dem = [c for c in ["Kh vay vốn", "Món vay"] if c in df_pdf.columns]
    cols_pct = ["TL QH (%)"] if "TL QH (%)" in df_pdf.columns else []
    return df_pdf, cols_tien, cols_dem, cols_pct


def _html_bang_no_quan_tam(df: pd.DataFrame) -> str:
    """Bảng cụm chỉ tiêu nợ cần quan tâm — header 2 hàng, 3 nhóm × 3 cột."""
    head = (
        "<thead><tr>"
        "<th rowspan='2'>STT</th><th rowspan='2'>Mã CBTD</th><th rowspan='2'>Họ tên</th>"
        "<th rowspan='2'>PGD</th>"
        "<th colspan='3'>Món đến hạn</th>"
        "<th colspan='3'>Món 3T không hoạt động</th>"
        "<th colspan='3'>Món tiềm ẩn rủi ro</th>"
        "</tr><tr>"
        + "<th>Hiện tại</th><th>So tháng trước</th><th>So 31/12 năm trước</th>" * 3
        + "</tr></thead>"
    )
    body: list[str] = []
    for _, r in df.iterrows():
        b = str(r.get("Ma_CBTD", "")) == "TỔNG"
        cells = [
            _td(str(r.get("STT", "")), b, "left", "cdp-stt"),
            _td(_html_esc(str(r.get("Ma_CBTD", ""))), b, "left", "cdp-txt"),
            _td(_html_esc(str(r.get("Ho_ten", ""))), b, "left", "cdp-txt"),
            _td(_html_esc(str(r.get("PGD", ""))), b, "left", "cdp-txt"),
            _td(fmt_so(r.get("No_den_han_mon")), b),
            _td_delta(r.get("DH_dTTr"), False, b, la_tien=False),
            _td_delta(r.get("DH_dNY"), False, b, la_tien=False),
            _td(fmt_so(r.get("So_mon_3m_khd")), b),
            _td_delta(r.get("K3_dTTr"), False, b, la_tien=False),
            _td_delta(r.get("K3_dNY"), False, b, la_tien=False),
            _td(fmt_so(r.get("So_mon_rui_ro")), b),
            _td_delta(r.get("RR_dTTr"), False, b, la_tien=False),
            _td_delta(r.get("RR_dNY"), False, b, la_tien=False),
        ]
        body.append(f'<tr class="cdp-row">{"".join(cells)}</tr>')
    return (
        '<div class="cdp-wrap cdp-fit"><table class="cdp-table cdp-fit-t">'
        f"{head}<tbody>{''.join(body)}</tbody></table></div>"
    )


def _cac_ky_so_sanh_cdto(thang_hien: str | None) -> tuple[str | None, str | None]:
    """Trả đúng tháng trước và 31/12 năm trước từ kỳ CDTOTKVV ``MM/YYYY``."""
    try:
        dt = datetime.strptime(str(thang_hien or "").strip(), "%m/%Y")
    except ValueError:
        return None, None
    if dt.month == 1:
        ky_truoc = f"{dt.year - 1}-12"
    else:
        ky_truoc = f"{dt.year}-{dt.month - 1:02d}"
    return ky_truoc, f"{dt.year - 1}-12"


def _bang_to_tkvv(cbtd_data: dict, dgd_map: dict):
    """Bảng xếp hạng chất lượng Tổ TK&VV theo CBTD (theo số Tổ Tốt giảm dần).

    Số liệu "hiện tại" lấy theo kỳ CDTOTKVV mới nhất (nguồn theo kỳ
    ``load_cdto_toan_cn``), KHÔNG dùng ``cdtotkvv_latest.xlsx`` vì file này có
    thể bị cũ. Hai mốc so sánh được tính từ chính kỳ CDTOTKVV hiện tại, không
    dùng kỳ HSTD. Trả về ``(DataFrame, kỳ_hiện_tại, kỳ_trước, kỳ_baseline)``.
    """
    try:
        from services.cbtd_dia_ban_service import lay_to_theo_cbtd
        from snapshot_service import doc_cbtd_to_tkvv_snapshot
    except Exception as e:
        logger.error("_bang_to_tkvv import: %s", e, exc_info=True)
        return pd.DataFrame(), None, None, None

    df_cdto = None
    thang_hien = None
    try:
        from services.tongquan_cdto_service import load_cdto_toan_cn
        _cdto = load_cdto_toan_cn() or {}
        df_cdto = _cdto.get("df_raw")
        thang_hien = _cdto.get("thang_hien")
    except Exception as e:
        logger.error("_bang_to_tkvv: lỗi load_cdto_toan_cn — %s", e, exc_info=True)
    if df_cdto is None or df_cdto.empty:
        try:
            from services.cdtotkvv_service import tong_hop_tu_pgd_data
            df_cdto = tong_hop_tu_pgd_data()
            thang_hien = None
        except Exception as e:
            logger.error("_bang_to_tkvv: lỗi fallback tong_hop_tu_pgd_data — %s", e, exc_info=True)

    def _counts(df_cdto):
        out: dict[str, tuple[int, int, int, int, int]] = {}
        for m, tos in (lay_to_theo_cbtd(cbtd_data, dgd_map, df_cdto) or {}).items():
            seen: set[str] = set()
            n_to = n_tot = n_kha = n_tb = n_yeu = 0
            for t in tos:
                _id = f"{t.get('ma_to') or ''}|{t.get('ten_xa') or ''}"
                if _id in seen:
                    continue
                seen.add(_id)
                xl = str(t.get("xep_loai") or "").strip()
                n_to += 1
                if xl == "Tốt":
                    n_tot += 1
                elif xl == "Khá":
                    n_kha += 1
                elif xl == "Trung bình":
                    n_tb += 1
                elif xl == "Yếu":
                    n_yeu += 1
            out[m] = (n_to, n_tot, n_kha, n_tb, n_yeu)
        return out

    def _snap(df):
        out: dict[str, tuple[int, int, int, int, int]] = {}
        if df is None or df.empty:
            return out
        for _, r in df.iterrows():
            out[str(r.get("ma_cb", ""))] = (
                int(r.get("so_to", 0) or 0), int(r.get("so_tot", 0) or 0),
                int(r.get("so_kha", 0) or 0), int(r.get("so_tb", 0) or 0),
                int(r.get("so_yeu", 0) or 0),
            )
        return out

    ky_truoc, ky_baseline = _cac_ky_so_sanh_cdto(thang_hien)
    cur = _counts(df_cdto)
    ttr = _snap(doc_cbtd_to_tkvv_snapshot(ky_truoc)) if ky_truoc else {}
    ntr = _snap(doc_cbtd_to_tkvv_snapshot(ky_baseline)) if ky_baseline else {}

    rows: list[dict] = []
    for m, info in (cbtd_data or {}).items():
        so_to, tot, kha, tb, yeu = cur.get(m, (0, 0, 0, 0, 0))
        t_tot = ttr[m][1] if m in ttr else None
        n_tot = ntr[m][1] if m in ntr else None
        rows.append({
            "Mã CBTD": m,
            "Họ tên": info.get("ho_ten", ""),
            "PGD": info.get("pgd", ""),
            "Tổng Tổ": so_to,
            "Tốt": tot,
            "Khá": kha,
            "TB": tb,
            "Yếu": yeu,
            "% Tốt": (round(tot / so_to * 100, 1) if so_to else 0.0),
            "Δ Tốt TTr": (tot - t_tot) if t_tot is not None else None,
            "Δ Tốt NTr": (tot - n_tot) if n_tot is not None else None,
        })
    if not rows:
        return pd.DataFrame(), thang_hien, ky_truoc, ky_baseline
    df = pd.DataFrame(rows).sort_values("Tốt", ascending=False).reset_index(drop=True)
    df.insert(0, "Hạng", range(1, len(df) + 1))
    return df, thang_hien, ky_truoc, ky_baseline


def _hien_thi_bang_to(df: pd.DataFrame):
    """Định dạng + tô màu cột Δ cho bảng chất lượng Tổ TK&VV."""
    def _color(v):
        if v is None or pd.isna(v):
            return ""
        if float(v) > 0:
            return "color: #2da44e"
        if float(v) < 0:
            return "color: #cf222e"
        return ""

    def _fmt_delta(v):
        if v is None or pd.isna(v):
            return "—"
        if float(v) == 0:
            return "0"
        s = fmt_so(abs(float(v)))
        return ("+" + s) if float(v) > 0 else ("-" + s)

    def _fmt_pct(v):
        if v is None or pd.isna(v):
            return "—"
        return f"{float(v):,.1f}%".replace(",", "X").replace(".", ",").replace("X", ".")

    return (
        df.style
        .map(_color, subset=["Δ Tốt TTr", "Δ Tốt NTr"])
        .format({
            "Tổng Tổ": lambda v: fmt_so(v),
            "Tốt": lambda v: fmt_so(v),
            "Khá": lambda v: fmt_so(v),
            "TB": lambda v: fmt_so(v),
            "Yếu": lambda v: fmt_so(v),
            "% Tốt": _fmt_pct,
            "Δ Tốt TTr": _fmt_delta,
            "Δ Tốt NTr": _fmt_delta,
        }, na_rep="—")
    )


DS_PGD_ALL = [DON_VI_CHI_NHANH] + DS_PGD

CHUC_VU_OPTS = ["Cán bộ tín dụng", "Trưởng nhóm", "Phó nhóm", "Khác"]
_NGUONG_DGD_QUATAI = 5
_NGUONG_DGD_THIEUTAI = 1
_SDT_REGEX = re.compile(r"^[0-9+\-\s]{8,15}$")
# Mã CBTD nhập tự do — chỉ cấm khoảng trắng và ký tự không an toàn cho tên file.
_MA_CB_REGEX = re.compile(r'^[^\s/\\:*?"<>|]{2,30}$')


def _cbtd_add_form_prefix(key_prefix: str, version: int) -> str:
    """Prefix widget key cho form thêm CBTD; tăng version để reset form sau khi lưu."""
    return f"{key_prefix}cbtd_add_v{version}_"


def _validate_dien_thoai(s: Any) -> tuple[bool, str]:
    """Validate SĐT: rỗng = OK (không bắt buộc); không rỗng phải khớp regex."""
    if not s or not str(s).strip():
        return True, ""
    if not _SDT_REGEX.match(str(s).strip()):
        return False, "Số điện thoại chỉ chứa chữ số, +, -, dấu cách; dài 8-15 ký tự"
    return True, ""


def _validate_ma_cb(s: Any, existed: dict | None = None, bo_qua_ma: str | None = None) -> tuple[bool, str]:
    """Validate mã CBTD: không trống, đúng format, không trùng."""
    existed = existed or {}
    bo_qua = (bo_qua_ma or "").strip().upper()
    v = (s or "").strip().upper()
    if not v:
        return False, "Mã CBTD không được trống"
    if not _MA_CB_REGEX.match(v):
        return False, ('Mã CBTD: 2-30 ký tự, không chứa khoảng trắng và các ký tự / \\ : * ? " < > | '
                       '(dùng gạch dưới _ thay khoảng trắng)')
    if v in existed and v != bo_qua:
        return False, f"Mã {v} đã tồn tại, chọn mã khác"
    return True, ""


def _auto_gen_ma_cb(pgd: str, existed: dict) -> str:
    """Tự sinh mã CBTD duy nhất: CB_{slug}_{3 số}."""
    slug = re.sub(r"[^A-Z0-9]+", "_", pgd.upper().strip()).strip("_") or "CN"
    for i in range(1, 999):
        candidate = f"CB_{slug}_{i:03d}"
        if candidate not in existed:
            return candidate
    return f"CB_{slug}_{datetime.now().strftime('%H%M%S')}"


def _workload_label(so_dgd: int) -> tuple[str, str]:
    """(icon, label) — emoji + text workload."""
    if so_dgd >= _NGUONG_DGD_QUATAI:
        return "🔴", "Quá tải"
    if so_dgd <= _NGUONG_DGD_THIEUTAI:
        return "⚠️", "Thiếu tải"
    return "✅", "Cân bằng"


def _pgd_slug_ma(pgd: str) -> str:
    # Giữ chữ có dấu (Unicode) để slug của mã CBTD tiếng Việt không bị rỗng/trùng key widget.
    return re.sub(r"\W+", "_", str(pgd).upper().strip()).strip("_") or "CN"


def _ddmmyyyy_to_date(s: Any) -> date | None:
    if not s:
        return None
    try:
        return datetime.strptime(str(s).strip(), "%d/%m/%Y").date()
    except Exception:
        return None


def _date_to_ddmmyyyy(d: date | None) -> str:
    if not d:
        return ""
    return d.strftime("%d/%m/%Y")


def _build_profile_pdf(ma_cb: str, info: dict, kpi_hstd: dict | None,
                       tos_info: list[dict] | None,
                       pgd_user_override: str | None = None) -> bytes | None:
    """Tạo PDF hồ sơ năng lực CBTD (A4). Trả về bytes hoặc None nếu lỗi.

    Khối: Header đơn vị + Thông tin cá nhân + Địa bàn phụ trách + KPI HSTD
          + Bảng Tổ TK&VV + Khối ký tên (3 vị trí).
    """
    try:
        from services.pdf_service import (
            _register_vbsp_fonts, _VBSP_GREEN, _VBSP_GREEN_LIGHT, _VBSP_ACCENT,
            _set_col_ratio, _PAGE_WIDTH, _PAGE_HEIGHT, _MARGIN,
        )
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm, cm
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
        )
        from reportlab.pdfbase.pdfmetrics import stringWidth

        _register_vbsp_fonts()
        buf = BytesIO()
        page_w, page_h = A4

        ngay_str = datetime.today().strftime("%d/%m/%Y")
        ho_ten = info.get("ho_ten", "")
        pgd = info.get("pgd", "") or (pgd_user_override or "")
        chuc_vu = info.get("chuc_vu", "") or "Cán bộ tín dụng"
        ngay_bn = info.get("ngay_bo_nhiem", "") or "—"
        dien_thoai = info.get("dien_thoai", "") or "—"
        ghi_chu = info.get("ghi_chu", "") or "—"
        ds_dgd = info.get("ds_dgd", []) or []

        def _on_page(canvas, doc):
            canvas.saveState()
            # Header kẻ xanh
            canvas.setStrokeColor(_VBSP_GREEN)
            canvas.setLineWidth(1.4)
            canvas.line(_MARGIN, page_h - _MARGIN + 4, page_w - _MARGIN, page_h - _MARGIN + 4)
            canvas.setFont("Times-Bold", 9)
            canvas.setFillColor(_VBSP_GREEN)
            canvas.drawString(_MARGIN, page_h - _MARGIN + 10,
                              TEN_CHI_NHANH_HIEN_THI or "Ngân hàng Chính sách Xã hội - Chi nhánh Đồng Nai")
            canvas.setFont("Times-Roman", 8)
            canvas.setFillColor(colors.black)
            canvas.drawRightString(page_w - _MARGIN, page_h - _MARGIN + 10,
                                   f"Ngày in: {ngay_str}")
            # Footer
            canvas.setStrokeColor(_VBSP_ACCENT)
            canvas.setLineWidth(0.6)
            canvas.line(_MARGIN, _MARGIN - 10, page_w - _MARGIN, _MARGIN - 10)
            canvas.setFont("Times-Roman", 7.5)
            canvas.setFillColor(colors.black)
            canvas.drawString(_MARGIN, _MARGIN - 22,
                              "Hồ sơ năng lực CBTD — Hệ thống Quản trị Tín dụng Nội bộ")
            canvas.drawRightString(page_w - _MARGIN, _MARGIN - 22,
                                   f"Trang {doc.page}    |    In lúc {datetime.today().strftime('%d/%m/%Y %H:%M')}")
            canvas.restoreState()

        doc = SimpleDocTemplate(
            buf, pagesize=A4,
            leftMargin=_MARGIN, rightMargin=_MARGIN,
            topMargin=_MARGIN + 14, bottomMargin=_MARGIN + 6,
            title=f"Hồ sơ năng lực CBTD - {ma_cb} - {ho_ten}",
            author="VBSP ĐN SCM",
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle("T", parent=styles["Title"], fontName="Times-Bold",
                                     fontSize=16, textColor=_VBSP_GREEN,
                                     alignment=TA_CENTER, spaceAfter=2)
        sub_style = ParagraphStyle("S", parent=styles["Normal"], fontName="Times-Italic",
                                   fontSize=10, alignment=TA_CENTER, textColor=colors.grey,
                                   spaceAfter=8)
        h2 = ParagraphStyle("H2", parent=styles["Heading2"], fontName="Times-Bold",
                            fontSize=12, textColor=_VBSP_GREEN, spaceBefore=6, spaceAfter=3)
        info_key = ParagraphStyle("IK", parent=styles["Normal"], fontName="Times-Bold",
                                  fontSize=10.5, leading=15)
        info_val = ParagraphStyle("IV", parent=styles["Normal"], fontName="Times-Roman",
                                  fontSize=10.5, leading=15)
        th_style = ParagraphStyle("TH", parent=styles["Normal"], fontName="Times-Bold",
                                  fontSize=9.5, textColor=colors.whiter, alignment=TA_CENTER,
                                  leading=13)
        td_style = ParagraphStyle("TD", parent=styles["Normal"], fontName="Times-Roman",
                                  fontSize=9.5, alignment=TA_CENTER, leading=13)
        td_left = ParagraphStyle("TL", parent=td_style, alignment=TA_LEFT)
        td_right = ParagraphStyle("TR", parent=td_style, alignment=TA_RIGHT)

        story = []
        # Header tiêu đề
        story.append(Paragraph("HỒ SƠ NĂNG LỰC CÁN BỘ TÍN DỤNG", title_style))
        story.append(Paragraph(f"Mã CBTD: {ma_cb} &nbsp;&nbsp;|&nbsp;&nbsp; "
                               f"PGD: {pgd} &nbsp;&nbsp;|&nbsp;&nbsp; In ngày {ngay_str}", sub_style))
        story.append(HRFlowable(width="100%", thickness=1.2, color=_VBSP_GREEN,
                                spaceBefore=0, spaceAfter=6))

        # --- Khối 1: Thông tin cá nhân ---
        story.append(Paragraph("1. Thông tin cá nhân", h2))
        info_rows = [
            ["Họ và tên:", ho_ten, "Chức vụ:", chuc_vu],
            ["Đơn vị PGD:", pgd, "Ngày bổ nhiệm:", ngay_bn],
            ["Điện thoại:", dien_thoai, "Số ĐGD phụ trách:", f"{len(ds_dgd)} ĐGD"],
            ["Ghi chú:", ghi_chu, "Mã CBTD:", ma_cb],
        ]
        tbl_info_data = []
        for r in info_rows:
            tbl_info_data.append([
                Paragraph(r[0], info_key), Paragraph(r[1], info_val),
                Paragraph(r[2], info_key), Paragraph(r[3], info_val),
            ])
        tbl_info = Table(tbl_info_data,
                         colWidths=[3*cm, 7.2*cm, 3.3*cm, 6.5*cm],
                         hAlign="LEFT")
        tbl_info.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(tbl_info)
        story.append(Spacer(1, 4))

        # --- Khối 2: Địa bàn phụ trách ---
        story.append(Paragraph("2. Địa bàn phụ trách (Điểm Giao Dịch / Thôn ấp)", h2))
        dgd_rows: list[list] = [[
            Paragraph("STT", th_style), Paragraph("Điểm Giao Dịch", th_style),
            Paragraph("Số ấp/thôn phụ trách", th_style), Paragraph("Danh sách ấp/thôn", th_style),
        ]]
        # Load dgd_map mới để đếm ấp
        dgd_map_pdf = db.doc_dgd_map() or {}
        tong_ap = 0
        for idx, dgd_name in enumerate(ds_dgd, 1):
            ap_list_pdf: list[str] = []
            for _, dgd_block in dgd_map_pdf.get(pgd, {}).items():
                if isinstance(dgd_block, dict) and dgd_name in dgd_block:
                    entry = dgd_block[dgd_name]
                    raw = entry.get("thon", []) if isinstance(entry, dict) else (entry or [])
                    ap_list_pdf = [str(a).strip() for a in raw if str(a).strip()]
                    break
            tong_ap += len(ap_list_pdf)
            dgd_rows.append([
                Paragraph(str(idx), td_style),
                Paragraph(dgd_name, td_left),
                Paragraph(str(len(ap_list_pdf)), td_style),
                Paragraph(", ".join(ap_list_pdf) or "—", td_left),
            ])
        # Tổng cộng
        dgd_rows.append([
            Paragraph("", td_style),
            Paragraph("<b>Tổng cộng</b>", td_left),
            Paragraph(f"<b>{len(ds_dgd)} ĐGD / {tong_ap} ấp</b>", td_style),
            Paragraph("", td_style),
        ])
        tbl_dgd = Table(dgd_rows, colWidths=[1.2*cm, 4.5*cm, 3.5*cm, 10.8*cm], hAlign="LEFT")
        tstyle_dgd = TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), _VBSP_GREEN),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("ROWBACKGROUNDS", (0, 1), (-2, -2), [colors.white, _VBSP_GREEN_LIGHT]),
        ])
        # Highlight dòng tổng
        tstyle_dgd.add("BACKGROUND", (0, -1), (-1, -1), _VBSP_GREEN_LIGHT)
        tstyle_dgd.add("FONTNAME", (0, -1), (-1, -1), "Times-Bold")
        tbl_dgd.setStyle(tstyle_dgd)
        story.append(tbl_dgd)
        story.append(Spacer(1, 6))

        # --- Khối 3: KPI HSTD ---
        story.append(Paragraph("3. Kết quả HSTD (từ dữ liệu mới nhất)", h2))
        if kpi_hstd:
            kpi_rows = [[
                Paragraph("Số KH", th_style), Paragraph("Số món vay", th_style),
                Paragraph("Tổng dư nợ (tỷ đồng)", th_style),
                Paragraph("Dư nợ QH (tỷ đồng)", th_style), Paragraph("Tỷ lệ QH", th_style),
            ]]
            so_kh_v = str(kpi_hstd.get("so_kh", "—"))
            so_mon_v = str(kpi_hstd.get("so_mon_vay", "—"))
            dn_v = f"{float(kpi_hstd.get('du_no_ty', 0)):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            qh_v = f"{float(kpi_hstd.get('du_no_qh_ty', 0)):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            tl_v = f"{float(kpi_hstd.get('tl_qh_pct', 0)):,.2f} %".replace(",", "X").replace(".", ",").replace("X", ".")
            kpi_rows.append([
                Paragraph(so_kh_v, td_style), Paragraph(so_mon_v, td_style),
                Paragraph(dn_v, td_right), Paragraph(qh_v, td_right),
                Paragraph(tl_v, td_right),
            ])
            tbl_kpi = Table(kpi_rows, colWidths=[3.5*cm, 3.5*cm, 4.5*cm, 4.5*cm, 4*cm], hAlign="LEFT")
            tbl_kpi.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), _VBSP_GREEN),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            story.append(tbl_kpi)
        else:
            story.append(Paragraph("(Chưa có dữ liệu HSTD cho địa bàn CBTD này)",
                                   ParagraphStyle("NN", parent=styles["Normal"],
                                                  fontName="Times-Italic", textColor=colors.grey)))
        story.append(Spacer(1, 6))

        # --- Khối 4: Tổ TK&VV ---
        story.append(Paragraph("4. Danh sách Tổ TK&VV thuộc địa bàn", h2))
        if tos_info:
            to_rows = [[
                Paragraph("STT", th_style), Paragraph("Xã", th_style),
                Paragraph("ĐGD", th_style), Paragraph("Mã Tổ", th_style),
                Paragraph("Tổ trưởng", th_style),
                Paragraph("Xếp loại", th_style), Paragraph("Điểm", th_style),
            ]]
            for i, t in enumerate(tos_info, 1):
                to_rows.append([
                    Paragraph(str(i), td_style),
                    Paragraph(str(t.get("ten_xa", "—")), td_left),
                    Paragraph(str(t.get("dgd", "—")), td_left),
                    Paragraph(str(t.get("ma_to", "—")), td_style),
                    Paragraph(str(t.get("ten_to_truong", "—")), td_left),
                    Paragraph(str(t.get("xep_loai", "—")), td_style),
                    Paragraph(str(t.get("tong_diem", "—")), td_right),
                ])
            tbl_to = Table(to_rows,
                           colWidths=[1*cm, 3*cm, 2.8*cm, 2.5*cm, 4.2*cm, 2.5*cm, 2*cm],
                           hAlign="LEFT", repeatRows=1)
            tbl_to.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), _VBSP_GREEN),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _VBSP_GREEN_LIGHT]),
            ]))
            story.append(tbl_to)
        else:
            story.append(Paragraph("(Chưa có dữ liệu Tổ TK&VV)",
                                   ParagraphStyle("NN2", parent=styles["Normal"],
                                                  fontName="Times-Italic", textColor=colors.grey)))

        story.append(Spacer(1, 18))

        # --- Khối 5: Ký tên 3 vị trí ---
        s_k1 = ParagraphStyle("k1", parent=styles["Normal"], fontName="Times-Bold",
                              fontSize=10.5, alignment=TA_CENTER)
        s_k2 = ParagraphStyle("k2", parent=styles["Normal"], fontName="Times-Italic",
                              fontSize=9.5, alignment=TA_CENTER, textColor=colors.grey,
                              leading=13)
        ky_row = [[
            Paragraph("Người lập", s_k1),
            Paragraph("Phòng Tổ chức Cán bộ", s_k1),
            Paragraph("Giám đốc Chi nhánh", s_k1),
        ]]
        ky_spacer = [[
            Paragraph("&nbsp;<br/>&nbsp;<br/>&nbsp;<br/>&nbsp;", s_k2),
            Paragraph("&nbsp;<br/>&nbsp;<br/>&nbsp;<br/>&nbsp;", s_k2),
            Paragraph("&nbsp;<br/>&nbsp;<br/>&nbsp;<br/>&nbsp;", s_k2),
        ]]
        ky_note = [[
            Paragraph("(Ký, ghi rõ họ tên)", s_k2),
            Paragraph("(Ký, họ tên, đóng dấu)", s_k2),
            Paragraph("(Ký, họ tên, đóng dấu)", s_k2),
        ]]
        combined = [ky_row[0], ky_spacer[0], ky_note[0]]
        tbl_ky = Table(combined, colWidths=[(page_w-2*_MARGIN)/3]*3, hAlign="CENTER")
        tbl_ky.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ]))
        story.append(tbl_ky)

        doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
        return buf.getvalue()
    except Exception as e:
        logger.error("_build_profile_pdf(%s) — %s", ma_cb, e, exc_info=True)
        return None


def render(tab: DeltaGenerator = None, **kwargs) -> None:
    df       = kwargs.get("df")
    df_full  = kwargs.get("df_full", df)
    role_raw = str(kwargs.get("role", "user") or "user")
    role     = normalize_role(role_raw)
    username = kwargs.get("username", "unknown")
    pgd_user = kwargs.get("pgd_user", "")  # PGD mode filter
    state = SCMStateManager()
    _kp = f"pgd_{pgd_user.strip().lower().replace(' ', '_')}_" if pgd_user else "cn_"

    ctx = tab if tab is not None else st.container()
    with ctx:
        st.subheader("👔 Quản lý Cán bộ Tín dụng (CBTD)")
        if pgd_user:
            st.caption(f"📍 **Địa bàn mode:** Chỉ xem CBTD thuộc PGD **{pgd_user}** (không chéo đơn vị).")
        else:
            st.caption("🏛️ **Chi nhánh mode:** Toàn bộ 22 đơn vị — có thể thêm/sửa/xóa CBTD toàn hệ thống.")

        # Bộ lọc Phòng giao dịch ngay từ đầu tab (chỉ CN mode)
        _pgd_filter = None
        if la_phan_he_cn(role) and not pgd_user:
            _pgd_filter = st.selectbox(
                "🏢 Phòng giao dịch",
                ["Tất cả"] + DS_PGD_ALL,
                key=f"{_kp}filter_pgd",
            )

        cbtd_data_raw: dict = doc_cbtd()
        # Filter theo PGD nếu có pgd_user (PGD mode) hoặc bộ lọc PGD (CN mode)
        if pgd_user:
            cbtd_data = {
                k: v for k, v in cbtd_data_raw.items()
                if str(v.get("pgd", "")).strip().lower() == pgd_user.strip().lower()
            }
        elif _pgd_filter and _pgd_filter != "Tất cả":
            cbtd_data = {
                k: v for k, v in cbtd_data_raw.items()
                if str(v.get("pgd", "")).strip().lower() == _pgd_filter.strip().lower()
            }
        else:
            cbtd_data = cbtd_data_raw

        dgd_map: dict = db.doc_dgd_map() or {}

        if not dgd_map:
            st.warning("⚠️ Chưa cấu hình Điểm giao dịch. "
                       "Vào tab **📍 Điểm GD** để cấu hình trước.")

        # ── Dữ liệu tính toán chung ──────────────────────────────────────────
        # Dict (pgd, dgd_name) → (ma_cb, ten_cb) — phát hiện trùng ĐGD
        dgd_da_phan: dict[tuple[str, str], tuple[str, str]] = {}
        for ma_cb, info in cbtd_data.items():
            pgd_cb = info.get("pgd", "")
            for dgd in info.get("ds_dgd", []):
                dgd_da_phan[(pgd_cb, dgd)] = (ma_cb, info.get("ho_ten", ""))

        # ── Helpers ──────────────────────────────────────────────────────────
        def _ds_dgd_cua_pgd(pgd: str) -> list[tuple[str, str]]:
            """[(xa, dgd_name)] — toàn bộ ĐGD trong PGD (từ DGD_DANH_SACH)."""
            dgd_list = lay_dgd_cho_pgd(pgd)
            return [(d["xa"], d["ten"]) for d in dgd_list]

        def _label_dgd(xa: str, dgd_name: str) -> str:
            return f"{xa} — {dgd_name}"

        def _ap_cua_dgd(pgd: str, dgd_name: str) -> list[str]:
            """List ấp của một ĐGD từ dgd_map (schema mới: dict với key 'thon')."""
            for xa, dgd_block in dgd_map.get(pgd, {}).items():
                if isinstance(dgd_block, dict) and dgd_name in dgd_block:
                    entry = dgd_block[dgd_name]
                    if isinstance(entry, dict):
                        thon_list = entry.get("thon", [])
                    elif isinstance(entry, list):
                        thon_list = entry
                    else:
                        thon_list = []
                    return [str(a).strip() for a in thon_list if str(a).strip()]
            return []

        def _label_dgd_day_du(pgd: str, xa: str, dgd_name: str) -> str:
            so_ap = len(_ap_cua_dgd(pgd, dgd_name))
            suffix = f"{so_ap} thôn/ấp" if so_ap else "chưa gom thôn"
            return f"{_label_dgd(xa, dgd_name)} · {suffix}"

        def _so_ap_cbtd(info: dict) -> int:
            pgd = info.get("pgd", "")
            ds_dgd = info.get("ds_dgd", [])
            return len(lay_ap_tu_dgd_list(pgd, ds_dgd, dgd_map))

        def _kiem_tra_trung_dgd(pgd: str, ds_dgd: list[str], bo_qua_ma: str | None = None) -> dict[str, str]:
            """Trả về {dgd_name: 'ma_cb — ten_cb'} cho ĐGD đã bị chiếm."""
            trung = {}
            for dgd_name in ds_dgd:
                found = dgd_da_phan.get((pgd, dgd_name))
                if found and found[0] != bo_qua_ma:
                    trung[dgd_name] = f"{found[0]} — {found[1]}"
            return trung

        def _fmt_tien(x: float) -> str:
            try:
                x = float(x)
                if abs(x) > 0:
                    return f"{x/1_000_000:,.0f}".replace(",","X").replace(".",",").replace("X",".")
                return "—"
            except Exception:
                return "—"

        # ════════════════════════════════════════════════════════════════════
        # 6 NHÓM NGHIỆP VỤ LEVEL-2 LAZY TABS MỚI
        # Thứ tự: Đầu tháng → Giữa tháng → Cuối tháng
        # ════════════════════════════════════════════════════════════════════
        labels_lv2 = [
            "🔎 Chi tiết theo CBTD",
            "👥 Quản lý hồ sơ CBTD",
            "📋 KHTD & Giao chỉ tiêu",
            "💰 Tác nghiệp & Đôn đốc",
            "📈 Xếp hạng & Báo cáo",
            "🛠️ Công cụ bổ trợ",
        ]

        # ── Nhóm 1: Chi tiết theo CBTD (chọn CBTD → xem chi tiết) ──────────
        def _render_g1(_c):
            with _c:
                _kp_g1 = f"{_kp}lv2_1_"
                if not cbtd_data:
                    st.warning("⚠️ Chưa có danh sách CBTD — qua **Nhóm 2** để thêm CBTD.")
                    return

                # 1) Scope guard: build danh sách CBTD cho phép
                if la_phan_he_cn(role):
                    _ds_cbtd_scope = list(cbtd_data.items())
                else:
                    _pgd_scope = pgd_user or ""
                    _ds_cbtd_scope = [
                        (m, i) for m, i in cbtd_data.items()
                        if (i.get("pgd") or "").strip() == (_pgd_scope or "").strip()
                    ]
                if not _ds_cbtd_scope:
                    st.warning("⚠️ Không có CBTD nào thuộc phạm vi được xem.")
                    return
                _ds_ma_cb = [m for m, _ in _ds_cbtd_scope]
                _label_by_ma_cb = {
                    m: f"{info.get('ho_ten', m)} — {info.get('pgd','')} [{m}]"
                    for m, info in _ds_cbtd_scope
                }
                _ma_cb = st.selectbox(
                    "Chọn Cán bộ tín dụng",
                    _ds_ma_cb, index=0,
                    format_func=lambda m: _label_by_ma_cb.get(m, str(m)),
                    key=f"{_kp_g1}chon_cb",
                )
                _info_cb = cbtd_data[_ma_cb]

                # 2) Kỳ chỉ tiêu tháng lấy từ ngày số liệu HSTD; việc hôm nay vẫn dùng ngày thật.
                _today = date.today()
                _nam, _thang, _ngay_hstd = _ky_hstd_hien_tai(df)
                if _ngay_hstd is not None:
                    st.caption(
                        f"📅 Kỳ số liệu HSTD: **tháng {_thang:02d}/{_nam}** "
                        f"(ngày số liệu {_ngay_hstd.strftime('%d/%m/%Y')}); "
                        f"công việc hôm nay tính đến {_today.strftime('%d/%m/%Y')}."
                    )
                else:
                    st.caption(
                        f"📅 HSTD chưa có ngày số liệu hợp lệ — tạm dùng kỳ {_thang:02d}/{_nam}; "
                        f"công việc hôm nay tính đến {_today.strftime('%d/%m/%Y')}."
                    )
                st.divider()

                # 3) Tính KPI tháng N via service
                _kpi_mon = lay_kpi_cbtd_theo_thang(
                    _ma_cb, int(_nam), int(_thang),
                    cbtd_data=cbtd_data, dgd_map=dgd_map, df_hstd=df,
                    scope_pgd=pgd_user if la_phan_he_pgd(role) else None,
                ) or {}
                _score = cham_diem_cbtd_thang(
                    _ma_cb, int(_nam), int(_thang),
                    cbtd_data=cbtd_data, dgd_map=dgd_map, df_hstd=df,
                    scope_pgd=pgd_user if la_phan_he_pgd(role) else None,
                ) or {}
                _top3 = top_3_viec_uu_tien(
                    _ma_cb, _today,
                    cbtd_data=cbtd_data, dgd_map=dgd_map, df_hstd=df,
                    scope_pgd=pgd_user if la_phan_he_pgd(role) else None,
                ) or []
                _df_sl_cbtd = tong_hop_hstd_theo_cbtd(
                    cbtd_data, dgd_map, df,
                    yyyy=int(_nam), mm=int(_thang),
                    scope_pgd=pgd_user if la_phan_he_pgd(role) else None,
                )

                # Tổ TK&VV theo CBTD (ghép qua ĐGD/thôn/xã) — bổ sung vào bảng số liệu
                _to_counts: dict[str, dict[str, int]] = {}
                try:
                    from services.cdtotkvv_service import tong_hop_tu_pgd_data
                    _df_cdto = tong_hop_tu_pgd_data()
                    if _df_cdto is not None and not _df_cdto.empty:
                        _to_map = lay_to_theo_cbtd(cbtd_data, dgd_map, _df_cdto) or {}
                        for _m, _tos in _to_map.items():
                            _seen = set()
                            _n_to = 0
                            _n_tot = _n_kha = _n_tb = _n_yeu = 0
                            for _t in _tos:
                                _id = f"{_t.get('ma_to') or ''}|{_t.get('ten_xa') or ''}"
                                if _id in _seen:
                                    continue
                                _seen.add(_id)
                                _xl = str(_t.get("xep_loai") or "").strip()
                                _n_to += 1
                                if _xl == "Tốt":
                                    _n_tot += 1
                                elif _xl == "Khá":
                                    _n_kha += 1
                                elif _xl == "Trung bình":
                                    _n_tb += 1
                                elif _xl == "Yếu":
                                    _n_yeu += 1
                            _to_counts[_m] = {
                                "So_to": _n_to, "To_tot": _n_tot,
                                "To_kha": _n_kha, "To_tb": _n_tb, "To_yeu": _n_yeu,
                            }
                except Exception as e:
                    logger.error("_render_g1 tong hop to tkvv: %s", e, exc_info=True)

                if _df_sl_cbtd is not None and not _df_sl_cbtd.empty:
                    for _c in ["So_to", "To_tot", "To_kha", "To_tb", "To_yeu"]:
                        _df_sl_cbtd[_c] = _df_sl_cbtd["Ma_CBTD"].map(
                            lambda m, _c=_c: _to_counts.get(m, {}).get(_c, 0)
                        )

                if not _kpi_mon.get("so_kh") and not _top3:
                    st.info(
                        f"ℹ️ Chưa tính được KPI cho **{_info_cb.get('ho_ten', _ma_cb)}** — "
                        "có thể chưa gán ĐGD hoặc file HSTD chưa được upload/tải lên."
                    )
                    _meta_warn = (_score or {}).get("meta", {}).get("warning")
                    if _meta_warn:
                        st.caption(f"Ghi chú: {_meta_warn}")

                # 4) 5 KPI card công việc hôm nay
                st.subheader("🏷️ Công việc hôm nay")
                _so_den_han = 0
                _so_nqh = 0
                for _v in _top3:
                    if _v.get("loai") == "den_han_hom_nay":
                        _so_den_han = int((_v.get("chi_tiet") or {}).get("so_hd", 0) or 0)
                    elif _v.get("loai") == "nqh_cao":
                        _so_nqh = int((_v.get("chi_tiet") or {}).get("so_mon", 0) or 0)
                _so_dgd = len(_info_cb.get("ds_dgd") or [])
                _so_ap = int(_score.get("so_ap", 0) or 0)
                _diem = float(_score.get("diem_tong", 0.0) or 0.0)
                _cols1: list[dict] = [
                    {"label": "🔴 HĐ đến hạn hôm nay", "value": fmt(_so_den_han),
                     "icon": "📅", "suffix": "hợp đồng",
                     "help": "Số hợp đồng có ngày đến hạn trả nợ = ngày hôm nay"},
                    {"label": "⚠️ HĐ NQH", "value": fmt(_so_nqh),
                     "icon": "🚨", "suffix": "hợp đồng",
                     "help": "Số hợp đồng có dư nợ nhóm 2-5 (quá hạn hoặc khả năng mất vốn)"},
                    {"label": "🗺️ Điểm GD phụ trách", "value": fmt(_so_dgd),
                     "icon": "📍", "suffix": "ĐGD",
                     "help": "Số điểm giao dịch đã phân công cho CBTD này"},
                    {"label": "🏘️ Ấp/Xã phụ trách", "value": fmt(_so_ap),
                     "icon": "🏡", "suffix": "ấp/xã",
                     "help": "Số ấp/xã suy ra từ danh sách ĐGD (gộp theo tên xã + thôn/ấp)"},
                    {"label": "⭐ Điểm tháng", "value": f"{_diem:,.1f}",
                     "icon": "🏆", "suffix": f"/100 → {_score.get('xep_loai', 'Yếu')}",
                     "help": "Điểm tổng hợp CBTD (scorecard 0-100, clamp BUGMAP C49)"},
                ]
                kpi_row(_cols1, num_columns=5)

                # 4b) Số liệu HSTD theo từng CBTD trong phạm vi đang xem
                st.subheader("📊 Số liệu theo từng CBTD")
                if _df_sl_cbtd is None or _df_sl_cbtd.empty:
                    st.info("Chưa có số liệu HSTD khớp theo CBTD trong phạm vi đang xem.")
                else:
                    _view_mode = st.radio(
                        "Phạm vi bảng",
                        ["Tất cả CBTD", "CBTD đang chọn"],
                        horizontal=True,
                        key=f"{_kp_g1}scope_bang_cbtd",
                    )
                    _df_sl_show = _df_sl_cbtd.copy()
                    if _view_mode == "CBTD đang chọn":
                        _df_sl_show = _df_sl_show[_df_sl_show["Ma_CBTD"] == _ma_cb]

                    _rename_map = {
                        "Ma_CBTD": "Mã CBTD",
                        "Ho_ten": "Họ tên",
                        "So_DGD": "Số ĐGD",
                        "So_ap": "Số ấp",
                        "So_KH": "Số KH",
                        "So_mon_vay": "Số món vay",
                        "Tong_du_no": "Tổng dư nợ (tr)",
                        "Du_no_trong_han": "Dư nợ TH (tr)",
                        "Du_no_qh": "Dư nợ QH (tr)",
                        "TL_QH_pct": "TL QH %",
                        "Cho_vay_thang": "Cho vay tháng (tr)",
                        "Thu_no_thang": "Thu nợ tháng (tr)",
                        "Cho_vay_nam": "Cho vay năm (tr)",
                        "Thu_no_nam": "Thu nợ năm (tr)",
                        "No_den_han_mon": "Món đến hạn",
                        "No_den_han_goc": "Gốc đến hạn (tr)",
                        "So_mon_3m_khd": "Món 3T KHĐ",
                        "So_mon_rui_ro": "Món rủi ro",
                        "So_KH_moi_thang": "KH mới tháng",
                        "So_giai_ngan_thang": "GN tháng",
                        "So_to": "Tổng số Tổ",
                        "To_tot": "Tổ Tốt",
                        "To_kha": "Tổ Khá",
                        "To_tb": "Tổ TB",
                        "To_yeu": "Tổ Yếu",
                        "Canh_bao": "Cảnh báo",
                    }
                    _cols_tien_disp = ["Tổng dư nợ (tr)", "Dư nợ TH (tr)", "Dư nợ QH (tr)",
                                       "Cho vay tháng (tr)", "Thu nợ tháng (tr)",
                                       "Cho vay năm (tr)", "Thu nợ năm (tr)", "Gốc đến hạn (tr)"]

                    # Tổng cộng trên dữ liệu thô
                    _tot = {}
                    for _c in _df_sl_show.columns:
                        if _c in ("Ma_CBTD", "Ho_ten", "PGD", "Canh_bao", "TL_QH_pct"):
                            continue
                        _tot[_c] = float(pd.to_numeric(_df_sl_show[_c], errors="coerce").fillna(0).sum())
                    _tot["TL_QH_pct"] = round(_tot.get("Du_no_qh", 0) / _tot.get("Tong_du_no", 0) * 100, 2) if _tot.get("Tong_du_no", 0) else 0.0
                    _tot["Ma_CBTD"] = "TỔNG CỘNG"
                    _tot["Ho_ten"] = "TỔNG CỘNG"
                    _tot["PGD"] = ""
                    _tot["Canh_bao"] = ""

                    _df_sl_all = pd.concat([_df_sl_show, pd.DataFrame([_tot])], ignore_index=True)

                    _df_sl_view = _df_sl_all.rename(columns=_rename_map)
                    for _col in _cols_tien_disp:
                        if _col in _df_sl_view.columns:
                            _df_sl_view[_col] = _df_sl_view[_col].map(_fmt_tien)
                    if "TL QH %" in _df_sl_view.columns:
                        _df_sl_view["TL QH %"] = _df_sl_view["TL QH %"].map(
                            lambda x: f"{float(x or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                        )
                    _cols_view = [
                        "Họ tên", "Số ĐGD", "Số ấp", "Số KH", "Số món vay",
                        "Tổng dư nợ (tr)", "Dư nợ TH (tr)", "Dư nợ QH (tr)", "TL QH %",
                        "Cho vay tháng (tr)", "Thu nợ tháng (tr)", "Cho vay năm (tr)", "Thu nợ năm (tr)",
                        "Món đến hạn", "Gốc đến hạn (tr)", "Món 3T KHĐ", "Món rủi ro",
                        "KH mới tháng", "GN tháng",
                        "Tổng số Tổ", "Tổ Tốt", "Tổ Khá", "Tổ TB", "Tổ Yếu",
                        "Cảnh báo",
                    ]
                    _cols_view = [c for c in _cols_view if c in _df_sl_view.columns]
                    hien_thi_dataframe_phan_trang(
                        _df_sl_view[_cols_view],
                        key=f"{_kp_g1}bang_so_lieu_cbtd",
                        height=360,
                    )

                    # Excel (thô + dòng tổng)
                    st.download_button(
                        "⬇ Tải Excel số liệu CBTD",
                        data=xuat_excel({"So_lieu_CBTD": _df_sl_all}),
                        file_name=f"So_lieu_CBTD_{int(_thang):02d}_{int(_nam)}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key=f"{_kp_g1}dl_so_lieu_cbtd",
                    )

                    # PDF (dữ liệu thô → đổi tên → quy triệu; tự thêm dòng tổng trong hàm xuất)
                    _df_pdf = _df_sl_show.rename(columns=_rename_map).copy()
                    for _col in _cols_tien_disp:
                        if _col in _df_pdf.columns:
                            _df_pdf[_col] = pd.to_numeric(_df_pdf[_col], errors="coerce").fillna(0).div(1_000_000).round(0)
                    _cols_tien_pdf = [c for c in _cols_tien_disp if c in _df_pdf.columns]
                    _cols_dem_pdf = [c for c in ["Số ĐGD", "Số ấp", "Số KH", "Số món vay",
                                                 "Món đến hạn", "Món 3T KHĐ", "Món rủi ro",
                                                 "KH mới tháng", "GN tháng",
                                                 "Tổng số Tổ", "Tổ Tốt", "Tổ Khá", "Tổ TB", "Tổ Yếu"] if c in _df_pdf.columns]
                    _cols_pct_pdf = ["TL QH %"] if "TL QH %" in _df_pdf.columns else []
                    _pdf_col1, _pdf_col2 = st.columns(2)
                    with _pdf_col1:
                        if st.button("🖨️ In PDF số liệu CBTD", key=f"{_kp_g1}btn_pdf_so_lieu", type="primary"):
                            try:
                                from components.export_pdf import xuat_pdf_co_chart
                                _pdf_bytes = xuat_pdf_co_chart(
                                    _df_pdf,
                                    tieu_de="SỐ LIỆU THEO TỪNG CBTD",
                                    nguoi_xuat=username or "system",
                                    cols_tien=_cols_tien_pdf,
                                    cols_dem=_cols_dem_pdf,
                                    cols_percent=_cols_pct_pdf,
                                    don_vi_tien="triệu đồng",
                                    prefix_file="So_lieu_CBTD",
                                    them_dong_tong=True,
                                )
                                if _pdf_bytes:
                                    state.downloads.set(
                                        "cbtd_so_lieu_pdf",
                                        _pdf_bytes,
                                        f"So_lieu_CBTD_{datetime.today().strftime('%d%m%Y')}.pdf",
                                    )
                                    db.ghi_audit(username, "xuat_pdf_so_lieu_cbtd", f"so_dong={len(_df_pdf)}")
                                    st.success("✅ Đã tạo PDF.")
                                else:
                                    st.error("❌ Lỗi tạo PDF (thiếu thư viện reportlab?).")
                            except Exception as e:
                                st.error(f"❌ Lỗi tạo PDF: {e}")
                    with _pdf_col2:
                        if state.downloads.has("cbtd_so_lieu_pdf"):
                            st.download_button(
                                "⬇ Tải file PDF",
                                data=state.downloads.get_bytes("cbtd_so_lieu_pdf"),
                                file_name=state.downloads.get_filename("cbtd_so_lieu_pdf") or "So_lieu_CBTD.pdf",
                                mime="application/pdf",
                                key=f"{_kp_g1}dl_so_lieu_pdf",
                            )

                # 5) 5 Đèn giao dịch tháng (ngưỡng xanh/vàng/đỏ VBSP)
                st.subheader("💡 Đèn giao dịch tháng")
                _tl_qh = float(_kpi_mon.get("tl_qh_pct", 0.0) or 0.0)
                _so_kh_moi = int(_kpi_mon.get("so_kh_moi_thang", 0) or 0)
                _so_gn_mon = int(_kpi_mon.get("so_giai_ngan_mon", 0) or 0)
                _dn_ty = float(_kpi_mon.get("tong_du_no_ty", 0.0) or 0.0)
                _pct_to_dat = float(_score.get("pct_to_dat", 0.0) or 0.0)
                def _mau_pct_thuan(pct: float) -> str:
                    if pct >= 85: return "🟢"
                    if pct >= 70: return "🟡"
                    return "🔴"
                def _mau_pct_nguoc(pct: float) -> str:
                    if pct < 10: return "🟢"
                    if pct < 15: return "🟡"
                    return "🔴"
                _den1 = _mau_pct_thuan(_pct_to_dat if _pct_to_dat else (100 if _tl_qh <= 3 else 75))
                _den2 = _mau_pct_nguoc(_tl_qh)
                _den3 = _mau_pct_thuan(100 if _dn_ty > 0 else 0)
                _den4 = _mau_pct_thuan(100 if _so_gn_mon >= 3 else (60 if _so_gn_mon >= 1 else 30))
                _den5 = _mau_pct_thuan(100 if _so_kh_moi >= 5 else (60 if _so_kh_moi >= 1 else 20))
                _cols2 = st.columns(5)
                _labels_den = [
                    ("% Tổ đạt CHXH",  _den1, f"{_pct_to_dat if _pct_to_dat else '—'}",  "%", "Đèn xanh ≥ 85% / Vàng 70-85 / Đỏ <70"),
                    ("NQH %",          _den2, f"{_tl_qh:,.1f}", "%", "Đèn xanh <10% / Vàng 10-15 / Đỏ >15"),
                    ("Dư nợ tháng",    _den3, f"{_dn_ty:,.1f}", "tỷ", "Dư nợ CBTD quản lý (tỷ đồng)"),
                    ("HĐ giải ngân",   _den4, fmt(_so_gn_mon),   "hợp đồng", "Số hợp đồng giải ngân trong tháng N"),
                    ("KH mới tháng",   _den5, fmt(_so_kh_moi),   "KH", "Số khách hàng mới có ngày vay trong tháng N"),
                ]
                for i, (_lb, _mau, _val, _suf, _hp) in enumerate(_labels_den):
                    with _cols2[i]:
                        delta_card(_lb, f"{_mau}  {_val}",
                                   icon="", suffix=_suf, help=_hp,
                                   key=f"{_kp_g1}den_{i}")
                st.caption(
                    "💡 Đèn giao dịch: 🟢 xanh = đạt mục tiêu · 🟡 vàng = cần theo dõi · 🔴 đỏ = phải hành động ngay"
                )

                # 6) Top 3 việc ưu tiên hôm nay
                st.subheader("🎯 Top 3 việc ưu tiên hôm nay")
                if not _top3:
                    st.info("🎉 Không có việc ưu tiên đặc biệt hôm nay — chúc CBTD làm việc hiệu quả!")
                else:
                    _stt_pri = {1: "🔝 Ưu tiên 1", 2: "⏰ Ưu tiên 2", 3: "📌 Ưu tiên 3", 99: "⚠️ Lỗi", 5: "ℹ️ Gợi ý"}
                    for idx, v in enumerate(_top3):
                        with st.container(border=True):
                            _pri = int(v.get("priority", 99))
                            lab = _stt_pri.get(_pri, f"Ưu tiên {_pri}")
                            st.markdown(f"**{lab}** — {v.get('noi_dung', '')}")
                            ct = v.get("chi_tiet") or {}
                            if ct:
                                bits = []
                                if ct.get("so_hd"): bits.append(f"{ct['so_hd']} hợp đồng")
                                if ct.get("so_mon"): bits.append(f"{ct['so_mon']} món")
                                if ct.get("ty_le_pct") is not None: bits.append(f"TL {ct['ty_le_pct']:,.1f}%")
                                if ct.get("so_tien_qh_ty"): bits.append(f"Số tiền QH {ct['so_tien_qh_ty']:,.1f} tỷ")
                                if ct.get("ma_kh_mau"): bits.append(f"KH mẫu: {ct['ma_kh_mau']}")
                                if ct.get("ngay"): bits.append(f"Ngày: {ct['ngay']}")
                                if ct.get("so_to"): bits.append(f"{ct['so_to']} tổ")
                                if bits:
                                    st.caption("  ·  ".join(bits))

                # 7) Thông tin phân công ĐGD hôm nay
                st.subheader("👥 Phân công ĐGD phụ trách")
                _ds_dgd = _info_cb.get("ds_dgd") or []
                if not _ds_dgd:
                    st.caption("⚠️ CBTD này chưa được phân công ĐGD nào — vào **Nhóm 2** để phân công.")
                else:
                    _ap_info = lay_thong_tin_dgd_theo_ten(_info_cb.get("pgd", ""), _ds_dgd, dgd_map)
                    _rows_pc = []
                    for j, _dgd in enumerate(_ds_dgd):
                        info_d = (_ap_info or {}).get(_dgd, {})
                        _rows_pc.append({
                            "STT": j + 1,
                            "Điểm giao dịch": _dgd,
                            "Xã/phường": info_d.get("xa", ""),
                            "Thôn/ấp": ", ".join(info_d.get("thon", []) or []),
                        })
                    hien_thi_dataframe_phan_trang(
                        pd.DataFrame(_rows_pc),
                        key=f"{_kp_g1}pc_dgd", height=250,
                    )

                # 8) Warning nếu có schema / fallback
                _warn_list: list[str] = []
                if _kpi_mon.get("meta", {}).get("warning"):
                    _warn_list.append(str(_kpi_mon["meta"]["warning"]))
                if _kpi_mon.get("meta", {}).get("fallback_all_time"):
                    _warn_list.append("⚠️ KPI tháng đang hiển thị toàn thời gian (thiếu cột ngày trong HSTD).")
                if _score.get("meta", {}).get("source"):
                    _warn_list.append(f"🔗 Điểm tính từ nguồn: {_score['meta']['source']}.")
                if _warn_list:
                    with st.expander("🔧 Thông tin kỹ thuật / Ghi chú", expanded=False):
                        for w in _warn_list:
                            st.markdown(f"- {w}")

        # ── Nhóm 2: Quản lý hồ sơ CBTD (toàn bộ nội dung cũ) ────────────────
        def _render_g2(_c):
            with _c:
                _kp_g2 = f"{_kp}lv2_2_"

                # ════════════════════════════════════════════════════════════════════
                # 3 SUB-TAB XEM
                # ════════════════════════════════════════════════════════════════════
                xem1, xem2, xem3 = st.tabs([
                    "📋 Danh sách CBTD",
                    "🗺️ Bản đồ ĐGD → CBTD",
                    "🔎 Chi tiết CBTD",
                ])

                # ── SUB-TAB 1: Danh sách ─────────────────────────────────────────────
                with xem1:
                    if not cbtd_data:
                        st.info("Chưa có CBTD nào. Thêm mới bên dưới.")
                    else:
                        tong_dgd = sum(len(i.get("ds_dgd", [])) for i in cbtd_data.values())
                        tong_ap  = sum(_so_ap_cbtd(i) for i in cbtd_data.values())
                        so_quatai = sum(1 for i in cbtd_data.values()
                                        if len(i.get("ds_dgd", [])) >= _NGUONG_DGD_QUATAI)
                        so_thieutai = sum(1 for i in cbtd_data.values()
                                          if 0 < len(i.get("ds_dgd", [])) <= _NGUONG_DGD_THIEUTAI)
                        c1, c2, c3, c4, c5 = st.columns(5)
                        c1.metric("Số CBTD", len(cbtd_data))
                        c2.metric("Tổng ĐGD đã phân", tong_dgd)
                        c3.metric("Tổng ấp phụ trách", tong_ap)
                        c4.metric("🔴 Quá tải (≥5 ĐGD)", so_quatai, delta=None, delta_color="inverse")
                        c5.metric("⚠️ Thiếu tải (≤1 ĐGD)", so_thieutai, delta=None, delta_color="off")

                        # Bộ lọc mạnh
                        with st.container(border=True):
                            fc1, fc2, fc3, fc4 = st.columns(4)
                            search_q = fc1.text_input("🔍 Tìm (Họ tên / SĐT / Mã CB)", "",
                                                      key=f"{_kp_g2}cbtd_search")
                            pgd_opts = ["Tất cả"] + DS_PGD_ALL
                            pgd_sel = fc2.selectbox("PGD trực thuộc", pgd_opts,
                                                    index=0, key=f"{_kp_g2}cbtd_pgd")
                            wl_opts = ["Tất cả", "✅ Cân bằng (2-4 ĐGD)", "🔴 Quá tải (≥5)", "⚠️ Thiếu tải (≤1)"]
                            wl_sel = fc3.selectbox("Workload", wl_opts, index=0,
                                                   key=f"{_kp_g2}cbtd_wl")
                            ap_opts = ["Tất cả", "≥20 ấp", "10-19 ấp", "<10 ấp"]
                            ap_sel = fc4.selectbox("Quy mô ấp", ap_opts, index=0,
                                                   key=f"{_kp_g2}cbtd_ap")

                        rows = []
                        for ma, info in cbtd_data.items():
                            ho_ten = info.get("ho_ten", "")
                            so_dgd = len(info.get("ds_dgd", []))
                            so_ap  = _so_ap_cbtd(info)
                            wl_icon, wl_label = _workload_label(so_dgd)
                            if search_q:
                                q = search_q.strip().lower()
                                haystack = " ".join([
                                    str(ma).lower(),
                                    ho_ten.lower(),
                                    str(info.get("dien_thoai", "")).lower(),
                                    str(info.get("ghi_chu", "")).lower(),
                                ])
                                if q not in haystack:
                                    continue
                            if pgd_sel != "Tất cả":
                                if info.get("pgd", "") != pgd_sel:
                                    continue
                            if wl_sel == "✅ Cân bằng (2-4 ĐGD)" and not (2 <= so_dgd <= 4):
                                continue
                            if wl_sel == "🔴 Quá tải (≥5)" and so_dgd < 5:
                                continue
                            if wl_sel == "⚠️ Thiếu tải (≤1)" and not (0 < so_dgd <= 1):
                                continue
                            if ap_sel == "≥20 ấp" and so_ap < 20:
                                continue
                            if ap_sel == "10-19 ấp" and not (10 <= so_ap <= 19):
                                continue
                            if ap_sel == "<10 ấp" and so_ap >= 10:
                                continue
                            rows.append({
                                "Mã CBTD": ma,
                                "Họ và tên": ho_ten,
                                "Chức vụ": info.get("chuc_vu", "") or "Cán bộ tín dụng",
                                "PGD": info.get("pgd", ""),
                                "Số ĐGD": so_dgd,
                                "Workload": f"{wl_icon} {wl_label}",
                                "Số ấp": so_ap,
                                "SĐT": info.get("dien_thoai", ""),
                                "Ngày bổ nhiệm": info.get("ngay_bo_nhiem", ""),
                                "Ghi chú": info.get("ghi_chu", ""),
                            })
                        if not rows:
                            st.caption("🔍 Không có CBTD phù hợp bộ lọc.")
                        else:
                            df_hien = pd.DataFrame(rows)
                            st.caption(f"📋 Tổng **{len(df_hien)}** CBTD phù hợp điều kiện.")
                            hien_thi_dataframe_phan_trang(df_hien, key=f"{_kp_g2}cbtd_ds", height=460)
                            bt1, bt2 = st.columns(2)
                            with bt1:
                                st.download_button(
                                    "📥 Xuất Excel danh sách CBTD",
                                    data=xuat_excel({
                                        "Danh_sach_CBTD": df_hien,
                                    }),
                                    file_name=f"Danh_sach_CBTD_{datetime.today().strftime('%d%m%Y')}.xlsx",
                                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                    use_container_width=True,
                                    key=f"{_kp_g2}dl_ds_cbtd_xlsx",
                                )
                            with bt2:
                                try:
                                    from components.export_pdf import xuat_pdf_co_chart
                                    _pdf_cbtd = None
                                    try:
                                        _cols_percent_cb = []
                                        if "Workload" in df_hien.columns:
                                            pass
                                        if "% Dư nợ / Tổng" in df_hien.columns:
                                            _cols_percent_cb.append("% Dư nợ / Tổng")
                                        _cols_tien_cb = [
                                            c for c in ["Tổng dư nợ", "Dư nợ QH",
                                                        "Dư nợ (triệu)", "Nợ quá hạn (triệu)",
                                                        "Tổng dư nợ (tr)", "Dư nợ TH (tr)",
                                                        "Dư nợ QH (tr)", "Dư nợ CT lớn nhất (tr)",
                                                        "GN tháng"]
                                            if c in df_hien.columns
                                        ]
                                        _cols_dem_cb = [
                                            c for c in ["Số KH", "Số món vay", "Số dòng HS",
                                                        "Số KH vay (unique)", "Số ĐGD", "Số ấp"]
                                            if c in df_hien.columns
                                        ]
                                        _pdf_cbtd = xuat_pdf_co_chart(
                                            df_hien,
                                            tieu_de="DANH SÁCH CÁN BỘ TÍN DỤNG",
                                            nguoi_xuat=username or "system",
                                            cols_tien=_cols_tien_cb,
                                            cols_dem=_cols_dem_cb,
                                            cols_percent=_cols_percent_cb,
                                            don_vi_tien="triệu đồng",
                                            them_dong_tong=False,
                                        )
                                    except Exception as _e_pdf:
                                        logger.warning("Tạo PDF Danh sách CBTD %s: %s", _kp_g2, _e_pdf, exc_info=True)
                                        _pdf_cbtd = None
                                    if _pdf_cbtd:
                                        st.download_button(
                                            "🖨️ In PDF danh sách CBTD",
                                            data=_pdf_cbtd,
                                            file_name=f"Danh_sach_CBTD_{datetime.today().strftime('%d%m%Y')}.pdf",
                                            mime="application/pdf",
                                            use_container_width=True,
                                            key=f"{_kp_g2}dl_ds_cbtd_pdf",
                                        )
                                    else:
                                        st.button("🖨️ In PDF (lỗi tạo PDF)", disabled=True,
                                                  use_container_width=True,
                                                  key=f"{_kp_g2}dl_ds_cbtd_pdf_disabled")
                                except Exception:
                                    st.button("🖨️ In PDF (cài ReportLab)", disabled=True,
                                              use_container_width=True,
                                              key=f"{_kp_g2}dl_ds_cbtd_pdf_disabled2")

                # ── SUB-TAB 2: Bản đồ ĐGD → CBTD ────────────────────────────────────
                with xem2:
                    st.caption("🗺️ **Bản đồ phân công:** Mỗi ĐGD trong HSTD thuộc đúng 1 CBTD. "
                               "ĐGD màu xám = chưa gán CBTD.")
                    pgd_opts_bd = ["Tất cả"] + DS_PGD_ALL
                    pgd_sel_bd = st.selectbox("Lọc PGD", pgd_opts_bd, index=0,
                                              key=f"{_kp_g2}cbtd_pgd_bd")
                    only_chua = st.checkbox("🔴 Chỉ xem ĐGD CHƯA gán CBTD",
                                            key=f"{_kp_g2}cbtd_only_chua")
                    rows_bd = []
                    for pgd_bd, xa_block in dgd_map.items():
                        if not isinstance(xa_block, dict):
                            continue
                        if pgd_sel_bd != "Tất cả" and pgd_bd != pgd_sel_bd:
                            continue
                        for xa_bd, dgd_block in xa_block.items():
                            if not isinstance(dgd_block, dict):
                                continue
                            for dgd_name_bd in dgd_block:
                                ap_bd = len(_ap_cua_dgd(pgd_bd, dgd_name_bd))
                                found = dgd_da_phan.get((pgd_bd, dgd_name_bd))
                                if only_chua and found:
                                    continue
                                if found:
                                    ma_cb, ten_cb = found
                                else:
                                    ma_cb, ten_cb = "", ""
                                rows_bd.append({
                                    "PGD": pgd_bd,
                                    "Xã": xa_bd,
                                    "ĐGD": dgd_name_bd,
                                    "Số ấp": ap_bd,
                                    "Mã CBTD": ma_cb,
                                    "CBTD": ten_cb,
                                    "Trạng thái": "✅ Đã gán" if ma_cb else "⚠️ CHƯA gán",
                                })
                    if not rows_bd:
                        st.info("Không có ĐGD phù hợp.")
                    else:
                        df_bd = pd.DataFrame(rows_bd)
                        _tong_dgd_phan = sum(len(i.get('ds_dgd', [])) for i in cbtd_data.values())
                        st.caption(f"🗺️ Hiển thị **{len(df_bd)}** ĐGD / **{_tong_dgd_phan}** đã gán CBTD.")
                        hien_thi_dataframe_phan_trang(df_bd, key=f"{_kp_g2}cbtd_bd_dgd", height=420)
                        bt_bd1, bt_bd2 = st.columns(2)
                        with bt_bd1:
                            st.download_button(
                                "📥 Xuất Excel bản đồ ĐGD-CBTD",
                                data=xuat_excel({
                                    "Ban_do_DGD_CBTD": df_bd,
                                }),
                                file_name=f"Ban_do_DGD_CBTD_{datetime.today().strftime('%d%m%Y')}.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                use_container_width=True,
                                key=f"{_kp_g2}dl_bd_xlsx",
                            )
                        with bt_bd2:
                            try:
                                from components.export_pdf import xuat_pdf_co_chart
                                _pdf_bd = None
                                try:
                                    _cols_dem_bd = [c for c in ["Số ấp"] if c in df_bd.columns]
                                    _pdf_bd = xuat_pdf_co_chart(
                                        df_bd,
                                        tieu_de="BẢN ĐỒ PHÂN CÔNG ĐIỂM GIAO DỊCH - CBTD",
                                        nguoi_xuat=username or "system",
                                        cols_dem=_cols_dem_bd,
                                        cols_tien=[],
                                        them_dong_tong=False,
                                    )
                                except Exception as _e_bd:
                                    logger.warning("Tạo PDF Bản đồ ĐGD-CBTD: %s", _e_bd, exc_info=True)
                                if _pdf_bd:
                                    st.download_button(
                                        "🖨️ In PDF bản đồ ĐGD-CBTD",
                                        data=_pdf_bd,
                                        file_name=f"Ban_do_DGD_CBTD_{datetime.today().strftime('%d%m%Y')}.pdf",
                                        mime="application/pdf",
                                        use_container_width=True,
                                        key=f"{_kp_g2}dl_bd_pdf",
                                    )
                                else:
                                    st.button("🖨️ In PDF (lỗi)", disabled=True, use_container_width=True,
                                              key=f"{_kp_g2}dl_bd_pdf_dis")
                            except Exception:
                                st.button("🖨️ In PDF (cài ReportLab)", disabled=True, use_container_width=True,
                                          key=f"{_kp_g2}dl_bd_pdf_dis2")

                # ── SUB-TAB 3: Chi tiết CBTD ─────────────────────────────────────────
                with xem3:
                    if not cbtd_data:
                        st.info("Chưa có CBTD nào.")
                    else:
                        chon = st.selectbox(
                            "Chọn CBTD để xem chi tiết",
                            list(cbtd_data.keys()),
                            format_func=lambda k: f"{k} — {cbtd_data[k].get('ho_ten','')} "
                                                  f"({cbtd_data[k].get('pgd','')})",
                            key=f"{_kp_g2}cbtd_chon_xem")
                        info = cbtd_data[chon]
                        ten_cb = info.get("ho_ten", "")
                        pgd_cb = info.get("pgd", "")
                        ds_dgd_cb = info.get("ds_dgd", []) or []

                        # Header 6 cột info
                        ic1, ic2, ic3, ic4, ic5, ic6 = st.columns(6)
                        ic1.metric("Chức vụ", info.get("chuc_vu", "") or "Cán bộ tín dụng")
                        ic2.metric("Số ĐGD", len(ds_dgd_cb))
                        tong_ap_ct = _so_ap_cbtd(info)
                        ic3.metric("Số ấp/phường", tong_ap_ct)
                        so_kl_cb = len(ds_dgd_cb)
                        wl_i, wl_l = _workload_label(so_kl_cb)
                        ic4.metric(f"{wl_i} Workload", wl_l)
                        ic5.metric("Ngày bổ nhiệm", info.get("ngay_bo_nhiem", "") or "—")
                        ic6.metric("SĐT", info.get("dien_thoai", "") or "—")
                        st.divider()

                        # PDF export
                        st.markdown("**📄 Hồ sơ năng lực CBTD** — Xuất PDF 1 trang (A4) gồm: "
                                    "Thông tin cá nhân · Địa bàn phụ trách · KPI HSTD · Tổ TK&VV · Khối ký tên.")

                        # Tính KPI HSTD cho CBTD này
                        kpi_hstd = None
                        tos_info = None
                        if df is not None and not df.empty and ds_dgd_cb:
                            try:
                                from services.cbtd_dia_ban_service import lay_to_theo_cbtd
                                joined = gan_cbtd_vao_df(df, {chon: info}, dgd_map)
                                joined = chuan_bi_hstd_bao_cao_dgd(joined)
                                df_cb = joined[joined["CBTD"] == chon]
                                if not df_cb.empty:
                                    so_kh = int(pd.to_numeric(df_cb[COT_MA_KH],
                                                              errors="coerce").dropna().nunique() or 0)
                                    so_mon = int(pd.to_numeric(df_cb[COT_SO_KU],
                                                               errors="coerce").dropna().nunique() or 0)
                                    tdn = float(pd.to_numeric(df_cb[COT_TONG_DU_NO],
                                                              errors="coerce").fillna(0).sum() or 0)
                                    dqh = float(pd.to_numeric(df_cb[COT_DU_NO_QH],
                                                              errors="coerce").fillna(0).sum() or 0)
                                    kpi_hstd = {
                                        "so_kh": so_kh,
                                        "so_mon_vay": so_mon,
                                        "du_no_ty": tdn / 1_000_000_000,
                                        "du_no_qh_ty": dqh / 1_000_000_000,
                                        "tl_qh_pct": (dqh / tdn * 100) if tdn > 0 else 0,
                                    }
                                    # Lấy list Tổ
                                    try:
                                        # Không có df_cdtotkvv truyền vào → None (tạm chấp nhận)
                                        to_dict = lay_to_theo_cbtd({chon: info}, dgd_map, None) or {}
                                        tos_info = to_dict.get(chon) or []
                                    except Exception:
                                        tos_info = []
                            except Exception as e:
                                logger.warning("Chi tiết CBTD KPI HSTD %s: %s", chon, e, exc_info=True)

                        col1_pdf, col2_pdf = st.columns([3, 1])
                        with col1_pdf:
                            st.caption("Tùy chọn nội dung PDF (có thể bỏ bớt nếu in ngắn gọn):")
                            co1, co2, co3, co4 = st.columns(4)
                            ck_tt = co1.checkbox("Thông tin cá nhân", True,
                                                 key=f"{_kp_g2}cbtd_ck_tt_{chon}")
                            ck_db = co2.checkbox("Địa bàn + ĐGD", True,
                                                 key=f"{_kp_g2}cbtd_ck_db_{chon}")
                            ck_kp = co3.checkbox("KPI HSTD", True,
                                                 key=f"{_kp_g2}cbtd_ck_kp_{chon}")
                            ck_to = co4.checkbox("Danh sách Tổ TK&VV", True,
                                                 key=f"{_kp_g2}cbtd_ck_to_{chon}")
                        with col2_pdf:
                            pdf_bytes = _build_profile_pdf(chon, info,
                                                           kpi_hstd if ck_kp else None,
                                                           tos_info if ck_to else None,
                                                           pgd_user_override=pgd_user or None)
                            if pdf_bytes:
                                if st.download_button(
                                    "⬇️ Tải PDF hồ sơ",
                                    data=pdf_bytes,
                                    file_name=f"CBTD_{chon}_{ten_cb}_HoSoNangLuc.pdf",
                                    mime="application/pdf",
                                    use_container_width=True,
                                    key=f"{_kp_g2}btn_export_pdf_{chon}",
                                ):
                                    db.ghi_audit(username, "xuat_pdf_cbtd",
                                                 f"Xuất PDF hồ sơ năng lực {chon} — {ten_cb}")
                            else:
                                st.button("⬇️ Tải PDF hồ sơ", disabled=True,
                                          use_container_width=True,
                                          key=f"{_kp_g2}btn_export_pdf_{chon}")
                                st.caption("⚠️ Lỗi tạo PDF — xem log.")
                        st.divider()

                        st.markdown("**1️⃣ Thông tin cá nhân & Kinh nghiệm**")
                        with st.container(border=True):
                            i1, i2 = st.columns(2)
                            i1.write(f"**Họ và tên:** {ten_cb}")
                            i1.write(f"**Chức vụ:** {info.get('chuc_vu', '') or 'Cán bộ tín dụng'}")
                            i1.write(f"**Ngày bổ nhiệm:** {info.get('ngay_bo_nhiem', '') or '—'}")
                            i1.write(f"**Số điện thoại:** {info.get('dien_thoai', '') or '—'}")
                            i2.write(f"**Đơn vị PGD trực thuộc:** {pgd_cb}")
                            i2.write(f"**Mã CBTD:** {chon}")
                            i2.write(f"**Ghi chú:** {info.get('ghi_chu', '') or '—'}")
                            i2.write(f"**Ngày cập nhật gần nhất:** {info.get('ngay_cap', '') or '—'}")

                        st.divider()
                        st.markdown("**2️⃣ Địa bàn phụ trách (Điểm Giao Dịch & Thôn/ấp)**")
                        with st.container(border=True):
                            if not ds_dgd_cb:
                                st.info("⚠️ CBTD này chưa được gán ĐGD nào. Sử dụng **Chỉnh sửa** để cập nhật.")
                            else:
                                rows_ct = []
                                for idx, dgd_name in enumerate(ds_dgd_cb, 1):
                                    ap_list = _ap_cua_dgd(pgd_cb, dgd_name)
                                    xa_name = "—"
                                    for xa_k, dgd_block in dgd_map.get(pgd_cb, {}).items():
                                        if isinstance(dgd_block, dict) and dgd_name in dgd_block:
                                            xa_name = xa_k
                                            break
                                    rows_ct.append({
                                        "STT": idx,
                                        "Xã/Phường": xa_name,
                                        "Điểm Giao Dịch": dgd_name,
                                        "Số ấp/thôn": len(ap_list),
                                        "Danh sách ấp/thôn": ", ".join(ap_list) or "—",
                                    })
                                hien_thi_dataframe_phan_trang(pd.DataFrame(rows_ct),
                                                              key=f"{_kp_g2}cbtd_ct_ap")

                        st.divider()
                        st.markdown("**3️⃣ KPI tổng hợp từ HSTD**")
                        with st.container(border=True):
                            if not kpi_hstd:
                                st.info("Chưa có dữ liệu HSTD cho CBTD này.")
                            else:
                                k1, k2, k3, k4, k5 = st.columns(5)
                                k1.metric("Số KH vay", fmt_so(kpi_hstd["so_kh"]))
                                k2.metric("Số món vay", fmt_so(kpi_hstd["so_mon_vay"]))
                                k3.metric("Tổng dư nợ (tỷ)", f"{kpi_hstd['du_no_ty']:,.2f}")
                                k4.metric("Dư nợ QH (tỷ)", f"{kpi_hstd['du_no_qh_ty']:,.2f}")
                                k5.metric("Tỷ lệ QH", f"{kpi_hstd['tl_qh_pct']:,.2f} %")
                                if kpi_hstd["tl_qh_pct"] >= 2:
                                    st.warning("⚠️ Tỷ lệ QH ≥ 2% — cần rà soát và kiểm soát.")
                                elif kpi_hstd["tl_qh_pct"] > 0:
                                    st.caption(f"ℹ️ Có {kpi_hstd['du_no_qh_ty']:,.2f} tỷ dư nợ chất vấn — đang theo dõi.")
                                else:
                                    st.success("✅ Không có dư nợ chất vấn — chất lượng tài sản tốt.")

                        st.divider()
                        st.markdown("**4️⃣ Cross-link: Tổ TK&VV thuộc địa bàn CBTD này**")
                        with st.container(border=True):
                            if not tos_info:
                                st.caption("ℹ️ Chưa load dữ liệu Tổ TK&VV (chỉ render ở Tab CDTO TKVV). "
                                           "Click vào Tab Tổ để xem chi tiết từng tổ.")
                            else:
                                st.caption(f"🏘️ Tổng **{len(tos_info)}** Tổ TK&VV thuộc địa bàn CBTD này.")
                                hien_thi_dataframe_phan_trang(pd.DataFrame(tos_info),
                                                              key=f"{_kp_g2}cbtd_ct_to_tkvv")

                st.divider()

                # ════════════════════════════════════════════════════════════════════
                # CRUD (admin + manager CN)
                # ════════════════════════════════════════════════════════════════════
                if not la_quan_ly_cn(role):
                    st.caption("🔒 Chỉ **Quản lý Chi nhánh** (admin/manager_cn) mới được thêm/sửa/xóa CBTD. "
                               "PGD/CBTD địa bàn vui lòng liên hệ phòng KH-NV.")
                else:
                    che_do = st.radio(
                        "Thao tác",
                        ["➕ Thêm mới", "✏️ Chỉnh sửa", "🔄 Sửa hàng loạt", "🪪 Đổi mã CBTD", "🗑️ Xóa"],
                        horizontal=True, key=f"{_kp_g2}cbtd_mode")

                    # ── THÊM MỚI ─────────────────────────────────────────────────────
                    if che_do == "➕ Thêm mới":
                        add_ver_key = f"{_kp_g2}cbtd_add_ver"
                        add_ver = int(st.session_state.get(add_ver_key, 0) or 0)
                        add_kp = _cbtd_add_form_prefix(_kp_g2, add_ver)
                        st.markdown("**➕ Thêm CBTD mới**")
                        c1, c2 = st.columns(2)
                        with c1:
                            ma_default = _auto_gen_ma_cb(DS_PGD_ALL[0] if not cbtd_data
                                                         else list(cbtd_data.values())[-1].get("pgd", DS_PGD_ALL[0]),
                                                         cbtd_data)
                            ma_new = st.text_input(
                                "Mã CBTD * (để trống = tự sinh)",
                                value=ma_default,
                                key=f"{add_kp}cbtd_ma_new",
                                placeholder="vd: 01, NGUYEN_VAN_A, CB_BIEN_HOA_001",
                                help="Nhập tự do, không bắt buộc tiền tố 'CB'. "
                                     "2-30 ký tự, không khoảng trắng (dùng _ thay thế). "
                                     "Để trống sẽ tự sinh dạng CB_<PGD>_<số thứ tự>.")
                            ten_new = st.text_input(
                                "Họ và tên *",
                                key=f"{add_kp}cbtd_ten_new",
                                placeholder="vd: Nguyễn Văn A")
                            chuc_vu_new = st.selectbox(
                                "Chức vụ *",
                                CHUC_VU_OPTS, index=0,
                                key=f"{add_kp}cbtd_chuc_vu_new")
                            ngay_bn_new = st.date_input(
                                "Ngày bổ nhiệm",
                                format="DD/MM/YYYY",
                                value=date.today(),
                                key=f"{add_kp}cbtd_ngay_bn_new")
                            dt_new = st.text_input(
                                "Số điện thoại",
                                placeholder="vd: 0912345678",
                                key=f"{add_kp}cbtd_dt_new")
                            gc_new = st.text_input(
                                "Ghi chú",
                                placeholder="(không bắt buộc)",
                                key=f"{add_kp}cbtd_gc_new")
                        with c2:
                            pgd_new = st.selectbox(
                                "PGD trực thuộc *",
                                DS_PGD_ALL, index=0,
                                key=f"{add_kp}cbtd_pgd_new")
                            dgd_opts_new = _ds_dgd_cua_pgd(pgd_new)
                            if not dgd_opts_new:
                                st.warning(f"PGD **{pgd_new}** chưa cấu hình ĐGD.")
                                dgd_sel_new = []
                            else:
                                labels_new = [_label_dgd_day_du(pgd_new, xa, d) for xa, d in dgd_opts_new]
                                label_to_dgd_new = {
                                    _label_dgd_day_du(pgd_new, xa, d): d
                                    for xa, d in dgd_opts_new
                                }
                                sel_labels = st.multiselect(
                                    "ĐGD phụ trách * (chọn nhiều cùng lúc)",
                                    labels_new,
                                    help="1 CBTD phụ trách 2–4 ĐGD trong cùng PGD — chọn hết rồi mới LƯU 1 lần",
                                    key=f"{add_kp}cbtd_dgd_new")
                                dgd_sel_new = [label_to_dgd_new[lbl] for lbl in sel_labels if lbl in label_to_dgd_new]

                                if dgd_sel_new:
                                    trung = _kiem_tra_trung_dgd(pgd_new, dgd_sel_new)
                                    if trung:
                                        for d, cb in trung.items():
                                            st.error(f"⛔ **{d}** đã thuộc CBTD **{cb}**")
                                    else:
                                        # Preview ấp
                                        tong_ap_new = lay_ap_tu_dgd_list(pgd_new, dgd_sel_new, dgd_map)
                                        wl_i, wl_t = _workload_label(len(dgd_sel_new))
                                        st.success(f"✅ {len(dgd_sel_new)} ĐGD hợp lệ — Workload: {wl_i} {wl_t} — "
                                                   f"{len(tong_ap_new)} ấp/thôn phụ trách")
                                        with st.expander("Xem danh sách ấp"):
                                            for xa_p, ap_p in sorted(tong_ap_new):
                                                st.caption(f"• {xa_p} / {ap_p}")
                                else:
                                    st.caption("👆 Chọn ít nhất 1 ĐGD (bấm chọn nhiều ĐGD cùng lúc rồi lưu 1 lần)")

                        if st.button("💾 LƯU CBTD MỚI", type="primary", key=f"{_kp_g2}btn_them_cbtd"):
                            err = []
                            # Mã CBTD
                            ma_val = (ma_new or "").strip().upper()
                            ok_ma, msg_ma = _validate_ma_cb(ma_val if ma_val else None, cbtd_data)
                            if not ok_ma:
                                err.append(msg_ma)
                            # Họ tên
                            if not ten_new.strip():
                                err.append("Thiếu Họ tên (không được trống)")
                            if len(ten_new.strip()) < 3:
                                err.append("Họ tên quá ngắn (≥3 ký tự)")
                            # Điện thoại
                            ok_dt, msg_dt = _validate_dien_thoai(dt_new)
                            if not ok_dt:
                                err.append(msg_dt)
                            # ĐGD
                            if not dgd_sel_new:
                                err.append("Chọn ít nhất 1 ĐGD")
                            # Trùng ĐGD
                            trung_luu = _kiem_tra_trung_dgd(pgd_new, dgd_sel_new)
                            if trung_luu:
                                for d, cb in trung_luu.items():
                                    err.append(f"ĐGD **{d}** đã thuộc CBTD **{cb}**")
                            # Show errors or save
                            if err:
                                for e in err:
                                    st.error(f"❌ {e}")
                            else:
                                ma_key = ma_val
                                cbtd_data[ma_key] = {
                                    "ho_ten":         ten_new.strip(),
                                    "chuc_vu":        chuc_vu_new,
                                    "ngay_bo_nhiem":  _date_to_ddmmyyyy(ngay_bn_new),
                                    "pgd":            pgd_new,
                                    "ds_dgd":         dgd_sel_new,
                                    "dien_thoai":     dt_new.strip(),
                                    "ghi_chu":        gc_new.strip(),
                                    "ngay_cap":       datetime.today().strftime("%d/%m/%Y %H:%M"),
                                }
                                luu_cbtd(cbtd_data)
                                db.ghi_audit(username, "luu_cbtd",
                                             f"Thêm {ma_key} — {ten_new.strip()} / {chuc_vu_new} "
                                             f"({pgd_new}, {len(dgd_sel_new)} ĐGD)")
                                st.cache_data.clear()
                                st.session_state[add_ver_key] = add_ver + 1
                                st.success(f"✅ Đã thêm **{ma_key}** — {ten_new.strip()} ({chuc_vu_new})")
                                st.rerun()

                    # ── CHỈNH SỬA (TÌM NHANH + LỌC) ────────────────────────────────
                    elif che_do == "✏️ Chỉnh sửa":
                        st.markdown("**✏️ Chỉnh sửa CBTD**")
                        if not cbtd_data:
                            st.info("Chưa có CBTD nào.")
                        else:
                            st.caption("💡 Tìm nhanh bằng bộ lọc dưới đây → Kết quả hiển thị ở bảng → chọn CBTD trong danh sách đã lọc")
                            f1, f2, f3 = st.columns(3)
                            with f1:
                                kw_sua = st.text_input("🔎 Tìm (Mã / Họ tên / SĐT / Ghi chú)", "",
                                                       key=f"{_kp_g2}cbtd_kw_sua")
                            with f2:
                                pgd_loc = st.selectbox("Lọc theo PGD", ["— Tất cả —"] + list(DS_PGD_ALL),
                                                       index=0, key=f"{_kp_g2}cbtd_pgd_loc_sua")
                            with f3:
                                cv_loc = st.selectbox("Lọc theo Chức vụ", ["— Tất cả —"] + list(CHUC_VU_OPTS),
                                                      index=0, key=f"{_kp_g2}cbtd_cv_loc_sua")

                            def _loc_cbtd(data: dict, kw: str, pgd: str, cv: str) -> list[str]:
                                keys = []
                                kw_lc = kw.strip().lower()
                                for k, info in data.items():
                                    if pgd != "— Tất cả —" and info.get("pgd", "") != pgd:
                                        continue
                                    cv_inf = info.get("chuc_vu", "") or "Cán bộ tín dụng"
                                    if cv != "— Tất cả —" and cv_inf != cv:
                                        continue
                                    if kw_lc:
                                        haystack = " ".join([
                                            k.lower(),
                                            str(info.get("ho_ten", "")).lower(),
                                            str(info.get("dien_thoai", "")).lower(),
                                            str(info.get("ghi_chu", "")).lower(),
                                        ])
                                        if kw_lc not in haystack:
                                            continue
                                    keys.append(k)
                                return keys

                            keys_loc = _loc_cbtd(cbtd_data, kw_sua, pgd_loc, cv_loc)
                            if not keys_loc:
                                st.warning("⚠️ Không có CBTD trùng điều kiện lọc.")
                            else:
                                rows_locthu = []
                                for k in keys_loc:
                                    info = cbtd_data[k]
                                    rows_locthu.append({
                                        "Mã CBTD": k,
                                        "Họ và tên": info.get("ho_ten", ""),
                                        "Chức vụ": info.get("chuc_vu", "") or "Cán bộ tín dụng",
                                        "PGD": info.get("pgd", ""),
                                        "SĐT": info.get("dien_thoai", ""),
                                        "Số ĐGD": len(info.get("ds_dgd", [])),
                                        "Ghi chú": info.get("ghi_chu", ""),
                                        "Tự tạo": "✅" if info.get("auto_generated") else "",
                                    })
                                st.dataframe(pd.DataFrame(rows_locthu), use_container_width=True, hide_index=True,
                                             key=f"{_kp_g2}cbtd_bang_loc_sua")

                                chon_sua = st.selectbox(
                                    "Chọn CBTD để sửa (danh sách đã lọc)",
                                    keys_loc,
                                    format_func=lambda k: f"{k} — {cbtd_data[k]['ho_ten']} "
                                                          f"/ {cbtd_data[k].get('pgd','?')} "
                                                          f"({len(cbtd_data[k].get('ds_dgd',[]))} ĐGD)",
                                    key=f"{_kp_g2}cbtd_chon_sua")
                                info_cu = cbtd_data[chon_sua]
                                edit_kp = f"{_kp_g2}edit_{_pgd_slug_ma(chon_sua)}_"
                                chuc_vu_cu = info_cu.get("chuc_vu", "") or "Cán bộ tín dụng"
                                ngay_bn_cu = _ddmmyyyy_to_date(info_cu.get("ngay_bo_nhiem", "")) or date.today()

                                c1, c2 = st.columns(2)
                                with c1:
                                    ten_sua = st.text_input("Họ và tên *",
                                        value=info_cu.get("ho_ten",""), key=f"{edit_kp}cbtd_ten_sua")
                                    cv_idx_sua = CHUC_VU_OPTS.index(chuc_vu_cu) if chuc_vu_cu in CHUC_VU_OPTS else 0
                                    chuc_vu_sua = st.selectbox("Chức vụ *", CHUC_VU_OPTS, index=cv_idx_sua,
                                                               key=f"{edit_kp}cbtd_chuc_vu_sua")
                                    ngay_bn_sua = st.date_input("Ngày bổ nhiệm", format="DD/MM/YYYY",
                                                                value=ngay_bn_cu,
                                                                key=f"{edit_kp}cbtd_ngay_bn_sua")
                                    dt_sua  = st.text_input("Số điện thoại",
                                        value=info_cu.get("dien_thoai",""), key=f"{edit_kp}cbtd_dt_sua",
                                        placeholder="vd: 0912345678")
                                    gc_sua  = st.text_input("Ghi chú",
                                        value=info_cu.get("ghi_chu",""), key=f"{edit_kp}cbtd_gc_sua")
                                    pgd_idx = DS_PGD_ALL.index(info_cu["pgd"]) if info_cu.get("pgd") in DS_PGD_ALL else 0
                                    pgd_sua = st.selectbox("PGD trực thuộc *",
                                        DS_PGD_ALL, index=pgd_idx, key=f"{edit_kp}cbtd_pgd_sua")

                                with c2:
                                    dgd_opts_sua = _ds_dgd_cua_pgd(pgd_sua)
                                    if not dgd_opts_sua:
                                        st.warning(f"PGD **{pgd_sua}** chưa cấu hình ĐGD.")
                                        dgd_sel_sua = []
                                    else:
                                        labels_sua = [_label_dgd_day_du(pgd_sua, xa, d) for xa, d in dgd_opts_sua]
                                        label_to_dgd_sua = {
                                            _label_dgd_day_du(pgd_sua, xa, d): d
                                            for xa, d in dgd_opts_sua
                                        }
                                        ds_dgd_cu  = info_cu.get("ds_dgd", []) if pgd_sua == info_cu.get("pgd") else []
                                        default_labels = [_label_dgd_day_du(pgd_sua, xa, d) for xa, d in dgd_opts_sua
                                                          if d in ds_dgd_cu]
                                        sel_labels_sua = st.multiselect(
                                            "ĐGD phụ trách *",
                                            labels_sua,
                                            default=default_labels,
                                            key=f"{edit_kp}cbtd_dgd_sua_{_pgd_slug_ma(pgd_sua)}")
                                        dgd_sel_sua = [label_to_dgd_sua[lbl] for lbl in sel_labels_sua if lbl in label_to_dgd_sua]

                                        if dgd_sel_sua:
                                            trung_sua = _kiem_tra_trung_dgd(pgd_sua, dgd_sel_sua, bo_qua_ma=chon_sua)
                                            if trung_sua:
                                                for d, cb in trung_sua.items():
                                                    st.error(f"⛔ **{d}** đang thuộc CBTD **{cb}**")
                                            else:
                                                tong_ap_sua = lay_ap_tu_dgd_list(pgd_sua, dgd_sel_sua, dgd_map)
                                                wl_i_s, wl_t_s = _workload_label(len(dgd_sel_sua))
                                                st.info(f"✅ {len(dgd_sel_sua)} ĐGD — WL: {wl_i_s} {wl_t_s} — "
                                                        f"{len(tong_ap_sua)} ấp/thôn")
                                        else:
                                            st.caption("👆 Chọn ít nhất 1 ĐGD")

                                if st.button("💾 Lưu thay đổi", type="primary", key=f"{_kp_g2}btn_luu_sua"):
                                    err_sua = []
                                    if not ten_sua.strip():
                                        err_sua.append("Họ tên không được để trống")
                                    if len(ten_sua.strip()) < 3 and ten_sua.strip():
                                        err_sua.append("Họ tên quá ngắn (≥3 ký tự)")
                                    ok_dt_s, msg_dt_s = _validate_dien_thoai(dt_sua)
                                    if not ok_dt_s:
                                        err_sua.append(msg_dt_s)
                                    if not dgd_sel_sua:
                                        err_sua.append("Chọn ít nhất 1 ĐGD")
                                    trung_luu_sua = _kiem_tra_trung_dgd(pgd_sua, dgd_sel_sua, bo_qua_ma=chon_sua)
                                    if trung_luu_sua:
                                        for d, cb in trung_luu_sua.items():
                                            err_sua.append(f"ĐGD **{d}** đang thuộc CBTD **{cb}**")
                                    if err_sua:
                                        for e in err_sua:
                                            st.error(f"❌ {e}")
                                    else:
                                        ngay_cap_cu = info_cu.get("ngay_cap", "")
                                        cbtd_data[chon_sua] = {
                                            "ho_ten":         ten_sua.strip(),
                                            "chuc_vu":        chuc_vu_sua,
                                            "ngay_bo_nhiem":  _date_to_ddmmyyyy(ngay_bn_sua),
                                            "pgd":            pgd_sua,
                                            "ds_dgd":         dgd_sel_sua,
                                            "dien_thoai":     dt_sua.strip(),
                                            "ghi_chu":        gc_sua.strip(),
                                            "ngay_cap":       ngay_cap_cu or datetime.today().strftime("%d/%m/%Y %H:%M"),
                                            "auto_generated": info_cu.get("auto_generated", False),
                                            "created_by":     info_cu.get("created_by", username),
                                        }
                                        luu_cbtd(cbtd_data)
                                        db.ghi_audit(username, "luu_cbtd",
                                                     f"Sửa {chon_sua} — {pgd_sua}, {chuc_vu_sua}, "
                                                     f"{len(dgd_sel_sua)} ĐGD")
                                        st.cache_data.clear()
                                        st.success(f"✅ Đã cập nhật **{chon_sua}**")
                                        st.rerun()

                    # ── SỬA HÀNG LOẠT (BATCH EDIT) ─────────────────────────────────
                    elif che_do == "🔄 Sửa hàng loạt":
                        st.markdown("**🔄 Sửa hàng loạt nhiều CBTD cùng lúc**")
                        if not cbtd_data:
                            st.info("Chưa có CBTD nào.")
                        else:
                            st.caption("💡 Bước 1: Lọc CBTD cần sửa → Bước 2: Tick cột [Sửa?] → Bước 3: Điền giá trị thay đổi → Bước 4: Lưu tất cả 1 lượt")
                            bf1, bf2, bf3, bf4 = st.columns(4)
                            with bf1:
                                kw_b = st.text_input("🔎 Tìm nhanh (Mã/Tên/SĐT/Ghi chú)", "",
                                                     key=f"{_kp_g2}cbtd_kw_batch")
                            with bf2:
                                pgd_b = st.selectbox("Lọc PGD", ["— Tất cả —"] + list(DS_PGD_ALL),
                                                     index=0, key=f"{_kp_g2}cbtd_pgd_batch")
                            with bf3:
                                cv_b = st.selectbox("Lọc Chức vụ", ["— Tất cả —"] + list(CHUC_VU_OPTS),
                                                    index=0, key=f"{_kp_g2}cbtd_cv_batch")
                            with bf4:
                                flag_b = st.selectbox("Lọc Dấu hiệu",
                                    ["— Tất cả —", "Chỉ CBTD tự tạo", "SĐT trống", "Ghi chú 'Tự tạo từ Điểm GD'"],
                                    index=0, key=f"{_kp_g2}cbtd_flag_batch")

                            def _loc_batch(data: dict) -> list[str]:
                                keys = []
                                kw_lc = kw_b.strip().lower()
                                for k, info in data.items():
                                    if pgd_b != "— Tất cả —" and info.get("pgd", "") != pgd_b:
                                        continue
                                    cv_inf = info.get("chuc_vu", "") or "Cán bộ tín dụng"
                                    if cv_b != "— Tất cả —" and cv_inf != cv_b:
                                        continue
                                    if flag_b == "Chỉ CBTD tự tạo" and not info.get("auto_generated"):
                                        continue
                                    if flag_b == "SĐT trống" and (info.get("dien_thoai", "") or "") != "":
                                        continue
                                    if flag_b == "Ghi chú 'Tự tạo từ Điểm GD'" and \
                                       "Tự tạo từ Điểm GD" not in str(info.get("ghi_chu", "")):
                                        continue
                                    if kw_lc:
                                        haystack = " ".join([
                                            k.lower(),
                                            str(info.get("ho_ten", "")).lower(),
                                            str(info.get("dien_thoai", "")).lower(),
                                            str(info.get("ghi_chu", "")).lower(),
                                        ])
                                        if kw_lc not in haystack:
                                            continue
                                    keys.append(k)
                                return keys

                            keys_b = _loc_batch(cbtd_data)
                            if not keys_b:
                                st.warning("⚠️ Không có CBTD trùng điều kiện.")
                            else:
                                rows_b = []
                                for k in keys_b:
                                    info = cbtd_data[k]
                                    rows_b.append({
                                        "Sửa?": False,
                                        "Mã CBTD": k,
                                        "Họ và tên": info.get("ho_ten", ""),
                                        "Chức vụ": info.get("chuc_vu", "") or "Cán bộ tín dụng",
                                        "PGD": info.get("pgd", ""),
                                        "SĐT": info.get("dien_thoai", ""),
                                        "Số ĐGD": len(info.get("ds_dgd", [])),
                                        "Ghi chú": info.get("ghi_chu", ""),
                                        "Tự tạo": "✅" if info.get("auto_generated") else "",
                                    })
                                df_bc_raw = pd.DataFrame(rows_b)
                                df_bc_edit = st.data_editor(
                                    df_bc_raw,
                                    use_container_width=True,
                                    hide_index=True,
                                    disabled=[c for c in df_bc_raw.columns if c != "Sửa?"],
                                    column_config={"Sửa?": st.column_config.CheckboxColumn("Sửa?", default=False)},
                                    key=f"{_kp_g2}cbtd_bang_batch",
                                )
                                sua_mask = df_bc_edit["Sửa?"].fillna(False).astype(bool)
                                ma_chon_batch = list(df_bc_edit.loc[sua_mask, "Mã CBTD"].unique())
                                st.caption(f"✅ Đã chọn **{len(ma_chon_batch)}** CBTD")

                                st.markdown("**🛠️ Giá trị thay đổi áp dụng cho tất cả CBTD đã chọn**")
                                bc1, bc2, bc3 = st.columns(3)
                                with bc1:
                                    ap_ten = st.text_input("Đổi Họ tên mới (bỏ trống = không đổi)", "",
                                                           key=f"{_kp_g2}cbtd_bc_ten")
                                    ap_cv_idx = st.selectbox("Đổi Chức vụ (— Không đổi —)",
                                        ["— Không đổi —"] + list(CHUC_VU_OPTS), index=0,
                                        key=f"{_kp_g2}cbtd_bc_cv")
                                    ap_dt = st.text_input("Đổi SĐT mới (bỏ trống = không đổi)", "",
                                                          key=f"{_kp_g2}cbtd_bc_dt",
                                                          placeholder="vd: 0912345678")
                                with bc2:
                                    ap_gc_append = st.text_input("Nối đuôi Ghi chú (thêm vào cuối)", "",
                                                                  key=f"{_kp_g2}cbtd_bc_gc_append",
                                                                  placeholder="vd: ; cập nhật 06/09")
                                    ap_xoa_auto = st.checkbox("Bỏ cờ [Tự tạo] (không còn là CBTD tự tạo)",
                                                               False, key=f"{_kp_g2}cbtd_bc_xoa_auto")
                                with bc3:
                                    st.caption("")
                                    st.caption("")
                                    bc_xn = st.checkbox(f"✅ Xác nhận áp dụng thay đổi cho {len(ma_chon_batch)} CBTD",
                                                        False, key=f"{_kp_g2}cbtd_bc_xn")

                                if st.button("💾 Lưu hàng loạt", type="primary",
                                             disabled=not bc_xn or not ma_chon_batch,
                                             key=f"{_kp_g2}btn_luu_batch"):
                                    ok_all = True
                                    da_sua = 0
                                    loi = []
                                    cbtd_draft = dict(cbtd_data)
                                    for ma in ma_chon_batch:
                                        if ma not in cbtd_data:
                                            continue
                                        info = cbtd_data[ma]
                                        info_moi = dict(info)
                                        if ap_ten.strip():
                                            if len(ap_ten.strip()) < 3:
                                                loi.append(f"{ma}: Họ tên quá ngắn")
                                                ok_all = False
                                                continue
                                            info_moi["ho_ten"] = ap_ten.strip()
                                        if ap_cv_idx != "— Không đổi —":
                                            info_moi["chuc_vu"] = ap_cv_idx
                                        if ap_dt.strip():
                                            okd, msgd = _validate_dien_thoai(ap_dt)
                                            if not okd:
                                                loi.append(f"{ma}: {msgd}")
                                                ok_all = False
                                                continue
                                            info_moi["dien_thoai"] = ap_dt.strip()
                                        elif "dien_thoai" not in info_moi:
                                            info_moi["dien_thoai"] = ""
                                        if ap_gc_append:
                                            gc_cu = info.get("ghi_chu", "") or ""
                                            info_moi["ghi_chu"] = (gc_cu + ap_gc_append).strip()
                                        if ap_xoa_auto:
                                            info_moi["auto_generated"] = False
                                        if "created_by" not in info_moi:
                                            info_moi["created_by"] = username
                                        cbtd_draft[ma] = info_moi
                                        da_sua += 1
                                    if not ok_all:
                                        for e in loi:
                                            st.error(f"❌ {e}")
                                        st.error("⛔ Không lưu gì cả do có lỗi validate — sửa lại rồi thử lại.")
                                    elif da_sua > 0:
                                        cbtd_data.clear()
                                        cbtd_data.update(cbtd_draft)
                                        luu_cbtd(cbtd_data)
                                        db.ghi_audit(username, "batch_update_cbtd",
                                                     f"Sửa hàng loạt {da_sua} CBTD: "
                                                     f"{'đổi tên ' if ap_ten.strip() else ''}"
                                                     f"{'đổi CV ' if ap_cv_idx != '— Không đổi —' else ''}"
                                                     f"{'đổi SĐT ' if ap_dt.strip() else ''}"
                                                     f"{'nối GC ' if ap_gc_append else ''}"
                                                     f"{'xóa auto_flag' if ap_xoa_auto else ''}")
                                        st.cache_data.clear()
                                        st.success(f"✅ Đã cập nhật **{da_sua}** CBTD")
                                        st.rerun()

                    # ── ĐỔI MÃ CBTD (RENAME KEY) ───────────────────────────────────
                    elif che_do == "🪪 Đổi mã CBTD":
                        st.markdown("**🪪 Đổi mã CBTD (sửa khi gõ nhầm mã)**")
                        if not cbtd_data:
                            st.info("Chưa có CBTD nào.")
                        else:
                            st.warning("⚠️ Đổi mã CBTD sẽ thay đổi key gốc — thông tin (tên, ĐGD, SĐT…) được giữ nguyên 100%.")
                            df1, df2 = st.columns(2)
                            with df1:
                                ma_cu = st.selectbox(
                                    "Chọn Mã CBTD cũ",
                                    list(cbtd_data.keys()),
                                    format_func=lambda k: f"{k} — {cbtd_data[k]['ho_ten']} "
                                                          f"/ {cbtd_data[k].get('pgd','?')}",
                                    key=f"{_kp_g2}cbtd_ma_cu")
                            info_cu = cbtd_data[ma_cu]
                            with df2:
                                ma_moi_raw = st.text_input("Nhập Mã CBTD mới (tự do, không khoảng trắng)",
                                    value=ma_cu,
                                    key=f"{_kp_g2}cbtd_ma_moi",
                                    placeholder="vd: 01, NGUYEN_VAN_A, CB_BINH_DUONG")
                            ma_moi_norm = ma_moi_raw.strip().upper()

                            col_info1, col_info2 = st.columns(2)
                            with col_info1:
                                st.info(
                                    f"**Mã cũ:** `{ma_cu}`\n\n"
                                    f"**Họ tên:** {info_cu.get('ho_ten','')}\n\n"
                                    f"**PGD:** {info_cu.get('pgd','')} | ĐGD: {len(info_cu.get('ds_dgd',[]))}"
                                )
                            with col_info2:
                                ok_ma, msg_ma = _validate_ma_cb(ma_moi_norm, cbtd_data, bo_qua_ma=ma_cu)
                                if ma_moi_norm == ma_cu:
                                    st.caption("Mã mới giống mã cũ — chưa có thay đổi.")
                                elif not ok_ma:
                                    st.error(f"❌ {msg_ma}")
                                else:
                                    st.success(f"✅ Mã mới hợp lệ: `{ma_moi_norm}`")

                            xn_doi = st.checkbox(
                                f"Xác nhận đổi mã: `{ma_cu}` → `{ma_moi_norm}` (thông tin khác giữ nguyên)",
                                False, key=f"{_kp_g2}cbtd_xn_doi")
                            disabled_btn = (not xn_doi) or (ma_moi_norm == ma_cu) or (not ok_ma)

                            if st.button("🪪 Thực hiện đổi mã", type="primary",
                                         disabled=disabled_btn, key=f"{_kp_g2}btn_doi_ma"):
                                if ma_moi_norm not in cbtd_data:
                                    info_moi = dict(info_cu)
                                    info_moi["ngay_cap"] = info_cu.get("ngay_cap", "") or \
                                                           datetime.today().strftime("%d/%m/%Y %H:%M")
                                    if "created_by" not in info_moi:
                                        info_moi["created_by"] = username
                                    cbtd_data[ma_moi_norm] = info_moi
                                    del cbtd_data[ma_cu]
                                    luu_cbtd(cbtd_data)
                                    db.ghi_audit(username, "rename_cbtd",
                                                 f"Đổi mã {ma_cu} → {ma_moi_norm} | "
                                                 f"{info_cu.get('ho_ten','')} | "
                                                 f"{info_cu.get('pgd','')}")
                                    st.cache_data.clear()
                                    st.success(f"✅ Đã đổi mã: **`{ma_cu}`** → **`{ma_moi_norm}`**")
                                    st.rerun()
                                else:
                                    st.error(f"⛔ Mã mới `{ma_moi_norm}` đã tồn tại (trùng key).")

                    # ── XÓA ─────────────────────────────────────────────────────────
                    elif che_do == "🗑️ Xóa":
                        st.markdown("**🗑️ Xóa CBTD**")
                        if not cbtd_data:
                            st.info("Chưa có CBTD nào.")
                        else:
                            chon_xoa = st.selectbox(
                                "Chọn CBTD",
                                list(cbtd_data.keys()),
                                format_func=lambda k: f"{k} — {cbtd_data[k]['ho_ten']} "
                                                      f"/ {cbtd_data[k].get('pgd','?')}",
                                key=f"{_kp_g2}cbtd_chon_xoa")
                            info_xoa = cbtd_data[chon_xoa]
                            st.warning(
                                f"⚠️ Sắp xóa: **{chon_xoa}** — {info_xoa['ho_ten']}\n\n"
                                f"PGD: {info_xoa.get('pgd','?')} | "
                                f"ĐGD: {', '.join(info_xoa.get('ds_dgd',[]))}"
                            )
                            xn = st.checkbox("Xác nhận xóa", key=f"{_kp_g2}cbtd_xn_xoa")
                            if st.button("🗑️ Xóa", type="primary",
                                         disabled=not xn, key=f"{_kp_g2}btn_xoa_cbtd"):
                                del cbtd_data[chon_xoa]
                                luu_cbtd(cbtd_data)
                                db.ghi_audit(username, "luu_cbtd", f"Xóa {chon_xoa}")
                                st.cache_data.clear()
                                st.success(f"✅ Đã xóa **{chon_xoa}**")
                                st.rerun()

                st.divider()

                # ════════════════════════════════════════════════════════════════════
                # BÁO CÁO DƯ NỢ THEO CBTD
                # ════════════════════════════════════════════════════════════════════
                cbtd_co_dgd = {ma: info for ma, info in cbtd_data.items()
                               if info.get("pgd") and info.get("ds_dgd")}
                if not cbtd_co_dgd:
                    if cbtd_data:
                        st.info("ℹ️ Chưa có CBTD nào được gán ĐGD. "
                                "Dùng **Chỉnh sửa** để cập nhật.")
                    return

                st.markdown("**📊 Tổng hợp dư nợ theo CBTD**")

                if df is None or df.empty:
                    st.warning("Chưa có dữ liệu HSTD.")
                    return

                # Join toàn bộ df với cbtd rồi chuẩn hóa theo báo cáo Điểm GD:
                # khử trùng Số khế ước, chỉ tách riêng NOXH vay trực tiếp.
                df_joined_all_raw = gan_cbtd_vao_df(df, cbtd_co_dgd, dgd_map)
                df_joined_all = chuan_bi_hstd_bao_cao_dgd(
                    df_joined_all_raw, loai_noxh_truc_tiep=False
                )
                _mask_noxh_vt = mask_noxh_truc_tiep(df_joined_all)

                # Phạm vi đối chiếu = các PGD đã có CBTD được gán ĐGD. Ngoài tập này
                # chưa cấu hình địa bàn nên không thể quy dư nợ cho CBTD nào.
                _ds_pgd_cbtd = sorted({
                    str(_i.get("pgd", "")).strip()
                    for _i in cbtd_co_dgd.values() if _i.get("pgd")
                })
                if COT_TEN_PGD in df_joined_all.columns and _ds_pgd_cbtd:
                    _pgd_norm = (
                        df_joined_all[COT_TEN_PGD].astype("string").str.strip().str.casefold()
                    )
                    _mask_scope = _pgd_norm.isin(
                        {p.casefold() for p in _ds_pgd_cbtd}
                    ).fillna(False)
                else:
                    _mask_scope = pd.Series(True, index=df_joined_all.index)

                df_joined = df_joined_all[~_mask_noxh_vt]
                _scope_joined = _mask_scope.reindex(df_joined.index).fillna(False)
                _df_vt = df_joined_all[_mask_noxh_vt & _mask_scope]
                _df_chua_pc = df_joined[df_joined["CBTD"].isna() & _scope_joined]
                _df_scope = df_joined[_scope_joined]

                def _agg_dong(d: pd.DataFrame) -> tuple[int, int, float, float]:
                    """(số KH, số món, tổng dư nợ, dư nợ QH) của một tập dòng."""
                    if d is None or d.empty:
                        return 0, 0, 0.0, 0.0
                    _kh = int(d[COT_MA_KH].nunique()) if COT_MA_KH in d.columns else 0
                    _mon = int(d[COT_SO_KU].nunique()) if COT_SO_KU in d.columns else 0
                    _tdn = (
                        float(pd.to_numeric(d[COT_TONG_DU_NO], errors="coerce").fillna(0).sum())
                        if COT_TONG_DU_NO in d.columns else 0.0
                    )
                    _dqh = (
                        float(pd.to_numeric(d[COT_DU_NO_QH], errors="coerce").fillna(0).sum())
                        if COT_DU_NO_QH in d.columns else 0.0
                    )
                    return _kh, _mon, _tdn, _dqh

                rows_bc = []
                _t_so_dgd = 0
                _t_so_ap = 0
                for ma, info in cbtd_co_dgd.items():
                    df_cb = df_joined[df_joined["CBTD"] == ma]
                    if df_cb.empty:
                        continue
                    so_kh, so_mon, tdn, dqh = _agg_dong(df_cb)
                    so_dgd = len(info.get("ds_dgd", []))
                    so_ap = _so_ap_cbtd(info)
                    _t_so_dgd += so_dgd
                    _t_so_ap += so_ap
                    rows_bc.append({
                        "Mã CBTD":       ma,
                        "Họ tên":        info["ho_ten"],
                        "PGD":           info.get("pgd",""),
                        "SĐT":           info.get("dien_thoai",""),
                        "Số KH":         fmt_so(so_kh),
                        "Số món vay":    fmt_so(so_mon),
                        "Tổng dư nợ":   _fmt_tien(tdn),
                        "Dư nợ QH":     _fmt_tien(dqh),
                        "Tỷ lệ QH %":   round(dqh/tdn*100, 2) if tdn else 0,
                        "Số ĐGD":       so_dgd,
                        "Số ấp":        so_ap,
                    })

                if not rows_bc:
                    st.info("Không có dữ liệu dư nợ cho CBTD nào (kiểm tra lại tên thôn trong ĐGD).")
                    return

                # NOXH vay trực tiếp — chỉ để đối chiếu, không tính vào TỔNG CỘNG Điểm GD.
                _vt_so_kh, _vt_so_mon, _vt_tdn, _vt_dqh = _agg_dong(_df_vt)
                if _vt_so_mon > 0:
                    rows_bc.append({
                        "Mã CBTD":       "NOXH TRỰC TIẾP (không tính ĐGD)",
                        "Họ tên":        "",
                        "PGD":           "",
                        "SĐT":           "",
                        "Số KH":         fmt_so(_vt_so_kh),
                        "Số món vay":    fmt_so(_vt_so_mon),
                        "Tổng dư nợ":   _fmt_tien(_vt_tdn),
                        "Dư nợ QH":     _fmt_tien(_vt_dqh),
                        "Tỷ lệ QH %":   round(_vt_dqh/_vt_tdn*100, 2) if _vt_tdn else 0,
                        "Số ĐGD":       "—",
                        "Số ấp":        "—",
                    })

                # Dòng thuộc phạm vi ĐGD nhưng chưa được gán cho CBTD nào → phải hiện rõ,
                # nếu không TỔNG CỘNG sẽ không đối chiếu được với tổng dư nợ đơn vị.
                _pc_so_kh, _pc_so_mon, _pc_tdn, _pc_dqh = _agg_dong(_df_chua_pc)
                if _pc_so_mon > 0:
                    rows_bc.append({
                        "Mã CBTD":       "CHƯA PHÂN CÔNG CBTD",
                        "Họ tên":        "",
                        "PGD":           "",
                        "SĐT":           "",
                        "Số KH":         fmt_so(_pc_so_kh),
                        "Số món vay":    fmt_so(_pc_so_mon),
                        "Tổng dư nợ":   _fmt_tien(_pc_tdn),
                        "Dư nợ QH":     _fmt_tien(_pc_dqh),
                        "Tỷ lệ QH %":   round(_pc_dqh/_pc_tdn*100, 2) if _pc_tdn else 0,
                        "Số ĐGD":       "—",
                        "Số ấp":        "—",
                    })

                # TỔNG CỘNG tính nunique trên TOÀN BỘ phạm vi Điểm GD (không cộng dồn từng
                # CBTD) — một KH/món vay ở 2 ấp thuộc 2 CBTD chỉ được đếm 1 lần.
                _tc_so_kh, _tc_so_mon, _tc_tdn, _tc_dqh = _agg_dong(_df_scope)
                rows_bc.append({
                    "Mã CBTD":       "TỔNG CỘNG",
                    "Họ tên":        "",
                    "PGD":           ", ".join(_ds_pgd_cbtd) if _ds_pgd_cbtd else "",
                    "SĐT":           "",
                    "Số KH":         fmt_so(_tc_so_kh),
                    "Số món vay":    fmt_so(_tc_so_mon),
                    "Tổng dư nợ":   _fmt_tien(_tc_tdn),
                    "Dư nợ QH":     _fmt_tien(_tc_dqh),
                    "Tỷ lệ QH %":   round(_tc_dqh/_tc_tdn*100, 2) if _tc_tdn else 0,
                    "Số ĐGD":       _t_so_dgd,
                    "Số ấp":        _t_so_ap,
                })

                hien_thi_dataframe_phan_trang(pd.DataFrame(rows_bc), key=f"{_kp_g2}cbtd_bc_tong_hop")
                st.caption(
                    f"ℹ️ Phạm vi đối chiếu: **{', '.join(_ds_pgd_cbtd) if _ds_pgd_cbtd else 'toàn bộ dữ liệu'}** "
                    f"(các đơn vị đã có CBTD được gán ĐGD). "
                    "TỔNG CỘNG = CBTD + Chưa phân công theo chuẩn báo cáo Điểm GD "
                    "(đã khử trùng Số khế ước, không gồm NOXH trực tiếp)."
                )

                if st.button("📥 Xuất báo cáo CBTD", key=f"{_kp_g2}btn_xuat_cbtd"):
                    buf = BytesIO()
                    with pd.ExcelWriter(buf, engine="openpyxl") as w:
                        pd.DataFrame(rows_bc).to_excel(w, index=False, sheet_name="Tổng hợp CBTD")
                        for ma, info in cbtd_co_dgd.items():
                            df_cb2 = df_joined[df_joined["CBTD"] == ma].copy()
                            if not df_cb2.empty:
                                df_cb2.drop(columns=["CBTD","Tên CBTD"], errors="ignore", inplace=True)
                                df_cb2.to_excel(w, index=False, sheet_name=f"CB_{ma}"[:31])
                        for _sheet, _d in (("NOXH truc tiep", _df_vt),
                                           ("Chua phan cong CBTD", _df_chua_pc)):
                            if _d is not None and not _d.empty:
                                _d2 = _d.drop(columns=["CBTD", "Tên CBTD"], errors="ignore")
                                _d2.to_excel(w, index=False, sheet_name=_sheet[:31])
                    state.downloads.set(
                        "cbtd_excel",
                        buf.getvalue(),
                        f"BC_CBTD_{datetime.today().strftime('%d%m%Y')}.xlsx",
                    )

                if state.downloads.has("cbtd_excel"):
                    if st.download_button(
                        "⬇ Tải Excel",
                        data=state.downloads.get_bytes("cbtd_excel"),
                        file_name=state.downloads.get_filename("cbtd_excel") or f"BC_CBTD_{datetime.today().strftime('%d%m%Y')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key=f"{_kp_g2}dl_cbtd",
                    ):
                        state.downloads.clear("cbtd_excel")

        # ── Nhóm 3: Đánh giá công việc + Nhập nhiệm vụ thủ công ──────────────
        def _render_g3(_c):
            with _c:
                _kp_g3 = f"{_kp}lv2_3_"
                st.markdown("### 📋 Đánh giá công việc & Nhiệm vụ thủ công CBTD")
                if not cbtd_data:
                    st.warning("⚠️ Chưa có danh sách CBTD — qua **Nhóm 2** để thêm CBTD.")
                    return

                scope_bang = "Toàn CN" if not pgd_user else pgd_user
                today = date.today()
                col_nam, col_th, col_cb = st.columns(3)
                nam = col_nam.number_input(
                    "Năm nhiệm vụ thủ công",
                    min_value=2024, max_value=today.year + 1,
                    value=today.year, step=1,
                    key=f"{_kp_g3}nam",
                )
                thang = col_th.number_input(
                    "Tháng nhiệm vụ thủ công",
                    min_value=1, max_value=12,
                    value=today.month, step=1,
                    key=f"{_kp_g3}thang",
                )
                list_ma_cb = ["🔄 Tất cả"] + sorted(cbtd_data.keys())
                default_cb = 0
                try:
                    default_cb = min(1, len(list_ma_cb) - 1)
                except Exception:
                    default_cb = 0
                ma_cb_pick = col_cb.selectbox(
                    "Chọn CBTD (hoặc tất cả)",
                    list_ma_cb,
                    index=default_cb,
                    key=f"{_kp_g3}pick_cb",
                )
                scope_ma_cb = None if ma_cb_pick == "🔄 Tất cả" else ma_cb_pick

                st.divider()
                g3a, g3b = st.tabs([
                    "📊 Số liệu đánh giá tự động (từ HSTD)",
                    "📝 Nhiệm vụ thủ công tháng",
                ])

                # ── Tab A: Số liệu đánh giá tự động ────────────────────────────
                with g3a:
                    nam_hstd, thang_hstd, ngay_hstd = _ky_hstd_hien_tai(df)
                    if ngay_hstd is not None:
                        st.caption(
                            f"📅 Số liệu tự động dùng HSTD kỳ **{thang_hstd:02d}/{nam_hstd}** "
                            f"(ngày số liệu {ngay_hstd.strftime('%d/%m/%Y')}). "
                            "Bộ chọn phía trên chỉ áp dụng cho nhiệm vụ thủ công."
                        )
                    else:
                        st.caption(
                            f"⚠️ HSTD thiếu ngày số liệu; số liệu tự động tạm dùng kỳ "
                            f"**{thang_hstd:02d}/{nam_hstd}**."
                        )
                    try:
                        df_eval = tong_hop_hstd_theo_cbtd(
                            cbtd_data, dgd_map, df,
                            yyyy=int(nam_hstd), mm=int(thang_hstd),
                            scope_pgd=pgd_user or None,
                            scope_ma_cb=scope_ma_cb,
                        )
                    except Exception as e:
                        logger.error("_render_g3 tong_hop: %s", e, exc_info=True)
                        st.error(f"❌ Lỗi tổng hợp số liệu: {e}")
                        df_eval = pd.DataFrame()

                    if df_eval is None or df_eval.empty:
                        st.info("ℹ️ Không có số liệu HSTD nào khớp phạm vi đang chọn.")
                    else:
                        # KPI tổng quan phạm vi
                        col_k1, col_k2, col_k3, col_k4, col_k5 = st.columns(5)
                        so_cb = int(pd.to_numeric(df_eval["Ma_CBTD"], errors="coerce").notna().sum() or len(df_eval))
                        tong_dn = float(pd.to_numeric(df_eval["Tong_du_no"], errors="coerce").fillna(0).sum())
                        tong_qh = float(pd.to_numeric(df_eval["Du_no_qh"], errors="coerce").fillna(0).sum())
                        tl_qh = round(tong_qh / tong_dn * 100, 1) if tong_dn > 0 else 0.0
                        so_kh = int(pd.to_numeric(df_eval["So_KH"], errors="coerce").fillna(0).sum())
                        col_k1.metric("Số CBTD trong phạm vi", f"{so_cb}")
                        col_k2.metric("Tổng dư nợ (tỷ)", f"{tong_dn/1e9:,.2f}")
                        dc_color = "inverse" if tl_qh >= 5 else ("off" if tl_qh >= 2 else "normal")
                        col_k3.metric(
                            "TL nợ quá hạn", f"{tl_qh:.1f}%",
                            delta_color=dc_color,
                        )
                        col_k4.metric("Tổng số khách hàng", f"{so_kh:,}")
                        cb_co_canh_bao = int((df_eval["Canh_bao"].fillna("").astype(str).str.len() > 0).sum())
                        col_k5.metric("CBTD có cảnh báo", f"{cb_co_canh_bao}/{so_cb}")

                        st.caption(
                            "💡 Số liệu tính tự động từ HSTD mới nhất; loại các hồ sơ có "
                            "Hình thức vay = 1."
                        )

                        # ── BẢNG 1: Dư nợ & Nợ quá hạn theo CBTD / xã / chương trình ──
                        st.markdown("#### 💰 Bảng 1 — Dư nợ theo CBTD / Xã / Chương trình")
                        df_bang1 = pd.DataFrame()
                        try:
                            df_bang1 = tong_hop_hstd_cbtd_xa_chuong_trinh(
                                cbtd_data, dgd_map, df,
                                scope_pgd=pgd_user or None,
                                scope_ma_cb=scope_ma_cb,
                            )
                        except Exception as e:
                            logger.error("_render_g3 bang1 du_no: %s", e, exc_info=True)
                            st.warning(f"⚠️ Chưa tính được bảng dư nợ theo CBTD/xã/chương trình: {e}")

                        if df_bang1.empty:
                            st.info(
                                "ℹ️ Chưa có dư nợ khớp địa bàn CBTD — kiểm tra việc gán ĐGD/ấp "
                                "ở **Nhóm 2** và file HSTD đã upload chưa."
                            )
                        else:
                            _b1c1, _b1c2, _b1c3, _b1c4 = st.columns(4)
                            _t_dn_b1 = float(
                                pd.to_numeric(df_bang1["Tổng dư nợ (triệu)"], errors="coerce").fillna(0).sum()
                            )
                            _t_qh_b1 = float(
                                pd.to_numeric(df_bang1["Quá hạn (triệu)"], errors="coerce").fillna(0).sum()
                            )
                            _t_mon_b1 = int(pd.to_numeric(df_bang1["Món vay"], errors="coerce").fillna(0).sum())
                            _b1c1.metric("Tổng dư nợ (tỷ)", f"{_t_dn_b1 / 1000:,.2f}")
                            _b1c2.metric("Dư nợ quá hạn (triệu)", f"{_t_qh_b1:,.0f}")
                            _b1c3.metric("Tổng món vay", f"{_t_mon_b1:,}")
                            _so_cb_co_qh = int(
                                df_bang1.loc[
                                    pd.to_numeric(df_bang1["Quá hạn (triệu)"], errors="coerce").fillna(0) > 0,
                                    "Mã CBTD",
                                ].nunique()
                            )
                            _b1c4.metric("CBTD có NQH", f"{_so_cb_co_qh}/{df_bang1['Mã CBTD'].nunique()}")
                            st.caption(
                                "Bảng mô phỏng mẫu RPT CBTD-Xã-Chương trình: các cột cho vay/thu nợ/tăng giảm "
                                "chỉ có số khi HSTD hiện tại chứa cột nghiệp vụ tương ứng."
                            )
                            hien_thi_dataframe_phan_trang(
                                df_bang1, key=f"{_kp_g3}bang1_dn_qh", height=300,
                            )

                        # ── BẢNG 2: Tổ TK&VV quản lý & chất lượng xếp loại ────────
                        st.markdown("#### 🏘️ Bảng 2 — Tổ TK&VV quản lý & xếp loại (Tốt / Khá / TB / Yếu)")
                        df_bang2 = pd.DataFrame()
                        try:
                            from services.cdtotkvv_service import tong_hop_tu_pgd_data
                            _df_cdto = tong_hop_tu_pgd_data()
                        except Exception as e:
                            logger.error("_render_g3 doc cdtotkvv: %s", e, exc_info=True)
                            _df_cdto = None

                        if _df_cdto is None or _df_cdto.empty:
                            st.info(
                                "ℹ️ Chưa có dữ liệu Tổ TK&VV — cần upload file CDTOTKVV "
                                "(xem tab 🏘️ Tổ TK&VV)."
                            )
                        else:
                            try:
                                _to_map = lay_to_theo_cbtd(cbtd_data, dgd_map, _df_cdto) or {}
                            except Exception as e:
                                logger.error("_render_g3 lay_to_theo_cbtd: %s", e, exc_info=True)
                                st.warning(f"⚠️ Chưa ghép được Tổ TK&VV vào CBTD: {e}")
                                _to_map = {}
                            _rows_b2: list[dict] = []
                            for _mc2, _info_b2 in cbtd_data.items():
                                if scope_ma_cb and _mc2 != scope_ma_cb:
                                    continue
                                if pgd_user and (_info_b2.get("pgd") or "").strip().lower() != pgd_user.strip().lower():
                                    continue
                                _tos = _to_map.get(_mc2) or []
                                _seen_to: set[str] = set()
                                _xl_list: list[str] = []
                                _diem_list: list[float] = []
                                _xa_list: list[str] = []
                                for _t in _tos:
                                    _id_to = f"{_t.get('ma_to') or ''}|{_t.get('ten_xa') or ''}"
                                    if _id_to in _seen_to:
                                        continue
                                    _seen_to.add(_id_to)
                                    _xl_list.append(str(_t.get("xep_loai") or "").strip())
                                    _d_to = _t.get("tong_diem")
                                    if isinstance(_d_to, (int, float)):
                                        _diem_list.append(float(_d_to))
                                    _xa_t = str(_t.get("ten_xa") or "").strip()
                                    if _xa_t and _xa_t not in _xa_list:
                                        _xa_list.append(_xa_t)
                                _n_to = len(_xl_list)
                                _n_tot = sum(1 for x in _xl_list if x == "Tốt")
                                _n_kha = sum(1 for x in _xl_list if x == "Khá")
                                _n_tb = sum(1 for x in _xl_list if x == "Trung bình")
                                _n_yeu = sum(1 for x in _xl_list if x == "Yếu")
                                _n_chua = max(0, _n_to - (_n_tot + _n_kha + _n_tb + _n_yeu))
                                _n_da_xl = _n_tot + _n_kha + _n_tb + _n_yeu
                                _rows_b2.append({
                                    "Mã CBTD": _mc2,
                                    "Họ và tên": _info_b2.get("ho_ten", ""),
                                    "PGD": _info_b2.get("pgd", ""),
                                    "Số ĐGD": len(_info_b2.get("ds_dgd") or []),
                                    "Số tổ": _n_to,
                                    "Tổ Tốt": _n_tot,
                                    "Tổ Khá": _n_kha,
                                    "Tổ TB": _n_tb,
                                    "Tổ Yếu": _n_yeu,
                                    "Chưa XL": _n_chua,
                                    "% Tổ đạt": round((_n_tot + _n_kha) / _n_da_xl * 100, 1) if _n_da_xl > 0 else 0.0,
                                    "Điểm TB tổ": round(sum(_diem_list) / len(_diem_list), 1) if _diem_list else 0.0,
                                    "Xã có tổ": ", ".join(_xa_list),
                                })
                            df_bang2 = pd.DataFrame(_rows_b2)
                            if not df_bang2.empty:
                                df_bang2 = df_bang2.sort_values(
                                    ["Số tổ", "% Tổ đạt"], ascending=[False, False]
                                ).reset_index(drop=True)

                        if not df_bang2.empty:
                            _b2c1, _b2c2, _b2c3, _b2c4, _b2c5 = st.columns(5)
                            _b2c1.metric("Tổng số tổ", f"{int(pd.to_numeric(df_bang2['Số tổ'], errors='coerce').fillna(0).sum()):,}")
                            _b2c2.metric("Tổ Tốt", f"{int(pd.to_numeric(df_bang2['Tổ Tốt'], errors='coerce').fillna(0).sum()):,}")
                            _b2c3.metric("Tổ Khá", f"{int(pd.to_numeric(df_bang2['Tổ Khá'], errors='coerce').fillna(0).sum()):,}")
                            _b2c4.metric("Tổ TB", f"{int(pd.to_numeric(df_bang2['Tổ TB'], errors='coerce').fillna(0).sum()):,}")
                            _b2c5.metric("Tổ Yếu", f"{int(pd.to_numeric(df_bang2['Tổ Yếu'], errors='coerce').fillna(0).sum()):,}")
                            st.caption(
                                "💡 **% Tổ đạt** = (Tổ Tốt + Tổ Khá) / tổng số tổ đã xếp loại. "
                                "Tổ được ghép vào CBTD qua ĐGD → thôn/ấp → xã."
                            )
                            hien_thi_dataframe_phan_trang(
                                df_bang2, key=f"{_kp_g3}bang2_to_tkvv", height=300,
                            )

                        # Bảng chi tiết: format cho đẹp
                        df_show = df_eval.copy()
                        _cols_tien = ["Tong_du_no", "Du_no_trong_han", "Du_no_qh", "Du_no_khoanh",
                                      "Cho_vay_thang", "Thu_no_thang", "Cho_vay_nam",
                                      "Thu_no_nam", "No_den_han_goc"]
                        for _c_tien in _cols_tien:
                            if _c_tien in df_show.columns:
                                df_show[_c_tien] = pd.to_numeric(df_show[_c_tien], errors="coerce").fillna(0) / 1_000_000
                        df_show = df_show.rename(columns={
                            "Ma_CBTD": "Mã CBTD",
                            "Ho_ten": "Họ và tên",
                            "PGD": "PGD",
                            "So_DGD": "Số ĐGD",
                            "So_ap": "Số ấp",
                            "So_KH": "Số KH",
                            "So_mon_vay": "Số HV",
                            "Tong_du_no": "Tổng DN (triệu)",
                            "Du_no_trong_han": "DN trong hạn (triệu)",
                            "Du_no_qh": "DN quá hạn (triệu)",
                            "Du_no_khoanh": "DN khoanh (triệu)",
                            "TL_QH_pct": "TL QH %",
                            "Cho_vay_thang": "Cho vay tháng (triệu)",
                            "Thu_no_thang": "Thu nợ tháng (triệu)",
                            "Cho_vay_nam": "Cho vay năm (triệu)",
                            "Thu_no_nam": "Thu nợ năm (triệu)",
                            "No_den_han_mon": "Món đến hạn",
                            "No_den_han_goc": "Gốc đến hạn (triệu)",
                            "So_mon_3m_khd": "Món 3T KHĐ",
                            "So_mon_rui_ro": "Món rủi ro",
                            "So_KH_moi_thang": "KH mới tháng",
                            "So_giai_ngan_thang": "Lần GN tháng",
                            "Canh_bao": "Cảnh báo",
                        })
                        if "Cảnh báo" in df_show.columns:
                            def _fmt_canh_bao(x):
                                if x is None:
                                    return ""
                                if isinstance(x, list):
                                    return "; ".join(str(v) for v in x)
                                return str(x)
                            df_show["Cảnh báo"] = df_show["Cảnh báo"].map(_fmt_canh_bao)

                        # So sánh với kỳ tháng trước: snapshot địa bàn → gán lại CBTD hiện tại.
                        from snapshot_service import danh_sach_ky_thon, ky_thang_truoc
                        _ky_hien_tai_g3 = f"{int(nam_hstd)}-{int(thang_hstd):02d}"
                        _ky_truoc = ky_thang_truoc(danh_sach_ky_thon(), _ky_hien_tai_g3)
                        _ly_do_khong_so_sanh = ""
                        _df_truoc = pd.DataFrame()
                        if _ky_truoc:
                            try:
                                from snapshot_service import doc_thon_snapshot, snapshot_la_cuoi_thang
                                from services.cbtd_dia_ban_service import tong_hop_thon_snapshot_theo_cbtd
                                _df_thon_truoc = doc_thon_snapshot(_ky_truoc)
                                if snapshot_la_cuoi_thang(_df_thon_truoc, _ky_truoc):
                                    _df_truoc = tong_hop_thon_snapshot_theo_cbtd(
                                        _df_thon_truoc, cbtd_data, dgd_map
                                    )
                                else:
                                    _df_truoc = pd.DataFrame()
                                    if _df_thon_truoc is not None and not _df_thon_truoc.empty:
                                        _ly_do_khong_so_sanh = (
                                            f"⚠️ Snapshot thôn kỳ **{_ky_truoc}** không phải dữ liệu cuối tháng; "
                                            "không dùng để tính chênh lệch."
                                        )
                            except Exception as e:
                                logger.error("_render_g3 doc_thon_snapshot: %s", e, exc_info=True)
                                _df_truoc = pd.DataFrame()
                        if _df_truoc is None or _df_truoc.empty:
                            st.caption(
                                _ly_do_khong_so_sanh
                                or f"ℹ️ Chưa có snapshot thôn kỳ tháng trước **{_ky_truoc or '—'}** "
                                f"(so với {_ky_hien_tai_g3}) — chưa so sánh được với tháng trước."
                            )
                        else:
                            _map_snap = {
                                "ma_cb": "Mã CBTD",
                                "tong_du_no": "Tổng DN (triệu)",
                                "du_no_qh": "DN quá hạn (triệu)",
                                "cho_vay_thang": "Cho vay tháng (triệu)",
                                "thu_no_thang": "Thu nợ tháng (triệu)",
                                "no_den_han_goc": "Gốc đến hạn (triệu)",
                                "no_den_han_mon": "Món đến hạn",
                                "so_mon_3m_khd": "Món 3T KHĐ",
                                "so_mon_rui_ro": "Món rủi ro",
                            }
                            _truoc_show = _df_truoc.rename(columns=_map_snap).copy()
                            _tien_truoc = ["Tổng DN (triệu)", "DN quá hạn (triệu)",
                                            "Cho vay tháng (triệu)", "Thu nợ tháng (triệu)",
                                            "Gốc đến hạn (triệu)"]
                            for _c in _tien_truoc:
                                if _c in _truoc_show.columns:
                                    _truoc_show[_c] = pd.to_numeric(_truoc_show[_c], errors="coerce").fillna(0) / 1_000_000
                            _merge_cols = ["Mã CBTD"] + [c for c in _map_snap.values()
                                                        if c != "Mã CBTD" and c in _truoc_show.columns]
                            df_show = df_show.merge(
                                _truoc_show[_merge_cols], on="Mã CBTD", how="left",
                                suffixes=("", " (TTr)"),
                            )
                            for _base in ["Tổng DN", "DN quá hạn", "Cho vay tháng", "Thu nợ tháng", "Gốc đến hạn"]:
                                _cur = f"{_base} (triệu)"
                                _prev = f"{_base} (triệu) (TTr)"
                                if _cur in df_show.columns and _prev in df_show.columns:
                                    df_show[f"Δ {_base} (triệu)"] = (
                                        pd.to_numeric(df_show[_cur], errors="coerce").fillna(0)
                                        - pd.to_numeric(df_show[_prev], errors="coerce").fillna(0)
                                    )

                        # Download excel
                        xl_bytes = xuat_excel({
                            "Du_no_Xa_CT_theo_CBTD": df_bang1,
                            "To_TKVV_theo_CBTD": df_bang2,
                            "Tong_hop_day_du": df_show,
                            "Tham_so": pd.DataFrame([
                                {"Tham_so": "Phạm vi", "Gia_tri": scope_bang},
                                {"Tham_so": "Năm HSTD", "Gia_tri": nam_hstd},
                                {"Tham_so": "Tháng HSTD", "Gia_tri": thang_hstd},
                                {"Tham_so": "CBTD lọc", "Gia_tri": ma_cb_pick},
                                {"Tham_so": "Nguồn dư nợ", "Gia_tri": "HSTD mới nhất theo chuẩn Điểm GD (khử trùng Số khế ước, loại NOXH trực tiếp), nhóm theo CBTD/Xã/Chương trình"},
                                {"Tham_so": "Nguồn Tổ TK&VV", "Gia_tri": "CDTOTKVV tổng hợp từ pgd_data"},
                            ]),
                        })
                        st.download_button(
                            "⬇️ Tải Excel đánh giá CBTD",
                            data=xl_bytes,
                            file_name=f"danh_gia_cbtd_{scope_bang}_{nam_hstd}_{thang_hstd:02d}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key=f"{_kp_g3}dl_eval",
                        )

                        # Nút xem chi tiết 1 CBTD
                        if scope_ma_cb and scope_ma_cb in cbtd_data:
                            st.markdown(f"#### 🧾 Điểm CBTD **{scope_ma_cb}** tháng {thang_hstd:02d}/{nam_hstd}")
                            try:
                                score = cham_diem_cbtd_thang(
                                    scope_ma_cb, int(nam_hstd), int(thang_hstd),
                                    cbtd_data=cbtd_data, dgd_map=dgd_map, df_hstd=df,
                                    scope_pgd=pgd_user or None,
                                ) or {}
                                tong_diem = float(score.get("diem_tong", score.get("tong_diem", 0)) or 0)
                                xep_loai = str(score.get("xep_loai") or "—")
                                kpi_row(
                                    cols=[
                                        ("Tổng điểm", f"{tong_diem:.1f}/100", "normal"),
                                        ("Xếp loại", xep_loai, "normal"),
                                    ],
                                    num_columns=2,
                                    key=f"{_kp_g3}score",
                                )
                                with st.expander("🔎 Chi tiết từng tiêu chí chấm điểm", expanded=False):
                                    rows_cham = []
                                    for k, v in (score or {}).items():
                                        if k in ("diem_tong", "tong_diem", "xep_loai"):
                                            continue
                                        if isinstance(v, (int, float)):
                                            rows_cham.append({"Tiêu chí": k, "Điểm": round(float(v), 2)})
                                        else:
                                            rows_cham.append({"Tiêu chí": k, "Điểm": str(v)})
                                    if rows_cham:
                                        st.dataframe(pd.DataFrame(rows_cham), use_container_width=True, hide_index=True)
                            except Exception as e:
                                logger.error("_render_g3 cham_diem %s: %s", scope_ma_cb, e, exc_info=True)
                                st.warning(f"⚠️ Chưa chấm được điểm cho CBTD {scope_ma_cb}: {e}")
                        else:
                            if so_cb <= 10:
                                # Chấm điểm hàng loạt nhanh (giới hạn số CBTD để không chậm)
                                st.markdown("#### 🏆 Bảng chấm điểm nhanh (auto clamp 0-100)")
                                rows_rank = []
                                for ma_cb, info in cbtd_data.items():
                                    if scope_ma_cb and ma_cb != scope_ma_cb:
                                        continue
                                    if pgd_user and (info or {}).get("pgd", "").strip().lower() != pgd_user.strip().lower():
                                        continue
                                    try:
                                        s = cham_diem_cbtd_thang(
                                            ma_cb, int(nam_hstd), int(thang_hstd),
                                            cbtd_data=cbtd_data, dgd_map=dgd_map, df_hstd=df,
                                            scope_pgd=pgd_user or None,
                                        ) or {}
                                    except Exception as e:
                                        logger.error("_render_g3 cham_diem loop %s: %s", ma_cb, e, exc_info=True)
                                        s = {}
                                    rows_rank.append({
                                        "Mã CBTD": ma_cb,
                                        "Họ và tên": (info or {}).get("ho_ten", ""),
                                        "PGD": (info or {}).get("pgd", ""),
                                        "Tổng điểm": round(float(s.get("diem_tong", s.get("tong_diem", 0)) or 0), 1),
                                        "Xếp loại": str(s.get("xep_loai") or "—"),
                                    })
                                if rows_rank:
                                    df_rank = pd.DataFrame(rows_rank).sort_values("Tổng điểm", ascending=False)
                                    st.dataframe(df_rank, use_container_width=True, hide_index=True)
                                    st.download_button(
                                        "⬇️ Tải Excel BXH CBTD",
                                        data=xuat_excel({"BXH_CBTD": df_rank}),
                                        file_name=f"bxh_cbtd_{scope_bang}_{nam_hstd}_{thang_hstd:02d}.xlsx",
                                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                        key=f"{_kp_g3}dl_bxh",
                                    )
                            else:
                                st.info(
                                    "ℹ️ Để xem BXH nhanh, chọn 1 CBTD cụ thể ở trên hoặc áp bộ lọc PGD. "
                                    "Với nhiều CBTD, ưu tiên tải Excel đánh giá (nút trên) để lọc/tính toán offline."
                                )

                        # Hiển thị bảng chi tiết cuối
                        st.markdown("#### 📋 Bảng 3 — Tổng hợp đầy đủ theo từng CBTD")
                        hien_thi_dataframe_phan_trang(
                            df_show,
                            key=f"{_kp_g3}bang_danhgia",
                        )

                # ── Tab B: Nhập nhiệm vụ thủ công tháng ─────────────────────────
                with g3b:
                    st.caption(
                        "📌 Các công việc ngoài số liệu HSTD (đôn đốc, phát tờ trình, họp hội đoàn thể, phiếu 01/02/03…). "
                        "Lưu theo {năm}/{tháng}/{mã CBTD} — persist kv_store."
                    )
                    # Chọn CBTD + Loại nhiệm vụ
                    list_ma_cb2 = sorted(cbtd_data.keys())
                    if not list_ma_cb2:
                        st.warning("⚠️ Chưa có CBTD.")
                    else:
                        i_def = 0
                        if scope_ma_cb and scope_ma_cb in list_ma_cb2:
                            try:
                                i_def = list_ma_cb2.index(scope_ma_cb)
                            except ValueError:
                                i_def = 0
                        cb_cbtd = st.selectbox(
                            "Chọn CBTD nhập nhiệm vụ",
                            list_ma_cb2,
                            index=i_def,
                            key=f"{_kp_g3}nv_cb",
                        )
                        # Key kv_store
                        kv_nv_key = f"nhiem_vu_cbtd_{int(nam)}_{int(thang):02d}"
                        nv_raw: dict[str, Any] = db.doc_kv(kv_nv_key) or {}
                        if not isinstance(nv_raw, dict):
                            nv_raw = {}
                        # Cấu trúc: nv_raw[ma_cb] = list[{loai, ten, trong_so, hoan_thanh_pct, ghi_chu, ngay_cn}]
                        nv_cb_list: list[dict[str, Any]] = nv_raw.get(cb_cbtd) or []
                        if not isinstance(nv_cb_list, list):
                            nv_cb_list = []

                        LOAI_NV_OPTS = [
                            "Đôn đốc trả nợ (chạy NQH)",
                            "Giải ngân (duyệt hồ sơ chờ)",
                            "Phát tờ trình / Phiếu đề xuất",
                            "Xuất phiếu 01/02/03 (đến hạn)",
                            "Hội đoàn thể / Tổ TK&VV",
                            "Họp xã / Chính quyền địa phương",
                            "Giải trình / Báo cáo đột xuất",
                            "Khác (ghi rõ)",
                        ]
                        st.markdown("##### ➕ Thêm nhiệm vụ mới")
                        with st.form(f"{_kp_g3}them_nv", clear_on_submit=True):
                            c1, c2, c3 = st.columns(3)
                            loai_nv = c1.selectbox("Loại nhiệm vụ", LOAI_NV_OPTS, key=f"{_kp_g3}nv_loai")
                            trong_so = c2.number_input(
                                "Trọng số (%)",
                                min_value=0, max_value=100, value=10, step=5,
                                key=f"{_kp_g3}nv_ts",
                            )
                            ht_pct = c3.number_input(
                                "Hoàn thành (%)",
                                min_value=0, max_value=100, value=0, step=5,
                                key=f"{_kp_g3}nv_ht",
                            )
                            ten_nv = st.text_input(
                                "Tên nhiệm vụ / Mô tả ngắn",
                                max_chars=200,
                                key=f"{_kp_g3}nv_ten",
                            )
                            ghi_chu_nv = st.text_area(
                                "Ghi chú (nguy nhân, phụ thuộc…)",
                                max_chars=500,
                                height=60,
                                key=f"{_kp_g3}nv_gc",
                            )
                            submitted = st.form_submit_button("➕ Thêm nhiệm vụ")
                            if submitted:
                                if not ten_nv.strip():
                                    st.error("❌ Vui lòng nhập Tên nhiệm vụ.")
                                else:
                                    nv_new = {
                                        "loai": loai_nv,
                                        "ten": ten_nv.strip(),
                                        "trong_so": int(trong_so),
                                        "hoan_thanh_pct": int(ht_pct),
                                        "ghi_chu": ghi_chu_nv.strip(),
                                        "ngay_cn": datetime.now().strftime("%d/%m/%Y %H:%M"),
                                        "nguoi_cn": username,
                                    }
                                    nv_cb_list.append(nv_new)
                                    nv_raw[cb_cbtd] = nv_cb_list
                                    db.ghi_kv(kv_nv_key, nv_raw, username)
                                    db.ghi_audit(
                                        username, "them_nhiem_vu_cbtd",
                                        f"Thêm nhiệm vụ [{loai_nv}] cho CBTD {cb_cbtd} kỳ {nam}/{thang:02d}"
                                    )
                                    st.success(f"✅ Đã thêm nhiệm vụ cho **{cb_cbtd}**.")
                                    state.downloads.clear(f"{_kp_g3}")

                        # Danh sách nhiệm vụ đã nhập
                        st.markdown(
                            f"##### 📋 Danh sách nhiệm vụ **{cb_cbtd}** kỳ {thang:02d}/{nam} "
                            f"({len(nv_cb_list)} mục)"
                        )
                        if not nv_cb_list:
                            st.info("ℹ️ Chưa có nhiệm vụ thủ công nào — dùng form trên để thêm.")
                        else:
                            # Tính tiến độ tổng hợp
                            tong_ts = 0
                            tong_ht = 0.0
                            for item in nv_cb_list:
                                ts = int(item.get("trong_so") or 0)
                                ht = float(item.get("hoan_thanh_pct") or 0)
                                tong_ts += ts
                                tong_ht += ts * ht / 100.0
                            tl_ht = round(tong_ht / tong_ts * 100, 1) if tong_ts > 0 else 0.0
                            prog_color = "normal" if tl_ht >= 80 else ("off" if tl_ht >= 50 else "inverse")
                            kpi_row(
                                cols=[
                                    ("Số nhiệm vụ", f"{len(nv_cb_list)} mục", "normal"),
                                    ("Tổng trọng số", f"{tong_ts}%", "normal"),
                                    (
                                        "Tiến độ hoàn thành",
                                        f"{tl_ht:.1f}%",
                                        prog_color,
                                    ),
                                ],
                                num_columns=3,
                                key=f"{_kp_g3}nv_kpi",
                            )
                            st.progress(int(min(100, max(0, tl_ht))) / 100.0)

                            # Form cập nhật hàng loạt
                            st.markdown("##### ✏️ Cập nhật tiến độ / Hoàn thành (chọn để cập nhật)")
                            df_nv = pd.DataFrame(nv_cb_list).copy()
                            if df_nv.empty:
                                df_nv = pd.DataFrame(columns=[
                                    "STT", "Loại nhiệm vụ", "Tên nhiệm vụ",
                                    "Trọng số %", "Hoàn thành %",
                                    "Ghi chú", "Cập nhật cuối", "Người cập nhật",
                                ])
                            else:
                                df_nv.insert(0, "STT", range(1, len(df_nv) + 1))
                                df_nv = df_nv.rename(columns={
                                    "loai": "Loại nhiệm vụ",
                                    "ten": "Tên nhiệm vụ",
                                    "trong_so": "Trọng số %",
                                    "hoan_thanh_pct": "Hoàn thành %",
                                    "ghi_chu": "Ghi chú",
                                    "ngay_cn": "Cập nhật cuối",
                                    "nguoi_cn": "Người cập nhật",
                                })
                                # Chọn đúng thứ tự cột hiển thị
                                cols_show = [
                                    "STT", "Loại nhiệm vụ", "Tên nhiệm vụ",
                                    "Trọng số %", "Hoàn thành %",
                                    "Ghi chú", "Cập nhật cuối", "Người cập nhật",
                                ]
                                for c in cols_show:
                                    if c not in df_nv.columns:
                                        df_nv[c] = ""
                                df_nv = df_nv[cols_show]

                            edited = st.data_editor(
                                df_nv,
                                use_container_width=True,
                                hide_index=True,
                                column_config={
                                    "STT": st.column_config.NumberColumn(disabled=True),
                                    "Loại nhiệm vụ": st.column_config.SelectboxColumn(
                                        options=LOAI_NV_OPTS, required=True,
                                    ),
                                    "Tên nhiệm vụ": st.column_config.TextColumn(required=True, max_chars=200),
                                    "Trọng số %": st.column_config.NumberColumn(
                                        min_value=0, max_value=100, step=1,
                                        format="%d", required=True,
                                    ),
                                    "Hoàn thành %": st.column_config.ProgressColumn(
                                        min_value=0, max_value=100, step=5,
                                        format="%d", required=True,
                                    ),
                                    "Ghi chú": st.column_config.TextColumn(max_chars=500),
                                    "Cập nhật cuối": st.column_config.TextColumn(disabled=True),
                                    "Người cập nhật": st.column_config.TextColumn(disabled=True),
                                },
                                num_rows="dynamic",
                                key=f"{_kp_g3}nv_edit",
                            )

                            col_save, col_del, col_dl = st.columns(3)
                            if col_save.button("💾 Lưu thay đổi nhiệm vụ", key=f"{_kp_g3}nv_save"):
                                try:
                                    new_list: list[dict[str, Any]] = []
                                    errors = []
                                    now_str = datetime.now().strftime("%d/%m/%Y %H:%M")
                                    for _idx, r in edited.iterrows():
                                        ten = str(r.get("Tên nhiệm vụ") or "").strip()
                                        if not ten:
                                            errors.append(f"Dòng {_idx + 1}: Tên nhiệm vụ không được rỗng.")
                                            continue
                                        loai = str(r.get("Loại nhiệm vụ") or "Khác (ghi rõ)").strip()
                                        try:
                                            ts = int(r.get("Trọng số %"))
                                        except Exception:
                                            ts = 0
                                        if ts < 0:
                                            ts = 0
                                        if ts > 100:
                                            ts = 100
                                        try:
                                            ht = int(r.get("Hoàn thành %"))
                                        except Exception:
                                            ht = 0
                                        if ht < 0:
                                            ht = 0
                                        if ht > 100:
                                            ht = 100
                                        gc = str(r.get("Ghi chú") or "").strip()
                                        new_list.append({
                                            "loai": loai,
                                            "ten": ten,
                                            "trong_so": ts,
                                            "hoan_thanh_pct": ht,
                                            "ghi_chu": gc,
                                            "ngay_cn": now_str,
                                            "nguoi_cn": username,
                                        })
                                    if errors:
                                        st.error("❌ " + "\n".join(errors))
                                    else:
                                        nv_raw[cb_cbtd] = new_list
                                        db.ghi_kv(kv_nv_key, nv_raw, username)
                                        db.ghi_audit(
                                            username, "cap_nhat_nhiem_vu_cbtd",
                                            f"Cập nhật {len(new_list)} nhiệm vụ cho CBTD {cb_cbtd} kỳ {nam}/{thang:02d}"
                                        )
                                        st.success(f"✅ Đã lưu {len(new_list)} nhiệm vụ cho **{cb_cbtd}**.")
                                        state.downloads.clear(f"{_kp_g3}")
                                        st.rerun()
                                except Exception as e:
                                    logger.error("_render_g3 luu nhiem vu: %s", e, exc_info=True)
                                    st.error(f"❌ Lỗi lưu nhiệm vụ: {e}")

                            if col_del.button("🗑️ Xóa toàn bộ nhiệm vụ CBTD này", key=f"{_kp_g3}nv_del"):
                                if cb_cbtd in nv_raw:
                                    del nv_raw[cb_cbtd]
                                    db.ghi_kv(kv_nv_key, nv_raw, username)
                                    db.ghi_audit(
                                        username, "xoa_nhiem_vu_cbtd",
                                        f"Xóa toàn bộ nhiệm vụ CBTD {cb_cbtd} kỳ {nam}/{thang:02d}"
                                    )
                                    st.success("✅ Đã xóa.")
                                    state.downloads.clear(f"{_kp_g3}")
                                    st.rerun()

                            # Download Excel nhiệm vụ toàn kỳ
                            rows_dl_nv: list[dict[str, Any]] = []
                            for mc, lst in (nv_raw or {}).items():
                                if pgd_user:
                                    info_mc = cbtd_data.get(mc) or {}
                                    if (info_mc.get("pgd") or "").strip().lower() != pgd_user.strip().lower():
                                        continue
                                ten_cb = (cbtd_data.get(mc) or {}).get("ho_ten", "")
                                pgd_cb = (cbtd_data.get(mc) or {}).get("pgd", "")
                                tong_ts_cb = 0
                                tong_ht_cb = 0.0
                                for it in (lst or []):
                                    ts = int(it.get("trong_so") or 0)
                                    ht = float(it.get("hoan_thanh_pct") or 0)
                                    tong_ts_cb += ts
                                    tong_ht_cb += ts * ht / 100.0
                                    rows_dl_nv.append({
                                        "Mã CBTD": mc,
                                        "Họ và tên": ten_cb,
                                        "PGD": pgd_cb,
                                        "Loại nhiệm vụ": it.get("loai", ""),
                                        "Tên nhiệm vụ": it.get("ten", ""),
                                        "Trọng số %": ts,
                                        "Hoàn thành %": ht,
                                        "Ghi chú": it.get("ghi_chu", ""),
                                        "Cập nhật cuối": it.get("ngay_cn", ""),
                                        "Người cập nhật": it.get("nguoi_cn", ""),
                                    })
                                tl = round(tong_ht_cb / tong_ts_cb * 100, 1) if tong_ts_cb > 0 else 0.0
                                rows_dl_nv.append({
                                    "Mã CBTD": mc,
                                    "Họ và tên": ten_cb,
                                    "PGD": pgd_cb,
                                    "Loại nhiệm vụ": "【TỔNG KẾT】",
                                    "Tên nhiệm vụ": f"Tiến độ kỳ: {tl}%",
                                    "Trọng số %": tong_ts_cb,
                                    "Hoàn thành %": tl,
                                    "Ghi chú": "",
                                    "Cập nhật cuối": "",
                                    "Người cập nhật": "",
                                })
                            df_dl_nv = pd.DataFrame(rows_dl_nv)
                            col_dl.download_button(
                                "⬇️ Tất cả nhiệm vụ kỳ này (Excel)",
                                data=xuat_excel({
                                    "Nhiem_vu_thang": df_dl_nv,
                                    "Tham_so": pd.DataFrame([
                                        {"Tham_so": "Phạm vi", "Gia_tri": scope_bang},
                                        {"Tham_so": "Năm", "Gia_tri": nam},
                                        {"Tham_so": "Tháng", "Gia_tri": thang},
                                        {"Tham_so": "Key KV", "Gia_tri": kv_nv_key},
                                    ]),
                                }),
                                file_name=f"nhiem_vu_cbtd_{scope_bang}_{nam}_{thang:02d}.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                key=f"{_kp_g3}dl_nv",
                                disabled=df_dl_nv.empty,
                            )

        # ── Nhóm 4: Tác nghiệp & Đôn đốc hàng ngày ──────────────────────────
        def _render_g4(_c):
            with _c:
                st.info(
                    "📝 **[Nhóm 4 / Giữa tháng] Tác nghiệp & Đôn đốc hàng ngày** — Sẽ cập nhật sau Step 3 helper:\n\n"
                    "• ① Hợp đồng đến hạn trả nợ hôm nay / trong 7 ngày tới\n"
                    "• ② Kiểm soát NQH 30/60/90 ngày (theo từng CBTD địa bàn)\n"
                    "• ③ Đôn đốc Giải ngân (đơn chờ duyệt > 3 ngày)\n"
                    "• ④ KH mới tháng này (theo dõi tiến độ)\n"
                    "• ⑤ Đôn đốc 3 tháng KHD (không hoạt động) — reuse logic tab_don_doc_khd\n"
                    "• ⑥ Phiếu đến hạn (export Word - Phiếu 01/02/03)\n"
                    "• Export Excel danh sách NQH chi tiết theo CBTD"
                )

        # ── Nhóm 5: Xếp hạng & Báo cáo cuối tháng ──────────────────────────
        def _render_g5(_c):
            with _c:
                st.info(
                    "📝 **[Nhóm 5 / Cuối tháng] Xếp hạng & Báo cáo** — Dùng service `xep_hang_cbtd()` đã có (cbtd_dia_ban_service.py L568):\n\n"
                    "• Chấm điểm tháng N tự động theo scorecard (0-100 clamp) — reuse `xep_hang_cbtd()`\n"
                    "• BXH toàn chi nhánh (Xuất sắc 85+ / Tốt 70-85 / Khá 55-70 / TB 40-55 / Yếu <40)\n"
                    "• Soạn nội dung giao ban ngày 01 tháng tự động từ BXH + Top 3 CBTD xuất sắc\n"
                    "• Xuất báo cáo cuối tháng (Word + PDF) — reuse template Word\n"
                    "• Download BXH Excel (có format màu theo xếp loại)"
                )

        # ── Nhóm 6: Công cụ bổ trợ ──────────────────────────────────────────
        def _render_g6(_c):
            with _c:
                st.info(
                    "📝 **[Nhóm 6 / Công cụ] Mapping & Mẫu biểu VBSP** — Sẽ cập nhật sau Step 4:\n\n"
                    "• ① Mapping ĐGD view theo từng CBTD (1 CBTD = bao nhiêu ĐGD = bao nhiêu ấp)\n"
                    "• ② Mapping Tổ TK&VV → CBTD (từ ĐGD auto-infer, có override manual) — persist kv_store\n"
                    "• ③ Xuất 10 mẫu biểu VBSP (Phiếu 01 → 10) theo khối Word\n"
                    "• ④ Tìm kiếm nâng cao Hợp đồng (tên KH / SĐT / CCCD / số tiền / ngày đến hạn)"
                )

        # ════════════════════════════════════════════════════════════════════
        # MỤC TỔNG QUAN THEO CBTD (hiển thị trước 6 nhóm)
        # ════════════════════════════════════════════════════════════════════
        st.divider()
        st.markdown("### 📊 Tổng quan theo CBTD")
        if df is None or df.empty:
            st.info("ℹ️ Chưa có dữ liệu HSTD để tổng quan.")
        elif not cbtd_data:
            st.info("ℹ️ Chưa có CBTD — thêm ở Nhóm 2 '👥 Quản lý hồ sơ CBTD'.")
        else:
            _nam, _thang, _ngay = _ky_hstd_hien_tai(df)
            _df_tq = tong_hop_hstd_theo_cbtd(cbtd_data, dgd_map, df, yyyy=_nam, mm=_thang)
            if _df_tq is None or _df_tq.empty:
                st.info("ℹ️ Chưa tính được tổng quan theo CBTD.")
            else:
                _ky_hien_tai = f"{int(_nam)}-{int(_thang):02d}"
                from snapshot_service import (
                    danh_sach_ky_thon, ky_thang_truoc, ky_baseline,
                )
                _ds_ky_thon = danh_sach_ky_thon()
                _ky_truoc = ky_thang_truoc(_ds_ky_thon, _ky_hien_tai)
                _ky_baseline = ky_baseline(_ds_ky_thon, _ky_hien_tai)
                _df_ttr = _lay_snapshot_cbtd(_ky_truoc, cbtd_data, dgd_map)
                _df_ntr = _lay_snapshot_cbtd(_ky_baseline, cbtd_data, dgd_map)
                st.caption(
                    f"📅 Kỳ số liệu **{_thang:02d}/{_nam}** · "
                    f"Tháng trước **{_ky_truoc or '—'}** {'✅' if not _df_ttr.empty else '⚠️ chưa có snapshot'} · "
                    f"31/12 năm trước **{_ky_baseline or '—'}** {'✅' if not _df_ntr.empty else '⚠️ chưa có snapshot'}"
                )

                _tq_tdn = float(pd.to_numeric(_df_tq["Tong_du_no"], errors="coerce").fillna(0).sum())
                _tq_dqh = float(pd.to_numeric(_df_tq["Du_no_qh"], errors="coerce").fillna(0).sum())
                _tq_tl = round(_tq_dqh / _tq_tdn * 100, 1) if _tq_tdn else 0.0
                kpi_row(cols=[
                    {"label": "Số CBTD", "value": fmt_so(len(_df_tq)), "icon": "👔"},
                    {"label": "Tổng dư nợ (tỷ)", "value": f"{_tq_tdn/1e9:,.2f}", "icon": "💰"},
                    {"label": "Dư nợ QH (tỷ)", "value": f"{_tq_dqh/1e9:,.2f}", "icon": "🚨"},
                    {"label": "TL QH %", "value": f"{_tq_tl:.1f}%", "icon": "📉"},
                ], num_columns=4)

                _df_th = _tao_bang_tong_hop(_df_tq, _df_ttr, _df_ntr)
                _df_nqt = _tao_bang_no_quan_tam(_df_tq, _df_ttr, _df_ntr)

                st.markdown("##### 📊 Dư nợ theo CBTD quản lý địa bàn (triệu đồng)")
                if _df_th.empty:
                    st.caption("⚠️ Chưa tổng hợp được dư nợ theo CBTD.")
                else:
                    st.html(_html_bang_du_no(_df_th))
                    st.caption(
                        "Màu Δ: **xanh** = thuận lợi, **đỏ** = cần chú ý · '—' = chưa có snapshot kỳ so sánh."
                    )

                st.markdown("##### ⏳ Cụm chỉ tiêu nợ cần quan tâm (món)")
                if _df_nqt.empty:
                    st.caption("⚠️ Chưa tổng hợp được chỉ tiêu nợ cần quan tâm.")
                else:
                    st.html(_html_bang_no_quan_tam(_df_nqt))

                st.markdown("##### 🏅 Chất lượng Tổ TK&VV")
                _bang_to, _ky_cdto, _ky_cdto_truoc, _ky_cdto_baseline = _bang_to_tkvv(
                    cbtd_data,
                    dgd_map,
                )
                if _bang_to.empty:
                    st.caption("⚠️ Chưa có dữ liệu Tổ TK&VV.")
                else:
                    if _ky_cdto:
                        st.caption(
                            f"🏅 Kỳ chấm điểm Tổ TK&VV: **{_ky_cdto}** · "
                            f"Tháng trước: **{_ky_cdto_truoc or '—'}** · "
                            f"31/12 năm trước: **{_ky_cdto_baseline or '—'}**"
                        )
                    hien_thi_dataframe_phan_trang(_hien_thi_bang_to(_bang_to), key=f"{_kp}tq_to")

                _rename_th = {
                    "STT": "STT", "Ma_CBTD": "Mã CBTD", "Ho_ten": "Họ tên", "PGD": "PGD",
                    "So_KH": "Kh vay vốn", "So_mon_vay": "Món vay",
                    "Tong_du_no": "Tổng dư nợ", "Du_no_trong_han": "Trong hạn",
                    "Du_no_qh": "Quá hạn", "Du_no_khoanh": "Khoanh", "TL_QH_pct": "TL QH (%)",
                    "Cho_vay_thang": "Cho vay", "Thu_no_thang": "Thu nợ",
                    "DN_dTTr": "Dư nợ Δ so tháng trước", "DN_dNY": "Dư nợ Δ so 31/12 năm trước",
                    "QH_dTTr": "QH Δ so tháng trước", "QH_dNY": "QH Δ so 31/12 năm trước",
                }
                _thu_tu_th = [
                    "STT", "Mã CBTD", "Họ tên", "PGD", "Kh vay vốn", "Món vay", "Tổng dư nợ",
                    "Trong hạn", "Quá hạn", "Khoanh", "Cho vay", "Thu nợ",
                    "Dư nợ Δ so tháng trước", "Dư nợ Δ so 31/12 năm trước",
                    "QH Δ so tháng trước", "QH Δ so 31/12 năm trước", "TL QH (%)",
                ]
                _rename_nqt = {
                    "STT": "STT", "Ma_CBTD": "Mã CBTD", "Ho_ten": "Họ tên", "PGD": "PGD",
                    "No_den_han_mon": "Món đến hạn",
                    "DH_dTTr": "Đến hạn Δ so tháng trước", "DH_dNY": "Đến hạn Δ so 31/12 năm trước",
                    "So_mon_3m_khd": "Món 3T KHĐ",
                    "K3_dTTr": "3T KHĐ Δ so tháng trước", "K3_dNY": "3T KHĐ Δ so 31/12 năm trước",
                    "So_mon_rui_ro": "Món rủi ro",
                    "RR_dTTr": "Rủi ro Δ so tháng trước", "RR_dNY": "Rủi ro Δ so 31/12 năm trước",
                }
                _df_th_x = pd.DataFrame()
                if not _df_th.empty:
                    _df_th_x = _df_th.rename(columns=_rename_th)
                    _df_th_x = _df_th_x[[c for c in _thu_tu_th if c in _df_th_x.columns]]
                _df_nqt_x = _df_nqt.rename(columns=_rename_nqt) if not _df_nqt.empty else pd.DataFrame()
                _xlsx = xuat_excel({
                    "Du_no_theo_CBTD": _df_th_x,
                    "No_can_quan_tam": _df_nqt_x,
                    "Chat_luong_To_TKVV": _bang_to,
                    "Thang_truoc": _df_ttr,
                    "3112_nam_truoc": _df_ntr,
                })
                _cl, _c2 = st.columns(2)
                with _cl:
                    st.download_button(
                        "⬇ Tải Excel tổng quan CBTD",
                        data=_xlsx,
                        file_name=f"Tong_quan_CBTD_{_thang:02d}_{_nam}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key=f"{_kp}tq_dl_xl",
                    )
                with _c2:
                    _df_pdf, _cols_tien, _cols_dem, _cols_pct = _chuan_bi_pdf_bang_du_no(_df_th_x)
                    _cols_dem_nqt = [
                        "Món đến hạn", "Món 3T KHĐ", "Món rủi ro",
                        "Đến hạn Δ so tháng trước", "Đến hạn Δ so 31/12 năm trước",
                        "3T KHĐ Δ so tháng trước", "3T KHĐ Δ so 31/12 năm trước",
                        "Rủi ro Δ so tháng trước", "Rủi ro Δ so 31/12 năm trước",
                    ]
                    _cols_dem_to = ["Tổng Tổ", "Tốt", "Khá", "TB", "Yếu", "Δ Tốt TTr", "Δ Tốt NTr"]
                    _cols_pct_to = ["% Tốt"]
                    if st.button("🖨️ In PDF tổng quan CBTD", key=f"{_kp}tq_btn_pdf", type="primary"):
                        try:
                            from components.export_pdf import xuat_pdf_co_chart
                            _pdf_bytes = xuat_pdf_co_chart(
                                _df_pdf,
                                tieu_de="TỔNG QUAN THEO CÁN BỘ TÍN DỤNG QUẢN LÝ ĐỊA BÀN",
                                nguoi_xuat=username or "system",
                                cols_tien=_cols_tien,
                                cols_dem=_cols_dem,
                                cols_percent=_cols_pct,
                                don_vi_tien="triệu đồng",
                                prefix_file="Tong_quan_CBTD",
                                # Bảng đã có dòng TỔNG với tỷ lệ QH gia quyền đúng.
                                them_dong_tong=False,
                                bang_phu=[
                                    {
                                        "tieu_de": "CỤM CHỈ TIÊU NỢ CẦN QUAN TÂM (MÓN)",
                                        "df": _df_nqt_x,
                                        "cols_dem": _cols_dem_nqt,
                                    },
                                    {
                                        "tieu_de": "CHẤT LƯỢNG TỔ TK&VV",
                                        "df": _bang_to,
                                        "cols_dem": _cols_dem_to,
                                        "cols_percent": _cols_pct_to,
                                    },
                                ],
                            )
                            if _pdf_bytes:
                                state.downloads.set("cbtd_tq_pdf", _pdf_bytes,
                                                    f"Tong_quan_CBTD_{datetime.today().strftime('%d%m%Y')}.pdf")
                                db.ghi_audit(username, "xuat_pdf_tong_quan_cbtd", f"so_dong={len(_df_pdf)}")
                                st.success("✅ Đã tạo PDF.")
                            else:
                                st.error("❌ Lỗi tạo PDF (thiếu reportlab?).")
                        except Exception as e:
                            st.error(f"❌ Lỗi tạo PDF: {e}")
                    if state.downloads.has("cbtd_tq_pdf"):
                        st.download_button(
                            "⬇ Tải file PDF",
                            data=state.downloads.get_bytes("cbtd_tq_pdf"),
                            file_name=state.downloads.get_filename("cbtd_tq_pdf") or "Tong_quan_CBTD.pdf",
                            mime="application/pdf",
                            key=f"{_kp}tq_dl_pdf",
                        )

        labels_final = list(labels_lv2)
        renderers_final = [
            _render_g1, _render_g2, _render_g3, _render_g4, _render_g5, _render_g6,
        ]
        _scope_slug = pgd_user.replace(" ", "_").lower() if pgd_user else "cn"
        lazy_tabs(labels_final, renderers_final, key=f"cbtd_lv2_{_scope_slug}")
