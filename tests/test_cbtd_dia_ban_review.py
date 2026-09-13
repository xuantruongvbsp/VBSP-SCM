from __future__ import annotations

import pandas as pd

from config import (
    COT_CQH_NAM,
    COT_CHUYEN_QH_TRONG_THANG,
    COT_DU_NO_QH,
    COT_DU_NO_TH,
    COT_DU_NO_KHOANH,
    COT_GIAI_NGAN_NAM,
    COT_GIAI_NGAN_TRONG_THANG,
    COT_HINH_THUC_VAY,
    COT_NGAY_GN_DAU_TIEN,
    COT_NGAY_VAY,
    COT_NGAY_DEN_HAN,
    COT_GOC_DEN_HAN_LK,
    COT_MA_KH,
    COT_MA_THON,
    COT_NGAY_SL,
    COT_SO_KU,
    COT_TEN_CT,
    COT_TEN_THON,
    COT_TEN_XA,
    COT_TEN_PGD,
    COT_TONG_DU_NO,
    COT_THU_NO_KHOANH_NAM,
    COT_THU_NO_KHOANH_THANG,
    COT_THU_NO_QH_NAM,
    COT_THU_NO_QH_THANG,
    COT_THU_NO_TH_NAM,
    COT_THU_NO_TH_THANG,
)
from data.khtd import gan_cbtd_vao_df
from services.cbtd_dia_ban_service import (
    _normalize,
    tong_hop_hstd_cbtd_xa_chuong_trinh,
    tong_hop_hstd_theo_cbtd,
    tong_hop_hstd_theo_thon,
    tong_hop_thon_snapshot_theo_cbtd,
)
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
    assert cb01["Cho_vay_thang"] == 0
    assert cb01["Thu_no_thang"] == 0
    assert cb01["No_den_han_mon"] == 0
    assert cb01["So_mon_3m_khd"] == 0
    assert cb01["So_mon_rui_ro"] == 2
    assert cb01["So_KH_moi_thang"] == 1
    assert cb01["So_giai_ngan_thang"] == 1
    assert cb02["Tong_du_no"] == 300_000_000
    assert cb03["Tong_du_no"] == 0
    assert "Chưa gán ĐGD" in cb03["Canh_bao"]


