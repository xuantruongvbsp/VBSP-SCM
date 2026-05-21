from __future__ import annotations

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

