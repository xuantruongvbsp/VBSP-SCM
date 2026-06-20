"""
tests/test_merge_du_lieu_toan_cn.py
────────────────────────────────────
Unit test cho merge_du_lieu_toan_cn() trong services/upload_service.py.

Chiến lược mock:
  - Không cần file Excel thật, không cần DB thật, không cần Streamlit
  - Mock hoàn toàn: duong_dan_pgd, excel_to_parquet, st.progress,
    st.session_state, db.ghi_audit, db.ghi_kv
  - Dùng tmp_path (pytest fixture) cho thư mục parquet tạm

Cấu trúc test:
  TestMergeLoaiKhongHoTro   — loai không hợp lệ → lỗi ngay
  TestMergeKhongCoFile      — không PGD nào có file → lỗi ngay
  TestMergeMotPGD           — merge 1 PGD thành công, kiểm tra parquet output
  TestMergeNhieuPGD         — nhiều PGD, kiểm tra concat + cột COT_TEN_PGD
  TestMergePGDLoi           — 1 PGD lỗi đọc file → bỏ qua, merge phần còn lại
  TestMergePGDCu            — PGD có file cũ quá ngưỡng → thêm vào pgd_cu
  TestMergeSchemaNormalize  — cột thiếu / null dtype → được fill và chuẩn hóa
  TestMergeRollback         — lỗi khi ghi parquet → rollback từ .bak
  TestMergeMetaGhiVaoKV     — metadata merge được ghi vào kv_store đúng key
  TestMergeAuditLog         — ghi_audit được gọi sau merge thành công
  TestMergeGQVL             — loai="gqvl" dùng GQVL_COT_MAP và Sheet1

Chạy:
  pytest tests/test_merge_du_lieu_toan_cn.py -v
"""
from __future__ import annotations

import io
import os
import threading
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, call, patch

import pandas as pd
import pytest

# ── Import module ─────────────────────────────────────────────────────────────
try:
    import services.upload_service as svc
    from services.upload_service import merge_du_lieu_toan_cn, KetQuaUpload
except ImportError:
    import upload_service as svc
    from upload_service import merge_du_lieu_toan_cn, KetQuaUpload


# ── Helpers / Fixtures ────────────────────────────────────────────────────────

def _df_hstd_mau(ten_pgd: str = "PGD Test", so_dong: int = 3) -> pd.DataFrame:
    """DataFrame HSTD mẫu đủ các cột số quan trọng."""
    return pd.DataFrame({
        "Mã KH":           [f"KH{i:03d}" for i in range(so_dong)],
        "Tên KH":          [f"Nguyễn Văn {chr(65+i)}" for i in range(so_dong)],
        "Dư nợ trong hạn": [1_000_000 * (i + 1) for i in range(so_dong)],
        "Dư nợ quá hạn":   [0] * so_dong,
        "Tổng dư nợ":      [1_000_000 * (i + 1) for i in range(so_dong)],
        "Tên PGD":         [ten_pgd] * so_dong,
    })


def _df_gqvl_mau(ten_pgd: str = "PGD Test") -> pd.DataFrame:
    """DataFrame GQVL mẫu sau khi đã rename cột."""
    return pd.DataFrame({
        "Mã KH":          ["KH001", "KH002"],
        "Dư nợ trong hạn": [500_000, 700_000],
        "Nguồn vốn":      ["TW", "ĐP"],
        "Tên PGD":        [ten_pgd, ten_pgd],
    })


@pytest.fixture(autouse=True)
def mock_telegram_service():
    """Block mọi HTTP call tới Telegram trong toàn bộ test file này.

    Nếu không mock, merge thành công sẽ gọi gui_thong_bao_merge() → requests.post()
    → SSL handshake thật → access violation ở C-level trong Python 3.14 trên Windows,
    không thể catch bằng try/except Python thông thường.
    """
    with patch("services.telegram_service.gui_thong_bao_merge", return_value=True):
        yield


@pytest.fixture
def mock_streamlit():
    """Mock toàn bộ Streamlit — không cần chạy trong browser."""
    prog_mock = MagicMock()
    with patch.object(svc.st, "progress", return_value=prog_mock), \
         patch.object(svc.st, "session_state", {"username": "test_user"}):
        yield prog_mock


@pytest.fixture
def mock_db():
    """Mock db.ghi_audit và db.ghi_kv."""
    with patch.object(svc.db, "ghi_audit") as mock_audit, \
         patch.object(svc.db, "ghi_kv") as mock_kv:
        yield mock_audit, mock_kv


@pytest.fixture
def duong_dan_pgd_factory(tmp_path):
    """
    Factory: tạo file Excel giả tại tmp_path/{slug}_{loai}_latest.xlsx
    và trả về patch cho duong_dan_pgd.
    """
    def _factory(ten_pgd_list: list[str], loai: str, tao_file: bool = True):
        duong_dan_map: dict[str, str] = {}
        for ten in ten_pgd_list:
            slug = ten.lower().replace(" ", "_")
            duong_dan = str(tmp_path / f"{slug}_{loai}_latest.xlsx")
            if tao_file:
                # Ghi file giả — nội dung không quan trọng vì excel_to_parquet được mock
                Path(duong_dan).write_bytes(b"PK\x03\x04" + b"\x00" * 2000)
            duong_dan_map[ten] = duong_dan

        def _fake_duong_dan(ten_pgd: str, _loai: str) -> str:
            return duong_dan_map.get(ten_pgd, str(tmp_path / f"missing_{ten_pgd}.xlsx"))

        return _fake_duong_dan
    return _factory


