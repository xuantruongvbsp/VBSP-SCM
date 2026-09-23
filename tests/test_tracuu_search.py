from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from components.filter_panel import (
    _keyword_search_mask,
    _normalize_search_text,
    _detect_keyword_type,
    _data_cache_scope,
    _due_date_mask,
    _get_unique_values,
    _pre_compute_search_text,
    _resolve_du_no_range,
    _snapshot_filters,
    _restore_filters,
)
from tabs.tab_tracuu_v2 import (
    _build_theo_khach_hang,
    _clamp_page,
    _mask_cmnd,
    _mask_df_pii,
    _mask_kw_for_audit,
    _mask_sdt,
    _selection_default_for_page,
    _sort_mac_dinh,
)
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
    COT_LAI_TON,
    COT_SO_DU_TG,
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

    def test_cache_scope_khong_dung_lan_du_lieu(self):
        _get_unique_values.clear()
        _pre_compute_search_text.clear()
        df_a = pd.DataFrame({COT_TEN_KH: ["Alpha"], COT_MA_KH: ["A"]})
        df_b = pd.DataFrame({COT_TEN_KH: ["Beta"], COT_MA_KH: ["B"]})
        scope_a = _data_cache_scope(df_a, "PGD A", 0.0)
        scope_b = _data_cache_scope(df_b, "PGD B", 0.0)
        assert scope_a != scope_b
        assert _get_unique_values(df_a, COT_TEN_KH, 0.0, scope_a) == ["Alpha"]
        assert _get_unique_values(df_b, COT_TEN_KH, 0.0, scope_b) == ["Beta"]
        assert _pre_compute_search_text(
            df_a, (COT_TEN_KH,), 0.0, scope_a
        ).tolist() == ["alpha"]
        assert _pre_compute_search_text(
            df_b, (COT_TEN_KH,), 0.0, scope_b
        ).tolist() == ["beta"]

    def test_bucket_du_no_va_tu_nhap(self):
        assert _resolve_du_no_range("10–30 triệu", 0, 0, 500_000_000) == (
            10_000_000.0, 30_000_000.0,
        )
        assert _resolve_du_no_range("Tự nhập", 80, 20, 500_000_000) == (
            80_000_000.0, 80_000_000.0,
        )

    def test_den_han_va_qua_han_n_ngay(self):
        today = date(2026, 9, 23)
        values = pd.Series([
            today - timedelta(days=31),
            today - timedelta(days=5),
            today + timedelta(days=7),
            today + timedelta(days=31),
        ])
        assert _due_date_mask(values, qua_han_ngay=30, today=today).tolist() == [
            True, False, False, False,
        ]
        assert _due_date_mask(values, den_han_trong=7, today=today).tolist() == [
            False, False, True, False,
        ]

    def test_group_khach_hang_dem_va_cong_tien(self):
        df = pd.DataFrame({
            COT_MA_KH: ["KH1", "KH1", "KH2"],
            COT_TEN_KH: ["A", "A", "B"],
            COT_TONG_DU_NO: [10, 20, 30],
            COT_DU_NO_QH: [0, 5, 0],
            COT_LAI_TON: [1, 2, 3],
            COT_SO_DU_TG: [4, 5, 6],
        })
        out = _build_theo_khach_hang(df).set_index(COT_MA_KH)
        assert out.loc["KH1", "Số món vay"] == 2
        assert out.loc["KH1", f"{COT_TONG_DU_NO} (tổng)"] == 30
        assert out.loc["KH1", f"{COT_DU_NO_QH} (tổng)"] == 5

    def test_selection_phan_trang_va_clamp(self):
        assert _selection_default_for_page(205, 200, 400) == {
            "selection": {"rows": [5]}
        }
        assert _selection_default_for_page(205, 0, 200) is None
        assert _clamp_page(9, 3) == 3
        assert _clamp_page(0, 3) == 1

    def test_audit_mask_pii_trong_tu_khoa_nhieu_token(self):
        masked = _mask_kw_for_audit("012345678901 nguyen 0901000001")
        assert "012345678901" not in masked
        assert "0901000001" not in masked
        assert "nguyen" in masked
