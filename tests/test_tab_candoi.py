"""Regression tests for Điện báo Cân đối helpers."""
from __future__ import annotations

import inspect
import os
from pathlib import Path

import pandas as pd

from tabs import tab_candoi


def _row(ten: str, val: float, *, he_so_vnd: int = 1_000_000) -> dict:
    return {
        "ten": ten,
        "val": val,
        "la_nqh_con": False,
        "cha": None,
        "he_so_vnd": he_so_vnd,
    }


def test_lookup_prev_vnd_kh_mode_dung_kh_name_map():
    rows_kh = [_row("Vốn TW", 12)]

    assert tab_candoi._lookup_prev_vnd(
        rows_kh,
        "Nguồn vốn cân đối từ TW (KHA)",
        1_000_000,
        kh_mode=True,
    ) == 12_000_000
    assert tab_candoi._lookup_prev_vnd(
        rows_kh,
        "Nguồn vốn cân đối từ TW (KHA)",
        1_000_000,
        kh_mode=False,
    ) == 0


def test_lookup_khoanh_vnd_cong_kha_va_khb_cho_ca_hai_che_do():
    rows = [
        _row("Dư nợ Khoanh KHA", 12),
        _row("Dư nợ Khoanh KHB", 8),
    ]

    assert tab_candoi._lookup_khoanh_vnd(rows, 1_000_000) == 20_000_000
    assert tab_candoi._lookup_khoanh_vnd(rows, 1_000_000, kh_mode=True) == 20_000_000


def test_render_card_no_khoanh_dung_helper_o_du_ba_nhanh():
    source = inspect.getsource(tab_candoi.render)

    assert source.count("_lookup_khoanh_vnd(") == 3
    assert '{"label": "Nợ khoanh", "icon": "🔒"' in source
    assert "], num_columns=4)" in source


def test_match_prev_row_vnd_kh_mode_fallback_khi_ten_lech():
    row_ht = _row("Dư nợ Kế hoạch A", 15)
    rows_kh = [_row("KHA", 20)]

    assert tab_candoi._match_prev_row_vnd(
        row_ht,
        rows_kh,
        1_000_000,
        kh_mode=True,
    ) == 20_000_000


def test_match_prev_row_vnd_exact_match_uu_tien_he_so_tren_row():
    row_ht = _row("Tổng dư nợ", 15)
    rows_prev = [_row("Tổng dư nợ", 20, he_so_vnd=1_000)]

    assert tab_candoi._match_prev_row_vnd(
        row_ht,
        rows_prev,
        1_000_000,
        kh_mode=False,
    ) == 20_000


def test_render_chart_va_export_dung_helper_kh_mapping():
    source = inspect.getsource(tab_candoi.render)
    export_source = inspect.getsource(tab_candoi._build_export_frames)

    assert "_lookup_prev_vnd(db_prev_rows, i[1], _he_so_pv, _la_kh)" in source
    assert "_build_export_frames(" in source
    assert "_match_prev_row_vnd(row_ht, rows_prev, he_so_prev, kh_mode)" in export_source
    assert "_lookup_prev_vnd(rows_prev, key, he_so_prev, kh_mode)" in export_source


def test_moc_choice_chi_luu_khi_user_thuc_su_doi():
    should_persist = tab_candoi._should_persist_moc_choice

    # Mở tab lần đầu không được tự ghi default.
    assert not should_persist(None, "custom", changed_by_user=False)
    # File mới thiếu sheet Y: fallback 31_12 -> kh_giao không được ghi đè KV.
    assert not should_persist("31_12", "kh_giao", changed_by_user=False)
    # Chỉ thao tác đổi thật của user mới được lưu.
    assert should_persist("31_12", "kh_giao", changed_by_user=True)
    assert not should_persist("kh_giao", "kh_giao", changed_by_user=True)