# ══════════════════════════════════════════════════════════════════════════════
# 1. LOAI KHÔNG HỖ TRỢ
# ══════════════════════════════════════════════════════════════════════════════

class TestMergeLoaiKhongHoTro:
    def test_cdtotkvv_bi_tu_choi(self):
        kq = merge_du_lieu_toan_cn("cdtotkvv")
        assert kq.thanh_cong is False
        assert "cdtotkvv" in kq.thong_bao.lower()

    def test_ten_loai_rac_bi_tu_choi(self):
        kq = merge_du_lieu_toan_cn("dienbao")
        assert kq.thanh_cong is False

    def test_loai_trong_bi_tu_choi(self):
        kq = merge_du_lieu_toan_cn("")
        assert kq.thanh_cong is False


# ══════════════════════════════════════════════════════════════════════════════
# 2. KHÔNG CÓ FILE NÀO
# ══════════════════════════════════════════════════════════════════════════════

class TestMergeKhongCoFile:
    def test_khong_pgd_nao_co_file(self, tmp_path, mock_streamlit, mock_db):
        """Tất cả PGD thiếu file → KetQuaUpload(False)."""
        def _duong_dan_miss(ten_pgd, loai):
            return str(tmp_path / f"missing_{ten_pgd}.xlsx")  # không tồn tại

        with patch.object(svc, "duong_dan_pgd", side_effect=_duong_dan_miss), \
             patch.object(svc, "DS_PGD", ["PGD A", "PGD B"]), \
             patch.object(svc, "DON_VI_CHI_NHANH", "Hội sở"), \
             patch.object(svc, "UPLOAD_CANH_BAO_NGAY", {"hstd": 3}):
            kq = merge_du_lieu_toan_cn("hstd")

        assert kq.thanh_cong is False
        assert "không có" in kq.thong_bao.lower() or "hstd" in kq.thong_bao.upper()

    def test_ds_pgd_rong(self, mock_streamlit, mock_db):
        """ds_pgd=[] → không có gì để merge → KetQuaUpload(False)."""
        with patch.object(svc, "UPLOAD_CANH_BAO_NGAY", {"hstd": 3}):
            kq = merge_du_lieu_toan_cn("hstd", ds_pgd=[])
        assert kq.thanh_cong is False


# ══════════════════════════════════════════════════════════════════════════════
# 3. MERGE 1 PGD THÀNH CÔNG
# ══════════════════════════════════════════════════════════════════════════════

class TestMergeMotPGD:
    def test_thanh_cong_ghi_parquet(
        self, tmp_path, mock_streamlit, mock_db, duong_dan_pgd_factory
    ):
        """
        1 PGD có file → merge thành công → parquet được ghi ra đĩa.
        """
        ten_pgd = "PGD Biên Hòa"
        df_mau = _df_hstd_mau(ten_pgd)
        fake_duong_dan = duong_dan_pgd_factory([ten_pgd], "hstd")
        cache_path = str(tmp_path / "hstd.parquet")

        with patch.object(svc, "duong_dan_pgd", side_effect=fake_duong_dan), \
             patch.object(svc, "DS_PGD", [ten_pgd]), \
             patch.object(svc, "DON_VI_CHI_NHANH", "Hội sở"), \
             patch.object(svc, "CACHE_HSTD", cache_path), \
             patch.object(svc, "UPLOAD_CANH_BAO_NGAY", {"hstd": 3}), \
             patch.object(svc, "excel_to_parquet", return_value=df_mau), \
             patch.object(svc, "kiem_tra_chat_luong", return_value=MagicMock(
                 df=df_mau, report={"so_loi": 0, "tong_dong": len(df_mau)}
             )):
            kq = merge_du_lieu_toan_cn("hstd", ds_pgd=[ten_pgd])

        assert kq.thanh_cong is True
        assert Path(cache_path).exists(), "File parquet phải được ghi ra đĩa"

    def test_ket_qua_chua_ten_don_vi_va_so_dong(
        self, tmp_path, mock_streamlit, mock_db, duong_dan_pgd_factory
    ):
        """Thông báo kết quả phải chứa số đơn vị và số dòng."""
        ten_pgd = "PGD Long Khánh"
        df_mau = _df_hstd_mau(ten_pgd, so_dong=5)
        fake_duong_dan = duong_dan_pgd_factory([ten_pgd], "hstd")
        cache_path = str(tmp_path / "hstd.parquet")

        with patch.object(svc, "duong_dan_pgd", side_effect=fake_duong_dan), \
             patch.object(svc, "DS_PGD", [ten_pgd]), \
             patch.object(svc, "DON_VI_CHI_NHANH", "Hội sở"), \
             patch.object(svc, "CACHE_HSTD", cache_path), \
             patch.object(svc, "UPLOAD_CANH_BAO_NGAY", {"hstd": 3}), \
             patch.object(svc, "excel_to_parquet", return_value=df_mau), \
             patch.object(svc, "kiem_tra_chat_luong", return_value=MagicMock(
                 df=df_mau, report={"so_loi": 0, "tong_dong": 5}
             )):
            kq = merge_du_lieu_toan_cn("hstd", ds_pgd=[ten_pgd])

        assert "1" in kq.thong_bao   # 1 đơn vị
        assert "5" in kq.thong_bao   # 5 dòng

    def test_duong_dan_tra_ve_la_cache_path(
        self, tmp_path, mock_streamlit, mock_db, duong_dan_pgd_factory
    ):
        """KetQuaUpload.duong_dan phải là đường dẫn parquet cache."""
        ten_pgd = "PGD Trảng Bom"
        df_mau = _df_hstd_mau(ten_pgd)
        fake_duong_dan = duong_dan_pgd_factory([ten_pgd], "hstd")
        cache_path = str(tmp_path / "hstd.parquet")

        with patch.object(svc, "duong_dan_pgd", side_effect=fake_duong_dan), \
             patch.object(svc, "DS_PGD", [ten_pgd]), \
             patch.object(svc, "DON_VI_CHI_NHANH", "Hội sở"), \
             patch.object(svc, "CACHE_HSTD", cache_path), \
             patch.object(svc, "UPLOAD_CANH_BAO_NGAY", {"hstd": 3}), \
             patch.object(svc, "excel_to_parquet", return_value=df_mau), \
             patch.object(svc, "kiem_tra_chat_luong", return_value=MagicMock(
                 df=df_mau, report={"so_loi": 0, "tong_dong": len(df_mau)}
             )):
            kq = merge_du_lieu_toan_cn("hstd", ds_pgd=[ten_pgd])

        assert kq.duong_dan == cache_path


