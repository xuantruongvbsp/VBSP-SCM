from __future__ import annotations

import warnings

import pandas as pd

from config import (
    COT_MA_CHUONG_TRINH,
    COT_MA_NHA_DAU_TU,
    COT_NGUON_VON,
    COT_TEN_CT,
    COT_TEN_PGD,
    COT_TEN_XA,
    COT_TONG_DU_NO,
)
from tabs import tab_hhi


def test_excel_state_key_hash_rules_key_khong_phinh_session_key():
    rules_key = "|".join(f"6:INV_{i}:xa" for i in range(500))

    key = tab_hhi._excel_state_key("cn_all", 123.45, rules_key, "kh123")

    assert key.startswith("nvdp_excel_buf_cn_all_123.45_")
    assert len(key) < 80
    assert rules_key not in key


def test_excel_state_key_doi_khi_kh_map_doi():
    rules_key = "6:INV_A:xa"
    kh_sig_a = tab_hhi._kh_map_cache_key("đợt Dot1, 01/2026", {"pgd_a": 100_000_000})
    kh_sig_b = tab_hhi._kh_map_cache_key("đợt Dot1, 01/2026", {"pgd_a": 200_000_000})

    assert kh_sig_a != kh_sig_b
    assert tab_hhi._excel_state_key("cn_all", 123.45, rules_key, kh_sig_a) != tab_hhi._excel_state_key(
        "cn_all", 123.45, rules_key, kh_sig_b
    )


def test_parse_khtd_period_key_chap_nhan_slug_va_dot_co_underscore():
    key = "khtd_pgd_long_khanh_2026_01_Dot_1"

    parsed = tab_hhi._parse_khtd_period_key(key, ["pgd_long_khanh"])

    assert parsed == (2026, "01", "Dot_1")


def test_parse_khtd_period_key_bo_qua_key_timestamp():
    key = "khtd_pgd_long_khanh_2026_01_Dot1_20260711T154254"

    parsed = tab_hhi._parse_khtd_period_key(key, ["pgd_long_khanh"])

    assert parsed == (2026, "01", "Dot1_20260711T154254")
    assert tab_hhi._is_khtd_timestamp_dot(parsed[2])
    assert not tab_hhi._is_khtd_timestamp_dot("Dot_1")


def test_clear_old_excel_buffers_chi_giu_active_key(monkeypatch):
    session_state = {
        "nvdp_excel_buf_old": b"old",
        "nvdp_excel_buf_active": b"active",
        "other_key": "keep",
    }
    monkeypatch.setattr(tab_hhi.st, "session_state", session_state)

    tab_hhi._clear_old_excel_buffers("nvdp_excel_buf_active")

    assert session_state == {
        "nvdp_excel_buf_active": b"active",
        "other_key": "keep",
    }


def test_export_condition_key_doi_khi_doi_dieu_kien():
    key_a = tab_hhi._export_condition_key(
        tab_hhi._EXPORT_SOURCE_DP,
        ["PGD A"],
        ["Xã A"],
        ["CT A"],
        [tab_hhi._EXPORT_SHEET_XA],
    )
    key_b = tab_hhi._export_condition_key(
        tab_hhi._EXPORT_SOURCE_DP_TINH,
        ["PGD A"],
        ["Xã A"],
        ["CT A"],
        [tab_hhi._EXPORT_SHEET_XA],
    )

    assert key_a != key_b
    assert len(key_a) == 12


