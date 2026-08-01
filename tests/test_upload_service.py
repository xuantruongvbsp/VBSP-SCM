"""
tests/test_upload_service.py
─────────────────────────────
Unit test cho services/upload_service.py.
Dùng pytest + unittest.mock — không cần DB thật, không cần file thật.
"""
from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

# ── Import module cần test ──────────────────────────────────────────────────
try:
    import services.upload_service as upload_service
    from services.upload_service import (
        KetQuaUpload,
        _ghi_va_xoa_cache,
        kiem_tra_file,
        kiem_tra_file_he_thong,
    )
except ImportError:
    import upload_service
    from upload_service import (
        KetQuaUpload,
        _ghi_va_xoa_cache,
        kiem_tra_file,
        kiem_tra_file_he_thong,
    )


# ── Helpers tạo file bytes giả ──────────────────────────────────────────────
def _excel_bytes_nho() -> bytes:
    """Trả về bytes Excel giả < 1KB (file quá nhỏ)."""
    return b"PK\x03\x04" + b"\x00" * 100  # magic bytes xlsx nhưng < 1KB


def _excel_bytes_hop_le() -> bytes:
    """Tạo file Excel thật bằng openpyxl (> 1KB)."""
    import openpyxl
    buf = io.BytesIO()
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Tên PGD", "Mã KH", "Tổng dư nợ"])
    ws.append(["PGD Biên Hòa", "KH001", 10_000_000])
    wb.save(buf)
    return buf.getvalue()


class TestGhiVaXoaCache:
    def test_ghi_nguyen_tu_va_xoa_cache_lien_quan(self, tmp_path):
        target = tmp_path / "dienbao.xlsx"
        cache = tmp_path / "dienbao.parquet"
        target.write_bytes(b"ban-cu")
        cache.write_bytes(b"cache-cu")

        _ghi_va_xoa_cache(str(target), b"ban-moi", str(cache))

        assert target.read_bytes() == b"ban-moi"
        assert not cache.exists()
        assert not list(tmp_path.glob(".dienbao.xlsx.*.tmp"))

    def test_retry_replace_khi_windows_bao_err_invalid_argument(self, tmp_path):
        target = tmp_path / "dienbao.xlsx"
        target.write_bytes(b"ban-cu")
        real_replace = upload_service.os.replace
        calls = 0

        def flaky_replace(src, dst):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise OSError(22, "Invalid argument", str(dst))
            return real_replace(src, dst)

        with (
            patch.object(upload_service.os, "replace", side_effect=flaky_replace),
            patch.object(upload_service.time, "sleep"),
        ):
            _ghi_va_xoa_cache(str(target), b"ban-moi")

        assert calls == 2
        assert target.read_bytes() == b"ban-moi"

    def test_replace_that_bai_khong_lam_hong_file_cu(self, tmp_path):
        target = tmp_path / "dienbao.xlsx"
        target.write_bytes(b"ban-cu")

        with (
            patch.object(
                upload_service.os,
                "replace",
                side_effect=OSError(22, "Invalid argument", str(target)),
            ),
            patch.object(upload_service.time, "sleep"),
            pytest.raises(OSError),
        ):
            _ghi_va_xoa_cache(str(target), b"ban-moi")

        assert target.read_bytes() == b"ban-cu"
        assert not list(tmp_path.glob(".dienbao.xlsx.*.tmp"))


# ══════════════════════════════════════════════════════════════════════════════
# TEST KetQuaUpload
# ══════════════════════════════════════════════════════════════════════════════
class TestKetQuaUpload:
    def test_thanh_cong_true(self):
        kq = KetQuaUpload(True, "OK", "/path/file.xlsx")
        assert kq.thanh_cong is True
        assert kq.thong_bao == "OK"
        assert kq.duong_dan == "/path/file.xlsx"

    def test_that_bai(self):
        kq = KetQuaUpload(False, "Lỗi upload")
        assert kq.thanh_cong is False
        assert kq.duong_dan == ""

    def test_hien_thi_thanh_cong(self):
        """hien_thi() gọi st.success khi thanh_cong=True."""
        kq = KetQuaUpload(True, "Upload OK")
        with patch("streamlit.success") as mock_success:
            kq.hien_thi()
            mock_success.assert_called_once_with("Upload OK")

    def test_hien_thi_that_bai(self):
        """hien_thi() gọi st.error khi thanh_cong=False."""
        kq = KetQuaUpload(False, "Upload lỗi")
        with patch("streamlit.error") as mock_error:
            kq.hien_thi()
            mock_error.assert_called_once_with("Upload lỗi")


