from __future__ import annotations

import pytest

import db as db_module
from services import khtd_service


def test_luu_khtd_dict_action_mapping(monkeypatch):
    calls = {"kv": [], "audit": []}

    def _ghi_kv(key, value, username):
        calls["kv"].append((key, value, username))

    def _ghi_audit(username, action, mo_ta):
        calls["audit"].append((username, action, mo_ta))

    monkeypatch.setattr(khtd_service.db, "ghi_kv", _ghi_kv)
    monkeypatch.setattr(khtd_service.db, "ghi_audit", _ghi_audit)

    khtd_service.luu_khtd_dict("khtd_cn", {"a": 1}, "u1")
    assert calls["audit"][-1][1] == "luu_khtd_cn"

    khtd_service.luu_khtd_dict("khtd_xa", {"x|1_TW": 100}, "u1")
    assert calls["audit"][-1][1] == "luu_khtd_cn"

    khtd_service.luu_khtd_dict("some_other_key", {"k": "v"}, "u1")
    assert calls["audit"][-1][1] == "luu_kv"


def test_luu_khtd_mau07_writes_three_keys(monkeypatch):
    calls = {"kv": [], "audit": [], "doc": []}

    def _doc_kv(key):
        calls["doc"].append(key)
        if key == "khtd_xa":
            return {"Xã A|1_TW": 1.0}
        return None

    def _ghi_kv(key, value, username):
        calls["kv"].append((key, value, username))

    def _ghi_audit(username, action, mo_ta):
        calls["audit"].append((username, action, mo_ta))

    monkeypatch.setattr(khtd_service.db, "doc_kv", _doc_kv)
    monkeypatch.setattr(khtd_service.db, "ghi_kv", _ghi_kv)
    monkeypatch.setattr(khtd_service.db, "ghi_audit", _ghi_audit)

    khtd_service.luu_khtd_mau07(
        pgd="PGD A",
        xa="Xã A",
        data_nhap={"Ấp 1|1_TW": 10.0, "Ấp 2|1_TW": 5.0},
        lich_su_moi=[{"lan": 1, "data": {"Ấp 1|1_TW": 10.0}}],
        username="u1",
        loai_van_ban="giao",
        lan_moi=1,
    )

    keys_written = [k for k, _, _ in calls["kv"]]
    assert any(k.startswith("khtd_ap_") for k in keys_written)
    assert any(k.startswith("khtd_ap_lich_su_") for k in keys_written)
    assert "khtd_xa" in keys_written
    assert all(a[1] == "luu_khtd_mau07" for a in calls["audit"])


# ── kv_key_mau07 ──────────────────────────────────────────────────────────────

def test_kv_key_mau07_returns_tuple_of_two():
    key_ht, key_ls = khtd_service.kv_key_mau07("PGD Long Thành", "Xã Phước Thái")
    assert key_ht.startswith("khtd_ap_")
    assert key_ls.startswith("khtd_ap_lich_su_")


def test_kv_key_mau07_consistent_slugging():
    key_ht_1, _ = khtd_service.kv_key_mau07("PGD Long Thành", "Xã A")
    key_ht_2, _ = khtd_service.kv_key_mau07("PGD Long Thành", "Xã A")
    assert key_ht_1 == key_ht_2


def test_kv_key_mau07_different_xa_different_key():
    key_a, _ = khtd_service.kv_key_mau07("PGD Long Thành", "Xã A")
    key_b, _ = khtd_service.kv_key_mau07("PGD Long Thành", "Xã B")
    assert key_a != key_b


# ── kv_key_dot ────────────────────────────────────────────────────────────────

def test_kv_key_dot_format():
    key = khtd_service.kv_key_dot("long_thanh", 2026, 5, "Dot1")
    assert key == "khtd_long_thanh_2026_05_Dot1"


def test_kv_key_dot_pads_month():
    key = khtd_service.kv_key_dot("long_thanh", 2026, 1, "Dot1")
    assert "_01_" in key


# ── _so_trieu_tu_oa ───────────────────────────────────────────────────────────

def test_so_trieu_tu_oa_numeric_string():
    assert khtd_service._so_trieu_tu_oa("1500") == 1500.0


def test_so_trieu_tu_oa_comma_separated():
    assert khtd_service._so_trieu_tu_oa("1,500") == 1500.0


def test_so_trieu_tu_oa_empty_string():
    assert khtd_service._so_trieu_tu_oa("") == 0.0


def test_so_trieu_tu_oa_none():
    assert khtd_service._so_trieu_tu_oa(None) == 0.0


