"""Hồi quy số liệu cho toàn bộ nhóm Báo cáo tín dụng."""
from __future__ import annotations

import pandas as pd

from config import (
    COT_DNO_NQ11,
    COT_DU_NO_KHOANH,
    COT_DU_NO_QH,
    COT_DU_NO_TH,
    COT_GIAI_NGAN_TRONG_NAM,
    COT_MA_KH,
    COT_MA_NDT,
    COT_NGAY_DH,
    COT_NQ11_NO_QH,
    COT_NQ11_NO_TH,
    COT_NQ11_MA_KH,
    COT_SO_KU,
    COT_TEN_CT,
    COT_TEN_KH,
    COT_TEN_PGD,
    COT_TEN_PNKT51,
    COT_TEN_XA,
    COT_TONG_DU_NO,
    NN_LINH_VUC_CHAN_NUOI,
    NN_LINH_VUC_KHAC,
    NN_LINH_VUC_LAM_NGHIEP,
    NN_LINH_VUC_THUY_SAN,
    NN_LINH_VUC_TRONG_TROT,
)
from tabs.tab_baocao.components.metric_cards import _tinh_chi_so_cards
from tabs.tab_baocao.reports.cdtotkvv import (
    _cac_cot_diem_co_du_lieu,
    _chuan_bi_cdto,
)
from tabs.tab_baocao.reports.gqvl import (
    _chuan_bi_gqvl,
    _fmt_df_trieu as _fmt_gqvl,
    _tong_hop_theo_nha_dau_tu,
)
from tabs.tab_baocao.reports.no_rui_ro_v2 import (
    _loc_den_han,
    _tao_ty_le_no_xau_theo_pgd,
)
from tabs.tab_baocao.reports.nq11 import (
    _chuan_bi_nq11,
    _doi_chieu_so_khe_uoc_nq11,
    _fmt_df_trieu as _fmt_nq11,
    _tao_tong_hop_nq11,
    _tinh_chi_so_nq11,
)
from tabs.tab_baocao.reports.nong_nghiep import (
    _gan_linh_vuc,
    _loc_pham_vi_nong_nghiep,
    _tong_hop_linh_vuc,
    phan_loai_linh_vuc_nong_nghiep,
)


def test_nq11_dem_mot_lan_moi_khe_uoc_va_khong_sua_nguon() -> None:
    df = pd.DataFrame({
        COT_SO_KU: [" KU1 ", "KU1", "KU2", ""],
        COT_DNO_NQ11: [100, 100, "200", 999],
        COT_NQ11_NO_TH: [90, 90, 180, 999],
        COT_NQ11_NO_QH: [10, 10, 20, 0],
    })
    original = df.copy(deep=True)

    result = _chuan_bi_nq11(df)

    pd.testing.assert_frame_equal(df, original)
    assert result[COT_SO_KU].tolist() == ["KU1", "KU2"]
    assert result[COT_DNO_NQ11].sum() == 300
    assert result[COT_NQ11_NO_QH].sum() == 30


def test_nq11_va_gqvl_format_dung_cot_tong_hop() -> None:
    nq11 = _fmt_nq11(pd.DataFrame({"DNO_NQ11": [1_000_000]}))
    gqvl = _fmt_gqvl(pd.DataFrame({"Tổng_dư_nợ": [2_000_000]}))

    assert nq11.loc[0, "DNO_NQ11"] == "1"
    assert gqvl.loc[0, "Tổng_dư_nợ"] == "2"


def test_nq11_kpi_va_tong_hop_dung_cung_pham_vi() -> None:
    df = pd.DataFrame({
        COT_SO_KU: ["KU1", "KU2", "KU3"],
        COT_NQ11_MA_KH: ["KH1", "KH1", "KH2"],
        COT_TEN_CT: ["CT A", "CT A", pd.NA],
        COT_DNO_NQ11: [1_000, 2_000, 1_000],
        COT_NQ11_NO_TH: [900, 2_000, 800],
        COT_NQ11_NO_QH: [100, 0, 200],
    })
    prepared = _chuan_bi_nq11(df)

    kpi = _tinh_chi_so_nq11(prepared)
    summary = _tao_tong_hop_nq11(prepared, COT_TEN_CT)

    assert kpi == {
        "so_mon": 3,
        "so_kh": 2,
        "du_no": 4_000.0,
        "no_qh": 300.0,
        "so_mon_qh": 2,
        "ty_le_qh": 7.5,
        "du_no_bq_mon": 4_000 / 3,
    }
    assert set(summary[COT_TEN_CT]) == {"CT A", "Chưa xác định"}
    assert summary["Dư nợ NQ11"].sum() == 4_000
    assert summary["Nợ quá hạn"].sum() == 300
    assert round(summary["Tỷ trọng (%)"].sum(), 8) == 100


