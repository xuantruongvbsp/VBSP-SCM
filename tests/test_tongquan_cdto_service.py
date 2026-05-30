"""Unit tests cho services/tongquan_cdto_service.py — Tổng quan CDTOTKVV."""
from __future__ import annotations

import pandas as pd

from services.tongquan_cdto_service import (
    compute_totkvv_kpi,
    render_totkvv_html,
    health_check_cdto,
)


class TestComputeTotkvvKpi:
    def test_tong_to_dung(self):
        df = pd.DataFrame({
            "stt": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            "ma_dv": ["004601"] * 5 + ["004602"] * 5,
            "ten_dv": ["PGD A"] * 5 + ["PGD B"] * 5,
            "xep_loai": ["Tốt", "Tốt", "Tốt", "Khá", "Khá",
                         "Trung bình", "Trung bình", "Yếu", "Yếu", "Yếu"],
            "tong_diem": [95, 93, 91, 85, 82, 75, 73, 65, 60, 55],
        })
        kpi = compute_totkvv_kpi(df)
        assert kpi["tong_to"] == 10
        assert kpi["to_tot"] == 3
        assert kpi["to_kha"] == 2
        assert kpi["to_tb"] == 2
        assert kpi["to_yeu"] == 3
        assert abs(kpi["tl_tot"] - 30.0) < 0.01
        assert abs(kpi["tl_kha"] - 20.0) < 0.01
        assert abs(kpi["tl_tb"] - 20.0) < 0.01
        assert abs(kpi["tl_yeu"] - 30.0) < 0.01
        assert abs(kpi["diem_tb"] - 76.7) < 0.5

    def test_empty_dataframe(self):
        df = pd.DataFrame(columns=["stt", "ma_dv", "ten_dv", "xep_loai", "tong_diem"])
        kpi = compute_totkvv_kpi(df)
        assert kpi["tong_to"] == 0
        assert kpi["to_tot"] == 0
        assert kpi["tl_tot"] == 0.0

    def test_missing_to_kha_co_lumn(self):
        df = pd.DataFrame({
            "stt": [1, 2],
            "ma_dv": ["004601", "004601"],
            "ten_dv": ["PGD A", "PGD A"],
            "xep_loai": ["Tốt", "Tốt"],
            "tong_diem": [90, 92],
        })
        kpi = compute_totkvv_kpi(df)
        assert kpi["to_kha"] == 0

    def test_no_tong_diem_co_lumn(self):
        df = pd.DataFrame({
            "stt": [1],
            "ma_dv": ["004601"],
            "ten_dv": ["PGD A"],
            "xep_loai": ["Tốt"],
        })
        kpi = compute_totkvv_kpi(df)
        assert kpi["diem_tb"] == 0.0


class TestRenderTotkvvHtml:
    def test_html_chua_du_5_loai(self):
        kpi = {
            "tong_to": 100,
            "to_tot": 40,
            "to_kha": 30,
            "to_tb": 20,
            "to_yeu": 10,
            "tl_tot": 40.0,
            "tl_kha": 30.0,
            "tl_tb": 20.0,
            "tl_yeu": 10.0,
            "diem_tb": 82.5,
        }
        html = render_totkvv_html(kpi, "05/2026")
        assert "Tốt" in html
        assert "Khá" in html
        assert "Trung bình" in html
        assert "Yếu" in html
        assert "Tổng Tổ" in html
        assert "Tháng 05/2026" in html

    def test_html_khong_thang(self):
        kpi = {
            "tong_to": 1,
            "to_tot": 1, "to_kha": 0, "to_tb": 0, "to_yeu": 0,
            "tl_tot": 100.0, "tl_kha": 0.0, "tl_tb": 0.0, "tl_yeu": 0.0,
            "diem_tb": 95.0,
        }
        html = render_totkvv_html(kpi, None)
        assert "Dữ liệu tổng hợp" in html

    def test_html_so_0(self):
        kpi = {
            "tong_to": 0, "to_tot": 0, "to_kha": 0, "to_tb": 0, "to_yeu": 0,
            "tl_tot": 0.0, "tl_kha": 0.0, "tl_tb": 0.0, "tl_yeu": 0.0,
            "diem_tb": 0.0,
        }
        html = render_totkvv_html(kpi)
        assert "0" in html


class TestHealthCheckCdto:
    def test_tra_ve_dict_hop_le(self):
        hc = health_check_cdto()
        assert isinstance(hc, dict)
        assert "co_du_lieu" in hc
        assert "so_pgd_co" in hc
        assert "so_pgd_thieu" in hc
        assert "ds_pgd_thieu" in hc
        assert "thang_hien" in hc