# ══════════════════════════════════════════════════════════════════════════════
# 4. MERGE NHIỀU PGD — CONCAT VÀ CỘT TEN_PGD
# ══════════════════════════════════════════════════════════════════════════════

class TestMergeNhieuPGD:
    def test_concat_nhieu_pgd_dung_so_dong(
        self, tmp_path, mock_streamlit, mock_db, duong_dan_pgd_factory
    ):
        """
        3 PGD × 3 dòng mỗi PGD → parquet output phải có 9 dòng.
        """
        ten_pgd_list = ["PGD A", "PGD B", "PGD C"]
        dfs = {t: _df_hstd_mau(t, so_dong=3) for t in ten_pgd_list}
        fake_duong_dan = duong_dan_pgd_factory(ten_pgd_list, "hstd")
        cache_path = str(tmp_path / "hstd.parquet")

        def _fake_excel_to_parquet(path_excel, path_pq, sheet, header, post_fn=None):
            # Tìm tên PGD từ đường dẫn file
            for t in ten_pgd_list:
                slug = t.lower().replace(" ", "_")
                if slug in path_excel:
                    return dfs[t]
            return dfs[ten_pgd_list[0]]

        with patch.object(svc, "duong_dan_pgd", side_effect=fake_duong_dan), \
             patch.object(svc, "DS_PGD", ten_pgd_list), \
             patch.object(svc, "DON_VI_CHI_NHANH", "Hội sở"), \
             patch.object(svc, "CACHE_HSTD", cache_path), \
             patch.object(svc, "UPLOAD_CANH_BAO_NGAY", {"hstd": 3}), \
             patch.object(svc, "excel_to_parquet", side_effect=_fake_excel_to_parquet), \
             patch.object(svc, "kiem_tra_chat_luong", return_value=MagicMock(
                 df=dfs[ten_pgd_list[0]], report={"so_loi": 0, "tong_dong": 3}
             )):
            kq = merge_du_lieu_toan_cn("hstd", ds_pgd=ten_pgd_list)

        assert kq.thanh_cong is True
        df_out = pd.read_parquet(cache_path)
        assert len(df_out) == 9

    def test_cot_ten_pgd_duoc_gan_dung(
        self, tmp_path, mock_streamlit, mock_db, duong_dan_pgd_factory
    ):
        """
        Giá trị cột 'Tên PGD' trong parquet phải khớp với từng đơn vị.
        """
        ten_pgd_list = ["PGD Xuân Lộc", "PGD Cẩm Mỹ"]
        dfs = {t: _df_hstd_mau(t, so_dong=2) for t in ten_pgd_list}
        fake_duong_dan = duong_dan_pgd_factory(ten_pgd_list, "hstd")
        cache_path = str(tmp_path / "hstd.parquet")

        def _fake_excel_to_parquet(path_excel, path_pq, sheet, header, post_fn=None):
            for t in ten_pgd_list:
                slug = t.lower().replace(" ", "_")
                if slug in path_excel:
                    return dfs[t]
            return dfs[ten_pgd_list[0]]

        with patch.object(svc, "duong_dan_pgd", side_effect=fake_duong_dan), \
             patch.object(svc, "DS_PGD", ten_pgd_list), \
             patch.object(svc, "DON_VI_CHI_NHANH", "Hội sở"), \
             patch.object(svc, "CACHE_HSTD", cache_path), \
             patch.object(svc, "UPLOAD_CANH_BAO_NGAY", {"hstd": 3}), \
             patch.object(svc, "excel_to_parquet", side_effect=_fake_excel_to_parquet), \
             patch.object(svc, "kiem_tra_chat_luong", return_value=MagicMock(
                 df=dfs[ten_pgd_list[0]], report={"so_loi": 0, "tong_dong": 2}
             )):
            merge_du_lieu_toan_cn("hstd", ds_pgd=ten_pgd_list)

        df_out = pd.read_parquet(cache_path)
        assert set(df_out["Tên PGD"].unique()) == set(ten_pgd_list)


# ══════════════════════════════════════════════════════════════════════════════
# 5. PGD LỖI ĐỌC FILE — BỎ QUA, MERGE PHẦN CÒN LẠI
# ══════════════════════════════════════════════════════════════════════════════

