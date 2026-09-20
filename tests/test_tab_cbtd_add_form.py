"""Regression tests for the CBTD add form widget-state reset."""
from __future__ import annotations

import inspect
import re
from datetime import date

import pandas as pd

import tabs.tab_cbtd as tab_cbtd
import tabs.tab_vay_noxh as tab_vay_noxh
from config import (
    COT_DU_NO_QH,
    COT_HINH_THUC_VAY,
    COT_MA_CHUONG_TRINH,
    COT_MA_KH,
    COT_NGAY_DH,
    COT_NGAY_VAY,
    COT_SO_KU,
    COT_TEN_KH,
    COT_TEN_PGD,
    COT_TEN_XA,
    COT_TONG_DU_NO,
)


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


def test_tong_quan_cbtd_truyen_ky_hien_tai_cho_service():
    source = inspect.getsource(tab_cbtd.render)

    assert "_nam, _thang, _ngay = _ky_hstd_hien_tai(df)" in source
    assert "tong_hop_hstd_theo_cbtd(cbtd_data, dgd_map, df, yyyy=_nam, mm=_thang)" in source


def test_ky_so_sanh_to_tkvv_tinh_tu_ky_cdto_khong_tu_hstd():
    assert tab_cbtd._cac_ky_so_sanh_cdto("08/2026") == ("2026-07", "2025-12")
    assert tab_cbtd._cac_ky_so_sanh_cdto("01/2026") == ("2025-12", "2025-12")
    assert tab_cbtd._cac_ky_so_sanh_cdto(None) == (None, None)


def test_bang_to_tkvv_doc_snapshot_dung_moc_cua_cdto(monkeypatch):
    from services import cbtd_dia_ban_service, tongquan_cdto_service
    import snapshot_service

    df_cdto = pd.DataFrame([
        {"ten_dv": "PGD A", "ten_xa": "Xã A", "ma_to": "T01", "xep_loai": "Tốt"},
    ])
    monkeypatch.setattr(
        tongquan_cdto_service,
        "load_cdto_toan_cn",
        lambda: {"df_raw": df_cdto, "thang_hien": "08/2026"},
    )
    monkeypatch.setattr(
        cbtd_dia_ban_service,
        "lay_to_theo_cbtd",
        lambda *_args: {
            "CB01": [{"ma_to": "T01", "ten_xa": "Xã A", "xep_loai": "Tốt"}],
        },
    )
    calls: list[str] = []

    def _doc(ky: str) -> pd.DataFrame:
        calls.append(ky)
        return pd.DataFrame([{"ma_cb": "CB01", "so_to": 1, "so_tot": 1}])

    monkeypatch.setattr(snapshot_service, "doc_cbtd_to_tkvv_snapshot", _doc)

    result, thang_hien, ky_truoc, ky_baseline = tab_cbtd._bang_to_tkvv(
        {"CB01": {"ho_ten": "A", "pgd": "PGD A"}},
        {},
    )

    assert not result.empty
    assert (thang_hien, ky_truoc, ky_baseline) == ("08/2026", "2026-07", "2025-12")
    assert calls == ["2026-07", "2025-12"]


