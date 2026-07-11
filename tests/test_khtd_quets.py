"""Hồi quy helper quét chương trình có dư nợ của KHTD."""
from __future__ import annotations

import pandas as pd

from config import COT_MA_CHUONG_TRINH, COT_NGUON_VON, COT_TEN_CT, COT_TONG_DU_NO
from tabs.tab_khtd import _quet_ct_co_du_no


def test_quet_ct_vectorized_loc_du_no_va_uu_tien_ten_hstd() -> None:
    df = pd.DataFrame(
        {
            COT_MA_CHUONG_TRINH: [7, 7, 13, 99],
            COT_NGUON_VON: [2, 2, 2, 1],
            COT_TONG_DU_NO: [8_000_000, 1_000_000, 500_000_000, 0],
            COT_TEN_CT: ["Nhà ở hộ nghèo HSTD", "Tên dòng sau", "Sau cai nghiện HSTD", "Bỏ qua"],
        }
    )

    keys, ten_map = _quet_ct_co_du_no(df)

    assert keys == {"7_DP", "13_DP"}
    assert ten_map == {
        "7_DP": "Nhà ở hộ nghèo HSTD",
        "13_DP": "Sau cai nghiện HSTD",
    }
