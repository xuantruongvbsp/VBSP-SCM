"""
Tests for services/uy_thac_service.py
Pure DataFrame logic + KV key generation + payload builders.
DB operations are monkeypatched.
"""
from __future__ import annotations

from datetime import date, datetime

import pandas as pd
import pytest

import db as db_module
from config import (
    COT_DU_NO_QH,
    COT_DVUT,
    COT_LAI_TON,
    COT_LAI_TON_QH,
    COT_NGAY_VAY,
    COT_SO_KU,
    COT_TEN_CT,
    COT_TEN_KH,
    COT_TEN_PGD,
    COT_TEN_TO,
    COT_TEN_XA,
    COT_TONG_DU_NO,
)
from data.pgd import pgd_slug
from services import uy_thac_service as svc


# ── fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def test_db(tmp_path, monkeypatch):
    db_file = str(tmp_path / "test.db")
    monkeypatch.setenv("VBSP_SCM_DB_PATH", db_file)
    db_module.reset_conn()
    db_module.init_db()
    yield db_module
    db_module.reset_conn()


def _df_ut():
    return pd.DataFrame({
        COT_DVUT:       ["DVUT A", "DVUT A", "DVUT B"],
        COT_TEN_TO:     ["Tổ 1", "Tổ 2", "Tổ 3"],
        COT_SO_KU:      ["KU1", "KU2", "KU3"],
        COT_TONG_DU_NO: [1_000_000, 2_000_000, 500_000],
        COT_DU_NO_QH:   [0, 100_000, 50_000],
        COT_LAI_TON:    [10_000, 20_000, 5_000],
        COT_TEN_KH:     ["KH A", "KH B", "KH C"],
        COT_TEN_XA:     ["Xã A", "Xã A", "Xã B"],
        COT_TEN_CT:     ["Chương trình 1", "Chương trình 2", "Chương trình 1"],
        COT_NGAY_VAY:   ["2026-01-15", "2026-03-20", "2025-12-01"],
    })


# ── tinh_theo_dvut ────────────────────────────────────────────────────────────

def test_tinh_theo_dvut_empty_df():
    result = svc.tinh_theo_dvut(pd.DataFrame())
    assert result.empty


def test_tinh_theo_dvut_missing_col():
    df = pd.DataFrame({"col_khac": [1, 2]})
    result = svc.tinh_theo_dvut(df)
    assert result.empty


def test_tinh_theo_dvut_aggregates_correctly():
    df = _df_ut()
    result = svc.tinh_theo_dvut(df)
    assert not result.empty
    assert COT_DVUT in result.columns
    row_a = result[result[COT_DVUT] == "DVUT A"].iloc[0]
    assert row_a["tong_dn"] == 3_000_000
    assert row_a["nqh"] == 100_000
    assert row_a["so_to"] == 2


def test_tinh_theo_dvut_counts_same_to_name_in_different_xa():
    df = pd.DataFrame({
        COT_DVUT: ["DVUT A", "DVUT A"],
        COT_TEN_PGD: ["PGD 1", "PGD 1"],
        COT_TEN_XA: ["Xã 1", "Xã 2"],
        COT_TEN_TO: ["Tổ 1", "Tổ 1"],
        COT_SO_KU: ["KU1", "KU2"],
        COT_TONG_DU_NO: [1_000_000, 2_000_000],
    })

    result = svc.tinh_theo_dvut(df)

    row = result[result[COT_DVUT] == "DVUT A"].iloc[0]
    assert row["so_to"] == 2


def test_tinh_theo_dvut_respects_order():
    df = _df_ut()
    order = ["DVUT B", "DVUT A"]
    result = svc.tinh_theo_dvut(df, dvut_order=order)
    assert list(result[COT_DVUT]) == order


# ── loc_mau06 ─────────────────────────────────────────────────────────────────