class TestMergePGDLoi:
    def test_1_loi_1_ok_van_thanh_cong(
        self, tmp_path, mock_streamlit, mock_db, duong_dan_pgd_factory
    ):
        """
        PGD A lỗi đọc file → PGD B vẫn merge → kq.thanh_cong=True.
        Thông báo phải nhắc đến '1 đơn vị lỗi'.
        """
        ten_ok = "PGD Biên Hòa"
        ten_loi = "PGD Long Khánh"
        df_ok = _df_hstd_mau(ten_ok)
        fake_duong_dan = duong_dan_pgd_factory([ten_ok, ten_loi], "hstd")
        cache_path = str(tmp_path / "hstd.parquet")

        slug_loi = ten_loi.lower().replace(" ", "_")

        def _fake_excel_to_parquet(path_excel, path_pq, sheet, header, post_fn=None):
            if slug_loi in path_excel:
                raise ValueError("Lỗi đọc file giả lập")
            return df_ok

        with patch.object(svc, "duong_dan_pgd", side_effect=fake_duong_dan), \
             patch.object(svc, "DS_PGD", [ten_ok, ten_loi]), \
             patch.object(svc, "DON_VI_CHI_NHANH", "Hội sở"), \
             patch.object(svc, "CACHE_HSTD", cache_path), \
             patch.object(svc, "UPLOAD_CANH_BAO_NGAY", {"hstd": 3}), \
             patch.object(svc, "excel_to_parquet", side_effect=_fake_excel_to_parquet), \
             patch.object(svc, "kiem_tra_chat_luong", return_value=MagicMock(
                 df=df_ok, report={"so_loi": 0, "tong_dong": len(df_ok)}
             )):
            kq = merge_du_lieu_toan_cn("hstd", ds_pgd=[ten_ok, ten_loi])

        assert kq.thanh_cong is True
        assert "lỗi" in kq.thong_bao.lower() or "⚠️" in kq.thong_bao

    def test_tat_ca_loi_tra_ve_that_bai(
        self, tmp_path, mock_streamlit, mock_db, duong_dan_pgd_factory
    ):
        """Tất cả PGD đều lỗi → KetQuaUpload(False)."""
        ten_pgd_list = ["PGD A", "PGD B"]
        fake_duong_dan = duong_dan_pgd_factory(ten_pgd_list, "hstd")

        with patch.object(svc, "duong_dan_pgd", side_effect=fake_duong_dan), \
             patch.object(svc, "DS_PGD", ten_pgd_list), \
             patch.object(svc, "DON_VI_CHI_NHANH", "Hội sở"), \
             patch.object(svc, "UPLOAD_CANH_BAO_NGAY", {"hstd": 3}), \
             patch.object(svc, "excel_to_parquet",
                          side_effect=Exception("Lỗi tất cả")):
            kq = merge_du_lieu_toan_cn("hstd", ds_pgd=ten_pgd_list)

        assert kq.thanh_cong is False

    def test_audit_log_ghi_pgd_loi(
        self, tmp_path, mock_streamlit, mock_db, duong_dan_pgd_factory
    ):
        """
        Khi PGD lỗi → db.ghi_audit phải được gọi với action='merge_toan_cn_pgd_loi'.
        """
        mock_audit, _ = mock_db
        ten_ok = "PGD Vĩnh Cửu"
        ten_loi = "PGD Nhơn Trạch"
        df_ok = _df_hstd_mau(ten_ok)
        fake_duong_dan = duong_dan_pgd_factory([ten_ok, ten_loi], "hstd")
        cache_path = str(tmp_path / "hstd.parquet")
        slug_loi = ten_loi.lower().replace(" ", "_")

        def _fake_excel_to_parquet(path_excel, path_pq, sheet, header, post_fn=None):
            if slug_loi in path_excel:
                raise RuntimeError("test error")
            return df_ok

        with patch.object(svc, "duong_dan_pgd", side_effect=fake_duong_dan), \
             patch.object(svc, "DS_PGD", [ten_ok, ten_loi]), \
             patch.object(svc, "DON_VI_CHI_NHANH", "Hội sở"), \
             patch.object(svc, "CACHE_HSTD", cache_path), \
             patch.object(svc, "UPLOAD_CANH_BAO_NGAY", {"hstd": 3}), \
             patch.object(svc, "excel_to_parquet", side_effect=_fake_excel_to_parquet), \
             patch.object(svc, "kiem_tra_chat_luong", return_value=MagicMock(
                 df=df_ok, report={"so_loi": 0, "tong_dong": len(df_ok)}
             )):
            merge_du_lieu_toan_cn("hstd", ds_pgd=[ten_ok, ten_loi])

        # Tìm call audit log cho PGD lỗi
        loi_calls = [
            c for c in mock_audit.call_args_list
            if "merge_toan_cn_pgd_loi" in str(c)
        ]
        assert len(loi_calls) >= 1


# ══════════════════════════════════════════════════════════════════════════════
# 6. PGD SỐ LIỆU CŨ QUÁ NGƯỠNG
# ══════════════════════════════════════════════════════════════════════════════

