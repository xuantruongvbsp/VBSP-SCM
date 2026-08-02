"""Hồi quy helper quét chương trình có dư nợ của KHTD."""
from __future__ import annotations

import re

import pandas as pd

from config import (
    COT_MA_CHUONG_TRINH,
    COT_NGUON_VON,
    COT_TEN_CT,
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
from tabs.tab_khtd_nhap import _hien_thi_bang_tom_tat_xa, _reset_khtd_xa_selection_if_stale


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