def test_tong_hop_hstd_cbtd_xa_chuong_trinh_giong_mau_rpt():
    cbtd_data = {
        "CB01": {"ho_ten": "Nguyễn Văn A", "pgd": "PGD A", "ds_dgd": ["ĐGD 1"]},
        "CB02": {"ho_ten": "Trần Thị B", "pgd": "PGD A", "ds_dgd": ["ĐGD 2"]},
    }
    dgd_map = {
        "PGD A": {
            "Xã A": {"ĐGD 1": {"thon": ["Thôn 1"]}},
            "Xã B": {"ĐGD 2": {"thon": ["Thôn 2"]}},
        }
    }
    df_hstd = pd.DataFrame({
        COT_TEN_XA: ["Xã A", "Xã A", "Xã B"],
        COT_TEN_THON: ["Thôn 1", "Thôn 1", "Thôn 2"],
        COT_TEN_CT: ["CT A", "CT B", "CT A"],
        COT_MA_KH: ["KH01", "KH02", "KH03"],
        COT_SO_KU: ["KU01", "KU02", "KU03"],
        COT_TONG_DU_NO: [100_000_000, 200_000_000, 300_000_000],
        COT_DU_NO_TH: [90_000_000, 180_000_000, 300_000_000],
        COT_DU_NO_QH: [10_000_000, 20_000_000, 0],
        COT_DU_NO_KHOANH: [0, 0, 0],
        COT_GIAI_NGAN_TRONG_THANG: [20_000_000, 0, 10_000_000],
        COT_THU_NO_TH_THANG: [5_000_000, 1_000_000, 0],
        COT_THU_NO_QH_THANG: [2_000_000, 0, 0],
        COT_THU_NO_KHOANH_THANG: [1_000_000, 0, 0],
        COT_GIAI_NGAN_NAM: [50_000_000, 5_000_000, 10_000_000],
        COT_THU_NO_TH_NAM: [15_000_000, 1_000_000, 0],
        COT_THU_NO_QH_NAM: [3_000_000, 0, 0],
        COT_THU_NO_KHOANH_NAM: [2_000_000, 0, 0],
        COT_CHUYEN_QH_TRONG_THANG: [4_000_000, 0, 0],
        COT_CQH_NAM: [6_000_000, 0, 0],
        COT_HINH_THUC_VAY: [2, 2, 1],
    })

    out = tong_hop_hstd_cbtd_xa_chuong_trinh(cbtd_data, dgd_map, df_hstd)

    assert list(out["Mã CBTD"].unique()) == ["CB01"]
    assert set(out["Chương trình"]) == {"CT A", "CT B"}
    row = out[out["Chương trình"] == "CT A"].iloc[0]
    assert row["Tên xã quản lý"] == "Xã A"
    assert row["KH vay vốn"] == 1
    assert row["Món vay"] == 1
    assert row["Tổng dư nợ (triệu)"] == 100
    assert row["Trong hạn (triệu)"] == 90
    assert row["Quá hạn (triệu)"] == 10
    assert row["Cho vay tháng (triệu)"] == 20
    assert row["Thu nợ tháng (triệu)"] == 8
    assert row["DN tăng/giảm tháng (triệu)"] == 12
    assert row["DN tăng/giảm năm (triệu)"] == 30
    assert row["QH tăng/giảm tháng (triệu)"] == 2
    assert row["QH tăng/giảm năm (triệu)"] == 3
    assert row["Tỷ lệ QH %"] == 10.0


def test_tong_hop_hstd_theo_thon_va_gan_lai_cbtd():
    df_hstd = pd.DataFrame({
        COT_TEN_PGD: ["PGD A", "PGD A", "PGD A"],
        COT_MA_THON: ["101", "101", "102"],
        COT_TEN_XA: ["Xã A", "Xã A", "Xã B"],
        COT_TEN_THON: ["Thôn 1", "Thôn 1", "Thôn 2"],
        COT_SO_KU: ["KU01", "KU02", "KU03"],
        COT_TONG_DU_NO: [100_000_000, 200_000_000, 300_000_000],
        COT_DU_NO_QH: [10_000_000, 0, 0],
        COT_GIAI_NGAN_TRONG_THANG: [20_000_000, 0, 30_000_000],
        COT_THU_NO_TH_THANG: [5_000_000, 0, 0],
        COT_THU_NO_QH_THANG: [0, 0, 0],
        COT_THU_NO_KHOANH_THANG: [0, 0, 0],
        COT_GOC_DEN_HAN_LK: [100_000_000, 200_000_000, 300_000_000],
        COT_HINH_THUC_VAY: [2, 2, 2],
        COT_NGAY_DEN_HAN: ["2026-09-15", "2026-09-20", "2026-08-01"],
        COT_NGAY_SL: ["30/09/2026", "30/09/2026", "29/09/2026"],
    })

    thon = tong_hop_hstd_theo_thon(df_hstd, yyyy=2026, mm=9)
    row_a = thon[thon["Ten_thon"] == "Thôn 1"].iloc[0]
    assert row_a["Tong_du_no"] == 300_000_000
    assert row_a["Du_no_qh"] == 10_000_000
    assert row_a["Cho_vay_thang"] == 20_000_000
    assert row_a["Thu_no_thang"] == 5_000_000
    assert row_a["No_den_han_mon"] == 2
    assert row_a["No_den_han_goc"] == 300_000_000
    assert row_a["So_mon_rui_ro"] == 1

    cbtd_data = {
        "CB01": {"ho_ten": "A", "pgd": "PGD A", "ds_dgd": ["ĐGD 1"]},
        "CB02": {"ho_ten": "B", "pgd": "PGD A", "ds_dgd": ["ĐGD 2"]},
    }
    dgd_map = {
        "PGD A": {
            "Xã A": {"ĐGD 1": {"thon": ["Thôn 1"], "ma_thon": ["101"]}},
            "Xã B": {"ĐGD 2": {"thon": ["Thôn 2"], "ma_thon": ["102"]}},
        }
    }

    # Giả lập doc_thon_snapshot (cột chữ thường)
    thon_snap = thon.rename(columns={
        "Ten_pgd": "ten_pgd", "Ma_thon": "ma_thon",
        "Ten_xa": "ten_xa", "Ten_thon": "ten_thon",
        "Tong_du_no": "tong_du_no", "Du_no_qh": "du_no_qh",
        "Cho_vay_thang": "cho_vay_thang", "Thu_no_thang": "thu_no_thang",
        "No_den_han_mon": "no_den_han_mon", "No_den_han_goc": "no_den_han_goc",
        "So_mon_3m_khd": "so_mon_3m_khd", "So_mon_rui_ro": "so_mon_rui_ro",
    })
    cbtd = tong_hop_thon_snapshot_theo_cbtd(thon_snap, cbtd_data, dgd_map)
    cb01 = cbtd[cbtd["ma_cb"] == "CB01"].iloc[0]
    assert cb01["tong_du_no"] == 300_000_000
    assert cb01["du_no_qh"] == 10_000_000
    assert cb01["cho_vay_thang"] == 20_000_000
    assert cb01["no_den_han_mon"] == 2
    assert cb01["so_mon_rui_ro"] == 1


