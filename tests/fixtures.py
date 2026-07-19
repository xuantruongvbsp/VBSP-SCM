from __future__ import annotations

from io import BytesIO

import pandas as pd


def tao_file_hstd_hop_le() -> bytes:
    df = pd.DataFrame(
        {
            "BoQua": ["x", "x"],
            "Số khế ước": ["KU001", "KU002"],
            "Mã KH": ["KH001", "KH002"],
            "Tên PGD": ["PGD Long Thành", "PGD Long Thành"],
            "Tên xã": ["Phước Thái", "Phước Thái"],
            "Dư nợ trong hạn": [1000, 2000],
            "Dư nợ quá hạn": [0, 0],
            "Tổng dư nợ": [1000, 2000],
            "Nguồn vốn": [1, 2],
        }
    )
    bio = BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="BCQUERY", startrow=4, index=False)
    return bio.getvalue()

