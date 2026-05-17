""" 
Script one-time: parse 3 file Excel → merge vào dgd_map trong kv_store. 
Chạy từ thư mục gốc project: python seed_dgd_map.py 

Các file Excel phải nằm cùng thư mục với script này hoặc chỉnh DATA_DIR bên dưới. 
""" 
import json 
import sys 
from pathlib import Path 

import pandas as pd 

# ── Đường dẫn file Excel (chỉnh nếu cần) ───────────────────────────────────── 
DATA_DIR = Path(__file__).parent 

FILE_BIEN_HOA   = DATA_DIR / "Danh_sách_Điểm_giao_dịch_và_Ấp_-_Biên_Hòa.xlsx" 
FILE_DINH_QUAN  = DATA_DIR / "Danh_sách_Thôn_Ấp_theo_Điểm_Giao_Dịch_và_Xã_Định_Quán.xlsx" 
FILE_LONG_THANH = DATA_DIR / "Danh_sách_Thôn_Ấp_theo_Điểm_Giao_Dịch_và_Xã_Long_Thành.xlsx" 

# ── Import db từ project ────────────────────────────────────────────────────── 
sys.path.insert(0, str(Path(__file__).parent)) 
import db 


def _parse_bien_hoa() -> dict: 
    """Cột: STT | Phường | Điểm GD | Ấp/KP (chuỗi phân tách bởi dấu phẩy)""" 
    df = pd.read_excel(FILE_BIEN_HOA, header=0) 
    df.columns = ["STT", "Phuong", "DGD", "Ap"] 
    result = {} 
    for _, row in df.iterrows(): 
        xa  = str(row["Phuong"]).strip() 
        dgd = str(row["DGD"]).strip() 
        ap_list = [a.strip() for a in str(row["Ap"]).split(",") if a.strip()] 
        result.setdefault(xa, {}).setdefault(dgd, []).extend(ap_list) 
    return result 


def _parse_one_row_per_thon(file_path: Path) -> dict: 
    """Cột: STT | Tên xã | Tên điểm GD | Tên thôn/Ấp (mỗi dòng 1 thôn)""" 
    df = pd.read_excel(file_path, header=0) 
    df.columns = ["STT", "Xa", "DGD", "Thon"] 
    result = {} 
    for _, row in df.iterrows(): 
        xa   = str(row["Xa"]).strip() 
        dgd  = str(row["DGD"]).strip() 
        thon = str(row["Thon"]).strip() 
        if thon.lower() == "nan" or not thon: 
            continue 
        result.setdefault(xa, {}).setdefault(dgd, []).append(thon) 
    return result 


def main(): 
    username = "admin" 

    # ── 1. Đọc dgd_map hiện có ─────────────────────────────────────────────── 
    dgd_map = db.doc_dgd_map() 
    print(f"dgd_map hiện có: {list(dgd_map.keys()) or '(rỗng)'}") 

    # ── 2. Parse 3 file Excel ──────────────────────────────────────────────── 
    new_data = { 
        "Hội sở Chi nhánh tỉnh": _parse_bien_hoa(), 
        "PGD Định Quán":         _parse_one_row_per_thon(FILE_DINH_QUAN), 
        "PGD Long Thành":        _parse_one_row_per_thon(FILE_LONG_THANH), 
    } 

    # ── 3. Merge (ghi đè theo PGD, giữ nguyên các PGD khác) ───────────────── 
    for pgd, xa_map in new_data.items(): 
        dgd_map[pgd] = xa_map 
        so_xa  = len(xa_map) 
        so_dgd = sum(len(v) for v in xa_map.values()) 
        print(f"  ✅ {pgd}: {so_xa} xã/phường, {so_dgd} điểm giao dịch") 

    # ── 4. Lưu vào kv_store ────────────────────────────────────────────────── 
    db.luu_dgd_map(dgd_map, username) 
    print(f"\n✅ Đã lưu dgd_map vào kv_store — tổng {len(dgd_map)} PGD") 
    print("Chạy lại app Streamlit để thấy thay đổi.") 


if __name__ == "__main__": 
    main()

