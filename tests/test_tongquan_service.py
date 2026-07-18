"""Tests cho services/tongquan_service.py — các hàm pure function."""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import (
    COT_DU_NO_KHOANH,
    COT_DU_NO_QH,
    COT_DU_NO_TH,
    COT_LAI_TON,
    COT_MA_KH,
    COT_MA_TO,
    COT_NGAY_DH,
    COT_NGAY_SL,
    COT_NGUON_VON,
    COT_SO_KU,
    COT_TEN_CT,
    COT_TEN_PGD,
    COT_TEN_TO,
    COT_TEN_XA,
    COT_TONG_DU_NO,
)
from services import tongquan_service
from services.tongquan_service import (
    ap_dung_loc_ket_hop,
    chuan_hoa_ngay,
    dem_so_to_hstd,
    loc_du_no_duong,
    loc_ho_so_con_du_no,
    tinh_co_cau_ct,
    tinh_kpi_tongquan,
    tong_chi_tieu_den_han,
)


@pytest.fixture
def df_co_ban() -> pd.DataFrame:
    """DataFrame mẫu với 3 PGD, 6 món vay."""
    return pd.DataFrame(
        {
            COT_TEN_PGD: ["PGD A", "PGD A", "PGD B", "PGD B", "PGD C", "PGD C"],
            COT_TONG_DU_NO: [100, 200, 0, 50, 300, 0],
            COT_DU_NO_TH: [80, 180, 0, 50, 280, 0],
            COT_DU_NO_QH: [10, 20, 0, 0, 20, 0],
            COT_DU_NO_KHOANH: [10, 0, 0, 0, 0, 0],
            COT_MA_KH: ["KH1", "KH2", "KH3", "KH4", "KH5", "KH6"],
            COT_SO_KU: ["KU1", "KU2", "KU3", "KU4", "KU5", "KU6"],
            COT_TEN_CT: ["CT1", "CT2", "CT1", "CT3", "CT2", "CT1"],
            COT_NGUON_VON: [1, 1, 2, 2, 1, 2],
            COT_TEN_XA: ["Xã 1", "Xã 1", "Xã 2", "Xã 2", "Xã 3", "Xã 3"],
            COT_TEN_TO: ["Tổ 1", "Tổ 1", "Tổ 2", "Tổ 2", "Tổ 3", "Tổ 3"],
            COT_MA_TO: ["M1", "M1", "M2", "M2", "M3", "M3"],
            COT_NGAY_SL: ["01/01/2025"] * 6,
            COT_NGAY_DH: pd.to_datetime(["2025-06-01"] * 6),
        }
    )


def test_loc_ho_so_con_du_no_loai_dong_du_no_0_va_giu_qh_khoanh(df_co_ban: pd.DataFrame) -> None:
    result = loc_ho_so_con_du_no(df_co_ban, COT_TONG_DU_NO, COT_DU_NO_QH, COT_DU_NO_KHOANH)
    assert result[COT_SO_KU].tolist() == ["KU1", "KU2", "KU4", "KU5"]


def test_loc_ho_so_con_du_no_het_so_du() -> None:
    df = pd.DataFrame(
        {
            COT_TONG_DU_NO: [0, 0, 0],
            COT_DU_NO_QH: [0, 0, 0],
            COT_MA_KH: ["A", "B", "C"],
        }
    )
    result = loc_ho_so_con_du_no(df, COT_TONG_DU_NO, COT_DU_NO_QH)
    assert result.empty


def test_loc_ho_so_con_du_no_giu_dong_co_qh() -> None:
    df = pd.DataFrame(
        {
            COT_TONG_DU_NO: [0, 100],
            COT_DU_NO_QH: [50, 0],
            COT_MA_KH: ["A", "B"],
        }
    )
    result = loc_ho_so_con_du_no(df, COT_TONG_DU_NO, COT_DU_NO_QH)
    assert result[COT_MA_KH].tolist() == ["A", "B"]


