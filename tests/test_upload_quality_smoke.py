import unittest
import os
import tempfile

os.environ.setdefault(
    "VBSP_SCM_DB_PATH",
    os.path.join(tempfile.gettempdir(), "vbsp_scm_unittest.db"),
)

from services.upload_service import danh_gia_chat_luong_file_upload
from tests.fixtures import tao_file_hstd_hop_le


class TestUploadQualitySmoke(unittest.TestCase):
    def _tao_file_hstd_hop_le(self) -> bytes:
        return tao_file_hstd_hop_le()

    def test_danh_gia_hstd_hop_le(self) -> None:
        file_bytes = self._tao_file_hstd_hop_le()
        ok, msg, bao_cao = danh_gia_chat_luong_file_upload("hstd", file_bytes)
        self.assertTrue(ok, msg)
        self.assertEqual(bao_cao.get("so_loi", -1), 0)


if __name__ == "__main__":
    unittest.main()
