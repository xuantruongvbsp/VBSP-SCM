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


def test_bang_theo_nv_them_dong_tong_cuoi_bang(monkeypatch):
    monkeypatch.setattr(tab_hhi.db, "doc_ndt_dp_rule_list", lambda: [])
    df = pd.DataFrame(
        {
            COT_TEN_PGD: ["PGD A", "PGD A", "PGD B", "PGD B"],
            COT_NGUON_VON: ["1", "2", "1", "2"],
            COT_MA_CHUONG_TRINH: [6, 6, 6, 6],
            COT_MA_NHA_DAU_TU: ["", "INV_A", "", "INV_B"],
            COT_TONG_DU_NO: [100_000_000, 50_000_000, 200_000_000, 150_000_000],
        }
    )

    out = tab_hhi._bang_theo_nv(df, COT_TEN_PGD, them_dong_tong=True)
    tong = out.iloc[-1]

    assert tong[COT_TEN_PGD] == "Tổng cộng"
    assert tong["TW (triệu đồng)"] == "300"
    assert tong["ĐP cấp xã/khác (triệu đồng)"] == "200"
    assert tong["ĐP (triệu đồng)"] == "200"
    assert tong["Tổng (triệu đồng)"] == "500"
    assert tong["Tỷ trọng ĐP (%)"] == "40,0%"


def test_bang_nguon_von_xa_02_ct_khop_so_chuan(monkeypatch):
    monkeypatch.setattr(tab_hhi.db, "doc_ndt_dp_rule_list", lambda: [])
    expected = [
        ("Hội sở tỉnh", 10400, 0),
        ("Long Thành", 4600, 0),
        ("Trảng Bom", 3100, 0),
        ("Long Khánh", 3550, 0),
        ("Xuân Lộc", 3900, 0),
        ("Định Quán", 4200, 0),
        ("Vĩnh Cửu", 3200, 1500),
        ("Tân Phú", 12669, 0),
        ("Thống Nhất", 3300, 0),
        ("Cẩm Mỹ", 2300, 0),
        ("Nhơn Trạch", 3800, 0),
        ("Bình Long", 3100, 0),
        ("Lộc Ninh", 4600, 0),
        ("Bình Phước", 3100, 0),
        ("Phước Long", 3000, 0),
        ("Bù Đăng", 4600, 0),
        ("Đồng Phú", 3800, 0),
        ("Chơn Thành", 3300, 0),
        ("Bù Đốp", 2800, 0),
        ("Bù Gia Mập", 3000, 980),
        ("Phú Riềng", 3500, 0),
        ("Hớn Quản", 3660, 0),
    ]
    rows = []
    for pgd, gqvl, nsvsmt in expected:
        rows.append(
            {
                COT_TEN_PGD: pgd,
                COT_NGUON_VON: "2",
                COT_MA_CHUONG_TRINH: 3,
                COT_MA_NHA_DAU_TU: "",
                COT_TONG_DU_NO: gqvl * 1_000_000,
            }
        )
        if nsvsmt:
            rows.append(
                {
                    COT_TEN_PGD: pgd,
                    COT_NGUON_VON: "2",
                    COT_MA_CHUONG_TRINH: 6,
                    COT_MA_NHA_DAU_TU: "",
                    COT_TONG_DU_NO: nsvsmt * 1_000_000,
                }
            )
    df = pd.DataFrame(rows)

    out = tab_hhi._bang_nguon_von_xa_02_ct(df)
    tong = out.iloc[-1]
    vinh_cuu = out[out["Đơn vị"] == "Vĩnh Cửu"].iloc[0]
    bu_gia_map = out[out["Đơn vị"] == "Bù Gia Mập"].iloc[0]

    assert tong["Đơn vị"] == "Tổng cộng"
    assert tong["GQVL nguồn vốn xã"] == "93.479"
    assert tong["NS&VSMTNT nguồn vốn xã"] == "2.480"
    assert tong["Tổng cộng"] == "95.959"
    assert vinh_cuu["NS&VSMTNT nguồn vốn xã"] == "1.500"
    assert bu_gia_map["NS&VSMTNT nguồn vốn xã"] == "980"


def test_bang_nguon_von_xa_02_ct_loai_tru_rule_cap_tinh(monkeypatch):
    monkeypatch.setattr(
        tab_hhi.db,
        "doc_ndt_dp_rule_list",
        lambda: [{"ma_ct": 6, "ma": "INV_TINH", "ghi_chu": "Nguồn tỉnh", "cap": "tinh"}],
    )
    df = pd.DataFrame(
        {
            COT_TEN_PGD: ["PGD A", "PGD A", "PGD A"],
            COT_NGUON_VON: ["2", "2", "2"],
            COT_MA_CHUONG_TRINH: [3, 6, 6],
            COT_MA_NHA_DAU_TU: ["INV_XA", "INV_XA", "INV_TINH"],
            COT_TONG_DU_NO: [100_000_000, 500_000_000, 999_000_000],
        }
    )

    out = tab_hhi._bang_nguon_von_xa_02_ct(df)
    row = out[out["Đơn vị"] == "A"].iloc[0]
    tong = out.iloc[-1]

    assert row["GQVL nguồn vốn xã"] == "100"
    assert row["NS&VSMTNT nguồn vốn xã"] == "500"
    assert row["Tổng cộng"] == "600"
    assert tong["Tổng cộng"] == "600"
