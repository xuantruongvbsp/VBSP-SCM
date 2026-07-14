from __future__ import annotations

from pathlib import Path
import sqlite3
from unittest.mock import MagicMock, patch

import pandas as pd

from data import cdtotkvv
from data import pgd
import snapshot_service


def test_luu_file_pgd_ghi_de_lich_su_khi_upload_toan_cn(tmp_path, monkeypatch):
    monkeypatch.setattr(pgd, "thu_muc_pgd", lambda _ten_pgd: tmp_path)
    history = tmp_path / "cdtotkvv_2026_06.xlsx"
    history.write_bytes(b"ban-cu")

    pgd.luu_file_pgd_voi_lich_su(
        "Hội sở Chi nhánh tỉnh",
        "cdtotkvv",
        b"ban-dung-da-tach",
        "06/2026",
        ghi_de_lich_su=True,
    )

    assert history.read_bytes() == b"ban-dung-da-tach"
    assert (tmp_path / "cdtotkvv_latest.xlsx").read_bytes() == b"ban-dung-da-tach"


def test_doc_cdtotkvv_loai_trung_ma_dv_ma_to(tmp_path, monkeypatch):
    pgd_data = tmp_path / "pgd_data"
    file_a = pgd_data / "don_vi_a" / "cdtotkvv_2026_06.xlsx"
    file_b = pgd_data / "don_vi_b" / "cdtotkvv_2026_06.xlsx"
    file_a.parent.mkdir(parents=True)
    file_b.parent.mkdir(parents=True)
    file_a.write_bytes(b"a")
    file_b.write_bytes(b"b")

    monkeypatch.setattr(cdtotkvv, "BASE_DIR", tmp_path)
    monkeypatch.setattr(cdtotkvv, "ts_file", lambda _path: 0)

    frames = {
        str(file_a): pd.DataFrame(
            [{"ma_dv": "000001", "ma_to": "0000001", "tong_diem": 80}]
        ),
        str(file_b): pd.DataFrame(
            [
                {"ma_dv": "000001", "ma_to": "0000001", "tong_diem": 90},
                {"ma_dv": "000002", "ma_to": "0000002", "tong_diem": 85},
            ]
        ),
    }
    monkeypatch.setattr(
        cdtotkvv,
        "doc_cdtotkvv_path",
        lambda path, _ts: frames[path].copy(),
    )

    cdtotkvv.doc_cdtotkvv.clear()
    result = cdtotkvv.doc_cdtotkvv("06/2026")

    assert len(result) == 2
    assert result.set_index("ma_to").loc["0000001", "tong_diem"] == 90


def test_chuan_hoa_phan_tich_bo_to_du_no_0_va_gop_nhan_yeu_kem():
    df = pd.DataFrame(
        [
            {"ma_to": "1", "du_no": 100, "xep_loai": "Tốt"},
            {"ma_to": "2", "du_no": 0, "xep_loai": "Khá"},
            {"ma_to": "3", "du_no": 50, "xep_loai": "Yếu kém"},
            {"ma_to": "4", "du_no": None, "xep_loai": "Yếu"},
        ]
    )

    result = cdtotkvv.chuan_hoa_cdtotkvv_phan_tich(df)

    assert result["ma_to"].tolist() == ["1", "3"]
    assert result["xep_loai"].tolist() == ["Tốt", "Yếu"]
    assert len(df) == 4  # không sửa dữ liệu nguồn


def test_tong_hop_theo_pgd_chi_dem_to_co_du_no_va_dem_yeu_kem():
    df = pd.DataFrame(
        {
            "ma_dv": ["001", "001", "001"],
            "ten_dv": ["PGD A", "PGD A", "PGD A"],
            "stt": [1, 2, 3],
            "du_no": [100, 0, 50],
            "tong_diem": [90, 70, 60],
            "xep_loai": ["Tốt", "Khá", "Yếu kém"],
            "tinh_trang": ["A", "B", "C"],
        }
    )

    result = cdtotkvv.tong_hop_theo_pgd(df)

    assert result.iloc[0]["tong_to"] == 2
    assert result.iloc[0]["to_tot"] == 1
    assert result.iloc[0]["to_kha"] == 0
    assert result.iloc[0]["to_yeu"] == 1


def test_snapshot_cdto_phong_ve_loai_du_no_0_va_dem_yeu_kem():
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """CREATE TABLE cdtotkvv_snapshot (
            ky TEXT NOT NULL,
            ten_pgd TEXT NOT NULL,
            so_to INTEGER,
            so_tot INTEGER,
            so_kha INTEGER,
            so_tb INTEGER,
            so_yeu INTEGER,
            diem_tb REAL,
            created_by TEXT,
            UNIQUE(ky, ten_pgd)
        )"""
    )
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=conn)
    cm.__exit__ = MagicMock(return_value=False)
    df = pd.DataFrame(
        {
            "ma_dv": ["001", "001", "001"],
            "ten_dv": ["PGD A", "PGD A", "PGD A"],
            "stt": [1, 2, 3],
            "du_no": [100, 0, 50],
            "tong_diem": [90, 70, 60],
            "xep_loai": ["Tốt", "Khá", "Yếu kém"],
        }
    )

    with patch("snapshot_service.db.get_conn", return_value=cm), patch(
        "snapshot_service.db.ghi_audit", return_value=None
    ):
        result = snapshot_service.luu_cdtotkvv_snapshot(df, "2026-06", "tester")

    row = conn.execute(
        "SELECT so_to, so_tot, so_kha, so_yeu FROM cdtotkvv_snapshot "
        "WHERE ky = '2026-06' AND ten_pgd = '__CN__'"
    ).fetchone()
    conn.close()
    assert result.thanh_cong is True
    assert row == (2, 1, 0, 1)


def test_doi_chieu_hstd_theo_ma_to_loai_ma_0_va_hien_to_thieu_cdto():
    df_cdto = pd.DataFrame(
        {
            "ma_dv": ["004601", "004601"],
            "ma_to": ["0000001", "0000002"],
            "du_no": [100, 200],
            "xep_loai": ["Tốt", "Khá"],
        }
    )
    df_hstd = pd.DataFrame(
        {
            "Mã PGD": ["004601"] * 6,
            "Mã tổ": ["0000001", "0000002", "0000003", "0000000", "0000004", "0000005"],
            "Tên PGD": ["Hội sở"] * 6,
            "Tên tổ": ["Tên đã đổi", "Tổ 2", "Cho vay trực tiếp", "Mã 0", "Tổ hết dư nợ", "Tổ thiếu CDTO"],
            "Tổng dư nợ": [100, 200, 50, 999, 0, 75],
            "Hình thức vay": [2, 2, 1, 1, 2, 2],
        }
    )

    result = cdtotkvv.doi_chieu_cdtotkvv_hstd(df_cdto, df_hstd)

    assert result["tong_cdto"] == 2
    assert result["tong_hstd"] == 3
    assert result["so_khop"] == 2
    assert result["chi_cdto"].empty
    assert result["chi_hstd"]["ma_to_chuan"].tolist() == ["0000005"]
    assert result["cho_vay_truc_tiep"]["ma_to_chuan"].tolist() == ["0000003"]
