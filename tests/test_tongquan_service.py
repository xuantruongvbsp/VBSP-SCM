from __future__ import annotations

from datetime import date

import pandas as pd

from config import (
    COT_DU_NO_KHOANH,
    COT_DU_NO_QH,
    COT_DU_NO_TH,
    COT_LAI_TON,
    COT_MA_KH,
    COT_NGAY_DH,
    COT_NGUON_VON,
    COT_SO_KU,
    COT_TEN_CT,
    COT_TEN_PGD,
    COT_TONG_DU_NO,
)
from services import tongquan_service


def test_tinh_kpi_tongquan_basic_and_no_mutation():
    df = pd.DataFrame(
        [
            {COT_TONG_DU_NO: "1000", COT_DU_NO_TH: "900", COT_DU_NO_QH: "50", COT_DU_NO_KHOANH: "50",
             COT_SO_KU: "KU1", COT_MA_KH: "KH1"},
            {COT_TONG_DU_NO: "2000", COT_DU_NO_TH: "1900", COT_DU_NO_QH: "50", COT_DU_NO_KHOANH: "50",
             COT_SO_KU: "KU2", COT_MA_KH: "KH2"},
        ]
    )
    df_before = df.copy(deep=True)
    kpi = tongquan_service.tinh_kpi_tongquan(
        df,
        cot_tdn=COT_TONG_DU_NO,
        cot_dth=COT_DU_NO_TH,
        cot_dqh=COT_DU_NO_QH,
        cot_nk=COT_DU_NO_KHOANH,
        cot_ku=COT_SO_KU,
        cot_ma_kh=COT_MA_KH,
    )
    assert kpi["tdn"] == 3000
    assert kpi["dth"] == 2800
    assert kpi["dqh"] == 100
    assert kpi["dnk"] == 100
    assert kpi["n_mon_vay"] == 2
    assert kpi["n_kh"] == 2
    assert df.equals(df_before)


def test_tinh_heatmap_pgd_basic():
    df = pd.DataFrame(
        [
            {COT_TEN_PGD: "PGD A", COT_TONG_DU_NO: 100, COT_MA_KH: "KH1", COT_DU_NO_QH: 1},
            {COT_TEN_PGD: "PGD A", COT_TONG_DU_NO: 200, COT_MA_KH: "KH2", COT_DU_NO_QH: 2},
            {COT_TEN_PGD: "PGD B", COT_TONG_DU_NO: 300, COT_MA_KH: "KH1", COT_DU_NO_QH: 3},
        ]
    )
    out = tongquan_service.tinh_heatmap_pgd(
        df,
        cot_pgd=COT_TEN_PGD,
        cot_tdn=COT_TONG_DU_NO,
        cot_ma_kh=COT_MA_KH,
        cot_dqh=COT_DU_NO_QH,
    )
    m = {r[COT_TEN_PGD]: r for r in out.to_dict("records")}
    assert m["PGD A"]["du_no"] == 300
    assert m["PGD A"]["so_kh"] == 2
    assert m["PGD A"]["nqh"] == 3
    assert m["PGD B"]["du_no"] == 300
    assert m["PGD B"]["so_kh"] == 1
    assert m["PGD B"]["nqh"] == 3


def test_tinh_co_cau_ct_basic():
    df = pd.DataFrame(
        [
            {COT_TEN_CT: "CT1", COT_MA_KH: "KH1", COT_TONG_DU_NO: 100, COT_DU_NO_QH: 1, COT_DU_NO_KHOANH: 0, COT_NGUON_VON: 1},
            {COT_TEN_CT: "CT1", COT_MA_KH: "KH2", COT_TONG_DU_NO: 200, COT_DU_NO_QH: 0, COT_DU_NO_KHOANH: 10, COT_NGUON_VON: 2},
            {COT_TEN_CT: "CT2", COT_MA_KH: "KH1", COT_TONG_DU_NO: 300, COT_DU_NO_QH: 3, COT_DU_NO_KHOANH: 0, COT_NGUON_VON: 1},
        ]
    )
    out = tongquan_service.tinh_co_cau_ct(
        df,
        col_khoanh="",
        col_gn="",
        cols_tn_key="",
        cot_ten_ct=COT_TEN_CT,
        cot_tdn=COT_TONG_DU_NO,
        cot_dqh=COT_DU_NO_QH,
        cot_dnk=COT_DU_NO_KHOANH,
        cot_nv=COT_NGUON_VON,
        cot_ma_kh=COT_MA_KH,
    )
    assert set(["ten_ct", "du_no", "so_kh", "so_mon", "ty_trong", "du_no_tw", "du_no_dp"]).issubset(out.columns)
    m = {r["ten_ct"]: r for r in out.to_dict("records")}
    assert m["CT1"]["du_no"] == 300
    assert m["CT1"]["so_kh"] == 2
    assert m["CT2"]["du_no"] == 300
    assert m["CT2"]["so_kh"] == 1


