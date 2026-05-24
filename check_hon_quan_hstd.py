#!/usr/bin/env python3
"""
Script kiểm tra HSTD của Hớn Quản để xem tên xã trong data thực tế
"""

import pandas as pd
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def check_hon_quan_hstd():
    """Kiểm tra file HSTD của Hớn Quản"""
    print("=" * 60)
    print("KIỂM TRA HSTD HỚN QUẢN")
    print("=" * 60)
    
    file_path = r'd:\VBSP-SCM\pgd_data\pgd_hon_quan\hstd_latest.xlsx'
    
    try:
        # Đọc file Excel với header=None để kiểm tra các dòng đầu tiên
        df_raw = pd.read_excel(file_path, header=None)
        print(f"✅ Đọc thành công file: {file_path}")
        print(f"📊 Tổng số records: {len(df_raw)}")
        print(f"📋 Số cột: {len(df_raw.columns)}")
        
        # Kiểm tra 5 dòng đầu tiên để tìm header
        print(f"\n🔍 Kiểm tra 5 dòng đầu tiên:")
        for i in range(min(5, len(df_raw))):
            print(f"  Dòng {i+1}: {list(df_raw.iloc[i, :10])}...")
        
        # Thử tìm dòng header có chứa từ khóa liên quan
        header_row = None
        for i in range(min(10, len(df_raw))):
            row_values = [str(val).strip() for val in df_raw.iloc[i, :20] if pd.notna(val)]
            row_text = ' '.join(row_values).lower()
            
            if any(keyword in row_text for keyword in ['pgd', 'xã', 'mã khách', 'tên khách', 'dư nợ']):
                header_row = i
                print(f"\n🎯 Tìm thấy header tại dòng {i+1}: {row_values[:10]}")
                break
        
        if header_row is not None:
            # Đọc lại file với header đúng
            df = pd.read_excel(file_path, header=header_row)
            print(f"\n✅ Đọc lại với header tại dòng {header_row+1}")
        else:
            # Nếu không tìm thấy header, dùng dòng đầu tiên
            df = df_raw
            print(f"\n⚠️ Không tìm thấy header, dùng dòng đầu tiên")
        
        print(f"📊 Tổng số records sau khi xử lý: {len(df)}")
        print(f"📋 Số cột sau khi xử lý: {len(df.columns)}")
        
        # Hiển thị tất cả các cột để tìm tên chính xác
        print(f"\n📋 Tất cả các cột (first 50):")
        for i, col in enumerate(df.columns[:50]):
            print(f"  {i+1:2d}. {col}")
        
        if len(df.columns) > 50:
            print(f"  ... và {len(df.columns) - 50} cột nữa")
        
        # Tìm cột Tên PGD và Tên xã với nhiều từ khóa hơn
        pgd_col = None
        xa_col = None
        
        for col in df.columns:
            col_str = str(col).strip().lower()
            # Tìm cột PGD
            if any(keyword in col_str for keyword in ['pgd', 'đơn vị', 'chi nhánh', 'phòng gd']):
                if pgd_col is None:  # Lấy cái đầu tiên
                    pgd_col = col
            # Tìm cột Xã  
            elif any(keyword in col_str for keyword in ['xã', 'xa', 'phường', 'thị trấn']):
                if xa_col is None:  # Lấy cái đầu tiên
                    xa_col = col
        
        print(f"\n📌 Cột được xác định:")
        print(f"  - PGD: {pgd_col}")
        print(f"  - Xã: {xa_col}")
        
        if pgd_col and xa_col:
            # Lấy các giá trị unique
            pgd_values = df[pgd_col].dropna().unique()
            xa_values = df[xa_col].dropna().unique()
            
            print(f"\n🏢 Các PGD trong file:")
            for pgd in sorted(pgd_values):
                count = len(df[df[pgd_col] == pgd])
                print(f"  - {pgd}: {count} records")
            
            print(f"\n🏘️ Các xã trong file:")
            for xa in sorted(xa_values):
                count = len(df[df[xa_col] == xa])
                print(f"  - '{xa}': {count} records")
            
            # Kiểm tra cụ thể Minh Đức
            minh_duc_records = df[df[xa_col].str.contains('Minh Đức', case=False, na=False)]
            if not minh_duc_records.empty:
                print(f"\n🔎 Chi tiết records chứa 'Minh Đức':")
                for i, (_, row) in enumerate(minh_duc_records.head(5).iterrows()):
                    pgd_val = row[pgd_col]
                    xa_val = row[xa_col]
                    print(f"  {i+1}. PGD: '{pgd_val}' | Xã: '{xa_val}'")
                
                if len(minh_duc_records) > 5:
                    print(f"  ... và {len(minh_duc_records) - 5} records nữa")
            
            # Validation test
            print(f"\n🧪 Validation test:")
            try:
                from services.validation_service import validate_dataframe
                
                result = validate_dataframe(df, "hstd")
                print(f"Kết quả: {result.get_summary()}")
                
                if result.errors:
                    print("Chi tiết lỗi:")
                    for i, error in enumerate(result.errors[:3], 1):
                        print(f"  {i}. [{error.level.value.upper()}] {error.column}: {error.message}")
                        
            except Exception as e:  # conv: skip
                print(f"Lỗi validation: {e}")

        else:
            print("❌ Không tìm thấy cột PGD hoặc Xã")

    except FileNotFoundError:
        print(f"❌ Không tìm thấy file: {file_path}")
    except Exception as e:  # conv: skip
        print(f"❌ Lỗi khi đọc file: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_hon_quan_hstd()
