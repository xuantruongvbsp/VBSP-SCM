from __future__ import annotations

import pandas as pd

from components.filter_panel import _keyword_search_mask, _normalize_search_text
from config import (
    COT_CMND,
    COT_MA_KH,
    COT_SDT,
    COT_SO_KU,
    COT_TEN_HSSV,
    COT_TEN_KH,
    COT_TEN_VC,
)
from tabs.tab_tracuu import _tim_mem


def _df_mau() -> pd.DataFrame:
    return pd.DataFrame(
        {
            COT_TEN_KH: ["NGUYỄN VĂN ĐỨC", "Trần Thị Hương", "Bùi Văn Nam"],
            COT_MA_KH: ["KH001", "KH002", "KH003"],
            COT_SO_KU: ["KU.01", "KU(02)", "KU03"],
            COT_CMND: ["012345678", "987654321", ""],
            COT_SDT: ["0901000001", "0901000002", "0901000003"],
            COT_TEN_HSSV: ["", "Lê Hồng Phúc", ""],
            COT_TEN_VC: ["", "", "Đỗ Thị Lan"],
        }
    )


class TestTracuuSearch:
    def test_normalize_search_text_bo_dau_va_chu_d(self):
        assert _normalize_search_text("  Nguyễn   Văn ĐỨC  ") == "nguyen van duc"

    def test_filter_panel_tim_ten_khong_dau(self):
        df = _df_mau()
        mask = _keyword_search_mask(df, "nguyen van duc", [COT_TEN_KH])
        assert df.loc[mask, COT_MA_KH].tolist() == ["KH001"]

    def test_filter_panel_tim_ten_co_dau_khac_hoa_thuong(self):
        df = _df_mau()
        mask = _keyword_search_mask(df, "trần thị hương", [COT_TEN_KH])
        assert df.loc[mask, COT_MA_KH].tolist() == ["KH002"]

    def test_filter_panel_tim_so_khe_uoc_literal(self):
        df = _df_mau()
        mask = _keyword_search_mask(df, "KU.01", [COT_SO_KU])
        assert df.loc[mask, COT_MA_KH].tolist() == ["KH001"]

    def test_legacy_tim_mem_tim_ten_va_truong_phu_khong_dau(self):
        df = _df_mau()
        cols = [COT_TEN_KH, COT_CMND, COT_SO_KU, COT_TEN_HSSV, COT_TEN_VC, COT_MA_KH]

        mask_ten = _tim_mem(df, cols, "bui van nam")
        mask_vc = _tim_mem(df, cols, "do thi lan")

        assert df.loc[mask_ten, COT_MA_KH].tolist() == ["KH003"]
        assert df.loc[mask_vc, COT_MA_KH].tolist() == ["KH003"]