def test_so_trieu_tu_oa_nan_string():
    assert khtd_service._so_trieu_tu_oa("nan") == 0.0


def test_so_trieu_tu_oa_float_value():
    assert khtd_service._so_trieu_tu_oa(250.5) == 250.5


# ── _du_lieu_chuyen_trieu_sang_vnd ────────────────────────────────────────────

def test_du_lieu_chuyen_trieu_sang_vnd_basic():
    data = [{"kh_tw": 100.0, "kh_dp": 50.0, "dc_tw": 10.0, "dc_dp": 5.0, "xa": "Xã A", "ma_key": "1_TW"}]
    result, loi = khtd_service._du_lieu_chuyen_trieu_sang_vnd("giao", data)
    assert len(result) == 1
    assert loi == []
    r = result[0]
    assert r["kh_tw"] == 100_000_000
    assert r["kh_dp"] == 50_000_000
    assert r["kh_moi_tw"] == 110_000_000
    assert r["kh_moi_dp"] == 55_000_000


def test_du_lieu_chuyen_trieu_sang_vnd_zero_dc():
    data = [{"kh_tw": 200.0, "kh_dp": 0.0, "dc_tw": 0.0, "dc_dp": 0.0}]
    result, loi = khtd_service._du_lieu_chuyen_trieu_sang_vnd("giao", data)
    assert loi == []
    r = result[0]
    assert r["kh_moi_tw"] == 200_000_000
    assert r["kh_moi_dp"] == 0.0


def test_du_lieu_chuyen_trieu_sang_vnd_empty_list():
    result, loi = khtd_service._du_lieu_chuyen_trieu_sang_vnd("giao", [])
    assert result == []
    assert loi == []


def test_du_lieu_chuyen_trieu_sang_vnd_kh_moi_am():
    # dc_tw âm quá lớn → kh_moi_tw < 0 → dòng bị bỏ qua, trả lỗi
    data = [{"kh_tw": 10.0, "kh_dp": 0.0, "dc_tw": -50.0, "dc_dp": 0.0, "xa": "Xã A", "ma_key": "1_TW"}]
    result, loi = khtd_service._du_lieu_chuyen_trieu_sang_vnd("dieu_chinh", data)
    assert result == []
    assert len(loi) == 1
    assert "âm" in loi[0]


# ── _parse_key_suffix ─────────────────────────────────────────────────────────

def test_parse_key_suffix_valid():
    result = khtd_service._parse_key_suffix("2026_05_Dot1")
    assert result == (2026, "05", "Dot1")


def test_parse_key_suffix_invalid():
    assert khtd_service._parse_key_suffix("invalid_format") is None
    assert khtd_service._parse_key_suffix("2026_5") is None


# ── kiem_tra_can_bang ─────────────────────────────────────────────────────────

@pytest.fixture
def test_db(tmp_path, monkeypatch):
    db_file = str(tmp_path / "test.db")
    monkeypatch.setenv("VBSP_SCM_DB_PATH", db_file)
    db_module.reset_conn()
    db_module.init_db()
    yield db_module
    db_module.reset_conn()


def test_kiem_tra_can_bang_empty_returns_empty(test_db):
    result = khtd_service.kiem_tra_can_bang(2026, "05", "Dot1")
    assert result == {}


def test_luu_dot_stores_payload(test_db):
    kq = khtd_service.luu_dot(
        pgd_slug="long_thanh",
        nam=2026,
        thang="05",
        dot="Dot1",
        loai="giao",
        du_lieu=[{"xa": "Xã A", "ma_key": "1_TW", "ten_ct": "CT1",
                  "nguon": "TW", "kh_tw": 100.0, "dc_tw": 0.0,
                  "kh_moi_tw": 100.0, "kh_dp": 0.0, "dc_dp": 0.0,
                  "kh_moi_dp": 0.0, "ly_do": ""}],
        username="tester",
    )
    assert kq.thanh_cong is True
    raw = test_db.doc_kv("khtd_long_thanh_2026_05_Dot1")
    assert raw is not None
    assert raw["loai"] == "giao"
    assert len(raw["du_lieu"]) == 1