def test_ky_so_lieu_cho_phep_xoa_nhan_da_luu_va_audit_lien_ke(monkeypatch):
    events = []
    monkeypatch.setattr(
        tab_candoi.db,
        "ghi_kv",
        lambda key, value, username: events.append(("kv", key, value, username)),
    )
    monkeypatch.setattr(
        tab_candoi.db,
        "ghi_audit",
        lambda username, action, detail: events.append(("audit", username, action, detail)),
    )

    assert tab_candoi._normalize_ky_label(" 31/07/2026 ") == "31/07/2026"
    assert tab_candoi._persist_ky_label_if_changed(
        "dienbao_ky_ht",
        "31/07/2026",
        "   ",
        "tester",
        "kỳ số liệu HT",
    )
    assert events == [
        ("kv", "dienbao_ky_ht", "", "tester"),
        ("audit", "tester", "dienbao_ky", "Xóa kỳ số liệu HT"),
    ]

    events.clear()
    assert not tab_candoi._persist_ky_label_if_changed(
        "dienbao_ky_ht",
        "",
        " ",
        "tester",
        "kỳ số liệu HT",
    )
    assert events == []


def test_render_moc_choice_dung_on_change_de_phan_biet_fallback():
    source = inspect.getsource(tab_candoi.render)

    assert "on_change=_mark_moc_changed" in source
    assert "_should_persist_moc_choice(" in source


def test_upload_card_ky_truoc_chi_la_nam_truoc_khong_date_input_disabled():
    source = inspect.getsource(tab_candoi._render_upload_section)

    assert 'st.markdown(f\'**🗓️ Kỳ trước** · {nam_prev}\')' in source
    assert 'st.caption(f"Kỳ số liệu: **{_ky_pv_str}** (cố định)")' in source
    assert "Mốc kỳ trước" not in source
    assert "moc_pv" not in source
    assert "cuối tháng trước" not in source
    assert "disabled=True" not in source


def test_custom_sheet_options_loai_sheet_hien_tai():
    assert tab_candoi._custom_sheet_options(["M", "Y", "KH"], "M") == ["Y", "KH"]
    assert tab_candoi._custom_sheet_options(["M"], "M") == []


def test_moc_tu_dong_khong_chon_lai_sheet_hien_tai():
    first_sheet = tab_candoi._first_comparison_sheet

    assert first_sheet(["M", "Y"], "M", ["Y"]) == "Y"
    assert first_sheet(["M", "Y"], "Y", ["Y"]) is None
    assert first_sheet(
        ["DB", "KH_GIAO_DAU_NAM", "KH"],
        "KH_GIAO_DAU_NAM",
        ["KH_GIAO_DAU_NAM", "KH", "DIEU_CHINH_KHTD"],
    ) == "KH"
    assert first_sheet(
        ["KH_GIAO_DAU_NAM"],
        "KH_GIAO_DAU_NAM",
        ["KH_GIAO_DAU_NAM", "KH", "DIEU_CHINH_KHTD"],
    ) is None


def test_custom_mot_sheet_van_co_option_file_ky_truoc():
    sentinel = tab_candoi._FILE_PREV_SENTINEL

    assert tab_candoi._custom_comparison_options(
        ["Formula"],
        "Formula",
        has_previous_file=True,
    ) == [sentinel]
    assert tab_candoi._custom_comparison_options(
        ["M", "Y"],
        "M",
        has_previous_file=True,
    ) == ["Y", sentinel]
    assert tab_candoi._custom_comparison_options(
        ["Formula"],
        "Formula",
        has_previous_file=False,
    ) == []


def test_label_option_file_ky_truoc_hien_ten_file():
    label = tab_candoi._fmt_nguon_ss(
        tab_candoi._FILE_PREV_SENTINEL,
        {},
        r"D:\VBSP-SCM\cache\dienbao_prev.xlsx",
    )

    assert label == "📁 File kỳ trước (dienbao_prev.xlsx)"


def test_has_previous_file_chi_nhan_file_khac_hien_tai(tmp_path: Path):
    path_ht = tmp_path / "current.xlsx"
    path_prev = tmp_path / "previous.xlsx"
    path_ht.touch()
    path_prev.touch()

    assert tab_candoi._has_previous_file(str(path_prev), str(path_ht))
    assert not tab_candoi._has_previous_file(str(path_ht), str(path_ht))
    assert not tab_candoi._has_previous_file(str(tmp_path / "missing.xlsx"), str(path_ht))
    assert not tab_candoi._has_previous_file(str(tmp_path), str(path_ht))


def test_has_previous_file_loai_alias_cung_mot_file(tmp_path: Path):
    path_ht = tmp_path / "current.xlsx"
    path_alias = tmp_path / "current_alias.xlsx"
    path_ht.touch()
    os.link(path_ht, path_alias)

    assert not tab_candoi._has_previous_file(str(path_alias), str(path_ht))