# ══════════════════════════════════════════════════════════════════════════════
# TEST kiem_tra_file
# ══════════════════════════════════════════════════════════════════════════════
class TestKiemTraFile:
    def test_file_hop_le(self):
        ok, msg = kiem_tra_file("HSTD_BienHoa.xlsx", _excel_bytes_hop_le())
        assert ok is True
        assert msg == "OK"

    def test_dinh_dang_sai(self):
        ok, msg = kiem_tra_file("bao_cao.pdf", b"\x00" * 5000)
        assert ok is False
        assert "không được hỗ trợ" in msg.lower() or "pdf" in msg.lower()

    def test_file_qua_nho(self):
        ok, msg = kiem_tra_file("HSTD.xlsx", b"\x00" * 100)
        assert ok is False
        assert "nhỏ" in msg.lower() or "kb" in msg.lower()

    def test_extension_xls_hop_le(self):
        ok, msg = kiem_tra_file("data.xls", _excel_bytes_hop_le())
        assert ok is True

    def test_ten_file_khong_co_extension(self):
        ok, msg = kiem_tra_file("HSTD", _excel_bytes_hop_le())
        assert ok is False

    def test_custom_exts_chophep(self):
        """Cho phép .csv nếu truyền exts_chophep tùy chỉnh."""
        ok, msg = kiem_tra_file(
            "data.csv",
            b"col1,col2\n" + b"a,b\n" * 250,
            exts_chophep={".csv"},
        )
        assert ok is True


# ══════════════════════════════════════════════════════════════════════════════
# TEST kiem_tra_file_he_thong
# ══════════════════════════════════════════════════════════════════════════════
class TestKiemTraFileHeThong:
    """
    FILES_HE_THONG là dict tên file → config trong upload_service.
    Test dùng patch để không phụ thuộc giá trị thực tế.
    """

    def _patch_files(self, ten_file_hop_le: str):
        try:
            import services.upload_service as svc
        except ImportError:
            import upload_service as svc
        return patch.object(
            svc, "FILES_HE_THONG", {ten_file_hop_le: {}}
        )

    def test_ten_file_hop_le(self):
        ten = "HSTD_CN.xlsx"
        with self._patch_files(ten):
            ok, msg = kiem_tra_file_he_thong(ten, _excel_bytes_hop_le())
        assert ok is True

    def test_ten_file_sai(self):
        with self._patch_files("HSTD_DUNG.xlsx"):
            ok, msg = kiem_tra_file_he_thong(
                "file_sai_ten.xlsx", _excel_bytes_hop_le()
            )
        assert ok is False
        assert "không hợp lệ" in msg.lower() or "tên" in msg.lower()

    def test_dinh_dang_sai_uu_tien_truoc(self):
        """Lỗi định dạng phải được trả về trước lỗi tên file."""
        with self._patch_files("HSTD_CN.xlsx"):
            ok, msg = kiem_tra_file_he_thong("wrong.pdf", b"\x00" * 5000)
        assert ok is False
        assert "pdf" in msg.lower() or "không được hỗ trợ" in msg.lower()


# ── trich_xuat_ky_dienbao ────────────────────────────────────────────────────

class TestTrichXuatKyDienbao:
    def test_dau_cham(self):
        from services.upload_service import trich_xuat_ky_dienbao
        assert trich_xuat_ky_dienbao("Dien bao 31.07.2026.xlsx") == "31/07/2026"

    def test_dau_gach(self):
        from services.upload_service import trich_xuat_ky_dienbao
        assert trich_xuat_ky_dienbao("DB_31-12-2025.xlsx") == "31/12/2025"

    def test_dau_underscore(self):
        from services.upload_service import trich_xuat_ky_dienbao
        assert trich_xuat_ky_dienbao("file_01_08_2026.xlsx") == "01/08/2026"

    def test_dang_lien(self):
        from services.upload_service import trich_xuat_ky_dienbao
        assert trich_xuat_ky_dienbao("report_31072026.xlsx") == "31/07/2026"

    def test_khong_co_ngay(self):
        from services.upload_service import trich_xuat_ky_dienbao
        assert trich_xuat_ky_dienbao("dienbao.xlsx") is None

    def test_ten_rong(self):
        from services.upload_service import trich_xuat_ky_dienbao
        assert trich_xuat_ky_dienbao("") is None
        assert trich_xuat_ky_dienbao(None) is None

    def test_ngay_khong_hop_le(self):
        from services.upload_service import trich_xuat_ky_dienbao
        assert trich_xuat_ky_dienbao("file_99.99.2026.xlsx") is None


class TestLuuDienbao:
    def test_ghi_metadata_co_audit_ngay_sau_ghi_kv(self):
        events = []

        def fake_ghi_kv(key, value, username):
            events.append(("kv", key, username))

        def fake_ghi_audit(username, action, detail):
            events.append(("audit", action, detail))

        with (
            patch.object(upload_service, "_ghi_va_xoa_cache"),
            patch.object(upload_service.db, "ghi_kv", side_effect=fake_ghi_kv),
            patch.object(upload_service.db, "ghi_audit", side_effect=fake_ghi_audit),
            patch.object(upload_service.st, "session_state", {"username": "tester"}),
        ):
            kq = upload_service.luu_dienbao(
                "prev_month",
                _excel_bytes_hop_le(),
                "Dien bao 31.07.2026.xlsx",
            )

        assert kq.thanh_cong is True
        kv_index = next(i for i, event in enumerate(events) if event[0] == "kv")
        assert events[kv_index][1] == "dienbao_meta_prev_month"
        assert events[kv_index + 1][0] == "audit"
        assert events[kv_index + 1][1] == "dienbao_meta"