def test_nq11_doi_chieu_voi_hstd_full_khong_bao_nham_mon_tat_toan() -> None:
    hstd_full = pd.DataFrame({
        COT_SO_KU: ["KU1", " KU2 ", "KU3", 1004.0],
        COT_TONG_DU_NO: [100, 200, 0, 0],
    })

    result = _doi_chieu_so_khe_uoc_nq11(
        hstd_full,
        ["KU1", "KU2", "KU3", "1004", "KU_MISSING", "nan", None],
    )

    assert result == {
        "tong_nq11": 5,
        "da_khop": 4,
        "chua_khop": ["KU_MISSING"],
    }


def test_gqvl_tinh_du_no_tu_thanh_phan_va_loai_ban_sao_khe_uoc() -> None:
    df = pd.DataFrame({
        COT_SO_KU: ["KU1", "KU1", "KU2"],
        COT_TEN_PGD: ["PGD Long Thành"] * 3,
        COT_DU_NO_TH: [90, 90, 180],
        COT_DU_NO_QH: [10, 10, 20],
        COT_DU_NO_KHOANH: [0, 0, 5],
        COT_GIAI_NGAN_TRONG_NAM: [50, 50, 70],
    })

    result = _chuan_bi_gqvl(df)

    assert len(result) == 2
    assert result["_so_ku_dem"].nunique() == 2
    assert result[COT_TONG_DU_NO].sum() == 305
    assert result[COT_DU_NO_QH].sum() == 30
    assert result[COT_GIAI_NGAN_TRONG_NAM].sum() == 120


def test_gqvl_theo_nha_dau_tu_khong_cat_top_20() -> None:
    df = pd.DataFrame({
        "_so_ku_dem": [f"KU{i}" for i in range(25)],
        COT_MA_NDT: [f"NDT{i}" for i in range(25)],
        COT_TONG_DU_NO: [i + 1 for i in range(25)],
        COT_DU_NO_QH: [1] * 25,
    })

    result, group_col = _tong_hop_theo_nha_dau_tu(df)

    assert group_col == COT_MA_NDT
    assert len(result) == 25
    assert result["Số_món"].sum() == 25
    assert result["Tổng_dư_nợ"].sum() == sum(range(1, 26))


def test_den_han_tinh_tu_dau_ngay_va_gom_ca_hom_nay() -> None:
    df = pd.DataFrame({
        COT_SO_KU: ["KU0", "KU1", "KU2", "KU3"],
        COT_NGAY_DH: ["21/08/2026", "22/08/2026", "21/09/2026", "22/09/2026"],
    })

    result = _loc_den_han(df, 30, hom_nay="2026-08-22 15:30:00")

    assert result[COT_SO_KU].tolist() == ["KU1", "KU2"]


def test_ty_le_no_xau_khong_lam_roi_pgd_trong() -> None:
    df = pd.DataFrame({
        COT_TEN_PGD: ["PGD A", pd.NA],
        COT_TONG_DU_NO: [1_000, 500],
        COT_DU_NO_QH: [100, 0],
        COT_DU_NO_KHOANH: [0, 50],
    })

    result = _tao_ty_le_no_xau_theo_pgd(df)

    assert set(result[COT_TEN_PGD]) == {"PGD A", "Chưa xác định"}
    assert result["Tổng_dư_nợ"].sum() == 1_500
    assert result["Tổng_nợ_xấu"].sum() == 150


def test_cdto_loai_to_het_du_no_loai_trung_va_nhan_dien_cot_diem() -> None:
    df = pd.DataFrame({
        "ma_dv": ["001", "001", "001"],
        "ma_to": ["T1", "T1", "T2"],
        "du_no": [100, 150, 0],
        "diem_gdtx": [pd.NA, pd.NA, pd.NA],
        "tong_diem": [80, 90, 70],
        "xep_loai": ["Khá", "Tốt", "Tốt"],
    })

    result = _chuan_bi_cdto(df)

    assert len(result) == 1
    assert result.loc[0, "du_no"] == 150
    assert result.loc[0, "xep_loai"] == "Tốt"
    assert _cac_cot_diem_co_du_lieu(
        result, ["diem_gdtx", "tong_diem"]
    ) == ["tong_diem"]


