import sys, os
os.chdir('D:/VBSP-SCM')
sys.path.insert(0, '.')

print('1. Importing tabs.pdf_no_khoanh...')
from tabs.pdf_no_khoanh import (
    _REPORTLAB_READY, _FN, _FB,
    _dang_ky_font_qlnk, _tim_logo_qlnk,
    _xuat_pdf_mau_02qlnk, _xuat_pdf_mau_kh,
    _xuat_pdf_mau_01qlnk, _xuat_pdf_mau_03qlnk,
    _xuat_pdf_mau_04qlnk,
    _xuat_pdf_ke_hoach_kt,
    _dong_ten_nd, _qlnk_fmt_dong, _qlnk_fmt_k,
)
print(f'   _REPORTLAB_READY = {_REPORTLAB_READY}')
print(f'   _FN = {_FN}, _FB = {_FB}')

print('2. Font registration...', end=' ')
_dang_ky_font_qlnk()
print('OK')

print('3. Logo search...', end=' ')
logo = _tim_logo_qlnk()
print(f'found: {logo}')

print('4. Date string...', end=' ')
s = _dong_ten_nd()
from datetime import date
today = date.today()
assert str(today.day) in s, f'Missing day in: {s}'
assert str(today.month) in s, f'Missing month in: {s}'
print('OK (contains today date)')

print('5. Format helpers...', end=' ')
assert _qlnk_fmt_dong(1234567) == '1,234,567', _qlnk_fmt_dong(1234567)
assert _qlnk_fmt_k(1234567) == '1,235', _qlnk_fmt_k(1234567)
print('OK')

print('6. Mau 02 (Cam ket)...', end=' ')
row = {
    'so_ku': 'KU001', 'ten_kh': 'Nguyen Van A',
    'ten_xa': 'Xa Tan Phong', 'ten_to': 'To TKVV 01',
    'ten_ct': 'Cho vay NS&VSMTNT',
    'du_no_khoanh': 15000000, 'ngay_hh_khoanh': '01/12/2026',
}
pdf02 = _xuat_pdf_mau_02qlnk(row, so_tien_cam_ket='5,000,000',
                               thoi_han='6 thang', phuong_thuc='Tra 1 lan')
print(f'{len(pdf02)} bytes OK')
with open('test_mau02.pdf', 'wb') as f: f.write(pdf02)

print('7. Mau 03 (HH khoanh)...', end=' ')
ds_het_han = [
    {'so_ku': 'KU001', 'ten_kh': 'Kim Thi B', 'ten_to': 'To TKVV 02',
     'du_no_khoanh': 8000000, 'ngay_hh_khoanh': '15/06/2026'},
    {'so_ku': 'KU002', 'ten_kh': 'Le Van C', 'ten_to': 'To TKVV 02',
     'du_no_khoanh': 12000000, 'ngay_hh_khoanh': '20/07/2026'},
]
pdf03 = _xuat_pdf_mau_03qlnk('PGD Bien Hoa', 'To TKVV 02', ds_het_han)
print(f'{len(pdf03)} bytes OK')
with open('test_mau03.pdf', 'wb') as f: f.write(pdf03)

print('8. Ke hoach KT...', end=' ')
ds_pc = [
    {'so_ku': 'KU001', 'ten_kh': 'Tran D', 'ten_to': 'To TKVV 01', 'ten_xa': 'Xa A',
     'du_no_khoanh': 10000000, 'ngay_hh_khoanh': '01/10/2026', 'ngay_kt_du_kien': '01/07/2026', 'ghi_chu': ''},
    {'so_ku': 'KU002', 'ten_kh': 'Pham E', 'ten_to': 'To TKVV 01', 'ten_xa': 'Xa A',
     'du_no_khoanh': 5000000, 'ngay_hh_khoanh': '15/11/2026', 'ngay_kt_du_kien': '15/08/2026', 'ghi_chu': ''},
]
tp = {'dai_dien_nhcsxh': 'CBTD A', 'to_tkv': 'To truong B', 'ct_xh': 'Hoi Phu nu',
      'truong_thon': 'Ong C', 'ubnd_xa': 'UBND Xa A'}
pdf_kh = _xuat_pdf_ke_hoach_kt({}, ds_pc, tp, 'PGD Bien Hoa', 2026)
print(f'{len(pdf_kh)} bytes OK')
with open('test_kehoach_kt.pdf', 'wb') as f: f.write(pdf_kh)

print('9. Mau 04 (Thong bao HH)...', end=' ')
row_hstd = {'so_ku': 'KU002', 'ten_kh': 'Pham E', 'ten_to': 'To TKVV 01',
            'du_no_khoanh': 5000000, 'ngay_hh_khoanh': '15/11/2026'}
row_bs = {'ngay_bat_dau_khoanh': '01/01/2025', 'so_thang_khoanh': 24}
pdf04 = _xuat_pdf_mau_04qlnk(row_hstd, row_bs, 'PGD Bien Hoa', noi_dung='', han_cuoi='30/11/2026')
print(f'{len(pdf04)} bytes OK')
with open('test_mau04.pdf', 'wb') as f: f.write(pdf04)

print('10. Mau 01 (Phieu KT)...', end=' ')
ke_hoach = {'id': 1, 'ten_xa': 'Xa Tan Phong', 'ngay_kiem_tra': '2026-05-01'}
ds_kq = [
    {'ma_mon_vay': 'KU001', 'ten_kh': 'Tran D', 'ten_pgd': 'PGD Bien Hoa', 'ten_ct': 'NS&VSMTNT',
     'so_ku': 'KU001', 'ngay_bat_dau_khoanh': '01/01/2025', 'so_thang_khoanh': 24,
     'ngay_het_han_khoanh': '01/01/2027', 'du_no_goc': 10000000, 'du_no_goc_khoanh': 10000000,
     'chenh_lech': 0, 'thuc_trang_du_an': '', 'tinh_hinh_khach_hang': '',
     'kha_nang_tra_no': 'co', 'cam_ket_tra_no': 'co',
     'trang_thai': 'da_phe_duyet', 'can_bo_kiem_tra': 'CBTD A', 'nguoi_nhap': 'CBTD A'},
]
pdf01 = _xuat_pdf_mau_01qlnk(ke_hoach, ds_kq)
print(f'{len(pdf01)} bytes OK')
with open('test_mau01.pdf', 'wb') as f: f.write(pdf01)

print()
print(f'=== ALL 10 TESTS PASSED ===')
print(f'Files: test_mau02.pdf, test_mau03.pdf, test_kehoach_kt.pdf, test_mau04.pdf, test_mau01.pdf')
