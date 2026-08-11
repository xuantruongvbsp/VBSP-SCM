from __future__ import annotations

import io

import pandas as pd

from data import phan_ky_nxh as nxh
from data.phan_ky_nxh import _read_excel_nxh


def _nxh_excel_bytes_header_dong_5() -> bytes:
    buf = io.BytesIO()
    rows = [
        [None, None, None, None, None],
        [None, "Sao kê nợ đến hạn kỳ con theo chương trình vay", None, None, None],
        [None, None, None, None, None],
        [None, None, None, None, None],
        [
            "Tên PGD",
            "Tên khách hàng",
            "Số điện thoại",
            "Số khế ước",
            "Ngày đến hạn kỳ con",
            "Dư nợ kỳ con đến hạn",
            "Lãi tồn",
            "Tổng TG, TK",
        ],
        [
            "Hội sở CN Đồng Nai",
            "NGUYEN VAN A",
            "0906028228",
            "6600000729007326",
            "12/08/2026",
            13_500_000,
            1_878_905,
            1_957_791,
        ],
    ]
    pd.DataFrame(rows).to_excel(buf, index=False, header=False)
    return buf.getvalue()


def test_read_excel_nxh_tu_do_header_dong_5_va_giu_sdt_text():
    df, header_row = _read_excel_nxh(io.BytesIO(_nxh_excel_bytes_header_dong_5()))

    assert header_row == 4
    assert len(df) == 1
    assert df.loc[0, "Số điện thoại"] == "0906028228"
    assert df.loc[0, "Số khế ước"] == "6600000729007326"
    assert df.loc[0, "Ngày đến hạn kỳ con"] == pd.Timestamp("2026-08-12")
    assert df.loc[0, "Dư nợ kỳ con đến hạn"] == 13_500_000


def test_lay_ngay_du_lieu_phan_ky_nxh_uu_tien_meta(monkeypatch):
    monkeypatch.setattr(
        nxh.db,
        "doc_kv",
        lambda key: {"ngay_upload": "2026-08-05T09:15:00"}
        if key == "phan_ky_nxh_meta" else None,
    )

    assert nxh.lay_ngay_du_lieu_phan_ky_nxh("01/08/2026") == "05/08/2026"
