from __future__ import annotations

from datetime import date

import pandas as pd

from components.filter_panel import (
    _keyword_search_mask,
    _normalize_search_text,
    _detect_keyword_type,
    _snapshot_filters,
    _restore_filters,
)
from tabs.tab_tracuu_v2 import _mask_cmnd, _mask_sdt, _mask_df_pii, _sort_mac_dinh
from config import (
    COT_CMND,
    COT_MA_KH,
    COT_SDT,
    COT_SO_KU,
    COT_TEN_HSSV,
    COT_TEN_KH,
    COT_TEN_VC,
    COT_TONG_DU_NO,
    COT_DU_NO_QH,
)


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

    def test_tim_truong_phu_hssv_va_vo_chong_khong_dau(self):
        df = _df_mau()
        cols = [COT_TEN_KH, COT_CMND, COT_SO_KU, COT_TEN_HSSV, COT_TEN_VC, COT_MA_KH]
        mask_ten = _keyword_search_mask(df, "bui van nam", cols)
        mask_vc = _keyword_search_mask(df, "do thi lan", cols)
        assert df.loc[mask_ten, COT_MA_KH].tolist() == ["KH003"]
        assert df.loc[mask_vc, COT_MA_KH].tolist() == ["KH003"]

    def test_multi_token_and_phai_khop_tat_ca(self):
        df = _df_mau()
        # "nguyen" (KH001) và "huong" (KH002) → AND không ai khớp cả 2
        mask_and = _keyword_search_mask(df, "nguyen huong", [COT_TEN_KH], mode="AND")
        assert mask_and.sum() == 0
        # OR → khớp cả KH001 lẫn KH002
        mask_or = _keyword_search_mask(df, "nguyen huong", [COT_TEN_KH], mode="OR")
        assert set(df.loc[mask_or, COT_MA_KH].tolist()) == {"KH001", "KH002"}

    def test_detect_keyword_type(self):
        assert _detect_keyword_type("0901000001") == "Số điện thoại"
        assert _detect_keyword_type("012345678901") == "Số CCCD"
        assert _detect_keyword_type("KU.01") == "Số khế ước"
        assert _detect_keyword_type("nguyen van a") == "Tên khách hàng"

    def test_mask_pii(self):
        assert _mask_cmnd("012345678901") == "012******901"
        assert _mask_sdt("0901000001") == "09******01"
        assert _mask_cmnd("") == ""

    def test_mask_df_pii(self):
        df = pd.DataFrame({COT_CMND: ["012345678901"], COT_SDT: ["0901000001"], COT_TEN_KH: ["A"]})
        out = _mask_df_pii(df)
        assert out[COT_CMND].iloc[0] == "012******901"
        assert out[COT_SDT].iloc[0] == "09******01"
        assert out[COT_TEN_KH].iloc[0] == "A"  # cột không PII giữ nguyên

    def test_sort_mac_dinh_qh_desc_roi_dn_desc(self):
        df = pd.DataFrame(
            {
                COT_MA_KH: ["A", "B", "C"],
                COT_DU_NO_QH: [0, 5_000_000, 5_000_000],
                COT_TONG_DU_NO: [9_000_000, 1_000_000, 7_000_000],
            }
        )
        out = _sort_mac_dinh(df)
        # QH DESC trước: B & C (QH=5tr) lên trên A (QH=0); trong B,C → DN DESC: C(7tr) rồi B(1tr)
        assert out[COT_MA_KH].tolist() == ["C", "B", "A"]
        # index label đi theo dòng (C=2, B=1, A=0) → map vị trí iloc nhất quán
        assert list(out.index) == [2, 1, 0]

    def test_snapshot_restore_filters_roundtrip(self):
        f = {
            "search_keyword": "abc",
            "ngay_vay_from": date(2026, 1, 15),
            "ngay_vay_to": None,
            "du_no_range": (0.0, 500_000_000.0),
            "selected_pgd": ["PGD X"],
            "den_han_trong": 30,
        }
        snap = _snapshot_filters(f)
        # snapshot phải JSON-serializable: không còn date/tuple
        assert snap["ngay_vay_from"] == "2026-01-15"
        assert isinstance(snap["du_no_range"], list)
        import json
        json.dumps(snap)  # không raise
        back = _restore_filters(snap)
        assert back["ngay_vay_from"] == date(2026, 1, 15)
        assert back["ngay_vay_to"] is None
        assert back["du_no_range"] == (0.0, 500_000_000.0)
        assert back["den_han_trong"] == 30
