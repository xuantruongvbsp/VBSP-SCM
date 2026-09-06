from __future__ import annotations

import pandas as pd

from config import (
    COT_DU_NO_QH,
    COT_DU_NO_TH,
    COT_NGAY_GN_DAU_TIEN,
    COT_NGAY_VAY,
    COT_MA_KH,
    COT_SO_KU,
    COT_TEN_CT,
    COT_TEN_THON,
    COT_TEN_XA,
    COT_TONG_DU_NO,
)
from data.khtd import gan_cbtd_vao_df
from services.cbtd_dia_ban_service import _normalize, tong_hop_hstd_theo_cbtd
from tabs.tab_quan_ly_dgd import (
    _build_prospective_xa_dgd,
    _gop_dgd_thon_tu_excel_df,
    _validate_trung_thon_toan_xa,
)


def test_cbtd_service_normalize_guard_none_nan_pdna():
    assert _normalize(None) == ""
    assert _normalize(float("nan")) == ""
    assert _normalize(pd.NA) == ""
    assert _normalize("  Xã A  ") == "xã a"


def test_gan_cbtd_vao_df_join_key_normalize_dong_nhat_pdna():
    cbtd_data = {
        "CB01": {
            "ho_ten": "Nguyễn Văn A",
            "pgd": "PGD A",
            "ds_dgd": ["ĐGD 1"],
        }
    }
    dgd_map = {
        "PGD A": {
            "Xã A": {
                "ĐGD 1": {"thon": ["Thôn 1", pd.NA, None]},
            }
        }
    }
    df = pd.DataFrame(
        {
            COT_TEN_XA: ["  xã a ", pd.NA],
            COT_TEN_THON: [" thôn 1 ", "Thôn 1"],
        }
    )

    out = gan_cbtd_vao_df(df, cbtd_data, dgd_map)

    assert out.loc[0, "CBTD"] == "CB01"
    assert pd.isna(out.loc[1, "CBTD"])


def test_build_prospective_xa_dgd_cho_phep_move_thon_khong_trung_gia():
    xa_dgd = {
        "ĐGD A": {"thon": ["Thôn 1", "Thôn 2"]},
        "ĐGD B": {"thon": ["Thôn 3"]},
    }
    pending = {
        "ĐGD B": ["Thôn 1", "Thôn 3"],
    }

    prospective = _build_prospective_xa_dgd(xa_dgd, pending)

    assert prospective["ĐGD A"] == ["Thôn 2"]
    assert prospective["ĐGD B"] == ["Thôn 1", "Thôn 3"]
    assert _validate_trung_thon_toan_xa(prospective) == []


def test_gop_dgd_thon_tu_excel_filldown_va_tach_nhieu_thon():
    df_imp = pd.DataFrame(
        {
            "PGD": ["PGD A", "", "", "PGD A"],
            "Xã": ["Xã A", "", "", "Xã A"],
            "Tên ĐGD": ["ĐGD 1", "", "", "ĐGD 2"],
            "Thôn/ấp": ["Thôn 1, Thôn 2", "Thôn 2", "Thôn 3\nThôn 4", "Ấp 5"],
        }
    )

    grouped, stats = _gop_dgd_thon_tu_excel_df(df_imp)

    assert stats["rows"] == 4
    assert stats["used_rows"] == 5
    assert grouped["PGD A"]["Xã A"]["ĐGD 1"] == [
        "Thôn 1",
        "Thôn 2",
        "Thôn 3",
        "Thôn 4",
    ]
    assert grouped["PGD A"]["Xã A"]["ĐGD 2"] == ["Ấp 5"]


def test_tong_hop_hstd_theo_cbtd_cong_so_lieu_tung_can_bo():
    cbtd_data = {
        "CB01": {"ho_ten": "Nguyễn Văn A", "pgd": "PGD A", "ds_dgd": ["ĐGD 1"]},
        "CB02": {"ho_ten": "Trần Thị B", "pgd": "PGD A", "ds_dgd": ["ĐGD 2"]},
        "CB03": {"ho_ten": "Lê Văn C", "pgd": "PGD A", "ds_dgd": []},
    }
    dgd_map = {
        "PGD A": {
            "Xã A": {
                "ĐGD 1": {"thon": ["Thôn 1"]},
                "ĐGD 2": {"thon": ["Thôn 2"]},
            }
        }
    }
    df_hstd = pd.DataFrame({
        COT_TEN_XA: ["Xã A", "Xã A", "Xã A"],
        COT_TEN_THON: ["Thôn 1", "Thôn 1", "Thôn 2"],
        COT_MA_KH: ["KH01", "KH02", "KH03"],
        COT_SO_KU: ["KU01", "KU02", "KU03"],
        COT_TONG_DU_NO: [100_000_000, 200_000_000, 300_000_000],
        COT_DU_NO_TH: [90_000_000, 150_000_000, 300_000_000],
        COT_DU_NO_QH: [10_000_000, 50_000_000, 0],
        COT_TEN_CT: ["CT A", "CT B", "CT A"],
        COT_NGAY_VAY: ["2026-09-01", "2026-08-15", "2026-09-02"],
        COT_NGAY_GN_DAU_TIEN: ["2026-09-01", None, "2026-09-03"],
    })

    out = tong_hop_hstd_theo_cbtd(cbtd_data, dgd_map, df_hstd, yyyy=2026, mm=9)
    cb01 = out[out["Ma_CBTD"] == "CB01"].iloc[0]
    cb02 = out[out["Ma_CBTD"] == "CB02"].iloc[0]
    cb03 = out[out["Ma_CBTD"] == "CB03"].iloc[0]

    assert cb01["So_KH"] == 2
    assert cb01["So_mon_vay"] == 2
    assert cb01["Tong_du_no"] == 300_000_000
    assert cb01["Du_no_qh"] == 60_000_000
    assert cb01["TL_QH_pct"] == 20.0
    assert cb01["CT_du_no_lon_nhat"] == "CT B"
    assert cb01["So_KH_moi_thang"] == 1
    assert cb01["So_giai_ngan_thang"] == 1
    assert cb02["Tong_du_no"] == 300_000_000
    assert cb03["Tong_du_no"] == 0
    assert "Chưa gán ĐGD" in cb03["Canh_bao"]
