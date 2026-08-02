"""Regression tests for Mã NĐT địa phương management helpers."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from tabs import tab_quan_ly_ndt_dp as tab_ndt


def test_hstd_selection_map_giu_duoc_bo_tick_thu_cong_sau_chon_tat_ca() -> None:
    selection_state: dict[str, bool] = {}
    row_keys = ["3|INV001", "3|INV002", "6|INV003"]

    tab_ndt._set_hstd_selection(selection_state, row_keys, True)
    tab_ndt._sync_hstd_selection(
        selection_state,
        row_keys,
        pd.DataFrame({"Chọn": [True, False, True]}),
    )

    assert selection_state == {
        "3|INV001": True,
        "3|INV002": False,
        "6|INV003": True,
    }


def test_clear_hstd_editor_state_xoa_ca_key_phu(monkeypatch) -> None:
    state = {
        "ndt_dp_hstd_editor": {"edited_rows": {}},
        "ndt_dp_hstd_editor-edited": {"0": {"Chọn": True}},
        "ndt_dp_hstd_selection": {"3|INV001": True},
        "other": "kept",
    }
    monkeypatch.setattr(tab_ndt.st, "session_state", state)

    tab_ndt._clear_hstd_editor_state()

    assert "ndt_dp_hstd_editor" not in state
    assert "ndt_dp_hstd_editor-edited" not in state
    assert state["ndt_dp_hstd_selection"] == {"3|INV001": True}
    assert state["other"] == "kept"


def test_rules_signature_doi_khi_rule_list_doi() -> None:
    before = tab_ndt._rules_signature([{"ma_ct": 3, "ma": "INV001", "cap": "xa"}])
    after = tab_ndt._rules_signature([
        {"ma_ct": 3, "ma": "INV001", "cap": "xa"},
        {"ma_ct": 6, "ma": "INV001", "cap": "tinh"},
    ])

    assert before != after
    assert after == ((3, "INV001", "xa"), (6, "INV001", "tinh"))


def test_dem_ma_moi_nhanh_truyen_rule_signature(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_scan(df_full, ds_all, ts_hstd, rules_sig):
        captured["rules_sig"] = rules_sig
        return pd.DataFrame({tab_ndt._COL_DA_CO_RULE: [False, True, False]})

    monkeypatch.setattr(tab_ndt, "_quet_ma_tu_hstd", fake_scan)

    result = tab_ndt._dem_ma_moi_nhanh(
        pd.DataFrame({"dummy": [1]}),
        [{"ma_ct": 3, "ma": "INV001", "cap": "xa"}],
        123.0,
    )

    assert result == 2
    assert captured["rules_sig"] == ((3, "INV001", "xa"),)


def test_ghi_chu_tu_editor_row_fallback_sang_ten_ndt() -> None:
    row = {
        "Ghi chú": "",
        tab_ndt._COL_TEN_NDT_VIEW: "UBND xã Long Thành",
    }

    assert tab_ndt._ghi_chu_tu_editor_row(row) == "UBND xã Long Thành"


def test_ghi_chu_tu_editor_row_uu_tien_ghi_chu_user_nhap() -> None:
    row = {
        "Ghi chú": "Ngân sách xã ủy thác",
        tab_ndt._COL_TEN_NDT_VIEW: "UBND xã Long Thành",
    }

    assert tab_ndt._ghi_chu_tu_editor_row(row) == "Ngân sách xã ủy thác"


def test_fragment_editor_chon_tat_ca_dung_fragment_rerun() -> None:
    source = Path(tab_ndt.__file__).read_text(encoding="utf-8")
    fragment_source = source.split("def _fragment_editor_ma_moi", 1)[1].split("def _render_danh_sach_theo_cap", 1)[0]

    assert 'st.rerun(scope="fragment")' in fragment_source
    assert fragment_source.count('st.rerun(scope="fragment")') == 2
    assert 'st.rerun()' not in fragment_source
