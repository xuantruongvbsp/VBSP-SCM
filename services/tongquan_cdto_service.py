"""
Dịch vụ load & tính KPI CDTOTKVV toàn Chi nhánh — dùng chung cho tab Tổng quan và tab CDTOTKVV.

Các hàm công khai:
  load_cdto_toan_cn()      — load dữ liệu CDTOTKVV toàn CN (chuỗi ưu tiên)
  compute_totkvv_kpi()     — tính KPI từ DataFrame raw
  render_totkvv_html()     — trả về HTML string card Xếp loại Tổ TK&VV
  health_check_cdto()      — kiểm tra nhanh trạng thái CDTOTKVV toàn CN
"""

from __future__ import annotations

import pandas as pd

from config import DS_PGD
from utils import fmt_so, vn

try:
    from logger import get_logger
    logger = get_logger(__name__)
except Exception:
    import logging
    logger = logging.getLogger(__name__)


def load_cdto_toan_cn() -> dict:
    """
    Load dữ liệu CDTOTKVV toàn Chi nhánh theo chuỗi ưu tiên:
      1. ds_thang_nam() → doc_cdtotkvv(tháng) cho từng tháng gần nhất
      2. Fallback: tong_hop_tu_pgd_data() (latest từ pgd_data/)

    Returns:
        {
            "df_raw":      pd.DataFrame | None,  # dữ liệu thô toàn CN
            "thang_hien":  str | None,            # "MM/YYYY"
            "so_pgd_co":   int,                   # số PGD đã có dữ liệu
            "so_pgd_thieu": int,                  # số PGD còn thiếu
            "ds_pgd_thieu": list[str],            # danh sách tên PGD thiếu
            "co_du_lieu":  bool,                  # có ít nhất 1 dòng dữ liệu
            "kpi":         dict | None,           # KPI đã tính sẵn (None nếu không có dữ liệu)
        }
    """
    from data.cdtotkvv import doc_cdtotkvv, ds_thang_nam

    df_raw = None
    thang_hien = None

    ds_thang = ds_thang_nam()
    if ds_thang:
        for _thang in ds_thang:
            _df = doc_cdtotkvv(_thang)
            if _df is not None and not _df.empty:
                df_raw = _df
                thang_hien = _thang
                break

    if df_raw is None or df_raw.empty:
        from services.cdtotkvv_service import tong_hop_tu_pgd_data
        df_raw = tong_hop_tu_pgd_data()
        thang_hien = None

    so_pgd_co = 0
    so_pgd_thieu = 0
    ds_pgd_thieu: list[str] = []

    if df_raw is not None and not df_raw.empty and "ten_dv" in df_raw.columns:
        pgd_da_co = set(df_raw["ten_dv"].dropna().astype(str).unique())
        ds_pgd_thieu = sorted(set(DS_PGD) - pgd_da_co)
        so_pgd_co = len(pgd_da_co)
        so_pgd_thieu = len(ds_pgd_thieu)

    return {
        "df_raw": df_raw,
        "thang_hien": thang_hien,
        "so_pgd_co": so_pgd_co,
        "so_pgd_thieu": so_pgd_thieu,
        "ds_pgd_thieu": ds_pgd_thieu,
        "co_du_lieu": df_raw is not None and not df_raw.empty,
        "kpi": compute_totkvv_kpi(df_raw) if (df_raw is not None and not df_raw.empty) else None,
    }


