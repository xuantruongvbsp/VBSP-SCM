"""Regression tests cho bảng Chi tiết của Báo cáo tổng hợp HSTD v2."""
from __future__ import annotations

import pandas as pd

from config import (
    COT_DU_NO_KHOANH,
    COT_DU_NO_QH,
    COT_DU_NO_TH,
    COT_DVUT,
    COT_MA_KH,
    COT_NGUON_VON,
    COT_SO_KU,
    COT_TEN_CT,
    COT_TEN_PGD,
    COT_TEN_TO,
    COT_TEN_XA,
    COT_TONG_DU_NO,
    DON_VI_CHI_NHANH,
)
from tabs.tab_baocao.components.sticky_table import (
    render_bang_chi_tiet_html,
    render_sticky_table,
)
from tabs.tab_baocao.reports import tong_hop_hstd_v2
from tabs.tab_baocao.reports.tong_hop_hstd_v2 import (
    _NHOM_KHONG_XAC_DINH,
    _doc_baseline_cung_pham_vi,
    _tao_so_sanh_du_no_theo_tieu_chi,
    _tao_tong_hop_theo_nhom,
    _tinh_tong_cong,
)
from utils_theme import _css_part2


def _df_mau() -> pd.DataFrame:
    return pd.DataFrame(
        {
            COT_TEN_CT: ["CT A", "CT A", "CT B", None],
            COT_MA_KH: ["KH1", "KH1", "KH1", "KH2"],
            COT_SO_KU: ["KU1", "KU1", "KU2", "KU3"],
            COT_TONG_DU_NO: [100, 100, 200, 300],
            COT_DU_NO_TH: [90, 90, 200, 300],
            COT_DU_NO_QH: [10, 10, 0, 0],
            COT_DU_NO_KHOANH: [0, 0, 0, 0],
        }
    )


def test_mon_qh_dem_khe_uoc_duy_nhat_thay_vi_dem_dong() -> None:
    df_th, _, _ = _tao_tong_hop_theo_nhom(_df_mau(), "ct", COT_TEN_CT)

    ct_a = df_th.loc[df_th[COT_TEN_CT] == "CT A"].iloc[0]

    assert int(ct_a["Số_món"]) == 1
    assert int(ct_a["Số_món_QH"]) == 1


def test_tong_kh_va_bq_kh_khong_cong_trung_giua_cac_nhom() -> None:
    df_th, df_group, _ = _tao_tong_hop_theo_nhom(_df_mau(), "ct", COT_TEN_CT)

    tong = _tinh_tong_cong(df_th, df_group)

    assert int(df_th["Số_KH"].sum()) == 3  # KH1 xuất hiện ở 2 nhóm; KH2 ở nhóm chưa rõ.
    assert tong["tong_kh"] == 2
    assert tong["tong_mon"] == 3
    assert tong["tong_mon_qh"] == 1
    assert tong["bq_kh"] == 350


def test_nhom_rong_duoc_giu_lai_va_tong_du_no_doi_chieu_du() -> None:
    df = _df_mau()

    df_th, df_group, _ = _tao_tong_hop_theo_nhom(df, "ct", COT_TEN_CT)
    tong = _tinh_tong_cong(df_th, df_group)

    assert _NHOM_KHONG_XAC_DINH in df_th[COT_TEN_CT].tolist()
    assert tong["tong_dn"] == df[COT_TONG_DU_NO].sum()
    assert tong["ty_trong"] == 100.0


def test_tap_du_no_bang_khong_khong_hien_ty_trong_100() -> None:
    df = _df_mau().assign(
        **{
            COT_TONG_DU_NO: 0,
            COT_DU_NO_TH: 0,
            COT_DU_NO_QH: 0,
        }
    )

    df_th, df_group, _ = _tao_tong_hop_theo_nhom(df, "ct", COT_TEN_CT)

    assert _tinh_tong_cong(df_th, df_group)["ty_trong"] == 0.0
    assert df_th["Tỷ_trọng_%"].eq(0).all()


