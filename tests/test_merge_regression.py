"""E2E regression test — upload HSTD for multiple PGDs and verify merge.

Chiến lược isolation (đã sửa 2026-06-21):
  - patch.object(svc, "CACHE_HSTD", ...) — bắt buộc vì upload_service import CACHE_HSTD
    ở module-level; patch config.CACHE_DIR sau khi module đã load KHÔNG có tác dụng.
  - patch.object(svc, "duong_dan_pgd", ...) — tương tự, data.pgd đã bind PGD_DATA_DIR
    ở module-level; patch config.PGD_DATA_DIR sau khi load KHÔNG redirect được.
  - Block background snapshot + Telegram threads để không ghi vào DB/file thật.
"""

from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

import services.upload_service as svc
from config import COT_DU_NO_QH, COT_LAI_TON, COT_MA_KH, COT_SO_KU, COT_TEN_PGD, COT_TONG_DU_NO


def _tao_file_hstd_pgd(ten_pgd, so_dong=10):
    """Tạo file Excel HSTD giả cho 1 PGD."""
    pgd_short = ten_pgd[-3:] if len(ten_pgd) > 3 else ten_pgd
    df = pd.DataFrame({
        "BoQua": ["x"] * so_dong,
        COT_SO_KU: [f"KU{pgd_short}{i:03d}" for i in range(so_dong)],
        COT_TEN_PGD: [ten_pgd] * so_dong,
        "Tên xã": [f"Xã {i}" for i in range(so_dong)],
        COT_TONG_DU_NO: [1000000 * (i + 1) for i in range(so_dong)],
        COT_DU_NO_QH: [100000 * (i % 3) for i in range(so_dong)],
        COT_MA_KH: [f"KH{pgd_short}{i:03d}" for i in range(so_dong)],
        COT_LAI_TON: [50000] * so_dong,
        "Tên KH": [f"Khách {i}" for i in range(so_dong)],
        "Nguồn vốn": ["1"] * so_dong,
    })

    bio = BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="BCQUERY", startrow=4, index=False)
    return bio.getvalue(), df


# Block Telegram HTTP calls (giống test_merge_du_lieu_toan_cn.py)
@pytest.fixture(autouse=True)
def mock_telegram():
    with patch("services.telegram_service.gui_thong_bao_merge", return_value=True):
        yield


# Block background snapshot threads — tránh ghi vào DB/file thật
@pytest.fixture(autouse=True)
def mock_snapshots():
    _ok = MagicMock(thanh_cong=True, thong_bao="mocked")
    with patch("snapshot_service.luu_snapshot", return_value=_ok), \
         patch("snapshot_service.luu_gqvl_snapshot", return_value=_ok), \
         patch("snapshot_service.luu_nq11_snapshot", return_value=_ok), \
         patch("snapshot_service.luu_cdtotkvv_snapshot", return_value=_ok):
        yield


class TestMergeRegression:
    """E2E: upload nhiều PGD → merge không crash, output vào tmp_path."""

    def test_merge_2_pgd_khong_crash(self, tmp_path):
        """Merge 2 PGD thật (từ Excel giả) → parquet output vào tmp_path, không ghi vào cache/ thật."""
        pgd_dir = tmp_path / "pgd_data"
        cache_hstd = str(tmp_path / "hstd.parquet")

        data_a, _ = _tao_file_hstd_pgd("PGD Long Thành", 5)
        data_b, _ = _tao_file_hstd_pgd("PGD Trảng Bom", 7)

        from data.pgd import pgd_slug
        for ten_pgd, data_bytes in [("PGD Long Thành", data_a), ("PGD Trảng Bom", data_b)]:
            slug_dir = pgd_dir / pgd_slug(ten_pgd)
            slug_dir.mkdir(parents=True)
            (slug_dir / "hstd_latest.xlsx").write_bytes(data_bytes)

        ten_pgd_list = ["PGD Long Thành", "PGD Trảng Bom"]

        def fake_duong_dan(ten_pgd, loai):
            return str(pgd_dir / pgd_slug(ten_pgd) / f"{loai}_latest.xlsx")

        with patch.object(svc.st, "progress", return_value=MagicMock()), \
             patch.object(svc.st, "session_state", {"username": "test_regression"}), \
             patch.object(svc.db, "ghi_audit"), \
             patch.object(svc.db, "ghi_kv"), \
             patch.object(svc, "CACHE_HSTD", cache_hstd), \
             patch.object(svc, "duong_dan_pgd", side_effect=fake_duong_dan), \
             patch.object(svc, "DS_PGD", ten_pgd_list), \
             patch.object(svc, "DON_VI_CHI_NHANH", "Hội sở"), \
             patch.object(svc, "UPLOAD_CANH_BAO_NGAY", {"hstd": 3}):
            kq = svc.merge_du_lieu_toan_cn("hstd", ds_pgd=ten_pgd_list)

        assert isinstance(kq, svc.KetQuaUpload), "Phải trả về KetQuaUpload"
        # Khi thành công, parquet phải được ghi vào tmp_path (không phải cache/ thật)
        if kq.thanh_cong:
            assert Path(cache_hstd).exists(), "Parquet phải được ghi ra tmp_path"
            assert not Path("cache/hstd.parquet").read_bytes() == Path(cache_hstd).read_bytes() \
                if Path("cache/hstd.parquet").exists() else True, \
                "Output không được ghi vào cache/hstd.parquet thật"

    def test_merge_pgd_thieu_khong_crash(self, tmp_path):
        """PGD không tồn tại → merge trả về KetQuaUpload(False), không crash."""
        cache_hstd = str(tmp_path / "hstd.parquet")

        def fake_duong_dan(ten_pgd, loai):
            return str(tmp_path / ten_pgd / f"{loai}_latest.xlsx")  # path không tồn tại

        with patch.object(svc.st, "progress", return_value=MagicMock()), \
             patch.object(svc.st, "session_state", {"username": "test_regression"}), \
             patch.object(svc.db, "ghi_audit"), \
             patch.object(svc.db, "ghi_kv"), \
             patch.object(svc, "CACHE_HSTD", cache_hstd), \
             patch.object(svc, "duong_dan_pgd", side_effect=fake_duong_dan), \
             patch.object(svc, "DS_PGD", ["PGD Không Tồn Tại"]), \
             patch.object(svc, "DON_VI_CHI_NHANH", "Hội sở"), \
             patch.object(svc, "UPLOAD_CANH_BAO_NGAY", {"hstd": 3}):
            kq = svc.merge_du_lieu_toan_cn("hstd", ds_pgd=["PGD Không Tồn Tại"])

        assert isinstance(kq, svc.KetQuaUpload), "Phải trả về KetQuaUpload"
        assert not kq.thanh_cong, "Không có file → phải báo thất bại"
        assert not Path(cache_hstd).exists(), "Không có file → parquet không được tạo"