def compute_totkvv_kpi(df_raw: pd.DataFrame) -> dict:
    """
    Tính KPI từ DataFrame CDTOTKVV thô.

    Returns:
        {
            "tong_to":   int,
            "to_tot":    int,
            "to_kha":    int,
            "to_tb":     int,
            "to_yeu":    int,
            "tl_tot":    float,
            "tl_kha":    float,
            "tl_tb":     float,
            "tl_yeu":    float,
            "diem_tb":   float,
        }
    """
    from data.cdtotkvv import tong_hop_theo_pgd

    th = tong_hop_theo_pgd(df_raw)
    tong_to = int(th["tong_to"].sum())
    to_tot = int(th["to_tot"].sum())
    to_kha = int(th.get("to_kha", pd.Series([0])).sum())
    to_tb = int(th.get("to_tb", pd.Series([0])).sum())
    to_yeu = int(th["to_yeu"].sum())

    tl_tot = (to_tot / tong_to * 100) if tong_to else 0.0
    tl_kha = (to_kha / tong_to * 100) if tong_to else 0.0
    tl_tb = (to_tb / tong_to * 100) if tong_to else 0.0
    tl_yeu = (to_yeu / tong_to * 100) if tong_to else 0.0

    diem_tb = round(float(df_raw["tong_diem"].mean()), 2) if "tong_diem" in df_raw.columns else 0.0

    return {
        "tong_to": tong_to,
        "to_tot": to_tot,
        "to_kha": to_kha,
        "to_tb": to_tb,
        "to_yeu": to_yeu,
        "tl_tot": tl_tot,
        "tl_kha": tl_kha,
        "tl_tb": tl_tb,
        "tl_yeu": tl_yeu,
        "diem_tb": diem_tb,
    }


def render_totkvv_html(kpi: dict, thang_hien: str | None = None, ten_don_vi: str = "toàn Chi nhánh") -> str:
    """
    Trả về HTML string cho card Xếp loại Tổ TK&VV.
    Gọi từ st.markdown(..., unsafe_allow_html=True).
    """
    tong_to = kpi["tong_to"]
    _tong_to = fmt_so(tong_to)
    _to_tot = fmt_so(kpi["to_tot"])
    _to_kha = fmt_so(kpi["to_kha"])
    _to_tb = fmt_so(kpi["to_tb"])
    _to_yeu = fmt_so(kpi["to_yeu"])
    _tl_tot = vn(kpi["tl_tot"], 1)
    _tl_kha = vn(kpi["tl_kha"], 1)
    _tl_tb = vn(kpi["tl_tb"], 1)
    _tl_yeu = vn(kpi["tl_yeu"], 1)

    chip_text = f"Tháng {thang_hien}" if thang_hien else "Dữ liệu tổng hợp"

    return f"""
<div class="totkvv-wrap">
    <div class="totkvv-head">
        <div class="totkvv-title">Xếp loại Tổ TK&amp;VV {ten_don_vi}</div>
        <div class="totkvv-chip">{chip_text}</div>
    </div>
    <div class="totkvv-grid">
        <div class="totkvv-item tot-a">
            <div class="v">{_tong_to}</div>
            <div class="l">Tổng Tổ</div>
        </div>
        <div class="totkvv-item tot-b">
            <div class="v">{_to_tot}</div>
            <div class="l">Tốt · <span class="s">{_tl_tot}%</span></div>
        </div>
        <div class="totkvv-item tot-c">
            <div class="v">{_to_kha}</div>
            <div class="l">Khá · <span class="s">{_tl_kha}%</span></div>
        </div>
        <div class="totkvv-item tot-d">
            <div class="v">{_to_tb}</div>
            <div class="l">Trung bình · <span class="s">{_tl_tb}%</span></div>
        </div>
        <div class="totkvv-item tot-e">
            <div class="v">{_to_yeu}</div>
            <div class="l">Yếu · <span class="s">{_tl_yeu}%</span></div>
        </div>
    </div>
</div>
"""


def health_check_cdto() -> dict:
    """
    Kiểm tra nhanh trạng thái CDTOTKVV toàn CN.
    Trả về dict để hiển thị badge trạng thái.

    Returns:
        {
            "co_du_lieu": bool,
            "so_pgd_co": int,
            "so_pgd_thieu": int,
            "ds_pgd_thieu": list[str],
            "thang_hien": str | None,
        }
    """
    result = load_cdto_toan_cn()
    return {
        "co_du_lieu": result["co_du_lieu"],
        "so_pgd_co": result["so_pgd_co"],
        "so_pgd_thieu": result["so_pgd_thieu"],
        "ds_pgd_thieu": result["ds_pgd_thieu"],
        "thang_hien": result["thang_hien"],
    }
