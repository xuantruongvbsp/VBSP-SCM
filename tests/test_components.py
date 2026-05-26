"""tests/test_components.py — Test các pure functions trong components.

Tất cả các hàm được test đều là pure functions (không phụ thuộc Streamlit runtime).
"""
from __future__ import annotations

import pandas as pd
import pytest


# ══════════════════════════════════════════════════════════════════════════════
# delta_card._fmt_vn_num()
# ══════════════════════════════════════════════════════════════════════════════

class TestFmtVnNum:
    def test_so_nguyen_dung_dau_phay_vn(self):
        from components.delta_card import _fmt_vn_num
        assert _fmt_vn_num(1000) == "1.000"
        assert _fmt_vn_num(1234567) == "1.234.567"
        assert _fmt_vn_num(0) == "0"

    def test_so_thuc_2_so_le(self):
        from components.delta_card import _fmt_vn_num
        assert _fmt_vn_num(1234.56) == "1.234,56"
        assert _fmt_vn_num(0.12) == "0,12"

    def test_so_thuc_nguyen_khong_thua_so_le(self):
        from components.delta_card import _fmt_vn_num
        assert _fmt_vn_num(5000.0) == "5.000"

    def test_chuoi_truyen_thang(self):
        from components.delta_card import _fmt_vn_num
        assert _fmt_vn_num("abc") == "abc"
        assert _fmt_vn_num("1.234") == "1.234"

    def test_so_am(self):
        from components.delta_card import _fmt_vn_num
        assert _fmt_vn_num(-1000) == "-1.000"


# ══════════════════════════════════════════════════════════════════════════════
# movers._pick_dim_col()
# ══════════════════════════════════════════════════════════════════════════════

class TestPickDimCol:
    def test_pgd_tra_ve_cot_ten_pgd(self):
        from components.movers import _pick_dim_col
        from config import COT_TEN_PGD
        result = _pick_dim_col("pgd")
        assert result == COT_TEN_PGD

    def test_xa_tra_ve_cot_ten_xa(self):
        from components.movers import _pick_dim_col
        from config import COT_TEN_XA
        result = _pick_dim_col("xa")
        assert result == COT_TEN_XA

    def test_chuong_trinh_tra_ve_cot_ten_ct(self):
        from components.movers import _pick_dim_col
        from config import COT_TEN_CT
        result = _pick_dim_col("chuongtrinh")
        assert result == COT_TEN_CT

    def test_khoa_khong_ton_tai_tra_none(self):
        from components.movers import _pick_dim_col
        assert _pick_dim_col("abc_xyz") is None
        assert _pick_dim_col("") is None

    def test_tung_khoa_hop_le_deu_tra_ve_cot(self):
        from components.movers import _pick_dim_col
        for key in ["pgd", "xa", "chuongtrinh", "to", "dvut"]:
            assert _pick_dim_col(key) is not None, f"Key '{key}' phải trả về cột"


# ══════════════════════════════════════════════════════════════════════════════
# movers._format_value()
# ══════════════════════════════════════════════════════════════════════════════

class TestFormatValue:
    def test_tien_hien_don_vi_trieu(self):
        from components.movers import _format_value
        result = _format_value(1_500_000_000, "tien")
        assert "1.500" in result

    def test_ty_le_dung_fmt_ty(self):
        from components.movers import _format_value
        result = _format_value(0.05, "ty_le")
        assert result in ("0,05", "0.05") or "0" in result

    def test_khac_tra_ve_fmt_so(self):
        from components.movers import _format_value
        result = _format_value(1234567, "khac")
        assert "." in result


# ══════════════════════════════════════════════════════════════════════════════
# loan_drawer._render_field()
# ══════════════════════════════════════════════════════════════════════════════

class TestRenderField:
    def test_chuoi_thong_thuong(self):
        from components.loan_drawer import _render_field
        html = _render_field("Họ tên", "Nguyễn Văn A")
        assert "Nguyễn Văn A" in html
        assert "Họ tên" in html

    def test_tien_format(self):
        from components.loan_drawer import _render_field
        html = _render_field("Dư nợ", 50000000, fmt="tien")
        assert "50,000,000 đ" in html

    def test_phan_tram_format(self):
        from components.loan_drawer import _render_field
        html = _render_field("Tỷ lệ NQH", 5.23, fmt="pct")
        assert "5.23%" in html

    def test_gia_tri_none(self):
        from components.loan_drawer import _render_field
        html = _render_field("Ghi chú", None)
        assert "—" in html

    def test_gia_tri_nan(self):
        from components.loan_drawer import _render_field
        html = _render_field("Ghi chú", float("nan"))
        assert "—" in html

    def test_tien_khong_parse_duoc(self):
        from components.loan_drawer import _render_field
        html = _render_field("Dư nợ", "abc", fmt="tien")
        assert "abc" in html

    def test_pct_khong_parse_duoc(self):
        from components.loan_drawer import _render_field
        html = _render_field("Tỷ lệ", "abc", fmt="pct")
        assert "abc" in html

    def test_so_0(self):
        from components.loan_drawer import _render_field
        html = _render_field("Dư nợ", 0, fmt="tien")
        assert "0 đ" in html


# ══════════════════════════════════════════════════════════════════════════════
# Tongquan service — loc_du_no_duong
# ══════════════════════════════════════════════════════════════════════════════

class TestLocDuNoDuong:
    def test_loc_ra_chi_du_no_duong(self):
        from services.tongquan_service import loc_du_no_duong
        from config import COT_TONG_DU_NO
        df = pd.DataFrame({COT_TONG_DU_NO: [100, 200, 0]})
        result = loc_du_no_duong(df, COT_TONG_DU_NO)
        assert len(result) == 2

    def test_cot_rong_tra_df_goc(self):
        from services.tongquan_service import loc_du_no_duong
        df = pd.DataFrame({"A": [1, 2, 3]})
        result = loc_du_no_duong(df, "B")
        assert len(result) == 3

    def test_df_rong_tra_df_rong(self):
        from services.tongquan_service import loc_du_no_duong
        df = pd.DataFrame()
        result = loc_du_no_duong(df, "X")
        assert result.empty


# ══════════════════════════════════════════════════════════════════════════════
# Tongquan service — chuan_hoa_ngay
# ══════════════════════════════════════════════════════════════════════════════

class TestChuanHoaNgay:
    def test_cot_datetime_giu_nguyen(self):
        from services.tongquan_service import chuan_hoa_ngay
        import pandas as pd
        from datetime import datetime
        df = pd.DataFrame({"ngay": [datetime(2026, 5, 26)]})
        result = chuan_hoa_ngay(df, "ngay")
        assert pd.api.types.is_datetime64_any_dtype(result["ngay"])

    def test_cot_string_chuyen_duoc(self):
        from services.tongquan_service import chuan_hoa_ngay
        import pandas as pd
        df = pd.DataFrame({"ngay": ["26/05/2026"]})
        result = chuan_hoa_ngay(df, "ngay")
        assert pd.api.types.is_datetime64_any_dtype(result["ngay"])

    def test_cot_khong_ton_tai_tra_nguyen(self):
        from services.tongquan_service import chuan_hoa_ngay
        import pandas as pd
        df = pd.DataFrame({"A": [1, 2]})
        result = chuan_hoa_ngay(df, "ngay")
        assert list(result.columns) == ["A"]