def test_loc_du_lieu_xuat_theo_nhieu_dieu_kien(monkeypatch):
    monkeypatch.setattr(
        tab_hhi.db,
        "doc_ndt_dp_rule_list",
        lambda: [{"ma_ct": 6, "ma": "INV_TINH", "ghi_chu": "Nguồn tỉnh", "cap": "tinh"}],
    )
    df = pd.DataFrame(
        {
            COT_TEN_PGD: ["PGD A", "PGD A", "PGD B", "PGD A"],
            COT_TEN_XA: ["Xã A", "Xã B", "Xã A", "Xã A"],
            COT_TEN_CT: ["CT 6", "CT 6", "CT 6", "CT 1"],
            COT_NGUON_VON: ["2", "2", "2", "1"],
            COT_MA_CHUONG_TRINH: [6, 6, 6, 1],
            COT_MA_NHA_DAU_TU: ["INV_TINH", "INV_XA", "INV_TINH", ""],
            COT_TONG_DU_NO: [100_000_000, 50_000_000, 80_000_000, 200_000_000],
        }
    )
    df_labeled = tab_hhi._phan_nguon_von(df)

    out = tab_hhi._loc_du_lieu_xuat_theo_dieu_kien(
        df_labeled,
        source_filter=tab_hhi._EXPORT_SOURCE_DP_TINH,
        pgd_values=["PGD A"],
        xa_values=["Xã A"],
        ct_values=["CT 6"],
    )

    assert len(out) == 1
    assert out.iloc[0][COT_MA_NHA_DAU_TU] == "INV_TINH"


def test_cached_bao_cao_sheets_chi_xuat_sheet_da_chon(monkeypatch):
    monkeypatch.setattr(tab_hhi.db, "doc_ndt_dp_rule_list", lambda: [])
    df = pd.DataFrame(
        {
            COT_TEN_PGD: ["PGD A", "PGD A"],
            COT_TEN_XA: ["Xã A", "Xã A"],
            COT_TEN_CT: ["CT 3", "CT 1"],
            COT_NGUON_VON: ["2", "1"],
            COT_MA_CHUONG_TRINH: [3, 1],
            COT_MA_NHA_DAU_TU: ["INV_XA", ""],
            COT_TONG_DU_NO: [100_000_000, 200_000_000],
        }
    )
    df_labeled = tab_hhi._phan_nguon_von(df)

    sheets = tab_hhi._cached_bao_cao_sheets(
        df_labeled,
        False,
        (),
        (tab_hhi._EXPORT_SHEET_XA,),
        "cn",
        1.0,
        "",
        "",
        "",
    )

    assert list(sheets.keys()) == [tab_hhi._EXPORT_SHEET_XA]
    assert sheets[tab_hhi._EXPORT_SHEET_XA].iloc[0][COT_TEN_XA] == "Xã A"


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
    assert out.loc[0, "Tổng dư nợ ĐP (triệu đồng)"] == "100"
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
    assert tong["Tổng dư nợ ĐP (triệu đồng)"] == "200"
    assert tong["Tổng (triệu đồng)"] == "500"
    assert tong["Tỷ trọng ĐP (%)"] == "40,0%"


def test_bang_theo_nv_pgd_bo_cot_kh_va_dat_kh(monkeypatch):
    monkeypatch.setattr(tab_hhi.db, "doc_ndt_dp_rule_list", lambda: [])
    df = pd.DataFrame(
        {
            COT_TEN_PGD: ["PGD A", "PGD A"],
            COT_NGUON_VON: ["1", "2"],
            COT_MA_CHUONG_TRINH: [6, 6],
            COT_MA_NHA_DAU_TU: ["", "INV_A"],
            COT_TONG_DU_NO: [100_000_000, 50_000_000],
        }
    )

    out = tab_hhi._bang_theo_nv(
        df,
        COT_TEN_PGD,
        them_dong_tong=True,
    )

    assert "KH ĐP giao (triệu đồng)" not in out.columns
    assert "Đạt KH (%)" not in out.columns
    assert "Tổng dư nợ ĐP (triệu đồng)" in out.columns
    assert out.loc[0, "Tổng dư nợ ĐP (triệu đồng)"] == "50"


def test_nguon_von_label_series_giu_logic_map_cu():
    values = pd.Series([1, 1.0, "1", "1.0", "TW", "Trung ương", 2, "2.0", "ĐP", "Địa phương", "", None, "abc", 3])

    out = tab_hhi._nguon_von_label_series(values)

    assert out.tolist() == [tab_hhi._map_nguon_von(v) for v in values.tolist()]


