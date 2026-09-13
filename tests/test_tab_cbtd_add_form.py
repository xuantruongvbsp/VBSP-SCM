"""Regression tests for the CBTD add form widget-state reset."""
from __future__ import annotations

import inspect

import pandas as pd

import tabs.tab_cbtd as tab_cbtd


def test_cbtd_add_form_prefix_changes_by_version():
    assert tab_cbtd._cbtd_add_form_prefix("cn_", 0) == "cn_cbtd_add_v0_"
    assert tab_cbtd._cbtd_add_form_prefix("cn_", 1) == "cn_cbtd_add_v1_"


def test_cbtd_add_form_uses_versioned_widget_keys():
    source = inspect.getsource(tab_cbtd.render)

    assert "_kp_g2 = f\"{_kp}lv2_2_\"" in source
    assert "add_ver_key = f\"{_kp_g2}cbtd_add_ver\"" in source
    assert "add_kp = _cbtd_add_form_prefix(_kp_g2, add_ver)" in source
    assert "key=f\"{add_kp}cbtd_dgd_new\"" in source
    assert "st.session_state[add_ver_key] = add_ver + 1" in source


def test_cbtd_edit_form_keys_are_scoped_to_selected_cbtd_and_pgd():
    source = inspect.getsource(tab_cbtd.render)

    assert "edit_kp = f\"{_kp_g2}edit_{_pgd_slug_ma(chon_sua)}_\"" in source
    assert "key=f\"{edit_kp}cbtd_ten_sua\"" in source
    assert "key=f\"{edit_kp}cbtd_pgd_sua\"" in source
    assert "key=f\"{edit_kp}cbtd_dgd_sua_{_pgd_slug_ma(pgd_sua)}\"" in source


def test_ky_hstd_hien_tai_lay_tu_ngay_so_lieu_khong_lay_ngay_may():
    df = pd.DataFrame({"Ngày số liệu": ["30/06/2026", "2026-07-31"]})

    nam, thang, ngay = tab_cbtd._ky_hstd_hien_tai(df)

    assert (nam, thang) == (2026, 7)
    assert ngay.strftime("%d/%m/%Y") == "31/07/2026"


def test_tao_bang_tong_hop_sap_giam_va_tinh_delta_khong_lan_nan():
    hien_tai = pd.DataFrame([
        {"Ma_CBTD": "CB01", "Ho_ten": "A", "PGD": "PGD A",
         "Tong_du_no": 100.0, "Du_no_trong_han": 90.0, "Du_no_qh": 10.0,
         "TL_QH_pct": 10.0, "Cho_vay_thang": 5.0, "Thu_no_thang": 2.0},
        {"Ma_CBTD": "CB02", "Ho_ten": "B", "PGD": "PGD B",
         "Tong_du_no": 200.0, "Du_no_trong_han": 195.0, "Du_no_qh": 5.0,
         "TL_QH_pct": 2.5, "Cho_vay_thang": 7.0, "Thu_no_thang": 1.0},
    ])
    thang_truoc = pd.DataFrame([
        {"Ma_CBTD": "CB01", "Tong_du_no": float("nan"), "Du_no_qh": 2.0},
        {"Ma_CBTD": "CB02", "Tong_du_no": 50.0, "Du_no_qh": 5.0},
    ])

    result = tab_cbtd._tao_bang_tong_hop(hien_tai, thang_truoc, None)

    assert result["Ma_CBTD"].tolist() == ["CB02", "CB01", "TỔNG"]
    assert result["STT"].tolist() == [1, 2, ""]
    assert result.loc[0, "DN_dTTr"] == 150.0
    assert result.loc[1, "DN_dTTr"] == 100.0
    assert result.loc[2, "DN_dTTr"] == 250.0
    assert result.loc[1, "QH_dTTr"] == 8.0
    assert pd.isna(result.loc[0, "DN_dNY"])
    assert result.loc[2, "TL_QH_pct"] == round(15.0 / 300.0 * 100, 1)
