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
