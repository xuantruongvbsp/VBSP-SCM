"""Unit tests cho services/cdtotkvv_service.py — Chấm điểm Tổ TK&VV."""
from __future__ import annotations

from io import BytesIO

import openpyxl
import pandas as pd

from config import DON_VI_CHI_NHANH
from data.cdtotkvv import doc_cdtotkvv_path, doc_thang_tu_cdto_toan_cn, tach_file_cdto_toan_cn
from services.cdtotkvv_service import (
    loc_df,
    cdtotkvv_ten_sheet_excel,
    fmt_xuat_to_khong_dat_vn,
)


class TestLocDf:
    def test_df_None(self):
        df = loc_df(None, "cn", "")
        assert df is None

    def test_df_trong(self):
        df = loc_df(pd.DataFrame(), "cn", "")
        assert df.empty

    def test_mode_cn_tra_ve_toan_bo(self):
        df_in = pd.DataFrame({"ten_dv": ["PGD A", "PGD B"]})
        df_out = loc_df(df_in, "cn", "PGD A")
        assert len(df_out) == 2

    def test_mode_pgd_loc_theo_ten(self):
        df_in = pd.DataFrame({"ten_dv": ["PGD A", "PGD B"]})
        df_out = loc_df(df_in, "pgd", "PGD B")
        assert len(df_out) == 1
        assert df_out.iloc[0]["ten_dv"] == "PGD B"

    def test_mode_pgd_khong_khop(self):
        df_in = pd.DataFrame({"ten_dv": ["PGD A"]})
        df_out = loc_df(df_in, "pgd", "PGD X")
        assert df_out.empty

    def test_mode_pgd_loc_theo_ma_khi_khong_co_ten(self):
        df_in = pd.DataFrame({"ma_dv": ["pgd_a", "pgd_b"]})
        df_out = loc_df(df_in, "pgd", "pgd_a")
        assert len(df_out) == 1

    def test_mode_pgd_khong_pgd_user(self):
        df_in = pd.DataFrame({"ten_dv": ["PGD A"]})
        df_out = loc_df(df_in, "pgd", "")
        assert len(df_out) == 1


class TestCdtotkvvTenSheetExcel:
    def test_ten_don_gian(self):
        da_dung = set()
        ten = cdtotkvv_ten_sheet_excel("PGD A - Tổ 1", da_dung)
        assert len(ten) <= 31
        assert ten in da_dung

    def test_ky_tu_cam(self):
        da_dung = set()
        ten = cdtotkvv_ten_sheet_excel("Tổ [1]: A/B\\C", da_dung)
        assert "[" not in ten
        assert ":" not in ten
        assert "/" not in ten
        assert "\\" not in ten

    def test_trung_thi_danh_so(self):
        da_dung = set()
        t1 = cdtotkvv_ten_sheet_excel("PGD A", da_dung)
        t2 = cdtotkvv_ten_sheet_excel("PGD A", da_dung)
        assert t1 != t2
        assert "_1" in t2 or t1.endswith("_")

    def test_ten_dai_cat_bot(self):
        da_dung = set()
        ten = cdtotkvv_ten_sheet_excel("A" * 40, da_dung)
        assert len(ten) <= 31

    def test_ten_toan_ky_tu_cam(self):
        da_dung = set()
        ten = cdtotkvv_ten_sheet_excel("[/:*]", da_dung)
        assert len(ten) > 0
        assert ten not in {"", "/", "\\"}


class TestFmtXuatToKhongDatVn:
    def test_co_du_no_va_diem(self):
        df_in = pd.DataFrame({
            "Dư nợ": [1234567, 0],
            "Số dư TK": [500000, 100000],
            "Điểm đạt được": [85, 90],
            "Điểm tối đa": [100, 100],
            "Tổng điểm": [85, 90],
        })
        df_out = fmt_xuat_to_khong_dat_vn(df_in)
        assert df_out["Dư nợ"].iloc[0] == "1.234.567"
        assert df_out["Điểm đạt được"].iloc[0] == "85"

    def test_cot_ko_co_van_chay(self):
        df_in = pd.DataFrame({"A": [1]})
        df_out = fmt_xuat_to_khong_dat_vn(df_in)
        assert len(df_out) == 1