def test_upload_dienbao_reset_uploader_sau_khi_luu_thanh_cong():
    source = inspect.getsource(tab_candoi._upload_one_file)

    assert 'ver_key = f"up_db_{loai}_ver{key_sfx}"' in source
    assert 'key=f"up_db_{loai}{key_sfx}_{ver}"' in source
    assert "luu_dienbao(\n                    loai," in source
    assert "ten_pgd=pgd_user if pgd_mode else None" in source
    assert "st.session_state[ver_key] = ver + 1" in source


def test_file_chip_uu_tien_ten_goc_va_thoi_diem_upload(monkeypatch):
    monkeypatch.setattr(tab_candoi.os.path, "exists", lambda _path: True)
    monkeypatch.setattr(tab_candoi.os.path, "getsize", lambda _path: 5511)
    monkeypatch.setattr(tab_candoi.os.path, "getmtime", lambda _path: 0)

    chip = tab_candoi._db_file_chip(
        r"D:\VBSP-SCM\cache\dienbao_prev.xlsx",
        meta={
            "ten_file": "31.12.xlsx",
            "ngay_upload": "2026-08-01T09:07:42.927228",
        },
    )

    assert "31.12.xlsx" in chip
    assert "5 KB · 01/08/2026 09:07" in chip
    assert "dienbao_prev.xlsx" not in chip
    assert "01/01/1970" not in chip


def test_file_details_fallback_filesystem_cho_metadata_legacy(monkeypatch):
    monkeypatch.setattr(tab_candoi.os.path, "getsize", lambda _path: 2048)
    monkeypatch.setattr(tab_candoi.os.path, "getmtime", lambda _path: 0)

    name, kb, timestamp = tab_candoi._db_file_details("cache/dienbao_prev.xlsx")

    assert name == "dienbao_prev.xlsx"
    assert kb == 2
    assert timestamp == tab_candoi.datetime.fromtimestamp(0).strftime("%d/%m/%Y %H:%M")


def test_render_upload_section_khong_hien_expander_lich_su_rong():
    source = inspect.getsource(tab_candoi._render_upload_section)

    assert "if _co_dienbao_lich_su(key_sfx):" in source
    assert "Lịch sử điện báo: chưa có file upload nào." in source


def test_tab_candoi_khong_con_su_dung_expander():
    source = inspect.getsource(tab_candoi)

    assert "st.expander(" not in source
    assert "st.popover(" in source


def test_quan_ly_tep_inline_upload_truc_tiep_khong_popover_trung_gian():
    source = inspect.getsource(tab_candoi._render_quan_ly_tep_inline)

    assert "st.popover(" not in source
    assert "Đổi/upload tệp" not in source
    assert "st.columns(3)" in source
    assert '_upload_one_file("ht"' in source
    assert '_upload_one_file("prev"' in source
    assert '_upload_one_file("prev_month"' in source
    assert 'key=_ky_ht_widget_key' in source
    assert 'key=_ky_pm_widget_key' in source


def test_upload_dienbao_chon_ngay_truoc_khi_upload_va_luu_truoc_rerun():
    source_initial = inspect.getsource(tab_candoi._render_upload_section)
    source_inline = inspect.getsource(tab_candoi._render_quan_ly_tep_inline)
    source_upload = inspect.getsource(tab_candoi._upload_one_file)

    assert source_initial.index('st.date_input(\n            "📅 Ngày số liệu"') < source_initial.index('_upload_one_file("ht"')
    assert source_initial.index('st.caption(f"Kỳ số liệu: **{_ky_pv_str}** (cố định)")') < source_initial.index('_upload_one_file("prev"')
    assert source_initial.index('st.date_input(\n                "📅 Ngày số liệu"') < source_initial.index('_upload_one_file("prev_month"')

    assert source_inline.index('st.date_input(\n                "📅 Ngày số liệu HT"') < source_inline.index('_upload_one_file("ht"')
    assert source_inline.index('st.caption(f"Kỳ số liệu: **{_ky_pv_str}** (cố định)")') < source_inline.index('_upload_one_file("prev"')
    assert source_inline.index('st.date_input(\n                "📅 Ngày số liệu tháng trước"') < source_inline.index('_upload_one_file("prev_month"')

    assert 'ky_saved_latest = db.doc_kv(ky_kv)' in source_upload
    assert 'ky_from_name = trich_xuat_ky_dienbao(f_up.name) if loai != "prev" else None' in source_upload
    assert "ky_effective = ky_from_name or ky_label" in source_upload
    assert "ky_widget_ver_key" in source_upload
    assert source_upload.index("_persist_ky_label_if_changed(") < source_upload.index("st.rerun()")


