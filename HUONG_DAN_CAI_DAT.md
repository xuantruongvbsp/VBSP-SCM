# Hướng dẫn cài đặt VBSP-SCM trên máy mới

> **Dành cho:** Người dùng nội bộ NHCSXH Chi nhánh Đồng Nai  
> **Cập nhật:** 28/05/2026

---

## Yêu cầu hệ thống

- **Windows** 10/11 (64-bit)
- **Python** 3.10 trở lên
- Kết nối Internet (để tải packages lần đầu)

---

## Bước 1: Cài Python (nếu chưa có)

1. Tải Python từ: https://www.python.org/downloads/
2. Chạy file cài đặt, **TÍCH CHỌN** ô "Add Python to PATH"
3. Nhấn Install Now, đợi hoàn tất
4. Mở PowerShell/CMD, gõ `python --version` để kiểm tra

> Nếu hiện `Python 3.x.x` là được.

---

## Bước 2: Copy dự án về máy

Copy toàn bộ thư mục `VBSP-SCM` từ USB/Share/Google Drive vào máy mới.

> **Lưu ý:** KHÔNG copy thư mục `venv/` — thư mục này sẽ được tạo lại tự động.

---

## Bước 3: Chạy file cài đặt

1. Mở thư mục `VBSP-SCM`
2. **Double-click** vào file `setup_env.bat`
3. Đợi 3-5 phút để script cài đặt tất cả packages
4. Nếu thấy dòng **"HOAN TAT! Moi truong da san sang."** là thành công

`setup_env.bat` sẽ tự động:
- Tạo môi trường ảo `venv/`
- Cài đặt toàn bộ thư viện (Streamlit, Pandas, DuckDB, Plotly...)
- Tạo các thư mục cần thiết (`cache/`, `pgd_data/`, `backups/`)
- Kiểm tra tất cả module đã import được

---

## Bước 4: Chạy ứng dụng

1. **Double-click** vào file `run.bat`
2. Trình duyệt sẽ tự mở tại địa chỉ **http://localhost:8501**
3. Đăng nhập bằng tài khoản được cấp
4. Nhấn `Ctrl+C` trong cửa sổ console để dừng server

---

## Các lỗi thường gặp

| Lỗi | Nguyên nhân | Cách khắc phục |
|---|---|---|
| `'python' is not recognized` | Chưa cài Python hoặc chưa thêm vào PATH | Cài lại Python, tích "Add Python to PATH" |
| `ModuleNotFoundError: No module named 'streamlit'` | Chưa chạy `setup_env.bat` | Double-click `setup_env.bat` |
| `Access is denied` | Thiếu quyền ghi thư mục | Chạy `setup_env.bat` với quyền Administrator |
| Cửa sổ tự đóng khi chạy `run.bat` | Lỗi khởi động | Mở PowerShell trong thư mục dự án, chạy: `venv\Scripts\streamlit run app.py` |
| `Address already in use` | Cổng 8501 đã bị chiếm | Đóng ứng dụng cũ, hoặc đổi cổng: `venv\Scripts\streamlit run app.py --server.port 8502` |

---

## Chạy bằng dòng lệnh (cách thủ công)

```powershell
cd D:\VBSP-SCM

# Cài đặt lần đầu
python -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt

# Chạy app
venv\Scripts\streamlit run app.py
```

---

## Cập nhật dự án

Khi có bản cập nhật mới từ Git:

```powershell
cd D:\VBSP-SCM
git pull
venv\Scripts\python.exe -m pip install -r requirements.txt
```

> Chỉ cần `pip install -r requirements.txt` nếu `requirements.txt` có thay đổi.
