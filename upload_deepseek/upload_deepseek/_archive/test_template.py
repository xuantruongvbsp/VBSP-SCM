from docxtpl import DocxTemplate
from pathlib import Path

TEMPLATE_DIR = Path("templates")

tpl = DocxTemplate(TEMPLATE_DIR / "MẪU 06TD_Template.docx")

context = {
    "don_vi_kt": "Hội Nông dân xã Phước Tân",
    "can_bo_1": "Nguyễn Văn A",
    "chuc_vu_1": "Chủ tịch Hội",
    "can_bo_2": "Trần Thị B",
    "chuc_vu_2": "Phó Chủ tịch",
    "thoi_diem_kt": "14h00",
    "dia_ban": "Ấp 1, xã Phước Tân",
    "ten_to": "Tổ TK&VV số 3",
    "ngay": 6, "thang": 5, "nam": 2026,
    "ds_kh": [
        {
            "stt": 1,
            "ten_kh": "Nguyễn Văn C",
            "so_ku": "004601-001",
            "ten_ct": "Hộ nghèo",
            "muc_vay": "50,000,000",
            "du_no": "45,000,000",
            "muc_dich": "Chăn nuôi bò",
            "no_lai": "150,000",
        },
        {
            "stt": 2,
            "ten_kh": "Trần Thị D",
            "so_ku": "004601-002",
            "ten_ct": "Hộ cận nghèo",
            "muc_vay": "30,000,000",
            "du_no": "28,000,000",
            "muc_dich": "Trồng rau",
            "no_lai": "90,000",
        },
        {
            "stt": 3,
            "ten_kh": "Lê Văn E",
            "so_ku": "004601-003",
            "ten_ct": "GQVL",
            "muc_vay": "100,000,000",
            "du_no": "95,000,000",
            "muc_dich": "Mua máy may",
            "no_lai": "300,000",
        },
    ],
    "tong_muc_vay": "180,000,000",
    "tong_du_no": "168,000,000",
    "so_kh_kt": 3,
    "tong_tien_kt": "168,000,000",
    "so_kh_dung": 3,
    "tien_dung": "168,000,000",
    "ty_le_dung": "100",
    "so_kh_sai": 0,
    "tien_sai": "0",
    "ty_le_sai": "0",
    "nhan_xet_phuong_an": "Các hộ sử dụng vốn đúng mục đích",
    "bien_phap_xu_ly": "Không có",
    "can_bo_chung_kien": "",
}

tpl.render(context)
output = TEMPLATE_DIR / "TEST_mau_06td_output.docx"
tpl.save(str(output))
print(f"✅ Render thành công! File output: {output}")