def test_tinh_kpi_tongquan_basic_and_no_mutation(df_co_ban: pd.DataFrame) -> None:
    df_before = df_co_ban.copy(deep=True)
    kpi = tinh_kpi_tongquan(
        df_co_ban,
        cot_tdn=COT_TONG_DU_NO,
        cot_dth=COT_DU_NO_TH,
        cot_dqh=COT_DU_NO_QH,
        cot_nk=COT_DU_NO_KHOANH,
        cot_ku=COT_SO_KU,
        cot_ma_kh=COT_MA_KH,
    )
    assert kpi["tdn"] == 650
    assert kpi["dth"] == 590
    assert kpi["dqh"] == 50
    assert kpi["dnk"] == 10
    assert kpi["n_mon_vay"] == 4
    assert kpi["n_kh"] == 4
    assert df_co_ban.equals(df_before)


def test_tinh_kpi_tongquan_bo_qua_ho_so_du_no_0_khi_dem() -> None:
    df = pd.DataFrame(
        [
            {
                COT_TONG_DU_NO: "1000",
                COT_DU_NO_TH: "1000",
                COT_DU_NO_QH: "0",
                COT_DU_NO_KHOANH: "0",
                COT_SO_KU: "KU_ACTIVE",
                COT_MA_KH: "KH_ACTIVE",
            },
            {
                COT_TONG_DU_NO: "0",
                COT_DU_NO_TH: "0",
                COT_DU_NO_QH: "0",
                COT_DU_NO_KHOANH: "0",
                COT_SO_KU: "KU_CLOSED",
                COT_MA_KH: "KH_CLOSED",
            },
            {
                COT_TONG_DU_NO: "0",
                COT_DU_NO_TH: "0",
                COT_DU_NO_QH: "10",
                COT_DU_NO_KHOANH: "0",
                COT_SO_KU: "KU_QH",
                COT_MA_KH: "KH_QH",
            },
        ]
    )
    kpi = tinh_kpi_tongquan(
        df,
        cot_tdn=COT_TONG_DU_NO,
        cot_dth=COT_DU_NO_TH,
        cot_dqh=COT_DU_NO_QH,
        cot_nk=COT_DU_NO_KHOANH,
        cot_ku=COT_SO_KU,
        cot_ma_kh=COT_MA_KH,
    )
    assert kpi["n_mon_vay"] == 2
    assert kpi["n_kh"] == 2
    assert kpi["tdn"] == 1000
    assert kpi["dqh"] == 10


def test_dem_so_to_hstd_uu_tien_ma_to(df_co_ban: pd.DataFrame) -> None:
    n_to = dem_so_to_hstd(df_co_ban, COT_TEN_PGD, COT_TEN_TO, cot_ma_to=COT_MA_TO)
    assert n_to == 3


def test_dem_so_to_hstd_fallback_theo_xa_ten_to(df_co_ban: pd.DataFrame) -> None:
    df = df_co_ban.drop(columns=[COT_MA_TO])
    n_to = dem_so_to_hstd(df, COT_TEN_PGD, COT_TEN_TO, cot_ten_xa=COT_TEN_XA)
    assert n_to == 3


def test_dem_so_to_hstd_bo_qua_ten_rong() -> None:
    df = pd.DataFrame(
        {
            COT_TEN_PGD: ["PGD A", "PGD A", "PGD B"],
            COT_TEN_TO: ["Tổ 1", "", None],
            COT_TONG_DU_NO: [1_000_000, 2_000_000, 3_000_000],
        }
    )
    assert dem_so_to_hstd(df, COT_TEN_PGD, COT_TEN_TO) == 1


