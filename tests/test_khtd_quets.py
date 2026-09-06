"""Hồi quy helper quét chương trình có dư nợ của KHTD."""
from __future__ import annotations

import re

import pandas as pd

from config import (
    COT_MA_CHUONG_TRINH,
    COT_NGUON_VON,
    COT_TEN_CT,
    COT_TEN_PGD,
    COT_TEN_XA,
    COT_TONG_DU_NO,
    DS_PGD,
    PGD_XA_MAP,
)
from tabs.tab_khtd import (
    KHTD_CN_NHOM_MA_CT,
    MA_KEYS_CO_KHTD,
    _quet_ct_co_du_no,
    _sanitize_ui_prefs,
    _ten_ct_base,
    _ui_prefs_key,
)
from tabs.tab_khtd_nhap import (
    _hien_thi_bang_tom_tat_xa,
    _ndt_dp_rules_cache_key,
    _phan_bo_kh_xa_theo_keys,
    _reset_khtd_xa_selection_if_stale,
    _render_bang_thuc_hien_95_xa,
    _tao_bang_thuc_hien_xa_theo_ct,
    _them_ke_hoach_vao_bang_xa,
    _ten_xa_hien_thi_khtd,
)


def test_bang_thuc_hien_xa_loc_chuong_trinh_va_giu_du_dia_ban() -> None:
    dia_ban = {
        "PGD A": ["Xã An Bình", "Phường Bình Minh"],
        "PGD B": ["Xã Hòa Phú"],
    }
    df = pd.DataFrame(
        {
            COT_TEN_PGD: ["PGD A", "PGD A", "PGD A", "PGD B"],
            COT_TEN_XA: ["An Bình", "Xã An Bình", "phường Bình Minh", "Hòa Phú"],
            COT_MA_CHUONG_TRINH: [1, 1, 2, 1],
            COT_NGUON_VON: [1, 2, 1, 1],
            COT_TONG_DU_NO: [10_000_000, 2_000_000, 99_000_000, 5_000_000],
        }
    )

    result = _tao_bang_thuc_hien_xa_theo_ct(df, 1, dia_ban)

    assert result["Xã/Phường"].tolist() == ["Xã An Bình", "Xã Bình Minh", "Xã Hòa Phú"]
    assert result["TH TW"].tolist() == [10_000_000.0, 0.0, 5_000_000.0]
    assert result["TH ĐP"].tolist() == [2_000_000.0, 0.0, 0.0]
    assert result["Tổng TH"].tolist() == [12_000_000.0, 0.0, 5_000_000.0]


def test_bang_thuc_hien_xa_rong_van_co_du_95_dia_ban() -> None:
    result = _tao_bang_thuc_hien_xa_theo_ct(pd.DataFrame(), None)

    assert len(result) == 95
    assert result["Tổng TH"].sum() == 0
    assert result.loc[result["PGD"] == "Hội sở Chi nhánh tỉnh", "Xã/Phường"].head(3).tolist() == [
        "Phường Phước Tân",
        "Phường Biên Hòa",
        "Phường Trấn Biên",
    ]
    assert "Xã Long Thành" in result["Xã/Phường"].tolist()
    assert "Xã Đak Lua" in result["Xã/Phường"].tolist()


def test_ten_xa_hien_thi_khtd_theo_danh_muc_hanh_chinh() -> None:
    assert _ten_xa_hien_thi_khtd("Phước Tân") == "Phường Phước Tân"
    assert _ten_xa_hien_thi_khtd("phường Long Thành") == "Xã Long Thành"
    assert _ten_xa_hien_thi_khtd("phường Dầu Giây") == "Xã Dầu Giây"
    assert _ten_xa_hien_thi_khtd("Dak Lua") == "Xã Đak Lua"


def test_bang_thuc_hien_xa_keo_ke_hoach_da_luu_theo_chuong_trinh() -> None:
    dia_ban = {"PGD A": ["An Bình", "Bình Minh"]}
    df = pd.DataFrame(
        {
            COT_TEN_PGD: ["PGD A"],
            COT_TEN_XA: ["An Bình"],
            COT_MA_CHUONG_TRINH: [1],
            COT_NGUON_VON: [1],
            COT_TONG_DU_NO: [4_000_000],
        }
    )
    bang = _tao_bang_thuc_hien_xa_theo_ct(df, 1, dia_ban)
    result = _them_ke_hoach_vao_bang_xa(
        bang,
        {"An Bình|1_TW": 10_000_000, "An Bình|1_DP": 5_000_000},
        1,
    )

    assert result.loc[0, "KH TW"] == 10_000_000
    assert result.loc[0, "KH ĐP"] == 5_000_000
    assert result.loc[0, "Tổng KH"] == 15_000_000
    assert round(float(result.loc[0, "TL %"]), 2) == 26.67
    assert result.loc[1, "Tổng KH"] == 0