def test_upload_dienbao_khong_luu_ngay_ht_mac_dinh_khi_chua_co_nguon():
    source_initial = inspect.getsource(tab_candoi._render_upload_section)
    source_inline = inspect.getsource(tab_candoi._render_quan_ly_tep_inline)

    assert "_ht_has_source = bool(_ky_ht_saved or _meta_ht.get(\"ky\") or os.path.exists(store_ht))" in source_initial
    assert "_ht_user_changed = _ky_ht_had_state and _ky_ht_date != _default_ht" in source_initial
    assert "if _ht_has_source or _ht_user_changed:" in source_initial
    assert "_ht_has_source = bool(_ky_ht_saved or _meta_ht.get(\"ky\") or _has_ht)" in source_inline


def test_render_state_b_khoi_phuc_has_file_prev_truoc_moc_so_sanh():
    source = inspect.getsource(tab_candoi.render)

    assign_pos = source.index("_has_file_prev = _has_previous_file(path_prev, path_ht)")
    use_pos = source.index("_can_31_12 = _has_y_sheet or _has_file_prev")
    assert assign_pos < use_pos


def test_moc_thang_truoc_khong_doc_lap_lai_cot_phu_thang_truoc():
    source = inspect.getsource(tab_candoi.render)

    assert 'MOC_VALUES.append(("thang_truoc", "delta"))' in source
    assert 'elif _moc_val == "thang_truoc" and path_prev_month:' in source
    assert 'if _moc_val != "thang_truoc" and path_prev_month:' in source


def test_co_dienbao_lich_su_doc_du_3_loai(monkeypatch):
    calls = []
    metas = {
        "dienbao_meta_ht": {},
        "dienbao_meta_prev": {},
        "dienbao_meta_prev_month": {"ten_file": "db.xlsx"},
    }

    def fake_doc_kv(key):
        calls.append(key)
        return metas.get(key)

    monkeypatch.setattr(tab_candoi.db, "doc_kv", fake_doc_kv)

    assert tab_candoi._co_dienbao_lich_su("") is True
    assert calls == ["dienbao_meta_ht", "dienbao_meta_prev", "dienbao_meta_prev_month"]


def test_tong_quan_an_card_huy_dong_nhung_van_tinh_tien_gui_ngoai_to():
    source = inspect.getsource(tab_candoi.render)

    assert '{"label": "Vốn TW (KHA)"' not in source
    assert '{"label": "Tổng huy động vốn"' not in source
    assert '{"label": "TG TT TCTC & TK CN"' in source
    assert 'huy_dong_ht = _lookup_vnd(db_ht_rows, "Tổng huy động vốn"' in source
    assert "tien_gui_tt_ht = huy_dong_ht - tiet_kiem_to_tkvv_ht" in source


def test_lookup_kh_optional_tkvv_ho_tro_ten_khong_co_ampersand():
    rows_kh = [_row("Tiền gửi tiết kiệm qua Tổ TKVV", 12)]

    assert tab_candoi._lookup_kh_optional_vnd(
        rows_kh,
        "Tiền gửi tiết kiệm qua Tổ TK&VV",
        1_000_000,
    ) == 12_000_000


def test_lookup_kh_optional_phan_biet_thieu_chi_tieu_va_gia_tri_zero():
    assert tab_candoi._lookup_kh_optional_vnd(
        [_row("Tiền gửi tiết kiệm qua Tổ TK&VV", 0)],
        "Tiền gửi tiết kiệm qua Tổ TK&VV",
        1_000_000,
    ) == 0
    assert tab_candoi._lookup_kh_optional_vnd(
        [_row("Chỉ tiêu khác", 5)],
        "Tiền gửi tiết kiệm qua Tổ TK&VV",
        1_000_000,
    ) is None


