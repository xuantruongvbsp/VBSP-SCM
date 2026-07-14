"""Tests cho PDF báo cáo và PDF điều hành Ủy thác."""
from __future__ import annotations

from io import BytesIO

import pandas as pd
import pdfplumber

from services.uy_thac_pdf_service import (
    tao_pdf_bao_cao_dang_xem,
    tao_pdf_dieu_hanh_uy_thac,
)


def _payload_mau() -> dict[str, object]:
    tong_quan = {
        "so_to": 125,
        "so_kh": 4_832,
        "tong_dn": 824_500_000_000,
        "ty_le_nqh": 0.42,
        "so_to_nqh": 5,
        "so_to_lai_ton": 8,
        "lai_ton": 1_635_000_000,
        "so_du_tg": 41_200_000_000,
    }
    theo_hoi = pd.DataFrame({
        "Hội đoàn thể": ["Hội Liên hiệp Phụ nữ", "Hội Nông dân"],
        "Số Tổ": [70, 55],
        "Số KH": [2_800, 2_032],
        "Dư nợ (triệu đồng)": [500_000_000_000, 324_500_000_000],
        "NQH (triệu đồng)": [1_500_000_000, 1_960_000_000],
        "Lãi tồn (triệu đồng)": [900_000_000, 735_000_000],
        "Tỷ lệ NQH": [0.30, 0.60],
    })
    dieu_hanh_pgd = pd.DataFrame({
        "PGD": ["PGD khu vực 1", "PGD khu vực 2"],
        "Số Tổ": [60, 65],
        "Số KH": [2_300, 2_532],
        "Dư nợ (triệu đồng)": [400_000_000_000, 424_500_000_000],
        "NQH (triệu đồng)": [1_200_000_000, 2_260_000_000],
        "Lãi tồn (triệu đồng)": [600_000_000, 1_035_000_000],
        "Số Tổ có NQH": [2, 3],
        "Số Tổ có lãi tồn": [3, 5],
        "Tỷ lệ NQH": [0.30, 0.53],
    })
    diem_nong_xa = pd.DataFrame({
        "PGD": ["PGD khu vực 2"],
        "Xã/Phường": ["Xã Long Thành"],
        "Dư nợ (triệu đồng)": [50_000_000_000],
        "NQH (triệu đồng)": [500_000_000],
        "Lãi tồn (triệu đồng)": [200_000_000],
        "Tỷ lệ NQH": [1.0],
    })
    diem_nong_to = pd.DataFrame({
        "PGD": ["PGD khu vực 2"],
        "Xã/Phường": ["Xã Long Thành"],
        "Hội đoàn thể": ["Hội Nông dân"],
        "Tổ TK&VV": ["Tổ 01"],
        "NQH (triệu đồng)": [120_000_000],
        "Lãi tồn (triệu đồng)": [50_000_000],
    })
    canh_bao = pd.DataFrame({
        "Mức độ": ["Cao", "Cần kiểm tra"],
        "Nhóm cảnh báo": ["Nợ quá hạn", "Tổ đa hội"],
        "Đơn vị/Đối tượng": ["PGD khu vực 2", "PGD khu vực 1 - Tổ 02"],
        "Giá trị": [2_260_000_000, 2],
        "Tỷ lệ (%)": [0.53, 0],
        "Hành động đề xuất": ["Rà soát kế hoạch thu hồi", "Kiểm tra Hội nhận ủy thác"],
    })
    to_da_hoi = pd.DataFrame({
        "PGD": ["PGD khu vực 1"],
        "Xã/Phường": ["Xã Trảng Bom"],
        "Tổ TK&VV": ["Tổ 02"],
        "Số Hội": [2],
        "Các Hội xuất hiện trong HSTD": ["Hội Nông dân · Hội Liên hiệp Phụ nữ"],
    })
    bien_dong = pd.DataFrame({
        "Kỳ": ["2026-05", "2026-06"],
        "Tổng dư nợ (triệu đồng)": [800_000_000_000, 824_500_000_000],
        "NQH (triệu đồng)": [3_200_000_000, 3_460_000_000],
        "Tỷ lệ NQH": [0.40, 0.42],
        "Lãi tồn (triệu đồng)": [1_500_000_000, 1_635_000_000],
        "Số Tổ": [120, 125],
    })
    return {
        "tong_quan": tong_quan,
        "theo_hoi": theo_hoi,
        "dieu_hanh_pgd": dieu_hanh_pgd,
        "diem_nong_xa": diem_nong_xa,
        "diem_nong_to": diem_nong_to,
        "canh_bao": canh_bao,
        "to_da_hoi": to_da_hoi,
        "bien_dong": bien_dong,
    }


def test_tao_pdf_bao_cao_dang_xem_dung_don_vi_trieu() -> None:
    payload = _payload_mau()
    pdf_bytes = tao_pdf_bao_cao_dang_xem(
        df=payload["dieu_hanh_pgd"],
        ten_bao_cao="Điều hành theo PGD",
        tong_quan=payload["tong_quan"],
        pham_vi="Toàn Chi nhánh",
        ngay_so_lieu="30/06/2026",
        nguoi_xuat="tester",
        bo_loc=["Hội đoàn thể: Tất cả"],
    )

    assert pdf_bytes.startswith(b"%PDF")
    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    assert "THEO PGD" in text
    assert "400.000" in text
    assert "400.000.000.000" not in text


def test_tao_pdf_dieu_hanh_co_du_cac_phan_va_nhieu_trang() -> None:
    payload = _payload_mau()
    pdf_bytes = tao_pdf_dieu_hanh_uy_thac(
        pham_vi="Toàn Chi nhánh",
        ngay_so_lieu="30/06/2026",
        nguoi_xuat="tester",
        bo_loc=[],
        **payload,
    )

    assert pdf_bytes.startswith(b"%PDF")
    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        assert len(pdf.pages) >= 8
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    assert "Nhận định điều hành" in text
    assert "Cảnh báo trọng điểm" in text
    assert "Tổ xuất hiện ở nhiều Hội" in text
    assert "2026-06" in text
    assert "Hành động đề xuất" in text
