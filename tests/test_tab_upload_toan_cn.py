"""Regression tests cho upload dữ liệu toàn Chi nhánh."""
from __future__ import annotations

import inspect
from types import SimpleNamespace

from tabs.tab_upload_khnv import _upload_toan_cn as upload_toan_cn


def _fake_st(state: dict, calls: list[tuple[str, str]]):
    return SimpleNamespace(
        session_state=state,
        success=lambda msg: calls.append(("success", msg)),
        warning=lambda msg: calls.append(("warning", msg)),
        error=lambda msg: calls.append(("error", msg)),
        caption=lambda msg: calls.append(("caption", msg)),
    )


def test_hien_thi_ket_qua_cdto_sau_rerun_giu_thong_bao_thanh_cong(monkeypatch):
    calls: list[tuple[str, str]] = []
    state = {
        upload_toan_cn._CDTO_SS_RESULT: {
            "so_ok": 22,
            "tong": 22,
            "thang": "06/2026",
            "loi": [],
        }
    }
    monkeypatch.setattr(upload_toan_cn, "st", _fake_st(state, calls))

    upload_toan_cn._hien_thi_ket_qua_cdto_sau_rerun()

    assert calls == [
        (
            "success",
            "✅ Upload xong CDTOTKVV toàn CN: đã lưu **22/22** đơn vị · kỳ **06/2026**.",
        )
    ]
    assert upload_toan_cn._CDTO_SS_RESULT in state


def test_hien_thi_ket_qua_cdto_sau_rerun_bao_ro_loi_tung_phan(monkeypatch):
    calls: list[tuple[str, str]] = []
    state = {
        upload_toan_cn._CDTO_SS_RESULT: {
            "so_ok": 21,
            "tong": 22,
            "thang": "06/2026",
            "loi": ["PGD Long Thành: lỗi lưu file"],
        }
    }
    monkeypatch.setattr(upload_toan_cn, "st", _fake_st(state, calls))

    upload_toan_cn._hien_thi_ket_qua_cdto_sau_rerun()

    assert calls[0] == (
        "warning",
        "⚠️ Upload CDTOTKVV toàn CN hoàn tất một phần: đã lưu **21/22** đơn vị · kỳ **06/2026**.",
    )
    assert calls[1] == ("caption", "Đơn vị lỗi: PGD Long Thành: lỗi lưu file")


def test_render_cdto_toan_cn_co_status_va_luu_ket_qua_truoc_rerun():
    source = inspect.getsource(upload_toan_cn.render_cdto_toan_cn)

    assert 'with st.status("🔍 Đang phân tích file CDTOTKVV toàn CN..."' in source
    assert 'with st.status("📤 Đang upload CDTOTKVV toàn CN..."' in source
    assert "st.session_state[_CDTO_SS_RESULT] = {" in source
    assert source.index("st.session_state[_CDTO_SS_RESULT] = {") < source.index("st.rerun()")