class TestMergePGDCu:
    def test_pgd_cu_duoc_them_vao_meta(
        self, tmp_path, mock_streamlit, mock_db, duong_dan_pgd_factory
    ):
        """
        File cũ hơn nguong_ngay → pgd_cu trong metadata phải chứa tên đó.
        """
        _, mock_kv = mock_db
        ten_pgd = "PGD Tân Phú"
        df_mau = _df_hstd_mau(ten_pgd)
        fake_duong_dan = duong_dan_pgd_factory([ten_pgd], "hstd")
        excel_path = fake_duong_dan(ten_pgd, "hstd")
        cache_path = str(tmp_path / "hstd.parquet")

        # Đặt ngày sửa file là 10 ngày trước (vượt ngưỡng 3 ngày)
        ten_ngay_truoc = time.time() - 10 * 24 * 3600
        os.utime(excel_path, (ten_ngay_truoc, ten_ngay_truoc))

        with patch.object(svc, "duong_dan_pgd", side_effect=fake_duong_dan), \
             patch.object(svc, "DS_PGD", [ten_pgd]), \
             patch.object(svc, "DON_VI_CHI_NHANH", "Hội sở"), \
             patch.object(svc, "CACHE_HSTD", cache_path), \
             patch.object(svc, "UPLOAD_CANH_BAO_NGAY", {"hstd": 3}), \
             patch.object(svc, "excel_to_parquet", return_value=df_mau), \
             patch.object(svc, "kiem_tra_chat_luong", return_value=MagicMock(
                 df=df_mau, report={"so_loi": 0, "tong_dong": len(df_mau)}
             )):
            merge_du_lieu_toan_cn("hstd", ds_pgd=[ten_pgd])

        # Kiểm tra meta được ghi vào kv_store có pgd_cu chứa tên PGD
        kv_calls = [
            c for c in mock_kv.call_args_list
            if "merge_meta_hstd" in str(c)
        ]
        assert kv_calls, "merge_meta_hstd phải được ghi vào kv_store"
        meta_value = kv_calls[0].args[1]  # argument thứ 2 là value
        assert ten_pgd in meta_value.get("pgd_cu", [])


# ══════════════════════════════════════════════════════════════════════════════
# 7. SCHEMA NORMALIZE — CỘT THIẾU VÀ NULL DTYPE
# ══════════════════════════════════════════════════════════════════════════════

class TestMergeSchemaNormalize:
    def test_pgd_thieu_cot_duoc_fill_na(
        self, tmp_path, mock_streamlit, mock_db, duong_dan_pgd_factory
    ):
        """
        PGD A có cột 'Lãi tồn TH', PGD B không có → parquet output phải có cột đó,
        PGD B có giá trị rỗng/NA ở cột đó.
        """
        ten_a = "PGD A"
        ten_b = "PGD B"
        df_a = _df_hstd_mau(ten_a)
        df_a["Lãi tồn TH"] = [100_000, 200_000, 300_000]

        df_b = _df_hstd_mau(ten_b)
        # df_b KHÔNG có cột 'Lãi tồn TH'

        fake_duong_dan = duong_dan_pgd_factory([ten_a, ten_b], "hstd")
        cache_path = str(tmp_path / "hstd.parquet")

        def _fake_excel_to_parquet(path_excel, path_pq, sheet, header, post_fn=None):
            if "pgd_a" in path_excel:
                return df_a
            return df_b

        with patch.object(svc, "duong_dan_pgd", side_effect=fake_duong_dan), \
             patch.object(svc, "DS_PGD", [ten_a, ten_b]), \
             patch.object(svc, "DON_VI_CHI_NHANH", "Hội sở"), \
             patch.object(svc, "CACHE_HSTD", cache_path), \
             patch.object(svc, "UPLOAD_CANH_BAO_NGAY", {"hstd": 3}), \
             patch.object(svc, "excel_to_parquet", side_effect=_fake_excel_to_parquet), \
             patch.object(svc, "kiem_tra_chat_luong", return_value=MagicMock(
                 df=df_a, report={"so_loi": 0, "tong_dong": len(df_a)}
             )):
            merge_du_lieu_toan_cn("hstd", ds_pgd=[ten_a, ten_b])

        df_out = pd.read_parquet(cache_path)
        assert "Lãi tồn TH" in df_out.columns, "Cột thiếu phải được fill vào output"

    def test_cot_so_duoc_ep_kieu_numeric(
        self, tmp_path, mock_streamlit, mock_db, duong_dan_pgd_factory
    ):
        """
        Cột số như 'Tổng dư nợ' dù đến từ text vẫn phải là numeric sau merge.
        """
        ten_pgd = "PGD Test Numeric"
        df = _df_hstd_mau(ten_pgd)
        # Giả lập cột số bị lưu dạng string
        df["Tổng dư nợ"] = df["Tổng dư nợ"].astype(str)

        fake_duong_dan = duong_dan_pgd_factory([ten_pgd], "hstd")
        cache_path = str(tmp_path / "hstd.parquet")

        with patch.object(svc, "duong_dan_pgd", side_effect=fake_duong_dan), \
             patch.object(svc, "DS_PGD", [ten_pgd]), \
             patch.object(svc, "DON_VI_CHI_NHANH", "Hội sở"), \
             patch.object(svc, "CACHE_HSTD", cache_path), \
             patch.object(svc, "UPLOAD_CANH_BAO_NGAY", {"hstd": 3}), \
             patch.object(svc, "excel_to_parquet", return_value=df), \
             patch.object(svc, "kiem_tra_chat_luong", return_value=MagicMock(
                 df=df, report={"so_loi": 0, "tong_dong": len(df)}
             )):
            merge_du_lieu_toan_cn("hstd", ds_pgd=[ten_pgd])

        df_out = pd.read_parquet(cache_path)
        assert pd.api.types.is_numeric_dtype(df_out["Tổng dư nợ"]), \
            "Cột 'Tổng dư nợ' phải là numeric sau merge"

    def test_nguon_von_khong_bi_ep_numeric(
        self, tmp_path, mock_streamlit, mock_db, duong_dan_pgd_factory
    ):
        """
        Cột 'Nguồn vốn' chứa 'TW'/'ĐP' → KHÔNG được ép thành NaN sau merge.
        Đây là bug đã từng xảy ra — regression test.
        """
        ten_pgd = "PGD Regression"
        df = _df_hstd_mau(ten_pgd)
        df["Nguồn vốn"] = ["TW", "ĐP", "TW"]

        fake_duong_dan = duong_dan_pgd_factory([ten_pgd], "hstd")
        cache_path = str(tmp_path / "hstd.parquet")

        with patch.object(svc, "duong_dan_pgd", side_effect=fake_duong_dan), \
             patch.object(svc, "DS_PGD", [ten_pgd]), \
             patch.object(svc, "DON_VI_CHI_NHANH", "Hội sở"), \
             patch.object(svc, "CACHE_HSTD", cache_path), \
             patch.object(svc, "UPLOAD_CANH_BAO_NGAY", {"hstd": 3}), \
             patch.object(svc, "excel_to_parquet", return_value=df), \
             patch.object(svc, "kiem_tra_chat_luong", return_value=MagicMock(
                 df=df, report={"so_loi": 0, "tong_dong": len(df)}
             )):
            merge_du_lieu_toan_cn("hstd", ds_pgd=[ten_pgd])

        df_out = pd.read_parquet(cache_path)
        assert "Nguồn vốn" in df_out.columns
        vals = df_out["Nguồn vốn"].dropna().unique().tolist()
        assert any(v in ("TW", "ĐP") for v in vals), \
            "Cột 'Nguồn vốn' không được bị ép sang NaN"


