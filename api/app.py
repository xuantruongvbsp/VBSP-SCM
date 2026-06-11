"""API RESTful nhẹ — đọc dữ liệu parquet + SQLite qua Flask.
Chạy song song với Streamlit: python -m flask --app api.app run --port 8502
"""
from __future__ import annotations
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from flask import Flask, jsonify, request, abort
except ImportError:
    raise ImportError("Cài flask: pip install flask")

import duckdb
import db as _db
from config import CACHE_HSTD, DS_PGD, COT_TEN_PGD, COT_TONG_DU_NO, COT_DU_NO_QH, COT_DU_NO_KHOANH, COT_TEN_CT

app = Flask(__name__)

def _check_parquet():
    return Path(CACHE_HSTD).exists()

@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "parquet": _check_parquet()})

@app.route("/api/pgd")
def pgd_list():
    return jsonify({"pgd": DS_PGD})

@app.route("/api/du_no")
def du_no():
    """Tổng dư nợ toàn CN. Query param: pgd=<ten_pgd>"""
    if not _check_parquet():
        return jsonify({"error": "Chưa có dữ liệu"}), 404
    pgd_filter = request.args.get("pgd", "")
    try:
        where = f"WHERE \"Tên PGD\" = '{pgd_filter}'" if pgd_filter else ""
        df = duckdb.query(f"""
            SELECT \"Tên PGD\" as ten_pgd,
                   SUM(\"Tổng dư nợ\") as tong_du_no,
                   SUM(\"Dư nợ quá hạn\") as du_no_qh,
                   COUNT(*) as so_ho
            FROM '{CACHE_HSTD}'
            {where}
            GROUP BY \"Tên PGD\"
            ORDER BY tong_du_no DESC
        """).df()
        return jsonify(df.to_dict(orient="records"))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/nqh")
def nqh():
    """NQH theo PGD."""
    if not _check_parquet():
        return jsonify({"error": "Chưa có dữ liệu"}), 404
    try:
        df = duckdb.query(f"""
            SELECT \"Tên PGD\" as ten_pgd,
                   SUM(\"Dư nợ quá hạn\") as du_no_qh,
                   SUM(\"Tổng dư nợ\") as tong_du_no,
                   CASE WHEN SUM(\"Tổng dư nợ\") > 0
                        THEN ROUND(SUM(\"Dư nợ quá hạn\") * 100.0 / SUM(\"Tổng dư nợ\"), 2)
                        ELSE 0 END as tl_nqh_pct
            FROM '{CACHE_HSTD}'
            GROUP BY \"Tên PGD\"
            ORDER BY tl_nqh_pct DESC
        """).df()
        return jsonify(df.to_dict(orient="records"))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/chuong_trinh")
def chuong_trinh():
    """Dư nợ theo chương trình."""
    if not _check_parquet():
        return jsonify({"error": "Chưa có dữ liệu"}), 404
    try:
        df = duckdb.query(f"""
            SELECT \"Tên chương trình\" as ten_ct,
                   SUM(\"Tổng dư nợ\") as tong_du_no,
                   COUNT(*) as so_ho
            FROM '{CACHE_HSTD}'
            GROUP BY \"Tên chương trình\"
            ORDER BY tong_du_no DESC
        """).df()
        return jsonify(df.to_dict(orient="records"))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=False, port=8502)