def test_gan_cbtd_khong_lan_hai_pgd_trung_ma_va_ten_thon():
    cbtd_data = {
        "CB_A": {"ho_ten": "A", "pgd": "PGD A", "ds_dgd": ["ĐGD A"]},
        "CB_B": {"ho_ten": "B", "pgd": "PGD B", "ds_dgd": ["ĐGD B"]},
    }
    dgd_map = {
        "PGD A": {"Xã Chung": {"ĐGD A": {"thon": ["Thôn Chung"], "ma_thon": ["101"]}}},
        "PGD B": {"Xã Chung": {"ĐGD B": {"thon": ["Thôn Chung"], "ma_thon": ["101"]}}},
    }
    df = pd.DataFrame({
        COT_TEN_PGD: ["PGD A", "PGD B"],
        COT_MA_THON: ["101", "101"],
        COT_TEN_XA: ["Xã Chung", "Xã Chung"],
        COT_TEN_THON: ["Thôn Chung", "Thôn Chung"],
    })

    out = gan_cbtd_vao_df(df, cbtd_data, dgd_map)

    assert out["CBTD"].tolist() == ["CB_A", "CB_B"]


def test_snapshot_thon_cu_thieu_pgd_chi_gan_khi_key_duy_nhat():
    cbtd_data = {
        "CB_A": {"ho_ten": "A", "pgd": "PGD A", "ds_dgd": ["ĐGD A"]},
        "CB_B": {"ho_ten": "B", "pgd": "PGD B", "ds_dgd": ["ĐGD B"]},
    }
    dgd_map = {
        "PGD A": {"Xã Chung": {"ĐGD A": {"thon": ["Thôn Chung"]}}},
        "PGD B": {"Xã Chung": {"ĐGD B": {"thon": ["Thôn Chung"]}}},
    }
    legacy = pd.DataFrame({
        "ten_pgd": ["__UNKNOWN__"], "ma_thon": [""],
        "ten_xa": ["Xã Chung"], "ten_thon": ["Thôn Chung"], "tong_du_no": [100],
    })

    out = tong_hop_thon_snapshot_theo_cbtd(legacy, cbtd_data, dgd_map)

    assert out.empty