def test_phan_bo_kh_xa_theo_keys_giu_ty_trong_cu_khi_co_nhieu_key_con() -> None:
    kh_xa = {"Xã A|3_DP_TINH": 30_000_000, "Xã A|3_DP_XA": 70_000_000}

    _phan_bo_kh_xa_theo_keys(kh_xa, "Xã A", ["3_DP_TINH", "3_DP_XA"], 200_000_000)

    assert kh_xa["Xã A|3_DP_TINH"] == 60_000_000
    assert kh_xa["Xã A|3_DP_XA"] == 140_000_000


def test_render_bang_95_xa_luu_ke_hoach_vao_kv_xa(monkeypatch) -> None:
    saved: dict[str, dict[str, float]] = {}
    gia_tri_nhap = {"tw": 123.0, "dp": 45.0}

    monkeypatch.setattr("tabs.tab_khtd_nhap.st.selectbox", lambda *args, **kwargs: 1)
    monkeypatch.setattr("tabs.tab_khtd_nhap.xuat_excel", lambda sheets: b"xlsx")
    monkeypatch.setattr("tabs.tab_khtd_nhap.ts_file", lambda path: 0.0)
    monkeypatch.setattr("tabs.tab_khtd_nhap.st.download_button", lambda *args, **kwargs: None)
    monkeypatch.setattr("tabs.tab_khtd_nhap.st.rerun", lambda: None)
    monkeypatch.setattr("tabs.tab_khtd_nhap.db.ghi_audit", lambda *args, **kwargs: None)
    monkeypatch.setattr("tabs.tab_khtd_nhap.st.form_submit_button", lambda *args, **kwargs: True)

    def fake_render_trieu_text_input(container, *, label, widget_key, value_trieu, help_text=None):
        if widget_key.endswith("_0_tw"):
            return gia_tri_nhap["tw"]
        if widget_key.endswith("_0_dp"):
            return gia_tri_nhap["dp"]
        return 0.0

    def fake_luu_kv(key, data, username):
        saved["key"] = key
        saved["data"] = dict(data)
        saved["username"] = username
        return True

    monkeypatch.setattr("tabs.tab_khtd_nhap.st.data_editor", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Không dùng data_editor để nhập nhanh 95 xã")))
    monkeypatch.setattr("tabs.tab_khtd_nhap._render_trieu_text_input", fake_render_trieu_text_input)
    monkeypatch.setattr("tabs.tab_khtd_nhap._luu_kv", fake_luu_kv)

    _render_bang_thuc_hien_95_xa(pd.DataFrame(), {}, "tester", True)

    assert saved["key"] == "khtd_xa"
    assert saved["username"] == "tester"
    assert saved["data"]["Phước Tân|1_TW"] == 123_000_000
    assert saved["data"]["Phước Tân|1_DP"] == 45_000_000


def test_ndt_dp_rules_cache_key_doi_khi_sua_noi_dung_rule(monkeypatch) -> None:
    rules_a = [
        {"ma_ct": 3, "ma": "INV_B", "cap": "xa", "ghi_chu": "B"},
        {"ma_ct": 6, "ma": "INV_A", "cap": "tinh", "ghi_chu": "A"},
    ]
    rules_a_reversed = list(reversed(rules_a))
    rules_b = [
        {"ma_ct": 3, "ma": "INV_B", "cap": "tinh", "ghi_chu": "B"},
        {"ma_ct": 6, "ma": "INV_A", "cap": "tinh", "ghi_chu": "A"},
    ]

    monkeypatch.setattr("tabs.tab_khtd_nhap.db.doc_ndt_dp_rule_list", lambda: rules_a)
    key_a = _ndt_dp_rules_cache_key()
    monkeypatch.setattr("tabs.tab_khtd_nhap.db.doc_ndt_dp_rule_list", lambda: rules_a_reversed)
    key_a_reversed = _ndt_dp_rules_cache_key()
    monkeypatch.setattr("tabs.tab_khtd_nhap.db.doc_ndt_dp_rule_list", lambda: rules_b)
    key_b = _ndt_dp_rules_cache_key()

    assert key_a == key_a_reversed
    assert key_a != key_b


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


def test_ui_prefs_key_tach_theo_username() -> None:
    assert _ui_prefs_key("User A") == "khtd_ui_prefs_user_a"
    assert _ui_prefs_key("User B") == "khtd_ui_prefs_user_b"


def test_sanitize_ui_prefs_bo_value_khong_con_trong_options() -> None:
    pgd = next(ten for ten in DS_PGD if PGD_XA_MAP.get(ten))
    xa = PGD_XA_MAP[pgd][0]

    prefs = _sanitize_ui_prefs(
        {
            "khtd_sub_tab": 99,
            "khtd_bc_sub_tab": 0,
            "khtd_cn_nv_radio": "Tất cả",
            "khtd_xa_pgd_sel": pgd,
            "khtd_xa_xa_sel": xa,
        }
    )
    assert "khtd_sub_tab" not in prefs
    assert prefs["khtd_xa_pgd_sel"] == pgd
    assert prefs["khtd_xa_xa_sel"] == xa

    prefs = _sanitize_ui_prefs({"khtd_xa_pgd_sel": pgd, "khtd_xa_xa_sel": "Xã không còn tồn tại"})
    assert prefs == {"khtd_xa_pgd_sel": pgd}

    prefs = _sanitize_ui_prefs({"khtd_xa_pgd_sel": "PGD không còn tồn tại", "khtd_xa_xa_sel": xa})
    assert "khtd_xa_pgd_sel" not in prefs
    assert "khtd_xa_xa_sel" not in prefs


def test_reset_khtd_xa_selection_pop_stale_session_state(monkeypatch) -> None:
    state = {"khtd_xa_xa_sel": "Xã không còn thuộc PGD"}
    monkeypatch.setattr("tabs.tab_khtd_nhap.st.session_state", state)

    _reset_khtd_xa_selection_if_stale(["Xã A", "Xã B"])

    assert "khtd_xa_xa_sel" not in state


def test_reset_khtd_xa_selection_giu_xa_hop_le(monkeypatch) -> None:
    state = {"khtd_xa_xa_sel": "Xã A"}
    monkeypatch.setattr("tabs.tab_khtd_nhap.st.session_state", state)

    _reset_khtd_xa_selection_if_stale(["Xã A", "Xã B"])

    assert state["khtd_xa_xa_sel"] == "Xã A"


def test_bang_tom_tat_xa_phang_giu_thu_tu_stt_va_tong_cong(monkeypatch) -> None:
    markdown_calls: list[tuple[str, bool]] = []
    captions: list[str] = []
    xa = "Xã kiểm thử"
    expected_ma_ct: list[int] = []
    kh_xa: dict[str, float] = {}
    th_xa: dict[str, float] = {}

    for _, ds_ma_ct in KHTD_CN_NHOM_MA_CT:
        for ma_ct in ds_ma_ct:
            keys = [mk for mk in (f"{ma_ct}_TW", f"{ma_ct}_DP") if mk in MA_KEYS_CO_KHTD]
            if not keys:
                continue
            expected_ma_ct.append(ma_ct)
            mk = keys[0]
            kh_xa[f"{xa}|{mk}"] = float((len(expected_ma_ct) + 1) * 1_000_000)
            th_xa[mk] = 1_000_000.0

    monkeypatch.setattr(
        "tabs.tab_khtd_nhap.st.markdown",
        lambda body, unsafe_allow_html=False: markdown_calls.append((body, unsafe_allow_html)),
    )
    monkeypatch.setattr("tabs.tab_khtd_nhap.st.caption", lambda body: captions.append(body))
    monkeypatch.setattr("tabs.tab_khtd_nhap.st.info", lambda body: None)

    _hien_thi_bang_tom_tat_xa(xa, kh_xa, th_xa)

    html = next(body for body, unsafe in markdown_calls if unsafe)
    for tieu_de_nhom, _ in KHTD_CN_NHOM_MA_CT:
        assert tieu_de_nhom not in html

    positions = [html.index(_ten_ct_base(ma_ct)) for ma_ct in expected_ma_ct]
    assert positions == sorted(positions)
    assert re.findall(r"<td style='[^']*text-align:center[^']*'>(\d+)</td>", html) == [
        str(i) for i in range(1, len(expected_ma_ct) + 1)
    ]
    assert "Tổng cộng" in html
    assert captions


def test_bang_tom_tat_xa_tong_cong_khong_cong_dong_chi_phat_sinh(monkeypatch) -> None:
    markdown_calls: list[tuple[str, bool]] = []
    xa = "Xã kiểm thử"
    ma_co_tien = 1
    ma_chi_phat_sinh = 19
    mk_co_tien = next(mk for mk in (f"{ma_co_tien}_TW", f"{ma_co_tien}_DP") if mk in MA_KEYS_CO_KHTD)
    mk_phat_sinh = next(mk for mk in (f"{ma_chi_phat_sinh}_TW", f"{ma_chi_phat_sinh}_DP") if mk in MA_KEYS_CO_KHTD)

    monkeypatch.setattr(
        "tabs.tab_khtd_nhap.st.markdown",
        lambda body, unsafe_allow_html=False: markdown_calls.append((body, unsafe_allow_html)),
    )
    monkeypatch.setattr("tabs.tab_khtd_nhap.st.caption", lambda body: None)
    monkeypatch.setattr("tabs.tab_khtd_nhap.st.info", lambda body: None)

    _hien_thi_bang_tom_tat_xa(
        xa,
        {f"{xa}|{mk_co_tien}": 5_000_000.0},
        {mk_co_tien: 2_000_000.0},
        keys_phat_sinh={mk_phat_sinh},
    )

    html = next(body for body, unsafe in markdown_calls if unsafe)
    assert _ten_ct_base(ma_chi_phat_sinh) in html
    assert re.search(r"Tổng cộng.*?>5</td>.*?>2</td>.*?>3</td>", html, re.S)