def test_phan_nguon_von_ma_ct_thap_phan_khong_crash_va_giu_logic_cu(monkeypatch):
    monkeypatch.setattr(
        tab_hhi.db,
        "doc_ndt_dp_rule_list",
        lambda: [{"ma_ct": "3.0", "ma": "INV_DEC", "ghi_chu": "Nguồn tỉnh", "cap": "tinh"}],
    )
    df = pd.DataFrame(
        {
            COT_NGUON_VON: ["2", "2"],
            COT_MA_CHUONG_TRINH: ["3.5", 6],
            COT_MA_NHA_DAU_TU: ["INV_DEC", pd.NA],
        }
    )

    out = tab_hhi._phan_nguon_von(df)

    assert out.loc[0, "_nv_cap_label"] == "ĐP cấp tỉnh"
    assert out.loc[1, "_nv_cap_label"] == "ĐP cấp xã/khác"


def test_bang_ma_ndt_cho_phan_loai_bo_rule_va_can_index_du_no(monkeypatch):
    monkeypatch.setattr(
        tab_hhi.db,
        "doc_ndt_dp_rule_list",
        lambda: [{"ma_ct": 6, "ma": "INV_RULE", "ghi_chu": "Nguồn tỉnh", "cap": "tinh"}],
    )
    df = pd.DataFrame(
        {
            "_nv_label": ["Địa phương", "Địa phương", "Địa phương", "Trung ương"],
            COT_MA_NHA_DAU_TU: ["INV_NEW", "INV_NEW", "INV_RULE", "INV_TW"],
            COT_TEN_PGD: ["PGD A", "PGD B", "PGD A", "PGD A"],
            COT_TEN_XA: ["Xã A", "Xã B", "Xã A", "Xã A"],
            COT_TEN_CT: ["CT nhỏ", "CT lớn", "CT ruled", "CT TW"],
        },
        index=[10, 20, 30, 40],
    )
    dn = pd.Series(
        [100_000_000, 500_000_000, 999_000_000, 1_000_000],
        index=[10, 20, 30, 40],
    )

    out = tab_hhi._bang_ma_ndt_cho_phan_loai(df, dn)

    assert out["Mã NĐT"].tolist() == ["INV_NEW"]
    assert out.loc[0, "Dư nợ (triệu đồng)"] == "600"
    assert out.loc[0, "Số PGD"] == 2
    assert out.loc[0, "Số xã"] == 2
    assert out.loc[0, "Chương trình chính"] == "CT lớn"


def test_dem_nguon_von_nan_co_ma_ndt_tinh_ca_chuoi_rong():
    df = pd.DataFrame(
        {
            COT_NGUON_VON: [None, "", "nan", "1", ""],
            COT_MA_NHA_DAU_TU: ["INV_A", "INV_B", "INV_C", "INV_D", ""],
        }
    )

    assert tab_hhi._dem_nguon_von_nan_co_ma_ndt(df) == 3


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


def test_bang_nguon_von_xa_02_ct_khong_phat_sinh_pandas4_warning(monkeypatch):
    monkeypatch.setattr(tab_hhi.db, "doc_ndt_dp_rule_list", lambda: [])
    df = pd.DataFrame(
        {
            COT_TEN_PGD: ["PGD A", "PGD A"],
            COT_NGUON_VON: ["2", "2"],
            COT_MA_CHUONG_TRINH: [3, 6],
            COT_MA_NHA_DAU_TU: ["INV_XA", "INV_XA"],
            COT_TONG_DU_NO: [100_000_000, 500_000_000],
        }
    )

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        tab_hhi._bang_nguon_von_xa_02_ct(df)

    assert not [w for w in caught if w.category.__name__ == "Pandas4Warning"]
