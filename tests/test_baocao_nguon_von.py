"""Regression tests cho bộ lọc nguồn vốn của Báo cáo tín dụng."""
from __future__ import annotations

import pandas as pd

from config import (
    COT_DU_NO_KHOANH,
    COT_DU_NO_QH,
    COT_MA_KH,
    COT_NGAY_DH,
    COT_NGUON_VON,
    COT_SO_KU,
    COT_TEN_CT,
    COT_TEN_KH,
    COT_TEN_PGD,
    COT_TEN_XA,
    COT_TONG_DU_NO,
    DON_VI_CHI_NHANH,
    DS_XA_THANH_THI,
)
from tabs.tab_baocao.components import inline_filter
from tabs.tab_baocao.components.inline_filter import (
    chuan_bi_du_lieu_bao_cao,
    chuan_hoa_nhom_nguon_von,
    loc_khu_vuc,
    loc_nguon_von,
    render_inline_filter,
)
from tabs.tab_baocao.dashboard import _loc_hstd_metric
from tabs.tab_baocao.reports import no_rui_ro_v2


def _df_mau() -> pd.DataFrame:
    return pd.DataFrame(
        {
            COT_TEN_PGD: ["PGD A"] * 5 + ["PGD B"] * 5 + ["PGD C"],
            COT_NGUON_VON: [1, "01", 1.0, "TW", "tw", 2, "02", 2.0, "DP", "ĐP", None],
            COT_TONG_DU_NO: [10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110],
        }
    )


def test_loc_nguon_von_nhan_du_cac_bien_the_tw_dp() -> None:
    df = _df_mau()

    df_tw = loc_nguon_von(df, "1")
    df_dp = loc_nguon_von(df, "2")

    assert df_tw[COT_TONG_DU_NO].tolist() == [10, 20, 30, 40, 50]
    assert df_dp[COT_TONG_DU_NO].tolist() == [60, 70, 80, 90, 100]
    assert loc_nguon_von(df, "all") is df


def test_loc_nguon_von_ma_khong_hien_co_khong_lam_rong_df() -> None:
    df = pd.DataFrame({COT_NGUON_VON: [None, "KHAC"], COT_TONG_DU_NO: [10, 20]})

    assert loc_nguon_von(df, "1") is df
    assert loc_nguon_von(df, "2") is df


def test_chuan_hoa_nhom_nguon_von_khong_tach_nhieu_nhom_tuong_duong() -> None:
    result = chuan_hoa_nhom_nguon_von(_df_mau())

    assert result[COT_NGUON_VON].value_counts().to_dict() == {
        "1 — Trung ương": 5,
        "2 — Địa phương": 5,
        "Khác/Không xác định": 1,
    }


def test_loc_khu_vuc_phan_loai_33_phuong_va_fallback_nong_thon() -> None:
    df = pd.DataFrame(
        {
            COT_TEN_XA: [
                "Biên Hòa",
                "phường Tân Phú",
                "  Trấn Biên  ",
                "La Ngà",
                "Vay trực tiếp",
                "Vay trực tiếp",
                None,
            ],
            COT_TEN_PGD: [
                "PGD A",
                "PGD B",
                "PGD C",
                "PGD D",
                DON_VI_CHI_NHANH,
                "PGD Đồng Phú",
                DON_VI_CHI_NHANH,
            ],
            COT_TONG_DU_NO: [1, 2, 3, 4, 5, 6, 7],
        }
    )

    assert len(DS_XA_THANH_THI) == 33
    assert loc_khu_vuc(df, "thanh_thi")[COT_TONG_DU_NO].tolist() == [1, 2, 3, 5]
    assert loc_khu_vuc(df, "nong_thon")[COT_TONG_DU_NO].tolist() == [4, 6, 7]
    assert (
        loc_khu_vuc(df, "thanh_thi")[COT_TONG_DU_NO].sum()
        + loc_khu_vuc(df, "nong_thon")[COT_TONG_DU_NO].sum()
        == df[COT_TONG_DU_NO].sum()
    )
    assert loc_khu_vuc(df, "all") is df
    assert loc_khu_vuc(df, "khac") is df


