from __future__ import annotations

import pandas as pd

from config import COT_TEN_THON, COT_TEN_XA
from data.khtd import gan_cbtd_vao_df
from services.cbtd_dia_ban_service import _normalize
from tabs.tab_quan_ly_dgd import (
    _build_prospective_xa_dgd,
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
