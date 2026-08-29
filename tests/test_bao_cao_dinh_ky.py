"""Regression tests cho tab/script Báo cáo định kỳ."""
from __future__ import annotations

from pathlib import Path


def test_pgd_role_khong_doc_bao_cao_toan_cn(monkeypatch):
    """PGD mở tab Báo cáo định kỳ không được liệt kê/tạo báo cáo toàn CN."""
    from tabs import tab_bao_cao_dinh_ky as mod

    def _fail(*args, **kwargs):
        raise AssertionError("PGD không được truy cập báo cáo định kỳ toàn CN")

    monkeypatch.setattr(mod, "list_reports", _fail)
    monkeypatch.setattr(mod, "generate_daily_report", _fail)
    monkeypatch.setattr(mod, "generate_word_report", _fail)

    mod.render(None, role="admin_pgd", username="pgd_user", pgd_user="PGD A")


def test_generate_daily_report_notify_false_chi_tao_file(monkeypatch, tmp_path):
    """Nút tạo thủ công trong UI truyền notify=False để không chạy nhánh Telegram."""
    from scripts import daily_report as mod

    parquet = tmp_path / "hstd.parquet"
    parquet.write_bytes(b"dummy")
    monkeypatch.setattr(mod, "CACHE_HSTD", parquet)
    monkeypatch.setattr(mod, "REPORT_DIR", tmp_path / "reports")

    monkeypatch.setattr(mod, "_build_tong_quan_sheet", lambda wb, path: None)
    monkeypatch.setattr(mod, "_build_nqh_top_sheet", lambda wb, path: None)
    monkeypatch.setattr(mod, "_build_den_han_sheet", lambda wb, path: None)
    monkeypatch.setattr(mod, "_build_khtd_sheet", lambda wb: None)

    def _notify_side_effect(*args, **kwargs):
        raise AssertionError("notify=False không được chạy nhánh thông báo")

    monkeypatch.setattr(mod, "_nhac_phan_ky_nxh", _notify_side_effect)
    monkeypatch.setattr(mod, "_canh_bao_tong_hop_rui_ro", _notify_side_effect)
    monkeypatch.setattr(mod, "_giai_ngan_tuan", _notify_side_effect)
    monkeypatch.setattr(mod, "_bao_cao_nqh_tuan", _notify_side_effect)
    monkeypatch.setattr(mod, "_bao_cao_khtd_theo_ct", _notify_side_effect)
    monkeypatch.setattr(mod, "_tong_ket_thang", _notify_side_effect)
    monkeypatch.setattr(mod, "_duckdb_query", _notify_side_effect)

    result = mod.generate_daily_report(notify=False)

    assert result is not None
    assert Path(result).exists()
    assert Path(result).suffix == ".xlsx"
