"""Unit test cho services/template_service.py — xử lý template Word."""
import os
import tempfile
import unittest
from io import BytesIO
from pathlib import Path


class TestTemplateService(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from services import template_service
        cls.ts = template_service
        cls.TEMPLATE_DIR = cls.ts.TEMPLATE_DIR

    def test_co_template_ton_tai(self) -> None:
        path = self.TEMPLATE_DIR / self.ts.TMPL_MAU06
        if path.exists():
            self.assertTrue(self.ts.co_template(self.ts.TMPL_MAU06))
        else:
            self.assertFalse(self.ts.co_template(self.ts.TMPL_MAU06))

    def test_co_template_khong_ton_tai(self) -> None:
        self.assertFalse(self.ts.co_template("khong_co_file_nay.docx"))

    def test_dien_template_file_not_found(self) -> None:
        with self.assertRaises(FileNotFoundError):
            self.ts.dien_template("khong_co_file_nay.docx", {})

    def test_docx_to_pdf_khong_co_word(self) -> None:
        result = self.ts.docx_to_pdf(b"dummy docx content")
        self.assertIsNone(result)

    def test_docx_bytes_to_pdf_khong_co_word(self) -> None:
        result = self.ts.docx_bytes_to_pdf(b"dummy docx content")
        self.assertIsNone(result)

    def test_template_constants_defined(self) -> None:
        self.assertIsNotNone(self.ts.TMPL_MAU06)
        self.assertIsNotNone(self.ts.TMPL_MAU15)
        self.assertIsNotNone(self.ts.TMPL_MAU16)
        self.assertIsNotNone(self.ts.TMPL_KH_KT)


class TestTemplateServiceRender(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from services import template_service
        cls.ts = template_service

    def _tao_file_docx_tam(self) -> str:
        from docx import Document as TaoDocx
        tmp_dir = Path(tempfile.mkdtemp())
        tmpl_path = tmp_dir / "test_template.docx"
        doc = TaoDocx()
        doc.add_paragraph("Hello {{ name }}")
        doc.save(str(tmpl_path))
        return str(tmpl_path)

    def test_dien_template_voi_context_don_gian(self) -> None:
        tmpl_path = self._tao_file_docx_tam()
        try:
            result = self.ts.dien_template(tmpl_path, {"name": "World"})
            self.assertIsInstance(result, bytes)
            self.assertGreater(len(result), 0)
        finally:
            import shutil
            shutil.rmtree(Path(tmpl_path).parent, ignore_errors=True)

    def test_dien_template_tra_ve_bytes(self) -> None:
        tmpl_path = self._tao_file_docx_tam()
        try:
            result = self.ts.dien_template(tmpl_path, {})
            self.assertGreater(len(result), 0)
        finally:
            import shutil
            shutil.rmtree(Path(tmpl_path).parent, ignore_errors=True)


class TestTemplateServiceConstants(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from services import template_service
        cls.ts = template_service

    def test_tmpl_mau06a_defined(self) -> None:
        self.assertTrue(hasattr(self.ts, "TMPL_MAU06A"))

    def test_tmpl_13xln_defined(self) -> None:
        self.assertTrue(hasattr(self.ts, "TMPL_13XLN"))

    def test_tmpl_14xln_defined(self) -> None:
        self.assertTrue(hasattr(self.ts, "TMPL_14XLN"))

    def test_tmpl_tt_khoanh_defined(self) -> None:
        self.assertTrue(hasattr(self.ts, "TMPL_TT_KHOANH"))

    def test_tmpl_tt_xoa_defined(self) -> None:
        self.assertTrue(hasattr(self.ts, "TMPL_TT_XOA"))

    def test_tmpl_bb_xmn_defined(self) -> None:
        self.assertTrue(hasattr(self.ts, "TMPL_BB_XMN"))


if __name__ == "__main__":
    unittest.main()
