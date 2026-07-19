from __future__ import annotations

import pandas as pd

from config import (
    COT_MA_CHUONG_TRINH,
    COT_MA_NHA_DAU_TU,
    COT_NGUON_VON,
    COT_TEN_PGD,
    COT_TONG_DU_NO,
)
from tabs import tab_hhi


def test_bang_theo_nv_tach_dp_cap_tinh_va_cap_xa(monkeypatch):
    monkeypatch.setattr(
        tab_hhi.db,
        "doc_ndt_dp_rule_list",
        lambda: [
            {"ma_ct": 6, "ma": "INV_TINH", "ghi_chu": "Nguồn tỉnh", "cap": "tinh"},
            {"ma_ct": 6, "ma": "INV_XA", "ghi_chu": "Nguồn xã", "cap": "xa"},
        ],
    )
    df = pd.DataFrame(
        {
            COT_TEN_PGD: ["PGD A", "PGD A", "PGD A", "PGD A"],
            COT_NGUON_VON: ["1", "2", "2", "2"],
            COT_MA_CHUONG_TRINH: [6, 6, 6, 6],
            COT_MA_NHA_DAU_TU: ["", "INV_TINH", "INV_XA", "INV_CHUA_RULE"],
            COT_TONG_DU_NO: [100_000_000, 50_000_000, 30_000_000, 20_000_000],
        }
    )

    out = tab_hhi._bang_theo_nv(df, COT_TEN_PGD)

    assert out.loc[0, "TW (triệu đồng)"] == "100"
    assert out.loc[0, "ĐP cấp tỉnh (triệu đồng)"] == "50"
    assert out.loc[0, "ĐP cấp xã/khác (triệu đồng)"] == "50"
    assert out.loc[0, "ĐP (triệu đồng)"] == "100"
    assert out.loc[0, "Tỷ trọng ĐP (%)"] == "50,0%"
