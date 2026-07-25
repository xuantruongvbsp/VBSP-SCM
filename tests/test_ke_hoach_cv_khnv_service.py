from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

import db as db_module
from services import ke_hoach_cv_khnv_service as svc


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    db_file = str(tmp_path / "test.db")
    monkeypatch.setenv("VBSP_SCM_DB_PATH", db_file)
    db_module.reset_conn()
    db_module.init_db()
    yield db_module
    db_module.reset_conn()


def test_luu_config_luu_form_nhiem_vu_url(test_db):
    svc.luu_config(
        {
            "sheet_id": "sheet-1",
            "form_ke_hoach_url": "https://forms.gle/kh",
            "form_ket_qua_url": "https://forms.gle/kq",
            "form_nhiem_vu_url": "https://forms.gle/nv",
            "dau_viec_custom": [" A ", "", "B"],
        },
        "tester",
    )

    cfg = svc.doc_config()
    assert cfg["sheet_id"] == "sheet-1"
    assert cfg["form_nhiem_vu_url"] == "https://forms.gle/nv"
    assert cfg["dau_viec_custom"] == ["A", "B"]


def test_doc_nhiem_vu_gsheet_chuan_hoa(monkeypatch):
    rows = [
        [
            "Timestamp",
            "Mã nhiệm vụ",
            "Ngày giao",
            "Người giao",
            "Cán bộ nhận",
            "Nhóm công tác",
            "Nội dung nhiệm vụ",
            "Sản phẩm/Yêu cầu đầu ra",
            "Hạn hoàn thành",
            "Ưu tiên",
            "Trạng thái",
            "Ghi chú",
        ],
        [
            "25/07/2026 08:00",
            "NV-20260725-001",
            "25/07/2026",
            "TP KHNV",
            "Nguyễn Văn A",
            "Công tác tổng hợp",
            "Tổng hợp báo cáo",
            "File Excel",
            "26/07/2026",
            "Quan trọng",
            "Mới giao",
            "gấp",
        ],
    ]
    monkeypatch.setattr(svc, "_doc_raw_values_sheet", lambda tab, sheet_id=None: rows)

    df = svc.doc_nhiem_vu_gsheet()

    assert len(df) == 1
    assert df.iloc[0]["ma_nhiem_vu"] == "NV-20260725-001"
    assert df.iloc[0]["han"] == date(2026, 7, 26)
    assert df.iloc[0]["nguon"] == "Google Sheet"


def test_them_cap_nhat_xoa_nhiem_vu_app(test_db):
    item = svc.them_nhiem_vu_app(
        {
            "ngay_giao": date(2026, 7, 25),
            "nguoi_giao": "TP KHNV",
            "can_bo_nhan": "Nguyễn Văn A",
            "nhom_cong_tac": "Công tác tham mưu",
            "noi_dung": "Rà soát hồ sơ",
            "san_pham": "Danh sách lỗi",
            "han_hoan_thanh": date(2026, 7, 26),
            "uu_tien": "Quan trọng",
        },
        "tester",
    )

    df = svc.doc_nhiem_vu_app()
    assert len(df) == 1
    assert df.iloc[0]["ma_nhiem_vu"] == item["ma_nhiem_vu"]
    assert df.iloc[0]["nguon"] == "VBSP-SCM"

    assert svc.cap_nhat_trang_thai_nhiem_vu_app(
        item["ma_nhiem_vu"], "Hoàn thành", "Đã xong", "tester"
    )
    df_updated = svc.doc_nhiem_vu_app()
    assert df_updated.iloc[0]["trang_thai"] == "Hoàn thành"
    assert df_updated.iloc[0]["ghi_chu"] == "Đã xong"

    assert svc.xoa_nhiem_vu_app(item["ma_nhiem_vu"], "tester")
    assert svc.doc_nhiem_vu_app().empty


def test_them_nhiem_vu_app_validate_bat_buoc(test_db):
    with pytest.raises(ValueError, match="Thiếu cán bộ"):
        svc.them_nhiem_vu_app(
            {
                "noi_dung": "Rà soát hồ sơ",
                "han_hoan_thanh": date(2026, 7, 26),
            },
            "tester",
        )


def test_gop_nhiem_vu_uu_tien_app_va_tinh_kpi():
    df_app = pd.DataFrame(
        [
            {
                "ma_nhiem_vu": "NV-1",
                "can_bo_nhan": "A",
                "han_hoan_thanh": pd.Timestamp("2000-01-01"),
                "han": date(2000, 1, 1),
                "trang_thai": "Đang thực hiện",
                "nguon": "VBSP-SCM",
            }
        ]
    )
    df_gsheet = pd.DataFrame(
        [
            {
                "ma_nhiem_vu": "NV-1",
                "can_bo_nhan": "A",
                "han_hoan_thanh": pd.Timestamp("2000-01-01"),
                "han": date(2000, 1, 1),
                "trang_thai": "Hoàn thành",
                "nguon": "Google Sheet",
            },
            {
                "ma_nhiem_vu": "NV-2",
                "can_bo_nhan": "B",
                "han_hoan_thanh": pd.Timestamp("2099-01-01"),
                "han": date(2099, 1, 1),
                "trang_thai": "Hoàn thành",
                "nguon": "Google Sheet",
            },
        ]
    )

    df = svc.gop_nhiem_vu(df_app, df_gsheet)
    assert len(df) == 2
    nv1 = df[df["ma_nhiem_vu"] == "NV-1"].iloc[0]
    assert nv1["nguon"] == "VBSP-SCM"
    assert bool(nv1["qua_han"]) is True

    kpi = svc.tinh_tong_hop_nhiem_vu(df)
    assert kpi == {"tong": 2, "hoan_thanh": 1, "qua_han": 1, "dang_mo": 1}