def _build_cdto_toan_cn_bytes(leading_blank: bool) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["BÁO CÁO CDTOTKVV"])
    ws.append(["Kỳ chấm điểm tháng 05/2026"])
    ws.append([])
    ws.append([])
    ws.append([])
    ws.append([])
    ws.append([])
    header = [
        "STT",
        "Mã PGD",
        "Tên PGD",
        "Mã xã",
        "Tên xã",
        "Mã tổ",
        "Tên tổ trưởng",
        "Loại tổ",
        "ĐVUT",
        "Dư nợ",
        "Tham gia GDX",
        "TL thu nợ gốc",
        "TL thu lãi",
        "TG Tổ TKVV",
        "TL nợ quá hạn",
        "Tổng điểm",
        "Xếp loại",
        "NGAYBC",
    ]
    row = [
        1,
        "004601",
        DON_VI_CHI_NHANH,
        "460001",
        "Xã A",
        "T01",
        "Nguyễn Văn A",
        "Tổ tốt",
        "Hội Phụ nữ",
        100_000_000,
        10,
        10,
        10,
        10,
        10,
        95,
        "Tốt",
        "31/05/2026",
    ]
    if leading_blank:
        header = [None] + header
        row = [None] + row
    ws.append(header)
    ws.append(row)

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


class TestCdtotkvvToanCnParser:
    def test_tach_file_nhan_dien_duoc_khi_khong_co_cot_trong_dau(self):
        file_bytes = _build_cdto_toan_cn_bytes(leading_blank=False)

        pgd_map = tach_file_cdto_toan_cn(file_bytes)

        assert DON_VI_CHI_NHANH in pgd_map
        assert isinstance(pgd_map[DON_VI_CHI_NHANH], bytes)

    def test_doc_thang_tu_file_toan_cn_khi_lech_cot(self):
        file_bytes = _build_cdto_toan_cn_bytes(leading_blank=False)

        thang = doc_thang_tu_cdto_toan_cn(file_bytes)

        assert thang == "05/2026"

    def test_tach_file_khong_bat_nham_cot_ma_don_vi_khac(self):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["BÁO CÁO CDTOTKVV"])
        ws.append(["Kỳ chấm điểm tháng 05/2026"])
        for _ in range(5):
            ws.append([])
        ws.append([
            "STT",
            "Mã đơn vị",
            "Tên đơn vị",
            "Mã PGD",
            "Tên PGD",
            "Mã xã",
            "Tên xã",
            "Mã tổ",
            "Tên tổ trưởng",
            "Loại tổ",
            "ĐVUT",
            "Dư nợ",
            "Tổng điểm",
            "Xếp loại",
            "NGAYBC",
        ])
        ws.append([1, "999999", "ĐVUT A", "004601", DON_VI_CHI_NHANH, "001", "Xã A", "T01", "A", "Tổ tốt", "Hội PN", 1, 90, "Tốt", "31/05/2026"])
        ws.append([2, "999999", "ĐVUT A", "004602", "PGD Long Thành", "002", "Xã B", "T02", "B", "Tổ tốt", "Hội ND", 1, 91, "Tốt", "31/05/2026"])

        buf = BytesIO()
        wb.save(buf)

        pgd_map = tach_file_cdto_toan_cn(buf.getvalue())

        assert DON_VI_CHI_NHANH in pgd_map
        assert "PGD Long Thành" in pgd_map
        assert len(pgd_map) == 2

    def test_tach_file_doc_lai_dung_cot_cho_ca_layout_cu_va_moi(self, tmp_path):
        for leading_blank in (False, True):
            file_bytes = _build_cdto_toan_cn_bytes(leading_blank=leading_blank)
            pgd_map = tach_file_cdto_toan_cn(file_bytes)
            path = tmp_path / f"cdtotkvv_{leading_blank}.xlsx"
            path.write_bytes(pgd_map[DON_VI_CHI_NHANH])

            df = doc_cdtotkvv_path(str(path), 1)

            assert df is not None
            assert len(df) == 1
            row = df.iloc[0]
            assert row["ma_dv"] == "004601"
            assert row["ten_dv"] == DON_VI_CHI_NHANH
            assert row["ma_xa"] == "460001"
            assert row["ten_xa"] == "Xã A"
            assert row["ma_to"] == "T01"
            assert row["ten_to_truong"] == "Nguyễn Văn A"
            assert row["dvut"] == "Hội Phụ nữ"
            assert row["loai_to"] == "Tổ tốt"
            assert row["du_no"] == 100_000_000
            assert row["tong_diem"] == 95
            assert row["xep_loai"] == "Tốt"
