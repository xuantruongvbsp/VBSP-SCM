from __future__ import annotations

from datetime import date

import pandas as pd

from config import (
    COT_DU_NO_QH,
    COT_DVUT,
    COT_LAI_TON,
    COT_MUC_VAY,
    COT_SO_DU_TG,
    COT_SO_KU,
    COT_TEN_CT,
    COT_TEN_KH,
    COT_TEN_TO,
    COT_TEN_XA,
    COT_TONG_DU_NO,
)
from services.template_service import (
    tao_word_uythac_bb_ct_cx,
    tao_word_uythac_bb_xac_minh,
    tao_word_uythac_bc_th,
    tao_word_uythac_ke_hoach,
    tao_word_uythac_mau06,
    tao_word_uythac_mau15,
    tao_word_uythac_mau16,
)


def _assert_docx_bytes(b: bytes) -> None:
    assert isinstance(b, (bytes, bytearray))
    assert len(b) > 200
    assert bytes(b[:2]) == b"PK"


def test_tao_word_uythac_ke_hoach_smoke() -> None:
    du_lieu = {
        "don_vi_kt": "HỘI NÔNG DÂN",
        "so_vb": "01/KH-HND",
        "dia_danh": "Biên Hòa",
        "nam_kh": 2026,
        "ngay_ky": date.today(),
        "muc_dich": "Mục đích kiểm tra",
        "yeu_cau": "Yêu cầu kiểm tra",
        "noi_dung_kt": "Nội dung kiểm tra",
        "thanh_phan": "Thành phần",
        "noi_dung_gs": "Nội dung giám sát",
        "phan_cong_gs": "Phân công",
        "to_chuc": "Tổ chức thực hiện",
        "chu_tich": "Nguyễn Văn A",
    }
    ds_to = [
        {COT_DVUT: "Hội nông dân", COT_TEN_XA: "Xã A", COT_TEN_TO: "Tổ 1"},
        {COT_DVUT: "Hội nông dân", COT_TEN_XA: "Xã B", COT_TEN_TO: "Tổ 2"},
    ]
    b = tao_word_uythac_ke_hoach(du_lieu, ds_to)
    _assert_docx_bytes(b)


def test_tao_word_uythac_mau06_smoke() -> None:
    df = pd.DataFrame(
        [
            {
                COT_TEN_KH: "Trần Thị B",
                COT_SO_KU: "KU001",
                COT_TEN_CT: "HSSV",
                COT_MUC_VAY: 50_000_000,
                COT_TONG_DU_NO: 45_000_000,
                "Mục đích sử dụng vốn vay": "Chăn nuôi",
                "Nợ lãi": 0,
                COT_SO_DU_TG: 0,
            }
        ]
    )
    du_lieu = {
        "don_vi_kt": "Hội nông dân",
        "can_bo_1": "CB1",
        "chuc_vu_1": "Chức vụ 1",
        "can_bo_2": "CB2",
        "chuc_vu_2": "Chức vụ 2",
        "dia_ban": "Xã A",
        "ten_to": "Tổ 1",
        "ngay_kt": date.today(),
        "nhan_xet_chung": "",
        "so_kh_dung": "",
        "so_tien_dung": "",
        "ty_trong_dung": "",
        "so_kh_sai": "",
        "so_tien_sai": "",
        "ty_trong_sai": "",
        "bien_phap": "",
    }
    b = tao_word_uythac_mau06(du_lieu, df, loai="06")
    _assert_docx_bytes(b)


def test_tao_word_uythac_mau15_smoke() -> None:
    df = pd.DataFrame(
        [
            {
                COT_TEN_KH: "Nguyễn Văn C",
                COT_TEN_CT: "GQVL",
                COT_SO_KU: "KU002",
                COT_TONG_DU_NO: 12_000_000,
                "Nợ lãi": 200_000,
                COT_SO_DU_TG: 1_000_000,
            }
        ]
    )
    du_lieu = {
        "pgd": "PGD Long Thành",
        "ten_xa": "Xã A",
        "ten_to": "Tổ 1",
        "to_truong": "Tổ trưởng",
        "ma_to": "T01",
        "dia_chi": "Ấp 1",
        "can_bo_kt": "CBKT",
        "ngay_chot": date.today(),
    }
    b = tao_word_uythac_mau15(du_lieu, df)
    _assert_docx_bytes(b)