def test_loc_khu_vuc_nhom_hop_le_khong_co_du_lieu_tra_rong() -> None:
    df = pd.DataFrame(
        {
            COT_TEN_XA: ["La Ngà", None],
            COT_TONG_DU_NO: [4, 7],
        }
    )

    assert loc_khu_vuc(df, "thanh_thi").empty
    assert loc_khu_vuc(df, "nong_thon")[COT_TONG_DU_NO].sum() == 11


def test_metric_dashboard_dung_cung_bo_loc_pgd_va_nguon_von() -> None:
    df = _df_mau()

    result = _loc_hstd_metric(df, selected_pgd="PGD B", selected_nv="2")

    assert result is not None
    assert result[COT_TEN_PGD].unique().tolist() == ["PGD B"]
    assert result[COT_TONG_DU_NO].sum() == 400


def test_chuan_bi_bao_cao_loai_khe_uoc_rong_va_trung_khoa_da_strip() -> None:
    df = pd.DataFrame(
        {
            COT_MA_KH: [" KH1 ", "KH1", "KH2", "KH3", "KH4", "KH5", "KH6"],
            COT_SO_KU: [" KU1 ", "KU1", "", None, "nan", "KU2", "KU2"],
            COT_TONG_DU_NO: [100, 100, 0, 0, 0, 50, 70],
        }
    )

    result = chuan_bi_du_lieu_bao_cao(df)

    assert result.index.tolist() == [0, 5, 6]
    assert result[COT_TONG_DU_NO].sum() == 220
    assert len(df) == 7  # helper không sửa DataFrame nguồn


def test_metric_dashboard_khong_dem_lap_cung_khoan_vay() -> None:
    df = pd.DataFrame(
        {
            COT_TEN_PGD: ["PGD A", "PGD A", "PGD A"],
            COT_NGUON_VON: [1, 1, 1],
            COT_MA_KH: ["KH1", " KH1 ", "KH2"],
            COT_SO_KU: ["KU1", "KU1 ", ""],
            COT_TONG_DU_NO: [100, 100, 0],
        }
    )

    result = _loc_hstd_metric(df, selected_pgd="PGD A", selected_nv="1")

    assert result is not None
    assert len(result) == 1
    assert result[COT_TONG_DU_NO].sum() == 100


class _FakeColumn:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False


class _FakeContainer:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def columns(self, count: int):
        return [_FakeColumn() for _ in range(count)]

    def caption(self, value: str) -> None:
        self.messages.append(value)

    def markdown(self, value: str) -> None:
        self.messages.append(value)

    def divider(self) -> None:
        pass

    def success(self, value: str) -> None:
        self.messages.append(value)


def test_inline_filter_thu_hai_phu_thuoc_filter_thu_nhat(monkeypatch) -> None:
    df = pd.DataFrame(
        {
            COT_TEN_XA: ["Xã A", "Xã A", "Xã B"],
            COT_TEN_CT: ["CT 1", "CT 1", "CT 2"],
        }
    )
    options_seen: dict[str, list] = {}

    def fake_selectbox(label, options, **kwargs):
        options_seen[label] = list(options)
        return "Xã A" if label == f"🔍 {COT_TEN_XA}" else "Tất cả"

    monkeypatch.setattr(inline_filter.st, "session_state", {})
    monkeypatch.setattr(inline_filter.st, "selectbox", fake_selectbox)

    result = render_inline_filter(
        df,
        [COT_TEN_XA, COT_TEN_CT],
        key="dependent",
        container=_FakeContainer(),
    )

    assert options_seen[f"🔍 {COT_TEN_CT}"] == ["Tất cả", "CT 1"]
    assert result[COT_TEN_XA].unique().tolist() == ["Xã A"]