def test_lookup_optional_vnd_phan_biet_thieu_chi_tieu_va_gia_tri_zero():
    assert tab_candoi._lookup_optional_vnd(
        [_row("Tổng huy động vốn", 0)],
        "Tổng huy động vốn",
        1_000_000,
    ) == 0
    assert tab_candoi._lookup_optional_vnd(
        [_row("Tổng huy động vốn", 12)],
        "Tổng huy động vốn",
        1_000_000,
    ) == 12_000_000
    assert tab_candoi._lookup_optional_vnd(
        [_row("Chỉ tiêu khác", 5)],
        "Tổng huy động vốn",
        1_000_000,
    ) is None


def test_tong_quan_an_kpi_tien_gui_khi_sheet_kh_thieu_thanh_phan():
    source = inspect.getsource(tab_candoi.render)

    assert "if tien_gui_tt_pv is not None:" in source
    assert "Không hiển thị KPI TG TT TCTC & TK CN" in source
    assert "and (not db_prev_rows or tien_gui_tt_pv is not None)" in source


def test_export_kh_thieu_thanh_phan_tien_gui_khong_crash_va_khong_chen_dong_tinh():
    rows_ht = [
        _row("Tổng huy động vốn", 100),
        _row("Tiền gửi tiết kiệm qua Tổ TK&VV", 30),
    ]
    rows_kh = [_row("Huy động vốn", 90)]

    df_summary, _ = tab_candoi._build_export_frames(
        rows_ht,
        rows_kh,
        1_000_000,
        1_000_000,
        True,
        "Kế hoạch giao",
        "Hiện tại",
    )

    assert not df_summary["Chỉ tiêu"].str.contains("TG TT TCTC", regex=False).any()


def test_export_tien_gui_tinh_doc_lap_voi_subtab_tong_quan():
    rows_ht = [
        _row("Tổng huy động vốn", 100),
        _row("Tiền gửi tiết kiệm qua Tổ TK&VV", 30),
    ]
    rows_prev = [
        _row("Tổng huy động vốn", 80),
        _row("Tiền gửi tiết kiệm qua Tổ TK&VV", 20),
    ]

    df_summary, _ = tab_candoi._build_export_frames(
        rows_ht,
        rows_prev,
        1_000_000,
        1_000_000,
        False,
        "Kỳ trước",
        "Hiện tại",
    )
    calculated = df_summary.loc[
        df_summary["Chỉ tiêu"].str.contains("TG TT TCTC", regex=False)
    ].iloc[0]

    assert calculated["Kỳ trước (triệu đồng)"] == 60
    assert calculated["Hiện tại (triệu đồng)"] == 70


def test_export_prev_month_rong_khong_them_cot_thang_truoc():
    rows_ht = [
        _row("Tổng huy động vốn", 100),
        _row("Tiền gửi tiết kiệm qua Tổ TK&VV", 30),
    ]

    df_summary, _ = tab_candoi._build_export_frames(
        rows_ht,
        None,
        1_000_000,
        1_000_000,
        False,
        "Kỳ trước",
        "Hiện tại",
        rows_prev_month=[],
    )

    assert not any("tháng trước" in col.lower() for col in df_summary.columns)


def test_export_prev_month_thieu_thanh_phan_tien_gui_de_trong_o_tinh_toan():
    rows_ht = [
        _row("Tổng huy động vốn", 100),
        _row("Tiền gửi tiết kiệm qua Tổ TK&VV", 30),
    ]
    rows_prev = [
        _row("Tổng huy động vốn", 80),
        _row("Tiền gửi tiết kiệm qua Tổ TK&VV", 20),
    ]
    rows_prev_month = [_row("Tổng huy động vốn", 90)]

    df_summary, _ = tab_candoi._build_export_frames(
        rows_ht,
        rows_prev,
        1_000_000,
        1_000_000,
        False,
        "Kỳ trước",
        "Hiện tại",
        rows_prev_month=rows_prev_month,
    )
    calculated = df_summary.loc[
        df_summary["Chỉ tiêu"].str.contains("TG TT TCTC", regex=False)
    ].iloc[0]

    assert pd.isna(calculated["Tháng trước (triệu đồng)"])
    assert pd.isna(calculated["Tăng/giảm so với tháng trước (triệu đồng)"])
    assert pd.isna(calculated["Tỷ lệ % tháng trước"])


