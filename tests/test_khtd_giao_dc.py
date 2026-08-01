"""Kiểm tra logic ghép dư nợ HSTD vào màn Giao KHTD."""

import pandas as pd

from config import (
    COT_MA_CHUONG_TRINH,
    COT_NGUON_VON,
    COT_TEN_PGD,
    COT_TEN_XA,
    COT_TONG_DU_NO,
    tim_ten_xa_trong_hstd,
)
from tabs.tab_khtd_giao_dc import _build_du_no_map
from tabs.tab_khtd_giao_dc import _build_rows_ct_theo_xa, _tinh_pivot_kh_th


def test_build_du_no_map_chuan_hoa_tien_to_xa_phuong() -> None:
    df = pd.DataFrame(
        {
            COT_TEN_PGD: ["PGD Long Thành", "PGD Long Thành"],
            COT_TEN_XA: ["Phước Thái", "Phường Long Thành"],
            COT_MA_CHUONG_TRINH: [1, 9],
            COT_NGUON_VON: [1, 2],
            COT_TONG_DU_NO: [2_500_000_000, 750_000_000],
        }
    )

    result = _build_du_no_map(df, "PGD Long Thành")

    key_xa = tim_ten_xa_trong_hstd("Xã Phước Thái").casefold()
    key_phuong = tim_ten_xa_trong_hstd("Phường Long Thành").casefold()
    assert result[(key_xa, 1, 1)] == 2_500.0
    assert result[(key_phuong, 9, 2)] == 750.0


def test_tinh_pivot_kh_th_quy_doi_kh_va_th_ra_trieu(monkeypatch) -> None:
    df_kh = pd.DataFrame(
        [
            {
                "pgd_slug": "pgd_long_thanh",
                "xa": "Xã Phước Thái",
                "ma_key": "1_TW",
                "ten_ct": "Hộ nghèo",
                "nguon": "TW",
                "kh_moi_tw": 100_000_000,
                "kh_moi_dp": 0,
            }
        ]
    )
    df_hstd = pd.DataFrame(
        {
            COT_TEN_PGD: ["PGD Long Thành"],
            COT_TEN_XA: ["Phước Thái"],
            COT_MA_CHUONG_TRINH: [1],
            COT_NGUON_VON: [1],
            COT_TONG_DU_NO: [80_000_000],
        }
    )
    monkeypatch.setattr(
        "tabs.tab_khtd_giao_dc.khtd_service.tong_hop",
        lambda *_args, **_kwargs: df_kh,
    )

    data, active_mk, xas_per_pgd = _tinh_pivot_kh_th(2026, "05", "Dot1", "TW", df_hstd)

    assert active_mk == ["1_TW"]
    assert xas_per_pgd == {"pgd_long_thanh": ["Xã Phước Thái"]}
    assert data[("pgd_long_thanh", "Xã Phước Thái", "1_TW")] == (100.0, 80.0, -20.0, 80.0)


def test_build_rows_ct_theo_xa_giu_ten_ct_va_nguon_rieng() -> None:
    data_tw = {
        ("pgd_long_thanh", "Xã Phước Thái", "1_TW"): (100.0, 80.0, -20.0, 80.0)
    }
    data_dp = {
        ("pgd_long_thanh", "Xã Phước Thái", "1_DP"): (30.0, 45.0, 15.0, 150.0)
    }

    rows = _build_rows_ct_theo_xa(data_tw, data_dp, "pgd_long_thanh", "Xã Phước Thái")

    assert {row["Nguồn"] for row in rows} == {"TW", "ĐP"}
    assert all(not isinstance(row["Chương trình"], tuple) for row in rows)
    assert {row["KH (tr.đ)"] for row in rows} == {100.0, 30.0}
