"""Profile: chỉ import, không load data"""
import time, os

items = [
    ("streamlit", "import streamlit as st"),
    ("auth", "import auth"),
    ("config", "from config import CACHE_HSTD"),
    ("db", "import db"),
    ("workspaces", "import workspaces"),
    ("duckdb", "import duckdb"),
    ("pandas", "import pandas as pd"),
    ("data/core", "from data.core import ts_file, excel_to_parquet"),
    ("data/hstd", "from data.hstd import doc_file"),
]

for name, code in items:
    t0 = time.perf_counter()
    exec(code)
    t = time.perf_counter() - t0
    size = os.path.getsize(name.split()[0] + ".py") if os.path.exists(name.split()[0] + ".py") else 0
    print(f"{t:>7.3f}s  {name:<20}  ({size/1024:.0f} KB)")
