"""tests/test_core.py
──────────────────────────────────────────────────────
Unit test cho data/core.py:
  - excel_to_parquet()    — cache-aware Excel→Parquet, post_fn
  - tong_hop_du_no_pgd()  — DuckDB group-by PGD+CT
  - dem_no_qua_han_pgd()  — DuckDB NQH filter
  - tong_hop_theo_xa()    — DuckDB filter theo PGD, group-by xã+CT

Không cần SQLite, không cần app context — test thuần file/DataFrame.
"""
from __future__ import annotations

import os

import pandas as pd
import pytest

from data.core import (
    dem_no_qua_han_pgd,
    excel_to_parquet,
    tong_hop_du_no_pgd,
    tong_hop_theo_xa,
)

# ── Tên cột khớp config.py ──────────────────────────────────────────────────
COT_TEN_PGD         = "Tên PGD"
COT_MA_KH           = "Mã KH"
COT_DU_NO_QH        = "Dư nợ quá hạn"
COT_TONG_DU_NO      = "Tổng dư nợ"
COT_TEN_XA          = "Tên xã"
COT_MA_CHUONG_TRINH = "Mã chương trình"


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _df_hstd(**overrides) -> pd.DataFrame:
    """DataFrame HSTD tối thiểu cho DuckDB tests (3 hàng, 2 PGD)."""
    data = {
        COT_TEN_PGD:         ["PGD Long Thành", "PGD Long Thành", "PGD Nhơn Trạch"],
        COT_MA_KH:           ["KH001",           "KH002",           "KH003"],
        COT_TONG_DU_NO:      [1_000_000,         2_000_000,         500_000],
        COT_DU_NO_QH:        [0,                 100_000,           50_000],
        COT_MA_CHUONG_TRINH: ["4",               "4",               "6"],
        COT_TEN_XA:          ["Xã An Bình",       "Xã An Bình",      "Xã Phú Hữu"],
    }
    data.update(overrides)
    return pd.DataFrame(data)


def _write_excel(df: pd.DataFrame, path: str, sheet: str = "Sheet1") -> None:
    df.to_excel(path, sheet_name=sheet, index=False)


def _write_parquet(df: pd.DataFrame, path: str) -> None:
    df.to_parquet(path, index=False, engine="pyarrow")


def _make_parquet(tmp_path, df: pd.DataFrame | None = None) -> str:
    path = str(tmp_path / "hstd.parquet")
    _write_parquet(df if df is not None else _df_hstd(), path)
    return path


# ══════════════════════════════════════════════════════════════════════════════
# excel_to_parquet()
# ══════════════════════════════════════════════════════════════════════════════

class TestExcelToParquet:

    def test_basic_roundtrip(self, tmp_path):
        """Excel mới → Parquet được tạo, dữ liệu trả về khớp Excel."""
        xl = str(tmp_path / "data.xlsx")
        pq = str(tmp_path / "cache" / "data.parquet")
        _write_excel(pd.DataFrame({"A": [1, 2], "B": ["x", "y"]}), xl)

        result = excel_to_parquet(xl, pq, sheet="Sheet1", header=0)

        assert os.path.exists(pq)
        assert list(result["A"]) == [1, 2]
        assert list(result["B"]) == ["x", "y"]

    def test_post_fn_applied(self, tmp_path):
        """post_fn được gọi và biến đổi dữ liệu trước khi ghi cache."""
        xl = str(tmp_path / "data.xlsx")
        pq = str(tmp_path / "data.parquet")
        _write_excel(pd.DataFrame({"val": [10, 20]}), xl)

        result = excel_to_parquet(
            xl, pq, sheet="Sheet1", header=0,
            post_fn=lambda df: df.assign(val=df["val"] * 2),
        )

        assert list(result["val"]) == [20, 40]

    def test_cache_hit_skips_excel_reread(self, tmp_path):
        """Parquet mới hơn Excel → trả về dữ liệu cache, không đọc lại Excel."""
        xl = str(tmp_path / "data.xlsx")
        pq = str(tmp_path / "data.parquet")

        _write_excel(pd.DataFrame({"val": [1]}), xl)
        _write_parquet(pd.DataFrame({"val": [999]}), pq)

        # Đặt Excel thành cũ hơn parquet 10 giây
        old_ts = os.path.getmtime(xl) - 10
        os.utime(xl, (old_ts, old_ts))

        result = excel_to_parquet(xl, pq, sheet="Sheet1", header=0)
        assert list(result["val"]) == [999]  # cache win, Excel không bị đọc lại

    def test_stale_cache_regenerated(self, tmp_path):
        """Excel mới hơn Parquet → cache cũ bị ghi đè bằng dữ liệu mới."""
        xl = str(tmp_path / "data.xlsx")
        pq = str(tmp_path / "data.parquet")

        _write_parquet(pd.DataFrame({"val": [999]}), pq)
        old_ts = os.path.getmtime(pq) - 10
        os.utime(pq, (old_ts, old_ts))

        _write_excel(pd.DataFrame({"val": [42]}), xl)

        result = excel_to_parquet(xl, pq, sheet="Sheet1", header=0)
        assert list(result["val"]) == [42]

    def test_parent_dir_created_automatically(self, tmp_path):
        """Thư mục cha của parquet_path chưa tồn tại → được tạo tự động."""
        xl = str(tmp_path / "data.xlsx")
        pq = str(tmp_path / "a" / "b" / "c" / "data.parquet")
        _write_excel(pd.DataFrame({"x": [1]}), xl)

        excel_to_parquet(xl, pq, sheet="Sheet1", header=0)

        assert os.path.exists(pq)

    def test_missing_excel_raises(self, tmp_path):
        """Cả Excel lẫn parquet đều không tồn tại → raise exception."""
        xl = str(tmp_path / "missing.xlsx")
        pq = str(tmp_path / "out.parquet")

        with pytest.raises(Exception):
            excel_to_parquet(xl, pq, sheet="Sheet1", header=0)

    def test_invalid_sheet_raises(self, tmp_path):
        """Sheet không tồn tại trong Excel → raise exception."""
        xl = str(tmp_path / "data.xlsx")
        pq = str(tmp_path / "out.parquet")
        _write_excel(pd.DataFrame({"a": [1]}), xl)

        with pytest.raises(Exception):
            excel_to_parquet(xl, pq, sheet="KhongCoSheet", header=0)


