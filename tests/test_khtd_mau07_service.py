from __future__ import annotations

import pandas as pd
import pytest

from config import (
    COT_MA_CHUONG_TRINH,
    COT_NGUON_VON,
    COT_TEN_THON,
    COT_TEN_XA,
    COT_TONG_DU_NO,
)
from services import khtd_mau07_service


def test_slug_and_kv_key_helpers():
    assert khtd_mau07_service._slug("Xã Phú Lý") == "xa_phu_ly"
    assert khtd_mau07_service._kv_key("PGD A", "Xã 1") == "khtd_ap_pgd_a_xa_1"
    assert khtd_mau07_service._kv_key_ls("PGD A", "Xã 1") == "khtd_ap_lich_su_pgd_a_xa_1"


def test_tinh_du_no_ap_baseline_basic():
    df = pd.DataFrame(
        [
            {
                COT_TEN_XA: "Xã A",
                COT_TEN_THON: "Ấp 1",
                COT_MA_CHUONG_TRINH: 1,
                COT_NGUON_VON: 1,
                COT_TONG_DU_NO: 1_500_000,
            },
            {
                COT_TEN_XA: "Xã A",
                COT_TEN_THON: "Ấp 1",
                COT_MA_CHUONG_TRINH: 1,
                COT_NGUON_VON: 1,
                COT_TONG_DU_NO: 500_000,
            },
            {
                COT_TEN_XA: "Xã B",
                COT_TEN_THON: "Ấp 2",
                COT_MA_CHUONG_TRINH: 1,
                COT_NGUON_VON: 1,
                COT_TONG_DU_NO: 10_000_000,
            },
        ]
    )
    out = khtd_mau07_service.tinh_du_no_ap_baseline(df, "Xã A")
    assert out
    key_any = next(iter(out.keys()))
    assert "|" in key_any
    assert out[key_any] == 2.0


def test_build_extract_and_total():
    ds_ap = ["Ấp 1"]
    ds_ma_key = {"1_TW"}
    du_no_baseline = {"Ấp 1|1_TW": 10.0}
    lich_su: list[dict] = []
    data_hien_tai: dict[str, float] = {"Ấp 1|1_TW": 12.0}
    nam = 2026

    df = khtd_mau07_service._build_table_data(
        ds_ap=ds_ap,
        ds_ma_key=ds_ma_key,
        du_no_baseline=du_no_baseline,
        lich_su=lich_su,
        data_hien_tai=data_hien_tai,
        nam=nam,
    )
    assert (df["_type"] == "total").any()

    extracted = khtd_mau07_service._extract_data_from_edited_df(df, nam)
    assert extracted["Ấp 1|1_TW"] == 12.0

    df2 = khtd_mau07_service._update_total_row(df.copy(), nam)
    row_total = df2[df2["_type"] == "total"].iloc[0]
    assert float(row_total[f"Chỉ tiêu KH {nam} (triệu)"]) == pytest.approx(12.0)


def test_xuat_mau07_word_returns_docx_bytes():
    try:
        import docx
    except Exception:
        pytest.skip("python-docx không khả dụng trong môi trường test")

    b = khtd_mau07_service.xuat_mau07_word(
        xa="Xã A",
        nam=2026,
        loai_van_ban="giao",
        data_dict={"Ấp 1|1_TW": 10.0},
        du_no_baseline={"Ấp 1|1_TW": 9.0},
        lich_su=[],
        lan_chon="dang_nhap",
    )
    assert isinstance(b, (bytes, bytearray))
    assert len(b) > 1000
    assert b[:2] == b"PK"