def test_build_print_html_escape_du_lieu_dong_va_hien_thi_ty_le_zero():
    df = pd.DataFrame([
        {"Chỉ tiêu": "<script>alert(1)</script>", "Tỷ lệ %": 0.0},
    ])

    result = tab_candoi._build_print_html(
        [("Tổng hợp chỉ tiêu", df)],
        "<Kỳ trước>",
        "Hiện tại",
        "<b>PGD thử</b>",
        True,
    )

    assert "<script>alert(1)</script>" not in result
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in result
    assert "&lt;b&gt;PGD thử&lt;/b&gt;" in result
    assert "+0.0%" in result


def test_theo_chuong_trinh_html_nhan_ro_no_qua_han_va_khong_in_nan():
    rows = [
        {
            "Chương trình": "Hộ nghèo KHA",
            "Tỷ lệ %": 0,
            "NQH hiện tại": float("nan"),
            "NQH kỳ trước": float("nan"),
            "_is_header": False,
            "_ht": 1_000_000,
            "_pv": 1_000_000,
        },
    ]

    result = tab_candoi._chuong_trinh_table_html(rows, "Kỳ trước", "Hiện tại")

    assert "Chênh lệch nợ quá hạn" in result
    assert "Chênh lệch NQH" not in result
    assert "NQH" not in result
    assert "nan" not in result.lower()
    assert result.index("Nợ quá hạn Kỳ trước") < result.index("Nợ quá hạn Hiện tại")


def test_export_theo_chuong_trinh_nhan_ro_no_qua_han_va_thu_tu_nhat_quan():
    rows_ht = [
        _row("Dư nợ hộ nghèo KHA", 100),
        {"ten": "Nợ quá hạn hộ nghèo", "val": 3, "la_nqh_con": True, "cha": "Dư nợ hộ nghèo KHA"},
    ]
    rows_prev = [
        _row("Dư nợ hộ nghèo KHA", 80),
        {"ten": "Nợ quá hạn hộ nghèo", "val": 1, "la_nqh_con": True, "cha": "Dư nợ hộ nghèo KHA"},
    ]

    _, df_program = tab_candoi._build_export_frames(
        rows_ht,
        rows_prev,
        1_000_000,
        1_000_000,
        False,
        "Kỳ trước",
        "Hiện tại",
    )

    assert "Chênh lệch nợ quá hạn (triệu đồng)" in df_program.columns
    assert not any("NQH" in col for col in df_program.columns)
    prev_idx = df_program.columns.get_loc("Nợ quá hạn Kỳ trước (triệu đồng)")
    current_idx = df_program.columns.get_loc("Nợ quá hạn Hiện tại (triệu đồng)")
    diff_idx = df_program.columns.get_loc("Chênh lệch nợ quá hạn (triệu đồng)")
    assert prev_idx < current_idx < diff_idx
    first_row = df_program[df_program["Chương trình"] == "Hộ nghèo KHA"].iloc[0]
    assert first_row["Chênh lệch nợ quá hạn (triệu đồng)"] == 2


def test_theo_chuong_trinh_kpi_dung_contract_render_grid_va_quy_doi_ty():
    source = inspect.getsource(tab_candoi.render)

    assert '_render_kpi_grid(_ct_cards, num_columns=2)' in source
    assert '_kpi_card_html("Dư nợ Kế hoạch A"' not in source
    assert '"value": _to_ty(_kha_ht)' in source
    assert '"value": _to_ty(_khb_ht)' in source
    assert '"delta": _ct_delta_fn(_kha_ht, _kha_pv) if db_prev_rows else None' in source
    assert "Chưa có mốc so sánh" in source


def test_safe_export_name_part_loai_ky_tu_cam_tren_windows():
    assert tab_candoi._safe_export_name_part("31/07/2026: HT", "fallback") == "31_07_2026_ HT"


# ── _parse_ddmmyyyy ──────────────────────────────────────────────────────────

def test_parse_ddmmyyyy_hop_le():
    from datetime import date
    assert tab_candoi._parse_ddmmyyyy("31/07/2026") == date(2026, 7, 31)
    assert tab_candoi._parse_ddmmyyyy("01/01/2025") == date(2025, 1, 1)


def test_parse_ddmmyyyy_khong_hop_le():
    assert tab_candoi._parse_ddmmyyyy("") is None
    assert tab_candoi._parse_ddmmyyyy("abc") is None
    assert tab_candoi._parse_ddmmyyyy("31/13/2026") is None  # tháng 13
    assert tab_candoi._parse_ddmmyyyy(None) is None
