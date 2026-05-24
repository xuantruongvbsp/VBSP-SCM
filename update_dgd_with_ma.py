#!/usr/bin/env python3
"""
Script cập nhật DGD_DANH_SACH trong config.py với mã Điểm GD từ Excel
"""

import pandas as pd
import re

def update_dgd_with_ma():
    # Read Excel file
    df_excel = pd.read_excel(r'd:\VBSP-SCM\MÃ ĐIỂM GIAO DỊCH ĐỒNG NAI.xlsx')
    
    # Create mapping from ten_dgd to ma_dgd
    ten_to_ma = {}
    for _, row in df_excel.iterrows():
        ten_dgd = row['TÊN ĐIỂM GIAO DỊCH']
        ma_dgd = row['MÃ ĐIỂM GD MỚI']
        ten_to_ma[ten_dgd] = ma_dgd
    
    print(f"Loaded {len(ten_to_ma)} mappings from Excel")
    
    # Read current config.py
    with open(r'd:\VBSP-SCM\config.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find and update DGD_DANH_SACH
    pattern = r'(DGD_DANH_SACH: list\[dict\] = \[)(.*?)(\])'
    match = re.search(pattern, content, re.DOTALL)
    
    if not match:
        print("Không tìm thấy DGD_DANH_SACH trong config.py")
        return False
    
    # Extract current entries
    current_entries = match.group(2)
    
    # Update each entry to add ma_dgd
    updated_entries = []
    entries = current_entries.split('},')
    
    for entry in entries:
        entry = entry.strip()
        if not entry or not entry.startswith('{'):
            continue
            
        # Extract ten value
        ten_match = re.search(r'"ten": "([^"]+)"', entry)
        if ten_match:
            ten = ten_match.group(1)
            ma_dgd = ten_to_ma.get(ten, "")
            
            # Add ma_dgd to entry
            if ma_dgd:
                # Check if ma_dgd already exists
                if '"ma_dgd"' not in entry:
                    # Add ma_dgd after stt
                    entry = re.sub(
                        r'(\{"stt": \d+)',
                        f'\\1, "ma_dgd": "{ma_dgd}"',
                        entry
                    )
            
        updated_entries.append(entry + '}')
    
    # Reconstruct the full DGD_DANH_SACH
    updated_dgd = match.group(1) + '\n    ' + ',\n    '.join(updated_entries) + '\n' + match.group(3)
    
    # Replace in content
    new_content = content.replace(match.group(0), updated_dgd)
    
    # Write back to config.py
    with open(r'd:\VBSP-SCM\config.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print(f"Đã cập nhật DGD_DANH_SACH với mã cho {len([e for e in updated_entries if '"ma_dgd"' in e])} Điểm GD")
    return True

if __name__ == "__main__":
    update_dgd_with_ma()