def test_luu_dot_negative_kh_skipped(test_db):
    """Dòng có KH mới âm bị bỏ qua, vẫn thành công với 0 dòng hợp lệ."""
    kq = khtd_service.luu_dot(
        pgd_slug="long_thanh",
        nam=2026,
        thang="05",
        dot="Dot2",
        loai="dieu_chinh",
        du_lieu=[{"xa": "Xã A", "ma_key": "1_TW", "ten_ct": "CT1",
                  "nguon": "TW", "kh_tw": 10.0, "dc_tw": -50.0,
                  "kh_dp": 0.0, "dc_dp": 0.0, "ly_do": ""}],
        username="tester",
    )
    assert kq.thanh_cong is True
    raw = test_db.doc_kv("khtd_long_thanh_2026_05_Dot2")
    assert raw["du_lieu"] == []


def test_luu_dot_converts_to_vnd(test_db):
    """Giá trị nhập triệu → lưu VND (×1_000_000)."""
    khtd_service.luu_dot(
        pgd_slug="long_thanh",
        nam=2026,
        thang="06",
        dot="Dot1",
        loai="giao",
        du_lieu=[{"xa": "Xã A", "ma_key": "1_TW", "kh_tw": 200.0,
                  "dc_tw": 0.0, "kh_dp": 0.0, "dc_dp": 0.0, "ly_do": ""}],
        username="tester",
    )
    raw = test_db.doc_kv("khtd_long_thanh_2026_06_Dot1")
    assert raw["du_lieu"][0]["kh_tw"] == 200_000_000
    assert raw["du_lieu"][0]["kh_moi_tw"] == 200_000_000


def test_luu_dot_xa_respects_explicit_empty_status(test_db):
    key = khtd_service.kv_key_dot("test_pgd", 2026, "05", "Dot1")
    test_db.ghi_kv(
        key,
        {
            "loai": "giao",
            "xa_da_nhap": [],
            "du_lieu": [
                {"xa": "Xã B", "ma_key": "2_TW", "ten_ct": "CT2",
                 "nguon": "TW", "kh_tw": 10_000_000, "dc_tw": 0,
                 "kh_moi_tw": 10_000_000, "kh_dp": 0, "dc_dp": 0,
                 "kh_moi_dp": 0, "ly_do": ""}
            ],
        },
        "seed",
    )

    kq = khtd_service.luu_dot_xa(
        "test_pgd", "Xã A", 2026, "05", "Dot1", "giao",
        [{"xa": "Xã A", "ma_key": "1_TW", "ten_ct": "CT1",
          "nguon": "TW", "kh_tw": 100.0, "dc_tw": 0.0,
          "kh_dp": 0.0, "dc_dp": 0.0, "ly_do": ""}],
        "tester",
    )

    raw = test_db.doc_kv(key)
    assert kq.thanh_cong is True
    assert raw["xa_da_nhap"] == ["Xã A"]
    assert {r["xa"] for r in raw["du_lieu"]} == {"Xã A", "Xã B"}
    assert next(r for r in raw["du_lieu"] if r["xa"] == "Xã A")["kh_moi_tw"] == 100_000_000


def test_trang_thai_xa_empty_list_does_not_fallback_to_du_lieu(test_db, monkeypatch):
    monkeypatch.setattr(khtd_service, "_slug_to_ten_dv", lambda _slug: "PGD Test")
    monkeypatch.setattr(khtd_service, "PGD_XA_MAP", {"PGD Test": ["Xã A", "Xã B"]})
    test_db.ghi_kv(
        khtd_service.kv_key_dot("test_pgd", 2026, "05", "Dot2"),
        {"loai": "giao", "xa_da_nhap": [], "du_lieu": [{"xa": "Xã A"}]},
        "seed",
    )

    assert khtd_service.trang_thai_xa("test_pgd", 2026, "05", "Dot2") == {
        "Xã A": False,
        "Xã B": False,
    }


def test_trang_thai_xa_legacy_payload_missing_field_fallbacks(test_db, monkeypatch):
    monkeypatch.setattr(khtd_service, "_slug_to_ten_dv", lambda _slug: "PGD Test")
    monkeypatch.setattr(khtd_service, "PGD_XA_MAP", {"PGD Test": ["Xã A", "Xã B"]})
    test_db.ghi_kv(
        khtd_service.kv_key_dot("test_pgd", 2026, "05", "Dot3"),
        {"loai": "giao", "du_lieu": [{"xa": "Xã A"}]},
        "seed",
    )

    assert khtd_service.trang_thai_xa("test_pgd", 2026, "05", "Dot3") == {
        "Xã A": True,
        "Xã B": False,
    }


# ── _dot_sort_key ─────────────────────────────────────────────────────────────

def test_dot_sort_key_numeric_order():
    k1 = khtd_service._dot_sort_key("Dot1")
    k2 = khtd_service._dot_sort_key("Dot2")
    k10 = khtd_service._dot_sort_key("Dot10")
    assert k1 < k2 < k10


