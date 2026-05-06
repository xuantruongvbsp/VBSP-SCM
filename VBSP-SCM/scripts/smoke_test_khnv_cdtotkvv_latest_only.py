from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import data.cdtotkvv as cdtotkvv_mod
import data.pgd as pgd_mod
import tabs.tab_upload_khnv as mod


class FakeSpinner:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeCacheData:
    def clear(self) -> None:
        return None


class FakeColumn:
    def info(self, *_args, **_kwargs) -> None:
        return None

    def success(self, *_args, **_kwargs) -> None:
        return None

    def warning(self, *_args, **_kwargs) -> None:
        return None


class FakeSt:
    def __init__(self):
        self.session_state: dict = {}
        self.cache_data = FakeCacheData()
        self.rerun_called = False

    def columns(self, n: int):
        return [FakeColumn() for _ in range(n)]

    def divider(self) -> None:
        return None

    def spinner(self, _msg: str):
        return FakeSpinner()

    def success(self, *_args, **_kwargs) -> None:
        return None

    def warning(self, *_args, **_kwargs) -> None:
        return None

    def rerun(self) -> None:
        self.rerun_called = True


class FakeFile:
    def __init__(self, name: str, payload: bytes):
        self.name = name
        self._payload = payload
        self._read_count = 0

    def read(self) -> bytes:
        # _xu_ly_upload chỉ đọc 1 lần; lần sau trả rỗng như UploadedFile thực tế.
        if self._read_count > 0:
            return b""
        self._read_count += 1
        return self._payload


def main() -> int:
    fake_st = FakeSt()
    mod.st = fake_st

    # Patch dependency functions used inside _xu_ly_upload
    mod.kiem_tra_file = lambda _name, _bytes: (True, "OK")
    mod._kiem_tra_don_vi = lambda _bytes, _loai, _ten: (True, "OK")
    mod.danh_gia_chat_luong_file_upload = lambda _loai, _bytes: (True, "OK", {"ti_le_dat_chuan": 100})
    mod.db.ghi_audit = lambda *_args, **_kwargs: None

    calls: dict[str, int] = {"latest": 0, "history": 0}

    def _fake_luu_latest(_ten_dv: str, _loai: str, _bytes: bytes) -> str:
        calls["latest"] += 1
        return "fake/latest.xlsx"

    def _fake_luu_history(_ten_dv: str, _loai: str, _bytes: bytes, _thang: str) -> str:
        calls["history"] += 1
        return "fake/latest.xlsx"

    pgd_mod.luu_file_pgd = _fake_luu_latest
    pgd_mod.luu_file_pgd_voi_lich_su = _fake_luu_history
    cdtotkvv_mod.doc_thang_nam_tu_file = lambda _bytes: None  # ép fallback thang_luu=None

    f_cdtotkvv = FakeFile("CT_CDTOTKVV_004604_30042026.xlsx", b"dummy-xlsx-content")

    mod._xu_ly_upload(
        ten_dv="PGD Long Khanh",
        username="smoke_test",
        f_hstd=None,
        f_nq11=None,
        f_gqvl=None,
        f_cdtotkvv=f_cdtotkvv,
        prefix="smoke",
        thang_cdtotkvv_override=None,
    )

    kq = fake_st.session_state.get("khnv_ket_qua_upload", {}).get("cdtotkvv", {})
    thong_bao = str(kq.get("thong_bao", ""))
    ok_msg = "chi luu latest" in thong_bao.lower() or "chỉ lưu latest" in thong_bao.lower()
    ok_calls = calls["latest"] == 1 and calls["history"] == 0
    ok_rerun = fake_st.rerun_called

    assert ok_msg, f"Thong bao khong dung ky vong: {thong_bao}"
    assert ok_calls, f"So lan goi luu sai: {calls}"
    assert ok_rerun, "Khong goi st.rerun()"

    print("PASS: KHNV fallback thang_luu=None -> latest only message + latest saver called.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
