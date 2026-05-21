from __future__ import annotations

from io import BytesIO

import pandas as pd
import pytest

from services import khtd_nhap_service


def _xlsx_bytes_from_df(df: pd.DataFrame) -> bytes:
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    return buf.getvalue()


def test_doc_excel_khtd_cn_upload_ok():
    df = pd.DataFrame(
        [
            {"Chương trình": "A", "Mã CT": "1_TW", "Nguồn vốn": "TW", "KH (triệu đồng)": 10},
            {"Chương trình": "B", "Mã CT": "2_DP", "Nguồn vốn": "DP", "KH (triệu đồng)": 0},
            {"Chương trình": "C", "Mã CT": "X_KO_HOP_LE", "Nguồn vốn": "TW", "KH (triệu đồng)": 5},
        ]
    )
    b = _xlsx_bytes_from_df(df)
    out, dem, bo_qua = khtd_nhap_service.doc_excel_khtd_cn_upload(
        b,
        ma_keys_co_khtd={"1_TW", "2_DP"},
    )
    assert dem == 1
    assert out["1_TW"] == 10 * 1_000_000
    assert "X_KO_HOP_LE" in bo_qua


def test_doc_excel_khtd_cn_upload_missing_ma_ct():
    df = pd.DataFrame([{"abc": 1, "KH (triệu đồng)": 10}])
    b = _xlsx_bytes_from_df(df)
    with pytest.raises(ValueError):
        khtd_nhap_service.doc_excel_khtd_cn_upload(b, ma_keys_co_khtd={"1_TW"})


def test_doc_excel_khtd_xa_upload_ok_and_validate_xa():
    df = pd.DataFrame(
        [
            ["Xã A", "1_TW", 10],
            ["Xã B", "1_TW", 20],
            ["Xã C", "1_TW", 30],
            ["Xã A", "X_BAD", 10],
            ["Xã A", "1_TW", 0],
        ]
    )
    b = _xlsx_bytes_from_df(df)
    updates, dem, canh_bao = khtd_nhap_service.doc_excel_khtd_xa_upload(
        b,
        ds_xa_hop_le={"Xã A", "Xã B"},
        ma_keys_co_khtd={"1_TW"},
    )
    assert dem == 2
    assert updates["Xã A|1_TW"] == 10 * 1_000_000
    assert updates["Xã B|1_TW"] == 20 * 1_000_000
    assert any("Xã không thuộc PGD" in s for s in canh_bao)
    assert any("Mã CT không hợp lệ" in s for s in canh_bao)


def test_luu_pdf_khtd_xa(tmp_path):
    pdf_bytes = b"%PDF-1.4\n%fake\n"
    p = khtd_nhap_service.luu_pdf_khtd_xa(
        pdf_bytes,
        str(tmp_path),
        pgd="PGD A",
        xa="Xã 1/2",
    )
    assert p.exists()
    assert p.suffix.lower() == ".pdf"
    assert p.read_bytes() == pdf_bytes