def test_so_sanh_du_no_theo_nhieu_tieu_chi_giu_quy_tac_phan_loai() -> None:
    df = pd.DataFrame(
        {
            COT_TEN_PGD: [DON_VI_CHI_NHANH, "PGD A", "PGD B"],
            COT_TEN_XA: ["Vay trực tiếp", "La Ngà", "phường Tân Phú"],
            COT_TEN_CT: ["CT A", "CT A", "CT B"],
            COT_NGUON_VON: [1, "02", "TW"],
            COT_DVUT: ["Hội A", "Hội B", "Hội A"],
            COT_TEN_TO: ["Tổ 1", "Tổ 2", "Tổ 3"],
            COT_MA_KH: ["KH1", "KH2", "KH3"],
            COT_SO_KU: ["KU1", "KU2", "KU3"],
            COT_TONG_DU_NO: [100, 200, 300],
            COT_DU_NO_TH: [100, 200, 300],
            COT_DU_NO_QH: [0, 0, 0],
            COT_DU_NO_KHOANH: [0, 0, 0],
        }
    )

    result = _tao_so_sanh_du_no_theo_tieu_chi(
        df,
        tieu_chi_chon=["Khu vực", "Nguồn vốn"],
        top_n=None,
    )

    theo_nhom = {
        (row["Tiêu chí"], row["Nhóm"]): row["Tổng dư nợ"]
        for _, row in result.iterrows()
    }
    assert theo_nhom[("Khu vực", "Thành thị")] == 400
    assert theo_nhom[("Khu vực", "Nông thôn")] == 200
    assert theo_nhom[("Nguồn vốn", "1 — Trung ương")] == 400
    assert theo_nhom[("Nguồn vốn", "2 — Địa phương")] == 200

    top_result = _tao_so_sanh_du_no_theo_tieu_chi(
        df,
        tieu_chi_chon=["PGD", "Chương trình"],
        top_n=1,
    )
    assert top_result.groupby("Tiêu chí").size().to_dict() == {"Chương trình": 1, "PGD": 1}
    assert top_result["Xếp hạng"].tolist() == [1, 1]
    assert _tao_so_sanh_du_no_theo_tieu_chi(df, tieu_chi_chon=[]).empty


def test_pdf_tong_hop_dung_dong_tong_chuan_va_co_bq_kh(monkeypatch) -> None:
    df_th, df_group, co_khoanh = _tao_tong_hop_theo_nhom(
        _df_mau(), "ct", COT_TEN_CT
    )
    tong = _tinh_tong_cong(df_th, df_group)
    captured: dict[str, object] = {}

    def fake_xuat_pdf(df, *args, **kwargs):
        captured["df"] = df.copy()
        captured["kwargs"] = kwargs
        return b"%PDF-test"

    monkeypatch.setattr(tong_hop_hstd_v2, "xuat_pdf", fake_xuat_pdf)

    result = tong_hop_hstd_v2._xuat_pdf_tong_hop(
        df_th,
        tong,
        COT_TEN_CT,
        "Chương trình",
        co_khoanh,
        "Báo cáo test",
        "tester",
        "BC_TEST",
    )

    df_pdf = captured["df"]
    kwargs = captured["kwargs"]
    assert result == b"%PDF-test"
    assert "BQ/KH" in df_pdf.columns
    assert "TỔNG CỘNG" not in df_pdf["Chương trình"].tolist()
    assert kwargs["them_dong_tong"] is True
    assert kwargs["dong_tong"]["Số KH"] == 2
    assert kwargs["dong_tong"]["Số món"] == 3


