"""
Tests for services/file_detection_service.py
Pure logic functions: md5, alias, unit-name detection, file-type sniffing.
"""
from __future__ import annotations

import hashlib
import tempfile
from io import BytesIO

import pandas as pd
import pytest

from config import DON_VI_CHI_NHANH, DS_PGD
from services.file_detection_service import (
    chuan_hoa_ten,
    kiem_tra_don_vi,
    md5_bytes,
    md5_file,
    nhan_dien_loai_tu_noi_dung,
    ten_doc_ve_don_vi_chuan,
)


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_excel(sheet_name: str, columns: list[str], startrow: int = 4) -> bytes:
    """Tạo file Excel tối giản với 1 sheet, 1 dòng dữ liệu."""
    df = pd.DataFrame({c: ["_"] for c in columns})
    bio = BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name=sheet_name, startrow=startrow, index=False)
    return bio.getvalue()


def _make_hstd_bytes() -> bytes:
    return _make_excel("BCQUERY", ["Tên PGD", "Tổng dư nợ"])


def _make_nq11_bytes() -> bytes:
    return _make_excel("BCQUERY", ["Mã ĐVUT", "Tên ĐVUT", "Mã PGD"])


# ── md5_bytes ─────────────────────────────────────────────────────────────────

def test_md5_bytes_returns_hex():
    data = b"hello"
    result = md5_bytes(data)
    assert result == hashlib.md5(b"hello").hexdigest()
    assert len(result) == 32


def test_md5_bytes_different_inputs_differ():
    assert md5_bytes(b"aaa") != md5_bytes(b"bbb")


# ── md5_file ──────────────────────────────────────────────────────────────────

def test_md5_file_not_found_returns_empty():
    assert md5_file("/nonexistent/path/file.xlsx") == ""


def test_md5_file_existing_matches_bytes():
    data = b"test data"
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(data)
        path = f.name
    assert md5_file(path) == md5_bytes(data)


# ── chuan_hoa_ten ─────────────────────────────────────────────────────────────

def test_chuan_hoa_ten_alias_pgd_bien_hoa():
    assert chuan_hoa_ten("PGD Biên Hòa") == DON_VI_CHI_NHANH


def test_chuan_hoa_ten_alias_hoi_so_cn():
    assert chuan_hoa_ten("Hội sở CN Đồng Nai") == DON_VI_CHI_NHANH


def test_chuan_hoa_ten_no_alias_passthrough():
    assert chuan_hoa_ten("PGD Long Thành") == "PGD Long Thành"


def test_chuan_hoa_ten_strips_whitespace():
    assert chuan_hoa_ten("  PGD Long Thành  ") == "PGD Long Thành"


# ── ten_doc_ve_don_vi_chuan ───────────────────────────────────────────────────

def test_ten_doc_ve_don_vi_chuan_none():
    assert ten_doc_ve_don_vi_chuan(None) is None


def test_ten_doc_ve_don_vi_chuan_empty():
    assert ten_doc_ve_don_vi_chuan("") is None


def test_ten_doc_ve_don_vi_chuan_nan_string():
    assert ten_doc_ve_don_vi_chuan("nan") is None
    assert ten_doc_ve_don_vi_chuan("None") is None


def test_ten_doc_ve_don_vi_chuan_valid_pgd():
    pgd = DS_PGD[0]
    assert ten_doc_ve_don_vi_chuan(pgd) == pgd


def test_ten_doc_ve_don_vi_chuan_alias_maps_to_chi_nhanh():
    assert ten_doc_ve_don_vi_chuan("PGD Biên Hòa") == DON_VI_CHI_NHANH


def test_ten_doc_ve_don_vi_chuan_partial_match():
    pgd = DS_PGD[0]
    partial = pgd.upper()
    result = ten_doc_ve_don_vi_chuan(partial)
    assert result == pgd


# ── kiem_tra_don_vi ───────────────────────────────────────────────────────────

def test_kiem_tra_don_vi_match(monkeypatch):
    pgd = DS_PGD[0]
    monkeypatch.setattr(
        "services.file_detection_service.lay_ten_don_vi_trong_file",
        lambda _b, _l: pgd,
    )
    ok, msg = kiem_tra_don_vi(b"", "hstd", pgd)
    assert ok is True
    assert "khớp" in msg.lower() or "✅" in msg


def test_kiem_tra_don_vi_mismatch(monkeypatch):
    monkeypatch.setattr(
        "services.file_detection_service.lay_ten_don_vi_trong_file",
        lambda _b, _l: DS_PGD[0],
    )
    ok, msg = kiem_tra_don_vi(b"", "hstd", DS_PGD[1])
    assert ok is False
    assert "nhầm" in msg.lower() or "⚠️" in msg


def test_kiem_tra_don_vi_cannot_read(monkeypatch):
    monkeypatch.setattr(
        "services.file_detection_service.lay_ten_don_vi_trong_file",
        lambda _b, _l: None,
    )
    ok, msg = kiem_tra_don_vi(b"", "hstd", DS_PGD[0])
    assert ok is True
    assert "không đọc" in msg.lower() or "⚠️" in msg


# ── nhan_dien_loai_tu_noi_dung ────────────────────────────────────────────────

def test_nhan_dien_invalid_bytes_returns_none():
    assert nhan_dien_loai_tu_noi_dung(b"not an excel file") is None


def test_nhan_dien_hstd():
    data = _make_hstd_bytes()
    result = nhan_dien_loai_tu_noi_dung(data)
    assert result == "hstd"


def test_nhan_dien_nq11():
    data = _make_nq11_bytes()
    result = nhan_dien_loai_tu_noi_dung(data)
    assert result == "nq11"
