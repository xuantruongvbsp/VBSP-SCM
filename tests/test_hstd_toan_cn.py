"""Regression tests cho upload một file HSTD toàn Chi nhánh."""
from __future__ import annotations

import inspect
from io import BytesIO
from pathlib import Path

import pandas as pd
import pytest

from config import COT_TEN_PGD, DON_VI_CHI_NHANH, DS_PGD
from services import upload_service
from tabs.tab_upload_khnv import _upload_toan_cn


def _tao_hstd(rows: list[dict]) -> bytes:
    frame = pd.DataFrame(rows)
    frame.insert(0, "BoQua", "x")
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        frame.to_excel(writer, sheet_name="BCQUERY", startrow=4, index=False)
    return output.getvalue()


def test_tach_hstd_chuan_hoa_alias_va_ten_pgd_rut_gon():
    file_bytes = _tao_hstd(
        [
            {COT_TEN_PGD: "PGD Biên Hòa", "Số khế ước": "001"},
            {COT_TEN_PGD: "Long Thành", "Số khế ước": "002"},
        ]
    )

    result = upload_service.tach_file_hstd_toan_cn(file_bytes)

    assert set(result) == {DON_VI_CHI_NHANH, "PGD Long Thành"}
    hoi_so = pd.read_excel(BytesIO(result[DON_VI_CHI_NHANH]), sheet_name="BCQUERY", header=4)
    assert hoi_so[COT_TEN_PGD].tolist() == [DON_VI_CHI_NHANH]


def test_tach_hstd_bao_loi_ten_don_vi_khong_nhan_dien():
    file_bytes = _tao_hstd([{COT_TEN_PGD: "Đơn vị không tồn tại", "Số khế ước": "001"}])

    with pytest.raises(ValueError, match="không nhận diện được"):
        upload_service.tach_file_hstd_toan_cn(file_bytes)


def test_xu_ly_hstd_thieu_don_vi_khong_ghi_file(monkeypatch):
    pgd_map = {ten: f"new-{ten}".encode() for ten in [DON_VI_CHI_NHANH] + DS_PGD[:-1]}
    monkeypatch.setattr(upload_service, "tach_file_hstd_toan_cn", lambda _bytes: pgd_map)
    monkeypatch.setattr(
        upload_service,
        "_ghi_va_xoa_cache",
        lambda *_args, **_kwargs: pytest.fail("Không được ghi khi thiếu đơn vị"),
    )

    result = upload_service.xu_ly_hstd_toan_cn(b"fake")

    assert set(result) == {"_loi_doc"}
    assert result["_loi_doc"].thanh_cong is False
    assert "đúng đủ 22 đơn vị" in result["_loi_doc"].thong_bao


