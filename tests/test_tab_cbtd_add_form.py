"""Regression tests for the CBTD add form widget-state reset."""
from __future__ import annotations

import inspect

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