# ══════════════════════════════════════════════════════════════════════════════
# 8. ROLLBACK KHI GHI PARQUET LỖI
# ══════════════════════════════════════════════════════════════════════════════

class TestMergeRollback:
    def test_file_bak_duoc_khoi_phuc_khi_to_parquet_loi(
        self, tmp_path, mock_streamlit, mock_db, duong_dan_pgd_factory
    ):
        """
        Nếu to_parquet() ném exception → file .bak phải được restore về cache_path.
        """
        ten_pgd = "PGD Rollback Test"
        df_mau = _df_hstd_mau(ten_pgd)
        fake_duong_dan = duong_dan_pgd_factory([ten_pgd], "hstd")
        cache_path = str(tmp_path / "hstd.parquet")
        bak_path = cache_path + ".bak"

        # Tạo file backup giả để simulate trạng thái có .bak
        bak_content = b"backup_parquet_content"
        Path(cache_path).write_bytes(bak_content)  # file cũ

        write_call_count = {"n": 0}

        def _fake_to_parquet(self_or_path, path_or_none=None, **kwargs):
            write_call_count["n"] += 1
            raise OSError("Disk full simulation")

        with patch.object(svc, "duong_dan_pgd", side_effect=fake_duong_dan), \
             patch.object(svc, "DS_PGD", [ten_pgd]), \
             patch.object(svc, "DON_VI_CHI_NHANH", "Hội sở"), \
             patch.object(svc, "CACHE_HSTD", cache_path), \
             patch.object(svc, "UPLOAD_CANH_BAO_NGAY", {"hstd": 3}), \
             patch.object(svc, "excel_to_parquet", return_value=df_mau), \
             patch.object(svc, "kiem_tra_chat_luong", return_value=MagicMock(
                 df=df_mau, report={"so_loi": 0, "tong_dong": len(df_mau)}
             )), \
             patch.object(pd.DataFrame, "to_parquet", _fake_to_parquet):
            with pytest.raises(OSError):
                merge_du_lieu_toan_cn("hstd", ds_pgd=[ten_pgd])

        # File gốc phải được khôi phục từ .bak
        assert Path(cache_path).exists(), "File cache phải được restore từ .bak"
        assert Path(cache_path).read_bytes() == bak_content, \
            "Nội dung file restore phải bằng nội dung .bak"


# ══════════════════════════════════════════════════════════════════════════════
# 9. METADATA ĐƯỢC GHI VÀO KV_STORE
# ══════════════════════════════════════════════════════════════════════════════