def test_xu_ly_hstd_loi_giua_chung_khoi_phuc_toan_bo(monkeypatch, tmp_path):
    ds_don_vi = [DON_VI_CHI_NHANH] + DS_PGD
    pgd_map = {ten: f"new-{index}".encode() for index, ten in enumerate(ds_don_vi)}
    paths = {ten: tmp_path / f"dv-{index}" / "hstd_khnv.xlsx" for index, ten in enumerate(ds_don_vi)}
    noi_dung_cu = {ten: f"old-{index}".encode() for index, ten in enumerate(ds_don_vi)}
    for ten, path in paths.items():
        path.parent.mkdir(parents=True)
        path.write_bytes(noi_dung_cu[ten])

    monkeypatch.setattr(upload_service, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(upload_service, "tach_file_hstd_toan_cn", lambda _bytes: pgd_map)
    monkeypatch.setattr(upload_service, "duong_dan_pgd", lambda ten, _loai: str(paths[ten]))
    ghi_goc = upload_service._ghi_va_xoa_cache
    so_lan_ghi_moi = 0

    def _ghi_co_loi(path: str, payload: bytes, cache: str | None = None) -> None:
        nonlocal so_lan_ghi_moi
        if payload.startswith(b"new-"):
            so_lan_ghi_moi += 1
            if so_lan_ghi_moi == 2:
                raise OSError("giả lập lỗi đĩa")
        ghi_goc(path, payload, cache)

    monkeypatch.setattr(upload_service, "_ghi_va_xoa_cache", _ghi_co_loi)

    result = upload_service.xu_ly_hstd_toan_cn(b"fake")

    assert set(result) == {"_loi_doc"}
    assert "Đã khôi phục" in result["_loi_doc"].thong_bao
    assert {ten: path.read_bytes() for ten, path in paths.items()} == noi_dung_cu
    assert not list((tmp_path / "cache").glob("hstd_cn_backup_*"))


def test_xu_ly_hstd_du_22_ghi_tron_bo_va_tra_duong_dan(monkeypatch, tmp_path):
    ds_don_vi = [DON_VI_CHI_NHANH] + DS_PGD
    pgd_map = {ten: f"new-{index}".encode() for index, ten in enumerate(ds_don_vi)}
    paths = {ten: tmp_path / f"dv-{index}" / "hstd_khnv.xlsx" for index, ten in enumerate(ds_don_vi)}
    monkeypatch.setattr(upload_service, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(upload_service, "tach_file_hstd_toan_cn", lambda _bytes: pgd_map)
    monkeypatch.setattr(upload_service, "duong_dan_pgd", lambda ten, _loai: str(paths[ten]))

    result = upload_service.xu_ly_hstd_toan_cn(b"fake")

    assert set(result) == set(ds_don_vi)
    assert all(item.thanh_cong for item in result.values())
    assert all(result[ten].duong_dan == str(paths[ten].resolve()) for ten in ds_don_vi)
    assert {ten: path.read_bytes() for ten, path in paths.items()} == pgd_map
    assert not list((tmp_path / "cache").glob("hstd_cn_backup_*"))


def test_xu_ly_hstd_dung_pgd_map_co_san_khong_tach_lai(monkeypatch, tmp_path):
    ds_don_vi = [DON_VI_CHI_NHANH] + DS_PGD
    pgd_map = {ten: f"preview-{index}".encode() for index, ten in enumerate(ds_don_vi)}
    paths = {ten: tmp_path / f"dv-{index}" / "hstd_khnv.xlsx" for index, ten in enumerate(ds_don_vi)}
    monkeypatch.setattr(upload_service, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(
        upload_service,
        "tach_file_hstd_toan_cn",
        lambda _bytes: pytest.fail("Không được tách lại khi đã có pgd_map từ preview"),
    )
    monkeypatch.setattr(upload_service, "duong_dan_pgd", lambda ten, _loai: str(paths[ten]))

    result = upload_service.xu_ly_hstd_toan_cn(b"fake", pgd_map=pgd_map)

    assert set(result) == set(ds_don_vi)
    assert all(item.thanh_cong for item in result.values())
    assert {ten: path.read_bytes() for ten, path in paths.items()} == pgd_map


def test_helper_doc_excel_nhanh_ton_tai_va_doc_duoc_bytes():
    file_bytes = _tao_hstd([{COT_TEN_PGD: DON_VI_CHI_NHANH, "Số khế ước": "001"}])

    df_service = upload_service._doc_excel_bytes(file_bytes, sheet_name="BCQUERY", header=4)
    df_ui = _upload_toan_cn._doc_excel_nhanh(file_bytes, sheet_name="BCQUERY", header=4)

    assert COT_TEN_PGD in df_service.columns
    assert COT_TEN_PGD in df_ui.columns


def test_ui_chi_nhan_xlsx_va_khoa_upload_khi_thieu_don_vi():
    source = inspect.getsource(_upload_toan_cn.render_hstd_toan_cn)

    assert 'type=["xlsx"]' in source
    assert "hashlib.sha256(uploaded_bytes).hexdigest()" in source
    assert "disabled=not du_22_don_vi" in source
    assert "if so_ok != tong_don_vi:" in source
    assert '"pgd_map": pgd_map' in source
    assert "_doc_excel_nhanh(" in source