def test_dot_sort_key_non_numeric_last():
    k_num = khtd_service._dot_sort_key("Dot1")
    k_str = khtd_service._dot_sort_key("ThuongXuyen")
    assert k_num < k_str


def test_dot_sort_key_case_insensitive():
    assert khtd_service._dot_sort_key("DOT1") == khtd_service._dot_sort_key("dot1")


# ── lay_dot_truoc ─────────────────────────────────────────────────────────────

def test_lay_dot_truoc_returns_none_when_empty(test_db):
    result = khtd_service.lay_dot_truoc("long_thanh", 2026, "05", "Dot1")
    assert result is None


def test_lay_dot_truoc_finds_earlier_dot(test_db):
    # Lưu Dot1, sau đó hỏi Dot2 → phải tìm được Dot1
    khtd_service.luu_dot("long_thanh", 2026, "05", "Dot1", "giao",
                          [{"xa": "X", "ma_key": "1_TW", "kh_tw": 100.0, "dc_tw": 0.0,
                            "kh_dp": 0.0, "dc_dp": 0.0, "ly_do": ""}], "tester")
    result = khtd_service.lay_dot_truoc("long_thanh", 2026, "05", "Dot2")
    assert result is not None
    assert result["loai"] == "giao"


def test_lay_dot_truoc_same_dot_not_returned(test_db):
    khtd_service.luu_dot("long_thanh", 2026, "05", "Dot1", "giao",
                          [{"xa": "X", "ma_key": "1_TW", "kh_tw": 50.0, "dc_tw": 0.0,
                            "kh_dp": 0.0, "dc_dp": 0.0, "ly_do": ""}], "tester")
    # Hỏi Dot1 — không được trả về chính nó
    result = khtd_service.lay_dot_truoc("long_thanh", 2026, "05", "Dot1")
    assert result is None


# ── tong_hop ─────────────────────────────────────────────────────────────────

def _tong_hop_direct(nam, thang, dot):
    """Gọi tong_hop không qua cache — dùng trong test."""
    import pandas as pd
    from services.khtd_service import _kv_key, ds_slug
    cols = ["pgd_slug", "xa", "ma_key", "ten_ct", "nguon", "loai",
            "kh_tw", "dc_tw", "kh_moi_tw", "kh_dp", "dc_dp", "kh_moi_dp", "ly_do"]
    rows = []
    for pgd_s in ds_slug():
        key = _kv_key(pgd_s, nam, thang, dot)
        raw = db_module.doc_kv(key)
        if not raw or not isinstance(raw, dict):
            continue
        loai = raw.get("loai") or ""
        for item in raw.get("du_lieu") or []:
            if not isinstance(item, dict):
                continue
            row = {"pgd_slug": pgd_s, "loai": loai}
            for c in ("xa", "ma_key", "ten_ct", "nguon", "kh_tw", "dc_tw",
                      "kh_moi_tw", "kh_dp", "dc_dp", "kh_moi_dp", "ly_do"):
                row[c] = item.get(c)
            rows.append(row)
    return pd.DataFrame(rows, columns=cols) if rows else pd.DataFrame(columns=cols)


def test_tong_hop_empty_returns_empty_dataframe(test_db):
    df = _tong_hop_direct(2026, "99", "Dot99")
    assert df.empty
    assert "pgd_slug" in df.columns


def test_tong_hop_with_data(test_db, monkeypatch):
    """tong_hop trả về DataFrame có dữ liệu từ kv_store (via hoi_so slug)."""
    khtd_service.luu_dot("hoi_so", 2026, "05", "Dot1", "giao",
                          [{"xa": "Xã A", "ma_key": "1_TW", "ten_ct": "CT1",
                            "nguon": "TW", "kh_tw": 100.0, "dc_tw": 0.0,
                            "kh_dp": 0.0, "dc_dp": 0.0, "ly_do": ""}], "tester")
    df = _tong_hop_direct(2026, "05", "Dot1")
    assert not df.empty
    assert df["pgd_slug"].iloc[0] == "hoi_so"
    assert df["ma_key"].iloc[0] == "1_TW"


# ── kiem_tra_can_bang với data ────────────────────────────────────────────────