def test_tinh_tqpgd_extended_basic():
    df = pd.DataFrame(
        [
            {COT_TEN_PGD: "PGD A", COT_MA_KH: "KH1", COT_SO_KU: "KU1", COT_TONG_DU_NO: 100, COT_DU_NO_QH: 1, COT_LAI_TON: 2, COT_NGAY_DH: date(2026, 5, 1)},
            {COT_TEN_PGD: "PGD A", COT_MA_KH: "KH2", COT_SO_KU: "KU2", COT_TONG_DU_NO: 200, COT_DU_NO_QH: 2, COT_LAI_TON: 0, COT_NGAY_DH: date(2025, 5, 1)},
            {COT_TEN_PGD: "PGD B", COT_MA_KH: "KH1", COT_SO_KU: "KU3", COT_TONG_DU_NO: 300, COT_DU_NO_QH: 3, COT_LAI_TON: 1, COT_NGAY_DH: date(2026, 12, 31)},
        ]
    )
    out = tongquan_service.tinh_tqpgd_extended(
        df,
        col_khoanh="",
        col_cv="",
        cols_thu_key="",
        nam_ht="2026",
        cot_pgd=COT_TEN_PGD,
        cot_tdn=COT_TONG_DU_NO,
        cot_dqh=COT_DU_NO_QH,
        cot_lai_ton=COT_LAI_TON,
        cot_ngay_dh=COT_NGAY_DH,
        cot_ma_kh=COT_MA_KH,
        cot_so_ku=COT_SO_KU,
    )
    m = {r[COT_TEN_PGD]: r for r in out.to_dict("records")}
    assert m["PGD A"]["du_no"] == 300
    assert m["PGD A"]["nqh"] == 3
    assert m["PGD A"]["no_dh_nam"] == 100
    assert m["PGD B"]["no_dh_nam"] == 300


def test_den_han_filters_and_groupby():
    df = pd.DataFrame(
        [
            {
                COT_TEN_PGD: "PGD A",
                COT_TEN_CT: "CT1",
                COT_TEN_XA: "Xã 1",
                COT_SO_KU: "KU1",
                COT_MA_KH: "KH1",
                COT_TONG_DU_NO: 100,
                COT_NGAY_DH: "21/05/2026",
            },
            {
                COT_TEN_PGD: "PGD A",
                COT_TEN_CT: "CT1",
                COT_TEN_XA: "Xã 1",
                COT_SO_KU: "KU2",
                COT_MA_KH: "KH2",
                COT_TONG_DU_NO: 0,
                COT_NGAY_DH: "22/05/2026",
            },
            {
                COT_TEN_PGD: "PGD B",
                COT_TEN_CT: "CT2",
                COT_TEN_XA: "Xã 2",
                COT_SO_KU: "KU3",
                COT_MA_KH: "KH3",
                COT_TONG_DU_NO: 300,
                COT_NGAY_DH: "01/01/2027",
            },
        ]
    )
    dt = tongquan_service.chuan_hoa_ngay(df, COT_NGAY_DH, dayfirst=True)
    dt_loc = tongquan_service.ap_dung_loc_ket_hop(
        dt,
        cot_pgd=COT_TEN_PGD,
        cot_ct=COT_TEN_CT,
        cot_xa=COT_TEN_XA,
        loc_pgd=["PGD A"],
        loc_ct=[],
        loc_xa=[],
    )
    dt_loc = tongquan_service.loc_du_no_duong(dt_loc, COT_TONG_DU_NO)
    df_1m = tongquan_service.loc_den_han(
        dt_loc,
        cot_ngay_dh=COT_NGAY_DH,
        tu_ngay=pd.Timestamp("2026-05-01"),
        den_ngay=pd.Timestamp("2026-06-01"),
    )
    assert len(df_1m) == 1
    tg = tongquan_service.tong_hop_den_han(
        df_1m,
        group_cols=[COT_TEN_PGD, COT_TEN_XA],
        cot_so_ku=COT_SO_KU,
        cot_ma_kh=COT_MA_KH,
        cot_tdn=COT_TONG_DU_NO,
    )
    assert len(tg) == 1
    assert tg.iloc[0]["_mon"] == 1
    assert tg.iloc[0]["_kh"] == 1
    assert tg.iloc[0]["_no"] == 100
