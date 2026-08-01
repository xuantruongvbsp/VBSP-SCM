"""Regression tests cho tối ưu numeric columns trong app.py."""
from __future__ import annotations

import pandas as pd

from config import (
    COT_DU_NO_KHOANH,
    COT_DU_NO_QH,
    COT_DU_NO_TH,
    COT_LAI_THANG,
    COT_LAI_TON,
    COT_LAI_TON_QH,
    COT_SO_KU,
    COT_TONG_DU_NO,
)


def _load_app_helpers() -> dict:
    """Load riêng helper cần test từ app.py, không chạy main()/Streamlit UI."""
    import ast
    from pathlib import Path

    source = Path("app.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    wanted = {"_toi_uu_dtype", "_num0", "_enrich_hstd", "_loc_hstd_active"}
    nodes = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in wanted
    ]
    module = ast.Module(body=nodes, type_ignores=[])
    ast.fix_missing_locations(module)
    namespace = {
        "pd": pd,
        "COT_SO_KU": COT_SO_KU,
        "COT_TONG_DU_NO": COT_TONG_DU_NO,
        "COT_DU_NO_QH": COT_DU_NO_QH,
        "COT_DU_NO_TH": COT_DU_NO_TH,
        "COT_DU_NO_KHOANH": COT_DU_NO_KHOANH,
        "COT_LAI_TON": COT_LAI_TON,
        "COT_LAI_THANG": COT_LAI_THANG,
        "COT_LAI_TON_QH": COT_LAI_TON_QH,
    }
    exec(compile(module, "app.py", "exec"), namespace)
    return namespace


def test_toi_uu_dtype_precompute_7_cot_tai_chinh():
    helpers = _load_app_helpers()

    numeric_cols = [
        COT_TONG_DU_NO,
        COT_DU_NO_QH,
        COT_DU_NO_TH,
        COT_DU_NO_KHOANH,
        COT_LAI_TON,
        COT_LAI_THANG,
        COT_LAI_TON_QH,
    ]
    df = pd.DataFrame({col: ["1000", "bad"] for col in numeric_cols})

    result = helpers["_toi_uu_dtype"](df)

    for col in numeric_cols:
        assert pd.api.types.is_numeric_dtype(result[col])
        assert result[col].iloc[0] == 1000
        assert pd.isna(result[col].iloc[1])


def test_enrich_hstd_object_numeric_khong_noi_chuoi(monkeypatch):
    import data.hstd as hstd
    helpers = _load_app_helpers()

    monkeypatch.setattr(hstd, "doc_so_khe_uoc_nq11", lambda: {"KU1", "KU2"})
    df = pd.DataFrame({
        COT_SO_KU: ["KU1", "KU2"],
        COT_DU_NO_TH: ["100", "200"],
        COT_DU_NO_QH: ["10", "20"],
    })

    result = helpers["_enrich_hstd"](df, None, None)

    assert result["__dn_nq11"].tolist() == [110, 220]
    assert result["__qh_nq11"].tolist() == [10, 20]


def test_loc_hstd_active_object_numeric_khong_crash_va_loc_dung():
    helpers = _load_app_helpers()

    df = pd.DataFrame({
        "id": [1, 2, 3, 4],
        COT_TONG_DU_NO: ["0", "100", "bad", None],
        COT_DU_NO_QH: ["0", "0", "5", None],
        COT_DU_NO_KHOANH: ["0", "0", "0", None],
    })

    result = helpers["_loc_hstd_active"](df)

    assert result["id"].tolist() == [2, 3]