def test_tinh_co_cau_ct_basic() -> None:
    df = pd.DataFrame(
        [
            {COT_TEN_CT: "CT1", COT_MA_KH: "KH1", COT_SO_KU: "KU1", COT_TONG_DU_NO: 100, COT_DU_NO_QH: 1, COT_DU_NO_KHOANH: 0, COT_NGUON_VON: 1},
            {COT_TEN_CT: "CT1", COT_MA_KH: "KH2", COT_SO_KU: "KU2", COT_TONG_DU_NO: 200, COT_DU_NO_QH: 0, COT_DU_NO_KHOANH: 10, COT_NGUON_VON: 2},
            {COT_TEN_CT: "CT2", COT_MA_KH: "KH1", COT_SO_KU: "KU3", COT_TONG_DU_NO: 300, COT_DU_NO_QH: 3, COT_DU_NO_KHOANH: 0, COT_NGUON_VON: 1},
        ]
    )
    out = tinh_co_cau_ct(
        df,
        col_khoanh=COT_DU_NO_KHOANH,
        col_gn="",
        cols_tn_key="",
        cot_ten_ct=COT_TEN_CT,
        cot_tdn=COT_TONG_DU_NO,
        cot_dqh=COT_DU_NO_QH,
        cot_dnk=COT_DU_NO_KHOANH,
        cot_nv=COT_NGUON_VON,
        cot_ma_kh=COT_MA_KH,
        cot_so_ku=COT_SO_KU,
    )
    m = {r["ten_ct"]: r for r in out.to_dict("records")}
    assert set(["ten_ct", "du_no", "so_kh", "so_mon", "ty_trong", "du_no_tw", "du_no_dp"]).issubset(out.columns)
    assert m["CT1"]["du_no"] == 300
    assert m["CT1"]["so_kh"] == 2
    assert m["CT1"]["so_mon"] == 2
    assert m["CT2"]["du_no"] == 300
    assert abs(out["ty_trong"].sum() - 100.0) < 0.2


def test_tinh_tqpgd_extended_basic() -> None:
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


def test_loc_du_no_duong(df_co_ban: pd.DataFrame) -> None:
    result = loc_du_no_duong(df_co_ban, COT_TONG_DU_NO)
    assert result[COT_SO_KU].tolist() == ["KU1", "KU2", "KU4", "KU5"]


def test_chuan_hoa_ngay() -> None:
    df = pd.DataFrame({COT_NGAY_DH: ["01/01/2025", "15/06/2025"]})
    result = chuan_hoa_ngay(df, COT_NGAY_DH, dayfirst=True)
    assert pd.api.types.is_datetime64_any_dtype(result[COT_NGAY_DH])


def test_ap_dung_loc_ket_hop_nhieu_dieu_kien(df_co_ban: pd.DataFrame) -> None:
    result = ap_dung_loc_ket_hop(
        df_co_ban,
        cot_pgd=COT_TEN_PGD,
        cot_ct=COT_TEN_CT,
        cot_xa=COT_TEN_XA,
        loc_pgd=["PGD A", "PGD B"],
        loc_ct=["CT1"],
        loc_xa=["Xã 1", "Xã 2"],
    )
    assert result[COT_SO_KU].tolist() == ["KU1", "KU3"]


def test_den_han_filters_and_groupby() -> None:
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
    tg = tongquan_service.tong_hop_den_han(
        df_1m,
        group_cols=[COT_TEN_PGD, COT_TEN_XA],
        cot_so_ku=COT_SO_KU,
        cot_ma_kh=COT_MA_KH,
        cot_tdn=COT_TONG_DU_NO,
    )
    assert len(df_1m) == 1
    assert len(tg) == 1
    assert tg.iloc[0]["_mon"] == 1
    assert tg.iloc[0]["_kh"] == 1
    assert tg.iloc[0]["_no"] == 100


def test_tong_chi_tieu_den_han(df_co_ban: pd.DataFrame) -> None:
    kq = tong_chi_tieu_den_han(
        df_co_ban,
        cot_tdn=COT_TONG_DU_NO,
        cot_so_ku=COT_SO_KU,
        cot_ma_kh=COT_MA_KH,
    )
    assert kq["tong_no"] == 650
    assert kq["tong_mon"] == 6
    assert kq["tong_kh"] == 6