def test_tao_bang_tong_hop_sap_giam_va_tinh_delta_khong_lan_nan():
    hien_tai = pd.DataFrame([
        {"Ma_CBTD": "CB01", "Ho_ten": "A", "PGD": "PGD A",
         "Tong_du_no": 100.0, "Du_no_trong_han": 90.0, "Du_no_qh": 10.0,
         "Du_no_khoanh": 1.0, "So_KH": 2, "So_mon_vay": 3,
         "TL_QH_pct": 10.0, "Cho_vay_thang": 5.0, "Thu_no_thang": 2.0},
        {"Ma_CBTD": "CB02", "Ho_ten": "B", "PGD": "PGD B",
         "Tong_du_no": 200.0, "Du_no_trong_han": 195.0, "Du_no_qh": 5.0,
         "Du_no_khoanh": 2.0, "So_KH": 4, "So_mon_vay": 5,
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
    assert result.loc[2, "So_KH"] == 6
    assert result.loc[2, "So_mon_vay"] == 8
    assert result.loc[2, "Du_no_khoanh"] == 3.0


def test_html_bang_du_no_du_17_cot_va_nan_delta_hien_thi_gach():
    df = pd.DataFrame([{
        "STT": 1, "Ma_CBTD": "CB01", "Ho_ten": "A", "PGD": "PGD A",
        "So_KH": 2, "So_mon_vay": 3, "Tong_du_no": 100_000_000,
        "Du_no_trong_han": 90_000_000, "Du_no_qh": 10_000_000,
        "Du_no_khoanh": 0, "Cho_vay_thang": 5_000_000, "Thu_no_thang": 2_000_000,
        "DN_dTTr": float("nan"), "DN_dNY": None,
        "QH_dTTr": 1_000_000, "QH_dNY": -1_000_000, "TL_QH_pct": 10.0,
    }])

    html = tab_cbtd._html_bang_du_no(df)
    body_rows = re.findall(r'<tr class="cdp-row">(.*?)</tr>', html)

    assert len(body_rows) == 1
    assert body_rows[0].count("<td") == 17
    assert tab_cbtd._fmt_tr_dau(float("nan")) == "—"
    assert tab_cbtd._fmt_so_dau(float("nan")) == "—"
    assert body_rows[0].count('cdp-zero">—</span>') == 2


def test_chuan_bi_pdf_bang_du_no_giu_gach_cho_delta_thieu_ky():
    df = pd.DataFrame([{
        "STT": 1, "Mã CBTD": "CB01", "Họ tên": "A", "PGD": "PGD A",
        "Kh vay vốn": 2, "Món vay": 3,
        "Tổng dư nợ": 1_000_000, "Trong hạn": 900_000, "Quá hạn": 100_000,
        "Khoanh": None, "Cho vay": 2_000_000, "Thu nợ": 1_000_000,
        "Dư nợ Δ so tháng trước": float("nan"),
        "Dư nợ Δ so 31/12 năm trước": None,
        "QH Δ so tháng trước": 1_000_000,
        "QH Δ so 31/12 năm trước": -1_000_000,
        "TL QH (%)": 10.0,
    }])

    out, cols_tien, cols_dem, cols_pct = tab_cbtd._chuan_bi_pdf_bang_du_no(df)

    assert out.loc[0, "Tổng dư nợ"] == 1
    assert out.loc[0, "Khoanh"] == 0
    assert out.loc[0, "Dư nợ Δ so tháng trước"] == "—"
    assert out.loc[0, "Dư nợ Δ so 31/12 năm trước"] == "—"
    assert out.loc[0, "QH Δ so tháng trước"] == 1
    assert out.loc[0, "QH Δ so 31/12 năm trước"] == -1
    assert "Dư nợ Δ so tháng trước" in cols_tien
    assert cols_dem == ["Kh vay vốn", "Món vay"]
    assert cols_pct == ["TL QH (%)"]


def test_pdf_bang_du_no_khong_cong_them_dong_tong_lan_hai():
    source = inspect.getsource(tab_cbtd.render)
    pdf_block = source.split('if st.button("🖨️ In PDF tổng quan CBTD"', 1)[1]
    pdf_block = pdf_block.split('if state.downloads.has("cbtd_tq_pdf")', 1)[0]

    assert "them_dong_tong=False" in pdf_block
    assert "them_dong_tong=True" not in pdf_block
    assert "bang_phu=[" in pdf_block
    assert "CỤM CHỈ TIÊU NỢ CẦN QUAN TÂM" in pdf_block
    assert "CHẤT LƯỢNG TỔ TK&VV" in pdf_block


def test_loc_vay_truc_tiep_noxh_chi_lay_ct12_con_du_no():
    df = pd.DataFrame([
        {COT_SO_KU: "KU01", COT_HINH_THUC_VAY: 1, COT_MA_CHUONG_TRINH: 12, COT_TONG_DU_NO: 100},
        {COT_SO_KU: "KU02", COT_HINH_THUC_VAY: 1, COT_MA_CHUONG_TRINH: 12, COT_TONG_DU_NO: 0},
        {COT_SO_KU: "KU03", COT_HINH_THUC_VAY: 1, COT_MA_CHUONG_TRINH: 3, COT_TONG_DU_NO: 100},
        {COT_SO_KU: "KU04", COT_HINH_THUC_VAY: 2, COT_MA_CHUONG_TRINH: 12, COT_TONG_DU_NO: 100},
    ])

    result = tab_vay_noxh._loc_vay_truc_tiep_noxh(df)

    assert result[COT_SO_KU].tolist() == ["KU01"]


def test_gioi_han_noxh_theo_pgd_khong_lo_du_lieu_khi_thieu_cot_dia_ban():
    df = pd.DataFrame({COT_SO_KU: ["KU01", "KU02"]})

    assert tab_vay_noxh._gioi_han_noxh_theo_pgd(df, "PGD A").empty

    co_pgd = df.assign(**{COT_TEN_PGD: ["PGD A", "PGD B"]})
    result = tab_vay_noxh._gioi_han_noxh_theo_pgd(co_pgd, " pgd a ")
    assert result[COT_SO_KU].tolist() == ["KU01"]


def test_quyen_quan_ly_noxh_chi_danh_cho_quan_ly_chi_nhanh():
    assert tab_vay_noxh._co_quyen_quan_ly_noxh("admin_cn") is True
    assert tab_vay_noxh._co_quyen_quan_ly_noxh("manager_cn") is True
    assert tab_vay_noxh._co_quyen_quan_ly_noxh("admin") is True
    assert tab_vay_noxh._co_quyen_quan_ly_noxh("executive") is False
    assert tab_vay_noxh._co_quyen_quan_ly_noxh("chuyenvien_cn") is False
    assert tab_vay_noxh._co_quyen_quan_ly_noxh("admin_pgd") is False
    assert tab_vay_noxh._co_quyen_quan_ly_noxh("user_pgd") is False


def test_tao_bang_theo_doi_noxh_ghep_phan_cong_va_canh_bao_qua_han():
    df = pd.DataFrame([{
        COT_SO_KU: "KU01",
        COT_MA_KH: pd.NA,
        COT_TEN_KH: "Nguyen Van A",
        COT_TEN_PGD: "Hội sở",
        COT_TEN_XA: "Phường A",
        COT_NGAY_VAY: "01/01/2025",
        COT_NGAY_DH: "01/01/2040",
        COT_TONG_DU_NO: 500_000_000,
        COT_DU_NO_QH: 0,
    }])
    phan_cong = {
        "KU01": {
            "ma_cb": "CB01",
            "ngay_giao": "01/07/2026 08:00",
            "trang_thai": "Đang theo dõi",
        }
    }
    cbtd = {"CB01": {"ho_ten": "Tran Thi B", "pgd": "Hội sở"}}

    result = tab_vay_noxh._tao_bang_theo_doi_noxh(
        df, phan_cong, cbtd, today=date(2026, 8, 5)
    )

    assert result.loc[0, "Mã KH"] == ""
    assert result.loc[0, "CBTD theo dõi"] == "CB01 — Tran Thi B / Hội sở"
    assert result.loc[0, "Trạng thái"] == "Đang theo dõi"
    assert bool(result.loc[0, "_da_giao"]) is True
    assert bool(result.loc[0, "_qua_han"]) is True
    assert result.loc[0, "Cảnh báo"] == "Quá hạn theo dõi"


def test_noxh_qua_han_khi_den_ngay_hen_tiep():
    record = {
        "ma_cb": "CB01",
        "ngay_giao": "01/09/2026",
        "ngay_hen_tiep": "13/09/2026",
    }

    assert tab_vay_noxh._noxh_qua_han_theo_doi(record, today=date(2026, 9, 13)) is True


def test_chuan_bi_va_xuat_pdf_noxh_giu_dung_tong_du_no():
    df = pd.DataFrame([{
        "Số khế ước": "KU01",
        "Tên KH": "Nguyen Van A",
        "PGD": "Hội sở Chi nhánh tỉnh",
        "Xã/phường": "Phường A",
        "Dư nợ": 500_000_000,
        "Dư nợ QH": 10_000_000,
        "CBTD theo dõi": "CB01 — Tran Thi B",
        "Trạng thái": "Đang theo dõi",
        "Kiểm tra gần nhất": "01/09/2026",
        "Hẹn tiếp": "30/09/2026",
        "Cảnh báo": "",
        "Kết quả": "Khách hàng trả nợ đúng lịch",
    }])

    out = tab_vay_noxh._chuan_bi_pdf_noxh(df)

    assert out.loc[0, "TT"] == 1
    assert out.loc[0, "Dư nợ (tr)"] == 500
    assert out.loc[0, "Dư nợ QH (tr)"] == 10
    assert "Xã/phường" not in out.columns
    assert "Kết quả" not in out.columns
    assert "Ghi chú" not in out.columns

    from components.export_pdf import xuat_pdf_co_chart
    pdf_bytes = xuat_pdf_co_chart(
        out,
        tieu_de="THEO DÕI VAY TRỰC TIẾP NOXH",
        nguoi_xuat="tester",
        cols_tien=["Dư nợ (tr)", "Dư nợ QH (tr)"],
        don_vi_tien="triệu đồng",
        them_dong_tong=True,
    )
    assert pdf_bytes.startswith(b"%PDF")
