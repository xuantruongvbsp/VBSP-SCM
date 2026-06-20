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
    from services.upload_service import KetQuaUpload
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