def test_loc_mau06_basic_date_filter():
    df = _df_ut()
    result = svc.loc_mau06(df, "2026-01-01", "2026-12-31")
    assert len(result) == 2


def test_loc_mau06_excludes_outside_range():
    df = _df_ut()
    result = svc.loc_mau06(df, "2026-01-01", "2026-04-30")
    assert len(result) == 2
    result_narrow = svc.loc_mau06(df, "2026-01-01", "2026-02-01")
    assert len(result_narrow) == 1


def test_loc_mau06_empty_df_returns_empty():
    result = svc.loc_mau06(pd.DataFrame(), "2026-01-01", "2026-12-31")
    assert result.empty


def test_loc_mau06_missing_col_returns_empty():
    df = pd.DataFrame({"col_khac": [1]})
    result = svc.loc_mau06(df, "2026-01-01", "2026-12-31")
    assert result.empty


# ── loc_mau15 ────────────────────────────────────────────────────────────────

def test_loc_mau15_filters_by_to():
    df = _df_ut()
    result = svc.loc_mau15(df, "Tổ 1")
    assert len(result) == 1
    assert COT_TEN_KH in result.columns


def test_loc_mau15_adds_no_lai_column():
    df = _df_ut()
    result = svc.loc_mau15(df, "Tổ 1")
    assert "Nợ lãi" in result.columns
    row = result.iloc[0]
    assert row["Nợ lãi"] == 10_000


def test_loc_mau15_combines_lai_ton_and_qh():
    df = _df_ut()
    df[COT_LAI_TON_QH] = [5_000, 8_000, 3_000]
    result = svc.loc_mau15(df, "Tổ 1")
    assert result.iloc[0]["Nợ lãi"] == 15_000


def test_loc_mau15_empty_df_returns_empty():
    result = svc.loc_mau15(pd.DataFrame(), "Tổ 1")
    assert result.empty


# ── co_du_lieu_to ─────────────────────────────────────────────────────────────

def test_co_du_lieu_to_true():
    df = _df_ut()
    assert svc.co_du_lieu_to(df) is True


def test_co_du_lieu_to_empty_df():
    assert svc.co_du_lieu_to(pd.DataFrame()) is False


def test_co_du_lieu_to_missing_col():
    df = pd.DataFrame({"col_khac": [1, 2]})
    assert svc.co_du_lieu_to(df) is False


def test_co_du_lieu_to_all_null():
    df = pd.DataFrame({COT_TEN_TO: [None, None, float("nan")]})
    assert svc.co_du_lieu_to(df) is False


# ── kv_key_bb_ct_cx ───────────────────────────────────────────────────────────

def test_kv_key_bb_ct_cx_tinh():
    key = svc.kv_key_bb_ct_cx("tinh", "PGD Long Thành", 2026)
    slug = pgd_slug("PGD Long Thành")
    assert key == f"ut_bbct_{slug}_2026"


def test_kv_key_bb_ct_cx_xa():
    key = svc.kv_key_bb_ct_cx("xa", "PGD Long Thành", 2026)
    slug = pgd_slug("PGD Long Thành")
    assert key == f"ut_bbcx_{slug}_2026"


def test_kv_key_bb_ct_cx_no_scope():
    key = svc.kv_key_bb_ct_cx("tinh", None, 2026)
    assert key == "ut_bbct_cn_2026"


# ── build_payload functions ───────────────────────────────────────────────────

def test_build_payload_mau15_returns_dict_and_filename():
    du_lieu, ten_file = svc.build_payload_mau15(
        pgd="PGD Long Thành",
        ten_xa="Xã A",
        ten_to="Tổ 1",
        to_truong="Ông X",
        ma_to="T001",
        dia_chi="Địa chỉ A",
        can_bo_kt="CBTD A",
        ngay_chot=date(2026, 5, 20),
        pgd_scope="PGD Long Thành",
    )
    assert isinstance(du_lieu, dict)
    assert du_lieu["ten_to"] == "Tổ 1"
    assert du_lieu["to_truong"] == "Ông X"
    assert "20052026" in ten_file