def test_no_qh_metrics_va_bang_dung_cung_pham_vi_filter(monkeypatch) -> None:
    df = pd.DataFrame(
        {
            COT_TEN_PGD: ["PGD A", "PGD A"],
            COT_TEN_XA: ["Xã A", "Xã B"],
            COT_TEN_KH: ["KH A", "KH B"],
            COT_MA_KH: ["1", "2"],
            COT_SO_KU: ["KU1", "KU2"],
            COT_TONG_DU_NO: [100, 200],
            COT_DU_NO_QH: [10, 20],
            COT_DU_NO_KHOANH: [0, 0],
        }
    )
    metrics: dict[str, str] = {}
    exported: list[pd.DataFrame] = []

    monkeypatch.setattr(
        no_rui_ro_v2,
        "render_combined_filter_search",
        lambda data, *args, **kwargs: data.loc[data[COT_TEN_XA].eq("Xã A")].copy(),
    )
    monkeypatch.setattr(
        no_rui_ro_v2,
        "render_metric_with_tooltip",
        lambda label, value, *args, **kwargs: metrics.__setitem__(label, value),
    )
    monkeypatch.setattr(no_rui_ro_v2, "get_suggestions", lambda alerts: [])
    monkeypatch.setattr(
        no_rui_ro_v2,
        "render_quick_export_buttons",
        lambda data, *args, **kwargs: exported.append(data.copy()),
    )
    monkeypatch.setattr(no_rui_ro_v2, "render_sticky_table", lambda *args, **kwargs: None)

    no_rui_ro_v2._render_no_qh_v2(_FakeContainer(), df, "tester")

    assert metrics["Số món QH"] == "1"
    assert metrics["Tỷ lệ QH"] == "10,00%"
    assert len(exported) == 1
    assert exported[0][COT_SO_KU].tolist() == ["KU1"]


def test_pdf_den_han_dinh_dang_ngay_dd_mm_yyyy(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_xuat_pdf_chi_tiet(df, cols, *args):
        captured["df"] = df.copy()
        captured["cols"] = cols
        return b"%PDF-test"

    monkeypatch.setattr(no_rui_ro_v2, "xuat_pdf_chi_tiet", fake_xuat_pdf_chi_tiet)
    df = pd.DataFrame({
        COT_NGAY_DH: [pd.Timestamp("2026-08-25"), pd.NaT],
        COT_TONG_DU_NO: [100, 200],
    })

    result = no_rui_ro_v2._xuat_pdf_chi_tiet_no_rui_ro(
        df, "Đến hạn", "tester", "BC_DH30"
    )

    assert result == b"%PDF-test"
    assert captured["df"][COT_NGAY_DH].tolist() == ["25/08/2026", ""]
    assert captured["cols"] == list(df.columns)


def test_pdf_no_xau_du_cot_tien_tong_ty_le_va_khong_co_emoji(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_xuat_pdf(df, *args, **kwargs):
        captured["df"] = df.copy()
        captured["kwargs"] = kwargs
        return b"%PDF-test"

    monkeypatch.setattr(no_rui_ro_v2, "xuat_pdf", fake_xuat_pdf)
    df = pd.DataFrame({
        COT_TEN_PGD: ["PGD A", "PGD B"],
        "Tổng_dư_nợ": [10_000_000_000, 20_000_000_000],
        "Nợ_quá_hạn": [1_000_000_000, 2_000_000_000],
        "Nợ_khoanh": [500_000_000, 200_000_000],
        "Tổng_nợ_xấu": [1_500_000_000, 2_200_000_000],
        "Tỷ_lệ_nợ_xấu_%": [15.0, 11.0],
        "⚠️": ["🚨", "⚠️"],
    })

    result = no_rui_ro_v2._xuat_pdf_ty_le_no_xau(
        df, "Báo cáo tỷ lệ nợ xấu", "tester"
    )

    df_pdf = captured["df"]
    kwargs = captured["kwargs"]
    assert result == b"%PDF-test"
    assert "⚠️" not in df_pdf.columns
    assert df_pdf["Nợ quá hạn"].tolist() == [1000.0, 2000.0]
    assert kwargs["cols_tien"] == [
        "Tổng dư nợ", "Nợ quá hạn", "Nợ khoanh", "Tổng nợ xấu"
    ]
    assert kwargs["dong_tong"]["Tổng nợ xấu"] == 3700
    assert kwargs["dong_tong"]["Tỷ lệ nợ xấu %"] == 12.33