class TestMergeMetaGhiVaoKV:
    def _run_merge(self, tmp_path, mock_db, duong_dan_pgd_factory, loai="hstd"):
        ten_pgd = "PGD Meta Test"
        df_mau = _df_hstd_mau(ten_pgd)
        fake_duong_dan = duong_dan_pgd_factory([ten_pgd], loai)
        cache_key = {"hstd": "CACHE_HSTD", "nq11": "CACHE_NQ11", "gqvl": "CACHE_GQVL"}
        cache_path = str(tmp_path / f"{loai}.parquet")

        prog_mock = MagicMock()
        with patch.object(svc.st, "progress", return_value=prog_mock), \
             patch.object(svc.st, "session_state", {"username": "test_user"}), \
             patch.object(svc, "duong_dan_pgd", side_effect=fake_duong_dan), \
             patch.object(svc, "DS_PGD", [ten_pgd]), \
             patch.object(svc, "DON_VI_CHI_NHANH", "Hội sở"), \
             patch.object(svc, cache_key[loai], cache_path), \
             patch.object(svc, "UPLOAD_CANH_BAO_NGAY", {loai: 3}), \
             patch.object(svc, "excel_to_parquet", return_value=df_mau), \
             patch.object(svc, "kiem_tra_chat_luong", return_value=MagicMock(
                 df=df_mau, report={"so_loi": 0, "tong_dong": len(df_mau)}
             )):
            return merge_du_lieu_toan_cn(loai, ds_pgd=[ten_pgd])

    def test_meta_key_dung_loai(
        self, tmp_path, mock_streamlit, mock_db, duong_dan_pgd_factory
    ):
        """ghi_kv phải được gọi với key 'merge_meta_hstd'."""
        _, mock_kv = mock_db
        self._run_merge(tmp_path, mock_db, duong_dan_pgd_factory, "hstd")

        keys_ghi = [c.args[0] for c in mock_kv.call_args_list]
        assert "merge_meta_hstd" in keys_ghi

    def test_meta_chua_cac_truong_can_thiet(
        self, tmp_path, mock_streamlit, mock_db, duong_dan_pgd_factory
    ):
        """Meta phải có: thoi_gian, so_pgd, so_dong, pgd_cu."""
        _, mock_kv = mock_db
        self._run_merge(tmp_path, mock_db, duong_dan_pgd_factory, "hstd")

        kv_calls = [
            c for c in mock_kv.call_args_list
            if "merge_meta_hstd" in str(c.args[0])
        ]
        assert kv_calls
        meta = kv_calls[0].args[1]
        for field in ("thoi_gian", "so_pgd", "so_dong", "pgd_cu"):
            assert field in meta, f"Trường '{field}' phải có trong meta merge"

    def test_meta_so_pgd_dung_so_luong(
        self, tmp_path, mock_streamlit, mock_db, duong_dan_pgd_factory
    ):
        """meta['so_pgd'] phải bằng số PGD đã merge thành công."""
        _, mock_kv = mock_db
        self._run_merge(tmp_path, mock_db, duong_dan_pgd_factory, "hstd")

        kv_calls = [
            c for c in mock_kv.call_args_list
            if "merge_meta_hstd" in str(c.args[0])
        ]
        meta = kv_calls[0].args[1]
        assert meta["so_pgd"] == 1  # 1 PGD trong test


# ══════════════════════════════════════════════════════════════════════════════
# 10. AUDIT LOG SAU MERGE THÀNH CÔNG
# ══════════════════════════════════════════════════════════════════════════════

class TestMergeAuditLog:
    def test_audit_ghi_sau_thanh_cong(
        self, tmp_path, mock_streamlit, mock_db, duong_dan_pgd_factory
    ):
        """Sau merge thành công, db.ghi_audit phải được gọi với action='merge_toan_cn'."""
        mock_audit, _ = mock_db
        ten_pgd = "PGD Audit Test"
        df_mau = _df_hstd_mau(ten_pgd)
        fake_duong_dan = duong_dan_pgd_factory([ten_pgd], "hstd")
        cache_path = str(tmp_path / "hstd.parquet")

        with patch.object(svc, "duong_dan_pgd", side_effect=fake_duong_dan), \
             patch.object(svc, "DS_PGD", [ten_pgd]), \
             patch.object(svc, "DON_VI_CHI_NHANH", "Hội sở"), \
             patch.object(svc, "CACHE_HSTD", cache_path), \
             patch.object(svc, "UPLOAD_CANH_BAO_NGAY", {"hstd": 3}), \
             patch.object(svc, "excel_to_parquet", return_value=df_mau), \
             patch.object(svc, "kiem_tra_chat_luong", return_value=MagicMock(
                 df=df_mau, report={"so_loi": 0, "tong_dong": len(df_mau)}
             )):
            merge_du_lieu_toan_cn("hstd", ds_pgd=[ten_pgd])

        audit_actions = [c.args[1] for c in mock_audit.call_args_list]
        assert "merge_toan_cn" in audit_actions

    def test_audit_detail_chua_loai_va_so_dong(
        self, tmp_path, mock_streamlit, mock_db, duong_dan_pgd_factory
    ):
        """Detail trong audit log phải chứa tên loại (HSTD) và số dòng."""
        mock_audit, _ = mock_db
        ten_pgd = "PGD Detail Test"
        df_mau = _df_hstd_mau(ten_pgd, so_dong=7)
        fake_duong_dan = duong_dan_pgd_factory([ten_pgd], "hstd")
        cache_path = str(tmp_path / "hstd.parquet")

        with patch.object(svc, "duong_dan_pgd", side_effect=fake_duong_dan), \
             patch.object(svc, "DS_PGD", [ten_pgd]), \
             patch.object(svc, "DON_VI_CHI_NHANH", "Hội sở"), \
             patch.object(svc, "CACHE_HSTD", cache_path), \
             patch.object(svc, "UPLOAD_CANH_BAO_NGAY", {"hstd": 3}), \
             patch.object(svc, "excel_to_parquet", return_value=df_mau), \
             patch.object(svc, "kiem_tra_chat_luong", return_value=MagicMock(
                 df=df_mau, report={"so_loi": 0, "tong_dong": 7}
             )):
            merge_du_lieu_toan_cn("hstd", ds_pgd=[ten_pgd])

        merge_call = next(
            (c for c in mock_audit.call_args_list if c.args[1] == "merge_toan_cn"),
            None
        )
        assert merge_call is not None
        detail = merge_call.args[2]
        assert "HSTD" in detail
        assert "7" in detail


