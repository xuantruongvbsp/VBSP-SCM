"""Test smoke cho services/giao_ban_thang_service.py — tạo PDF từ dữ liệu giả."""
from __future__ import annotations

import sys
import os
import importlib.util
import pandas as pd
import numpy as np

_mod_path = os.path.join(os.path.dirname(__file__), "..", "services", "giao_ban_thang_service.py")
_mod_path = os.path.abspath(_mod_path)
spec = importlib.util.spec_from_file_location("giao_ban_thang_service", _mod_path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
tao_bao_cao_giao_ban_thang = mod.tao_bao_cao_giao_ban_thang


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


def main():
    df = _tao_df_gia()
    print(f"Mock data: {len(df):,} rows, {df['Tên PGD'].nunique()} PGD")
    print(f"Total dư nợ: {int(df['Tổng dư nợ'].sum() / 1e6):,} triệu đồng")
    print(f"Total QH: {int(df['Dư nợ quá hạn'].sum() / 1e6):,} triệu đồng")
    print(f"Total Khoanh: {int(df['Dư nợ khoanh'].sum() / 1e6):,} triệu đồng")
    print(f"Total Lãi tồn: {int(df['Lãi tồn TH'].sum() / 1e6):,} triệu đồng")

    bytes_out = tao_bao_cao_giao_ban_thang(
        df, thang=6, nam=2026, username="test_user",
    )

    if bytes_out and len(bytes_out) > 1000:
        out_path = "tests/test_giao_ban_output.pdf"
        with open(out_path, "wb") as f:
            f.write(bytes_out)
        print(f"\n✅ OK — PDF: {len(bytes_out):,} bytes → {out_path}")
    else:
        size = len(bytes_out) if bytes_out else 0
        print(f"\n❌ FAIL — output: {size} bytes")


if __name__ == "__main__":
    main()
