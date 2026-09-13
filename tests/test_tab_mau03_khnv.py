from __future__ import annotations

import pandas as pd

from config import DON_VI_CHI_NHANH, DS_PGD
from tabs import tab_mau03_khnv as mod


def _snapshot_row(ten_pgd: str, tong: float, qh: float, khoanh: float) -> dict:
    return {
        "ten_pgd": ten_pgd,
        "tong_du_no": tong,
        "du_no_qh": qh,
        "du_no_khoanh": khoanh,
    }


def test_tim_ba_ky_khong_fallback_sang_ky_cu_khi_thieu_thang_lien_truoc():
    assert mod._tim_ba_ky(["2026-07", "2026-04", "2025-12"]) == ("2026-07", None)


def test_lay_du_lieu_khong_dung_snapshot_thang_truoc_neu_chua_cuoi_thang(monkeypatch):
    monkeypatch.setattr(mod, "danh_sach_ky", lambda: ["2026-07", "2026-06"])
    monkeypatch.setattr(mod, "_doc_baseline_theo_pgd", lambda _nam: pd.DataFrame())

    def _doc_snapshot(ky):
        ngay = "31/07/2026" if ky == "2026-07" else "23/06/2026"
        row = _snapshot_row(DON_VI_CHI_NHANH, 100_000_000, 1_000_000, 0)
        row["ngay_so_lieu"] = ngay
        return pd.DataFrame([row])

    monkeypatch.setattr(mod, "doc_snapshot", _doc_snapshot)

    _ky_ht, ky_tt, _moc_cn, _df_ht, df_tt, _df_cn = mod._lay_du_lieu_3_ky()
    assert ky_tt is None
    assert df_tt.empty


def test_ngay_so_lieu_uu_tien_dong_tong_cn_va_khong_tu_suy_dien():
    df = pd.DataFrame([
        {"ten_pgd": DON_VI_CHI_NHANH, "ngay_so_lieu": "30/07/2026"},
        {"ten_pgd": "__CN__", "ngay_so_lieu": "31/07/2026"},
    ])
    assert mod._ngay_so_lieu_cn(df) == "31/07/2026"
    assert mod._ngay_so_lieu_cn(pd.DataFrame()) == ""


def test_build_report_data_thieu_moc_so_sanh_khong_tinh_nhu_so_0():
    df_ht = pd.DataFrame([
        _snapshot_row(DON_VI_CHI_NHANH, 1_000_000_000, 10_000_000, 5_000_000)
    ])

    df = mod._build_report_data(df_ht, pd.DataFrame(), pd.DataFrame())
    row = df.loc[df["ten_pgd"].eq(DON_VI_CHI_NHANH)].iloc[0]
    total = df.iloc[-1]

    for col in ["d_nqhk_tt", "d_nqhk_cn", "d_nqh_tt", "d_nqh_cn", "d_nkh_tt", "d_nkh_cn"]:
        assert pd.isna(row[col])
        assert pd.isna(total[col])


def test_build_report_data_tinh_delta_tu_baseline_31_12():
    df_ht = pd.DataFrame([
        _snapshot_row(DON_VI_CHI_NHANH, 1_000_000_000, 10_000_000, 5_000_000)
    ])
    df_tt = pd.DataFrame([
        _snapshot_row(DON_VI_CHI_NHANH, 900_000_000, 7_000_000, 4_000_000)
    ])
    df_cn = pd.DataFrame([
        _snapshot_row(DON_VI_CHI_NHANH, 800_000_000, 12_000_000, 1_000_000)
    ])

    df = mod._build_report_data(df_ht, df_tt, df_cn)
    row = df.loc[df["ten_pgd"].eq(DON_VI_CHI_NHANH)].iloc[0]

    assert row["d_nqh_tt"] == 3.0
    assert row["d_nkh_tt"] == 1.0
    assert row["d_nqhk_tt"] == 4.0
    assert row["d_nqh_cn"] == -2.0
    assert row["d_nkh_cn"] == 4.0
    assert row["d_nqhk_cn"] == 2.0


def test_build_report_data_bo_qua_dong_tong_cn_de_tranh_cong_trung():
    pgd = DS_PGD[0]
    df_ht = pd.DataFrame([
        _snapshot_row(DON_VI_CHI_NHANH, 100_000_000, 10_000_000, 5_000_000),
        _snapshot_row(pgd, 200_000_000, 20_000_000, 5_000_000),
        _snapshot_row("__CN__", 999_000_000, 999_000_000, 999_000_000),
    ])

    df = mod._build_report_data(df_ht, pd.DataFrame(), pd.DataFrame())
    total = df.iloc[-1]

    assert "__CN__" not in set(df["ten_pgd"])
    assert total["tong_du_no"] == 300.0
    assert total["nqh"] == 30.0
    assert total["nkh"] == 10.0


def test_render_bang_html_escape_text_dong_va_giu_span_delta(monkeypatch):
    captured = []
    monkeypatch.setattr(mod.st, "html", lambda html: captured.append(html))
    df = pd.DataFrame([{
        "ten_pgd": "<b>PGD & Test</b>",
        "tong_du_no": 100.0,
        "nqhk": 15.0,
        "tl_nqhk": 15.0,
        "d_nqhk_tt": 1.0,
        "d_nqhk_cn": -2.0,
        "nqh": 10.0,
        "tl_nqh": 10.0,
        "d_nqh_tt": 1.0,
        "d_nqh_cn": -2.0,
        "nkh": 5.0,
        "tl_nkh": 5.0,
        "d_nkh_tt": 0.0,
        "d_nkh_cn": pd.NA,
    }])

    mod._render_bang_html(df, "31/07/2026")

    assert captured
    html = captured[0]
    assert "&lt;b&gt;PGD &amp; Test&lt;/b&gt;" in html
    assert "<b>PGD & Test</b>" not in html
    assert '<span style="color:#2E7D32;font-weight:600">+1,00</span>' in html