# ══════════════════════════════════════════════════════════════════════════════
# 11. LOAI GQVL — DÙNG COT_MAP VÀ SHEET1
# ══════════════════════════════════════════════════════════════════════════════

class TestMergeGQVL:
    def test_gqvl_thanh_cong(
        self, tmp_path, mock_streamlit, mock_db, duong_dan_pgd_factory
    ):
        """loai='gqvl' → merge thành công, dùng cache CACHE_GQVL."""
        ten_pgd = "PGD GQVL Test"
        df_mau = _df_gqvl_mau(ten_pgd)
        fake_duong_dan = duong_dan_pgd_factory([ten_pgd], "gqvl")
        cache_path = str(tmp_path / "gqvl.parquet")

        with patch.object(svc, "duong_dan_pgd", side_effect=fake_duong_dan), \
             patch.object(svc, "DS_PGD", [ten_pgd]), \
             patch.object(svc, "DON_VI_CHI_NHANH", "Hội sở"), \
             patch.object(svc, "CACHE_GQVL", cache_path), \
             patch.object(svc, "UPLOAD_CANH_BAO_NGAY", {"gqvl": 3}), \
             patch.object(svc, "excel_to_parquet", return_value=df_mau), \
             patch.object(svc, "kiem_tra_chat_luong", return_value=MagicMock(
                 df=df_mau, report={"so_loi": 0, "tong_dong": len(df_mau)}
             )):
            kq = merge_du_lieu_toan_cn("gqvl", ds_pgd=[ten_pgd])

        assert kq.thanh_cong is True
        assert Path(cache_path).exists()

    def test_gqvl_nguon_von_khong_bi_ep_numeric(
        self, tmp_path, mock_streamlit, mock_db, duong_dan_pgd_factory
    ):
        """
        GQVL: 'Nguồn vốn' = 'TW'/'ĐP' phải giữ nguyên sau merge.
        Regression test cho bug đã fix.
        """
        ten_pgd = "PGD GQVL Regression"
        df_mau = _df_gqvl_mau(ten_pgd)  # có cột Nguồn vốn = TW/ĐP
        fake_duong_dan = duong_dan_pgd_factory([ten_pgd], "gqvl")
        cache_path = str(tmp_path / "gqvl.parquet")

        with patch.object(svc, "duong_dan_pgd", side_effect=fake_duong_dan), \
             patch.object(svc, "DS_PGD", [ten_pgd]), \
             patch.object(svc, "DON_VI_CHI_NHANH", "Hội sở"), \
             patch.object(svc, "CACHE_GQVL", cache_path), \
             patch.object(svc, "UPLOAD_CANH_BAO_NGAY", {"gqvl": 3}), \
             patch.object(svc, "excel_to_parquet", return_value=df_mau), \
             patch.object(svc, "kiem_tra_chat_luong", return_value=MagicMock(
                 df=df_mau, report={"so_loi": 0, "tong_dong": len(df_mau)}
             )):
            merge_du_lieu_toan_cn("gqvl", ds_pgd=[ten_pgd])

        df_out = pd.read_parquet(cache_path)
        vals = df_out["Nguồn vốn"].dropna().unique().tolist()
        assert any(v in ("TW", "ĐP") for v in vals), \
            "GQVL: 'Nguồn vốn' không được bị ép thành NaN"


# ══════════════════════════════════════════════════════════════════════════════
# 12. LOCK AN TOÀN — KHÔNG RACE CONDITION
# ══════════════════════════════════════════════════════════════════════════════

class TestMergeConcurrency:
    def test_merge_dong_thoi_2_luong_khong_corrupt_file(
        self, tmp_path, mock_db, duong_dan_pgd_factory
    ):
        """
        Gọi merge_du_lieu_toan_cn từ 2 thread đồng thời → chỉ 1 thread ghi,
        file parquet output phải đọc được (không corrupt).
        """
        ten_pgd = "PGD Concurrent"
        df_mau = _df_hstd_mau(ten_pgd, so_dong=10)
        fake_duong_dan = duong_dan_pgd_factory([ten_pgd], "hstd")
        cache_path = str(tmp_path / "hstd_concurrent.parquet")

        errors: list[Exception] = []

        def _run():
            prog_mock = MagicMock()
            try:
                with patch.object(svc.st, "progress", return_value=prog_mock), \
                     patch.object(svc.st, "session_state", {"username": "user1"}), \
                     patch.object(svc, "duong_dan_pgd", side_effect=fake_duong_dan), \
                     patch.object(svc, "DS_PGD", [ten_pgd]), \
                     patch.object(svc, "DON_VI_CHI_NHANH", "Hội sở"), \
                     patch.object(svc, "CACHE_HSTD", cache_path), \
                     patch.object(svc, "UPLOAD_CANH_BAO_NGAY", {"hstd": 3}), \
                     patch.object(svc, "excel_to_parquet", return_value=df_mau), \
                     patch.object(svc, "kiem_tra_chat_luong", return_value=MagicMock(
                         df=df_mau, report={"so_loi": 0, "tong_dong": len(df_mau)}
                     )):
                    merge_du_lieu_toan_cn("hstd", ds_pgd=[ten_pgd])
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=_run)
        t2 = threading.Thread(target=_run)
        t1.start(); t2.start()
        t1.join(); t2.join()

        assert not errors, f"Lỗi khi chạy đồng thời: {errors}"
        if Path(cache_path).exists():
            # File phải đọc được, không bị corrupt
            df_check = pd.read_parquet(cache_path)
            assert len(df_check) > 0