def test_cards_no_qua_han_dung_tu_so_va_khong_dem_trung() -> None:
    hstd = pd.DataFrame({
        COT_SO_KU: ["KU1", "KU1", "KU2"],
        COT_MA_KH: ["KH1", "KH1", "KH2"],
        COT_TONG_DU_NO: [1_000, 1_000, 3_000],
        COT_DU_NO_QH: [100, 100, 0],
        COT_DU_NO_KHOANH: [500, 500, 0],
    })
    nq11 = pd.DataFrame({
        COT_SO_KU: ["KU1", "KU1"],
        COT_DNO_NQ11: [1_000, 1_000],
    })
    gqvl = pd.DataFrame({
        COT_SO_KU: ["G1", "G1", "G2"],
        COT_TONG_DU_NO: [2_000, 2_000, 3_000],
        COT_GIAI_NGAN_TRONG_NAM: [700, 700, 800],
    })

    result = _tinh_chi_so_cards(hstd, nq11, gqvl)

    assert result == {
        "tong_du_no": 4_000.0,
        "no_qh": 100.0,
        "no_khoanh": 500.0,
        "no_rui_ro": 600.0,
        "so_mon": 2,
        "so_kh": 2,
        "tl_no_qh": 2.5,
        "tl_no_khoanh": 12.5,
        "tl_no_rui_ro": 15.0,
        "du_no_bq_mon": 2_000.0,
        "dno_nq11": 1_000.0,
        "dno_gqvl": 5_000.0,
        "giai_ngan_gqvl": 1_500.0,
        "so_mon_gqvl": 2,
    }


def test_nong_nghiep_phan_loai_khong_bat_nham_tu_khoa_ngan() -> None:
    assert phan_loai_linh_vuc_nong_nghiep("Chăn nuôi bò") == NN_LINH_VUC_CHAN_NUOI
    assert phan_loai_linh_vuc_nong_nghiep("Nuôi trồng thủy sản") == NN_LINH_VUC_THUY_SAN
    assert phan_loai_linh_vuc_nong_nghiep("Chăm sóc vườn cây điều") == NN_LINH_VUC_TRONG_TROT
    assert phan_loai_linh_vuc_nong_nghiep("Trồng rừng sản xuất") == NN_LINH_VUC_LAM_NGHIEP
    assert (
        phan_loai_linh_vuc_nong_nghiep("Mua sắm dụng cụ của hộ trong khu phố")
        == NN_LINH_VUC_KHAC
    )


def test_nong_nghiep_pham_vi_phuong_chi_lay_trong_trot_chan_nuoi() -> None:
    df = pd.DataFrame({
        COT_TEN_XA: ["Xã Long Đức", "Biên Hòa", "Biên Hòa", "Xã Long Đức"],
        COT_TEN_PNKT51: [
            "Nuôi tôm",
            "Nuôi trồng thủy sản",
            "Chăn nuôi bò",
            "Trồng rừng sản xuất",
        ],
        COT_TONG_DU_NO: [100, 200, 300, 400],
        COT_DU_NO_QH: [0, 20, 30, 40],
        COT_SO_KU: ["KU1", "KU2", "KU3", "KU4"],
    })

    result = _loc_pham_vi_nong_nghiep(_gan_linh_vuc(df))

    assert result[COT_SO_KU].tolist() == ["KU1", "KU3", "KU4"]
    assert result[COT_TONG_DU_NO].sum() == 800


def test_nong_nghiep_tong_hop_fallback_khi_ma_kh_rong_va_thieu_cot_no() -> None:
    df = pd.DataFrame({
        COT_TEN_PNKT51: ["Trồng cây cao su", "Trồng cây cao su"],
        COT_TONG_DU_NO: [100, 200],
        COT_MA_KH: ["", None],
        COT_TEN_KH: ["Khách A", "Khách B"],
    })

    result = _tong_hop_linh_vuc(df, [NN_LINH_VUC_TRONG_TROT])

    assert result.loc[0, "Số_KH"] == 2
    assert result.loc[0, "Số_món"] == 2
    assert result.loc[0, "Dư_nợ_trong_hạn"] == 0
    assert result.loc[0, "Dư_nợ_quá_hạn"] == 0