def test_kiem_tra_can_bang_balanced(monkeypatch):
    """Điều chỉnh cân bằng giữa 2 PGD (dc_tw bù trừ nhau → cân bằng)."""
    import pandas as pd
    df_fake = pd.DataFrame([
        {"pgd_slug": "a", "loai": "dieu_chinh", "ma_key": "2_TW",
         "dc_tw": 10_000_000, "dc_dp": 0},
        {"pgd_slug": "b", "loai": "dieu_chinh", "ma_key": "2_TW",
         "dc_tw": -10_000_000, "dc_dp": 0},
    ])
    monkeypatch.setattr(khtd_service, "tong_hop", lambda *a, **kw: df_fake)

    result = khtd_service.kiem_tra_can_bang(2026, "05", "Dot1")
    assert "2_TW" in result
    assert result["2_TW"]["can_bang"] is True
    assert abs(result["2_TW"]["tong_dc_tw"]) <= 1_000_000


def test_kiem_tra_can_bang_unbalanced(monkeypatch):
    """Điều chỉnh lệch → can_bang = False."""
    import pandas as pd
    df_fake = pd.DataFrame([
        {"pgd_slug": "a", "loai": "dieu_chinh", "ma_key": "2_TW",
         "dc_tw": 50_000_000, "dc_dp": 0},
    ])
    monkeypatch.setattr(khtd_service, "tong_hop", lambda *a, **kw: df_fake)

    result = khtd_service.kiem_tra_can_bang(2026, "06", "Dot1")
    assert "2_TW" in result
    assert result["2_TW"]["can_bang"] is False


# ── duyet ─────────────────────────────────────────────────────────────────────

def test_duyet_da_duyet(test_db):
    khtd_service.luu_dot("long_thanh", 2026, "05", "Dot1", "giao",
                          [{"xa": "X", "ma_key": "1_TW", "kh_tw": 100.0, "dc_tw": 0.0,
                            "kh_dp": 0.0, "dc_dp": 0.0, "ly_do": ""}], "tester")
    khtd_service.duyet("long_thanh", 2026, "05", "Dot1", "da_duyet", "OK", "admin")
    raw = test_db.doc_kv("khtd_long_thanh_2026_05_Dot1")
    assert raw["trang_thai"] == "da_duyet"
    assert raw["nguoi_duyet"] == "admin"
    assert raw["y_kien_duyet"] == "OK"


def test_duyet_tu_choi(test_db):
    khtd_service.luu_dot("long_thanh", 2026, "05", "Dot2", "giao",
                          [{"xa": "X", "ma_key": "1_TW", "kh_tw": 100.0, "dc_tw": 0.0,
                            "kh_dp": 0.0, "dc_dp": 0.0, "ly_do": ""}], "tester")
    khtd_service.duyet("long_thanh", 2026, "05", "Dot2", "tu_choi", "Sai số liệu", "admin")
    raw = test_db.doc_kv("khtd_long_thanh_2026_05_Dot2")
    assert raw["trang_thai"] == "tu_choi"
    assert raw["y_kien_duyet"] == "Sai số liệu"


def test_duyet_invalid_status_no_change(test_db):
    """trang_thai không hợp lệ → không ghi gì vào DB."""
    khtd_service.luu_dot("long_thanh", 2026, "07", "Dot1", "giao",
                          [{"xa": "X", "ma_key": "1_TW", "kh_tw": 100.0, "dc_tw": 0.0,
                            "kh_dp": 0.0, "dc_dp": 0.0, "ly_do": ""}], "tester")
    khtd_service.duyet("long_thanh", 2026, "07", "Dot1", "trang_thai_la", "...", "admin")
    raw = test_db.doc_kv("khtd_long_thanh_2026_07_Dot1")
    # trang_thai vẫn là "cho_duyet" do ghi từ luu_dot
    assert raw["trang_thai"] == "cho_duyet"


def test_duyet_missing_data_noop(test_db):
    """Duyệt key không tồn tại → không raise exception."""
    khtd_service.duyet("khong_ton_tai", 2026, "05", "Dot99", "da_duyet", "", "admin")


# ── _sync_khtd_xa_from_ap ────────────────────────────────────────────────────

def test_sync_khtd_xa_from_ap_accumulates(test_db):
    """Tổng hợp data_ap → cập nhật khtd_xa đúng."""
    data_ap = {
        "Ấp 1|1_TW": 100.0,
        "Ấp 2|1_TW": 50.0,
        "Ấp 1|2_DP": 30.0,
    }
    khtd_service._sync_khtd_xa_from_ap("Xã A", data_ap, "tester")
    kv_xa = test_db.doc_kv("khtd_xa")
    assert kv_xa is not None
    assert kv_xa.get("Xã A|1_TW") == 150.0
    assert kv_xa.get("Xã A|2_DP") == 30.0