def test_pdf_tong_hop_moc_3112_bo_emoji_va_can_cot_tien(monkeypatch) -> None:
    df_th, df_group, co_khoanh = _tao_tong_hop_theo_nhom(
        _df_mau(), "ct", COT_TEN_CT
    )
    df_th = df_th.assign(DN_moc_3112=[80, 200, 250])
    tong = _tinh_tong_cong(df_th, df_group)
    captured: dict[str, object] = {}

    def fake_xuat_pdf(df, *args, **kwargs):
        captured["df"] = df.copy()
        captured["title"] = args[0]
        captured["kwargs"] = kwargs
        return b"%PDF-test"

    monkeypatch.setattr(tong_hop_hstd_v2, "xuat_pdf", fake_xuat_pdf)

    result = tong_hop_hstd_v2._xuat_pdf_tong_hop(
        df_th,
        tong,
        COT_TEN_CT,
        "Chương trình",
        co_khoanh,
        "🏢 Theo Chương trình",
        "tester",
        "BC_TEST",
        nam_bl=2025,
    )

    df_pdf = captured["df"]
    kwargs = captured["kwargs"]
    assert result == b"%PDF-test"
    assert captured["title"] == "BÁO CÁO TỔNG HỢP HSTD — Theo Chương trình (triệu đồng)"
    assert "🏢" not in captured["title"]
    assert ["31/12/2025", "± 31/12"] == [
        col for col in df_pdf.columns if col in {"31/12/2025", "± 31/12"}
    ]
    assert "31/12/2025" in kwargs["cols_tien"]
    assert "± 31/12" in kwargs["cols_tien"]


def test_baseline_nguon_von_khong_khop_giu_schema_de_moc_bang_0(monkeypatch) -> None:
    df_bl = pd.DataFrame(
        {
            COT_TEN_PGD: ["PGD A"],
            COT_TEN_XA: ["Xã A"],
            COT_TEN_CT: ["CT A"],
            COT_NGUON_VON: [1],
            COT_MA_KH: ["KH1"],
            COT_SO_KU: ["KU1"],
            COT_TONG_DU_NO: [100],
            COT_DU_NO_TH: [100],
            COT_DU_NO_QH: [0],
            COT_DU_NO_KHOANH: [0],
        }
    )
    monkeypatch.setattr(tong_hop_hstd_v2, "_ds_nam_baseline_hstd", lambda: [2025])
    monkeypatch.setattr(tong_hop_hstd_v2, "ts_baseline_merged", lambda _nam: 123.0)
    monkeypatch.setattr(
        tong_hop_hstd_v2,
        "doc_baseline_merged",
        lambda _nam, ts=0.0: df_bl,
    )
    monkeypatch.setattr(
        tong_hop_hstd_v2.st,
        "session_state",
        {"nv_filter_th_ct": "2"},
    )

    result, nam = _doc_baseline_cung_pham_vi(
        "ct",
        COT_TEN_CT,
        role="admin",
        pgd_user="",
        hien_loc_pgd=False,
        filter_cols=[],
    )

    assert nam == 2025
    assert result is not None
    assert result.empty
    assert COT_TEN_CT in result.columns


class _FakeContainer:
    def __init__(self) -> None:
        self.html = ""

    def markdown(self, value: str, unsafe_allow_html: bool = False) -> None:
        assert unsafe_allow_html is True
        self.html = value


def test_bang_chi_tiet_chi_dung_class_theme_toan_cuc_va_escape_ten() -> None:
    container = _FakeContainer()
    df = pd.DataFrame(
        {
            "Nhóm": ["<script>alert(1)</script>"],
            "Số KH": [1],
            "Tổng dư nợ": [12.5],
            "Tỷ trọng %": [100],
            "Tỷ lệ QH %": [0.5],
        }
    )

    render_bang_chi_tiet_html(
        df,
        key="test",
        cot_ten="Nhóm",
        cot_dem=["Số KH"],
        cot_tien=["Tổng dư nợ"],
        cot_bar="Tỷ trọng %",
        cot_badge="Tỷ lệ QH %",
        container=container,
    )

    assert "<style>" not in container.html
    assert "#FFFFFF" not in container.html
    assert 'class="bct-wrap"' in container.html
    assert '&lt;script&gt;alert(1)&lt;/script&gt;' in container.html


def test_sticky_table_khong_inject_css_tai_component() -> None:
    container = _FakeContainer()

    render_sticky_table(pd.DataFrame({"A": [1]}), key="test", container=container)

    assert "<style>" not in container.html
    assert 'class="sticky-table-wrap"' in container.html
    assert 'class="dataframe sticky-table"' in container.html


def test_theme_toan_cuc_co_css_cho_bang_bao_cao() -> None:
    css = _css_part2()

    assert ".bct-wrap" in css
    assert ".bct-table thead" in css
    assert ".sticky-table-wrap" in css