# ══════════════════════════════════════════════════════════════════════════════
# tong_hop_du_no_pgd()
# ══════════════════════════════════════════════════════════════════════════════

class TestTongHopDuNoPgd:

    def test_output_columns(self, tmp_path):
        result = tong_hop_du_no_pgd(_make_parquet(tmp_path))
        assert set(result.columns) == {"ten_pgd", "ma_ct", "tong_du_no", "so_ho"}

    def test_aggregates_by_pgd_and_ct(self, tmp_path):
        """2 hàng PGD Long Thành CT '4' → gộp 1 dòng, tổng dư nợ đúng."""
        result = tong_hop_du_no_pgd(_make_parquet(tmp_path))

        lt = result[result["ten_pgd"] == "PGD Long Thành"]
        assert len(lt) == 1
        assert lt["tong_du_no"].iloc[0] == 3_000_000   # 1M + 2M
        assert lt["so_ho"].iloc[0] == 2

    def test_filters_zero_du_no(self, tmp_path):
        """Dòng có dư nợ = 0 bị loại khỏi kết quả."""
        df = _df_hstd()
        df.loc[2, COT_TONG_DU_NO] = 0   # PGD Nhơn Trạch → bị lọc
        result = tong_hop_du_no_pgd(_make_parquet(tmp_path, df))

        assert "PGD Nhơn Trạch" not in result["ten_pgd"].values

    def test_file_not_found_returns_empty(self, tmp_path):
        result = tong_hop_du_no_pgd(str(tmp_path / "missing.parquet"))
        assert isinstance(result, pd.DataFrame)
        assert result.empty


# ══════════════════════════════════════════════════════════════════════════════
# dem_no_qua_han_pgd()
# ══════════════════════════════════════════════════════════════════════════════

class TestDemNoQuaHanPgd:

    def test_output_columns(self, tmp_path):
        result = dem_no_qua_han_pgd(_make_parquet(tmp_path))
        assert set(result.columns) == {"ten_pgd", "so_mon_qh", "tong_no_qh"}

    def test_counts_only_qua_han(self, tmp_path):
        """KH001 nqh=0 bị loại; KH002 nqh=100k và KH003 nqh=50k được giữ."""
        result = dem_no_qua_han_pgd(_make_parquet(tmp_path))

        assert len(result) == 2
        lt = result[result["ten_pgd"] == "PGD Long Thành"].iloc[0]
        assert lt["so_mon_qh"] == 1
        assert lt["tong_no_qh"] == 100_000

    def test_ordered_desc_by_tong_no_qh(self, tmp_path):
        """Kết quả sắp xếp giảm dần theo tổng nợ quá hạn."""
        result = dem_no_qua_han_pgd(_make_parquet(tmp_path))
        totals = list(result["tong_no_qh"])
        assert totals == sorted(totals, reverse=True)

    def test_all_zero_nqh_returns_empty(self, tmp_path):
        """Không có khoản NQH nào → DataFrame rỗng."""
        df = _df_hstd(**{COT_DU_NO_QH: [0, 0, 0]})
        result = dem_no_qua_han_pgd(_make_parquet(tmp_path, df))
        assert result.empty

    def test_file_not_found_returns_empty(self, tmp_path):
        result = dem_no_qua_han_pgd(str(tmp_path / "missing.parquet"))
        assert isinstance(result, pd.DataFrame)
        assert result.empty


# ══════════════════════════════════════════════════════════════════════════════
# tong_hop_theo_xa()
# ══════════════════════════════════════════════════════════════════════════════

class TestTongHopTheoXa:

    def test_output_columns(self, tmp_path):
        result = tong_hop_theo_xa(_make_parquet(tmp_path), "PGD Long Thành")
        assert set(result.columns) == {"ten_xa", "ma_ct", "tong_du_no", "so_ho"}

    def test_filters_by_pgd(self, tmp_path):
        """Chỉ trả về hàng của PGD được yêu cầu."""
        result = tong_hop_theo_xa(_make_parquet(tmp_path), "PGD Long Thành")
        assert all(xa == "Xã An Bình" for xa in result["ten_xa"])

    def test_aggregates_by_xa_and_ct(self, tmp_path):
        """PGD LT: 2 khoản tại Xã An Bình CT '4' → gộp 1 dòng."""
        result = tong_hop_theo_xa(_make_parquet(tmp_path), "PGD Long Thành")
        assert len(result) == 1
        assert result["tong_du_no"].iloc[0] == 3_000_000
        assert result["so_ho"].iloc[0] == 2

    def test_wrong_pgd_returns_empty(self, tmp_path):
        """Tên PGD không có trong dữ liệu → DataFrame rỗng."""
        result = tong_hop_theo_xa(_make_parquet(tmp_path), "PGD Không Tồn Tại")
        assert result.empty

    def test_file_not_found_returns_empty(self, tmp_path):
        result = tong_hop_theo_xa(str(tmp_path / "missing.parquet"), "PGD Long Thành")
        assert isinstance(result, pd.DataFrame)
        assert result.empty