def test_tao_word_uythac_mau16_smoke() -> None:
    df = pd.DataFrame(
        [
            {
                COT_TEN_KH: "Nguyễn Văn D",
                COT_TONG_DU_NO: 20_000_000,
                COT_DU_NO_QH: 0,
                COT_LAI_TON: 0,
                COT_SO_DU_TG: 0,
            }
        ]
    )
    du_lieu = {
        "don_vi_kt": "NHCSXH",
        "ten_xa": "Xã A",
        "ten_thon": "Ấp 1",
        "ten_to": "Tổ 1",
        "hoi_doan_the": "Hội nông dân",
        "to_truong": "Tổ trưởng",
        "to_pho": "Tổ phó",
        "can_bo_1": "CB1",
        "chuc_vu_1": "Chức vụ 1",
        "can_bo_2": "CB2",
        "chuc_vu_2": "Chức vụ 2",
        "ngay_kt": date.today(),
        "ty_le_nqh": "0",
        "xep_loai_to": "Tốt",
        "so_kh_kt_thuc_te": "1",
        "uu_diem": "Ưu điểm",
        "ton_tai": "Tồn tại",
        "kien_nghi": "Kiến nghị",
        "so_phieu_kem_theo": "1",
    }
    b = tao_word_uythac_mau16(du_lieu, df)
    _assert_docx_bytes(b)


def test_tao_word_uythac_bb_xac_minh_smoke() -> None:
    du_lieu = {
        "ten_kh": "Nguyễn Văn E",
        "so_ku": "KU003",
        "so_tien": "1,0",
        "ly_do": "Lý do",
        "bien_phap": "Biện pháp",
        "can_bo_lap": "CB",
        "pgd_user": "PGD Long Thành",
        "ngay_lap": date.today(),
    }
    b = tao_word_uythac_bb_xac_minh(du_lieu)
    _assert_docx_bytes(b)


def test_tao_word_uythac_bb_ct_cx_smoke() -> None:
    du_lieu = {
        "don_vi_kt": "NHCSXH",
        "dia_danh": "Biên Hòa",
        "ngay_kt": date.today(),
        "truong_doan": "Trưởng đoàn",
        "can_bo_2": "CB2",
        "chuc_vu_2": "CV2",
        "ten_don_vi": "Hội nông dân xã A",
        "dai_dien_dc": "Đại diện",
        "chuc_vu_dc": "Chủ tịch",
        "uu_diem": "Ưu điểm",
        "ton_tai_chung": "Tồn tại",
        "kien_nghi": "Kiến nghị",
        "y_kien_don_vi_dc": "Ý kiến",
        "han_hoan_thanh": "2026-12-31",
        "loai_cap": "tinh",
    }
    b = tao_word_uythac_bb_ct_cx(du_lieu, cap="tinh")
    _assert_docx_bytes(b)


def test_tao_word_uythac_bc_th_smoke() -> None:
    du_lieu = {
        "don_vi_kt": "NHCSXH",
        "truong_doan": "Trưởng đoàn",
        "dia_danh": "Biên Hòa",
        "ngay_bc": date.today(),
        "cap_uy": "",
        "noi_dung_kt": "",
        "nx_ctxh": "",
        "nx_to": "",
        "nx_to_vien": "",
        "kn_ctxh": "",
        "kn_nhcs": "",
        "kn_cap_tren": "",
    }
    ds_bb = [{"ngay_kt": "2026-05-21", "ten_don_vi": "Hội A", "dia_danh": "Biên Hòa"}]
    b = tao_word_uythac_bc_th(du_lieu, ds_bb)
    _assert_docx_bytes(b)

