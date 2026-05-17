from __future__ import annotations

import os

import pandas as pd


def test_smoke_imports() -> None:
    import snapshot_service  # noqa: F401
    import services.upload_service  # noqa: F401
    import workspaces.ws_executive  # noqa: F401
    import tabs.tab_ban_dai_dien  # noqa: F401


def test_snapshot_roundtrip(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("VBSP_SCM_DB_PATH", str(tmp_path / "test_vbsp_scm.db"))

    import db
    from snapshot_service import danh_sach_ky, doc_snapshot, luu_snapshot
    from config import (
        COT_DU_NO_QH,
        COT_DU_NO_TH,
        COT_MA_CHUONG_TRINH,
        COT_MA_KH,
        COT_NGAY_SL,
        COT_NGUON_VON,
        COT_SO_KU,
        COT_TEN_PGD,
        COT_TONG_DU_NO,
    )

    db.reset_conn()
    db.init_db()

    df = pd.DataFrame(
        {
            COT_TEN_PGD: ["PGD A", "PGD A", "PGD B"],
            COT_MA_KH: ["KH1", "KH2", "KH3"],
            COT_SO_KU: ["KU1", "KU2", "KU3"],
            COT_TONG_DU_NO: [10_000_000_000, 20_000_000_000, 5_000_000_000],
            COT_DU_NO_TH: [10_000_000_000, 19_000_000_000, 5_000_000_000],
            COT_DU_NO_QH: [0, 1_000_000_000, 0],
            "Dư nợ khoanh": [0, 0, 0],
            "Giải ngân trong năm": [1_000_000_000, 2_000_000_000, 500_000_000],
            COT_MA_CHUONG_TRINH: ["1", "1", "2"],
            COT_NGUON_VON: [1, 1, 2],
            COT_NGAY_SL: ["01/05/2026", "01/05/2026", "01/05/2026"],
        }
    )

    kq = luu_snapshot(df, username="tester")
    assert kq.thanh_cong is True

    ds = danh_sach_ky()
    assert "2026-05" in ds

    df_snap = doc_snapshot("2026-05")
    assert not df_snap.empty
    assert "ten_pgd" in df_snap.columns
    assert "__CN__" in set(df_snap["ten_pgd"].astype(str))

