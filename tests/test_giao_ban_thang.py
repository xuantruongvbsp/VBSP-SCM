"""Test smoke cho services/giao_ban_thang_service.py — tạo PDF từ dữ liệu giả."""
from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
import pytest

from services.giao_ban_thang_service import tao_bao_cao_giao_ban_thang


def _tao_df_gia():
    np.random.seed(42)
    pgd_list = [
        "Hội sở CN Đồng Nai", "PGD Biên Hòa", "PGD Long Bình", "PGD Trảng Dài",
        "PGD Vĩnh Cửu", "PGD Tân Phong", "PGD Hố Nai", "PGD Tam Phước",
        "PGD Long Thành", "PGD Nhơn Trạch", "PGD Cẩm Mỹ", "PGD Xuân Lộc",
        "PGD Định Quán", "PGD Tân Phú", "PGD Thống Nhất", "PGD Trảng Bom",
        "PGD Long Khánh", "PGD An Phước", "PGD Phước Tân", "PGD Bình Sơn",
        "PGD Gia Kiệm", "PGD Bảo Vinh",
    ]
    rows = []
    for pgd in pgd_list:
        n_mons = np.random.randint(50, 300)
        for i in range(n_mons):
            rows.append({
                "Tên PGD": pgd,
                "Mã KH": f"KH{np.random.randint(100000, 999999)}",
                "Tổng dư nợ": np.random.randint(10, 500) * 1_000_000,
                "Dư nợ quá hạn": np.random.randint(0, 50) * 1_000_000 if np.random.random() < 0.3 else 0,
                "Dư nợ khoanh": np.random.randint(0, 20) * 1_000_000 if np.random.random() < 0.1 else 0,
                "Lãi tồn TH": np.random.randint(0, 5000) * 1000,
            })
    return pd.DataFrame(rows)


class TestGiaoBanThang:
    def test_tao_pdf_ok(self):
        df = _tao_df_gia()
        assert df is not None
        assert len(df) > 0

        bytes_out = tao_bao_cao_giao_ban_thang(
            df, thang=6, nam=2026, username="test_user",
        )

        assert bytes_out is not None
        assert len(bytes_out) > 2000, f"PDF too small: {len(bytes_out)} bytes"
        assert bytes_out[:4] == b"%PDF", "Output is not valid PDF"

        with open("tests/test_giao_ban_output.pdf", "wb") as f:
            f.write(bytes_out)

    def test_df_empty(self):
        import streamlit as st
        df = pd.DataFrame(columns=["Tên PGD", "Mã KH", "Tổng dư nợ"])
        bytes_out = tao_bao_cao_giao_ban_thang(
            df, thang=6, nam=2026, username="test_user",
        )
        assert bytes_out == b""

    def test_pdf_co_du_bang_xep_hang(self):
        df = _tao_df_gia()
        bytes_out = tao_bao_cao_giao_ban_thang(
            df, thang=6, nam=2026, username="test_user",
        )
        assert bytes_out is not None
        assert len(bytes_out) > 2000


if __name__ == "__main__":
    import sys
    import warnings
    warnings.filterwarnings("ignore")

    df = _tao_df_gia()
    print(f"Mock data: {len(df)} rows, {df['Tên PGD'].nunique()} PGD")

    bytes_out = tao_bao_cao_giao_ban_thang(
        df, thang=6, nam=2026, username="test_user",
    )

    if bytes_out:
        out_path = "test_giao_ban.pdf"
        with open(out_path, "wb") as f:
            f.write(bytes_out)
        print(f"✅ OK — PDF: {len(bytes_out):,} bytes → {out_path}")
    else:
        print("❌ FAIL — no PDF output")