def test_build_payload_bb_xac_minh_formats_so_tien():
    du_lieu, ten_file = svc.build_payload_bb_xac_minh(
        ten_kh="Khách hàng A",
        so_ku="KU001",
        so_tien=50_000_000.0,
        ly_do="Không trả được",
        bien_phap="Gia hạn",
        can_bo_lap="CBTD B",
        ngay_lap=date(2026, 5, 20),
        pgd_scope="PGD Long Thành",
    )
    assert "50,000,000.0" in du_lieu["so_tien"] or "50000000" in du_lieu["so_tien"].replace(",", "")
    assert du_lieu["ngay"] == 20
    assert du_lieu["thang"] == 5
    assert "KU001" in ten_file


def test_build_payload_bc_th_returns_dict_and_filename():
    du_lieu, ten_file = svc.build_payload_bc_th(
        don_vi_kt="Chi nhánh",
        truong_doan="Ông Y",
        cap_uy="Huyện ủy",
        dia_danh="Đồng Nai",
        ngay_bc=date(2026, 5, 20),
        noi_dung_kt="Kiểm tra định kỳ",
        nx_ctxh="Tốt",
        nx_to="Khá",
        nx_to_vien="Tốt",
        kn_ctxh="Tiếp tục",
        kn_nhcs="Tăng cường",
        kn_cap_tren="Hỗ trợ thêm",
        nam_td=2026,
    )
    assert du_lieu["truong_doan"] == "Ông Y"
    assert ten_file == "BaoCaoTH_UyThac_2026"


# ── doc_ds_bien_ban / luu_bien_ban ────────────────────────────────────────────

def test_doc_ds_bien_ban_empty_key(test_db):
    result = svc.doc_ds_bien_ban("ut_bbct_test_2026")
    assert result == []


def test_luu_va_doc_bien_ban(test_db):
    key = "ut_bbct_test_2026"
    record = {
        "id": "rec_001",
        "loai": "CT",
        "loai_cap": "tinh",
        "ten_don_vi": "PGD Test",
        "ngay_kt": "2026-05-20",  # string — date object không JSON-serializable
    }
    svc.luu_bien_ban(key, [], record, username="tester")
    result = svc.doc_ds_bien_ban(key)
    assert len(result) == 1
    assert result[0]["id"] == "rec_001"


# ── cap_nhat_trang_thai_bien_ban ──────────────────────────────────────────────

def test_cap_nhat_trang_thai_found(test_db):
    key = "ut_bbct_test2_2026"
    record = {"id": "r1", "loai_cap": "tinh", "ten_don_vi": "PGD X", "ngay_kt": "2026-05-20"}
    db_module.ghi_kv(key, [record], "tester")  # list of dict → JSON-safe

    ok = svc.cap_nhat_trang_thai_bien_ban(
        key, "r1", "Đã xử lý xong", "tester", "PGD X"
    )
    assert ok is True
    updated = db_module.doc_kv(key)
    assert updated[0]["trang_thai"] == "da_xu_ly"
    assert updated[0]["ket_qua_xu_ly"] == "Đã xử lý xong"


def test_cap_nhat_trang_thai_not_found(test_db):
    key = "ut_bbct_test3_2026"
    db_module.ghi_kv(key, [{"id": "r99", "loai_cap": "tinh"}], "tester")

    ok = svc.cap_nhat_trang_thai_bien_ban(key, "r_not_exist", "Xử lý", "tester")
    assert ok is False


def test_cap_nhat_trang_thai_empty_list(test_db):
    key = "ut_bbct_test4_2026"
    db_module.ghi_kv(key, [], "tester")

    ok = svc.cap_nhat_trang_thai_bien_ban(key, "r1", "Xử lý", "tester")
    assert ok is False
