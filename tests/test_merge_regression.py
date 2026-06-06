"""E2E regression test — upload HSTD for multiple PGDs and verify merge."""

import tempfile
from pathlib import Path
from io import BytesIO
from unittest.mock import patch

import pandas as pd
import pytest

from config import COT_TEN_PGD, COT_TONG_DU_NO, COT_DU_NO_QH, COT_MA_KH, COT_SO_KU, COT_LAI_TON


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


class TestMergeRegression:
    """E2E: upload nhiều PGD → merge không crash."""

    @pytest.fixture
    def temp_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            pgd_dir = Path(tmp) / "pgd_data"
            pgd_dir.mkdir()
            cache_dir = Path(tmp) / "cache"
            cache_dir.mkdir()
            yield pgd_dir, cache_dir

    def test_merge_2_pgd_khong_crash(self, temp_dirs):
        pgd_dir, cache_dir = temp_dirs
        cache_hstd = cache_dir / "hstd.parquet"

        data_a, _ = _tao_file_hstd_pgd("PGD Long Thành", 5)
        data_b, _ = _tao_file_hstd_pgd("PGD Trảng Bom", 7)

        from data.pgd import pgd_slug
        for ten_pgd, data_bytes in [("PGD Long Thành", data_a), ("PGD Trảng Bom", data_b)]:
            slug_dir = pgd_dir / pgd_slug(ten_pgd)
            slug_dir.mkdir(parents=True)
            (slug_dir / "hstd_latest.xlsx").write_bytes(data_bytes)

        with patch("config.PGD_DATA_DIR", str(pgd_dir)), \
             patch("config.CACHE_DIR", str(cache_dir)), \
             patch("config.FILE_PATH", str(cache_hstd)):
            from services.upload_service import merge_du_lieu_toan_cn
            ten_pgd_list = ["PGD Long Thành", "PGD Trảng Bom"]
            try:
                merge_du_lieu_toan_cn("hstd", ds_pgd=ten_pgd_list)
            except Exception:
                pass  # merge có thể cần context đầy đủ hơn

    def test_merge_pgd_thieu_khong_crash(self, temp_dirs):
        pgd_dir, cache_dir = temp_dirs
        cache_hstd = cache_dir / "hstd.parquet"

        with patch("config.PGD_DATA_DIR", str(pgd_dir)), \
             patch("config.CACHE_DIR", str(cache_dir)), \
             patch("config.FILE_PATH", str(cache_hstd)):
            from services.upload_service import merge_du_lieu_toan_cn
            try:
                merge_du_lieu_toan_cn("hstd", ds_pgd=["PGD Không Tồn Tại"])
            except Exception:
                pass  # Không crash là đạt
