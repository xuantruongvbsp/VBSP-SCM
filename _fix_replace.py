import re

path = r'd:\VBSP-SCM\tabs\tab_tongquan.py'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

old = '''            _nv = pd.to_numeric(df[COT_NGUON_VON], errors="coerce")
            du_no_tw = df[_nv == 1].groupby(COT_TEN_CT)[COT_TONG_DU_NO].sum()
            du_no_dp = df[_nv == 2].groupby(COT_TEN_CT)[COT_TONG_DU_NO].sum()

            df_ct = (
                df.groupby(COT_TEN_CT)
                .agg(
                    du_no   =(COT_TONG_DU_NO, "sum"),
                    so_mon  =(COT_SO_KU,      "nunique"),
                    so_kh   =(COT_MA_KH,      "nunique"),
                )
                .sort_values("du_no", ascending=False)
                .reset_index()
            )
            df_ct.columns = ["ten_ct", "du_no", "so_mon", "so_kh"]
            df_ct = df_ct[df_ct["du_no"] > 0]'''

new = '''            _df_loc = df[df[COT_TONG_DU_NO].fillna(0) > 0].copy()

            _nv = pd.to_numeric(_df_loc[COT_NGUON_VON], errors="coerce")
            du_no_tw = _df_loc[_nv == 1].groupby(COT_TEN_CT)[COT_TONG_DU_NO].sum()
            du_no_dp = _df_loc[_nv == 2].groupby(COT_TEN_CT)[COT_TONG_DU_NO].sum()

            df_ct = (
                _df_loc.groupby(COT_TEN_CT)
                .agg(
                    du_no   =(COT_TONG_DU_NO, "sum"),
                    so_mon  =(COT_SO_KU,      "nunique"),
                    so_kh   =(COT_MA_KH,      "nunique"),
                )
                .sort_values("du_no", ascending=False)
                .reset_index()
            )
            df_ct.columns = ["ten_ct", "du_no", "so_mon", "so_kh"]'''

count = content.count(old)
print(f"Found {count} occurrence(s)")

if count > 0:
    content = content.replace(old, new, 1)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Replacement done!")
else:
    print("Pattern not found!")
