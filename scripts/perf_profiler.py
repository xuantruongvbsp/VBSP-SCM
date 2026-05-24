"""Performance profiler cho các tab module của VBSP-SCM.

Đo:
  1. Thời gian import từng tab (lần đầu + cached)
  2. Thời gian import services mà tab gọi
  3. Các module import nặng (pandas, openpyxl, duckdb, etc.)
  4. Báo cáo top-20 điểm nóng

Cách dùng:
  python scripts/perf_profiler.py
"""
from __future__ import annotations

import importlib
import io
import os
import sys
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

ROOT = Path(__file__).resolve().parent.parent
TABS_DIR = ROOT / "tabs"
SERVICES_DIR = ROOT / "services"
WORKSPACES_DIR = ROOT / "workspaces"

sys.path.insert(0, str(ROOT))


def medida_import(module_name: str, clear_first: bool = True) -> tuple[float, float]:
    """Đo thời gian import module.

    Returns:
        (cold_time_ms, warm_time_ms)
    """
    if clear_first:
        for key in list(sys.modules.keys()):
            if key == module_name or key.startswith(module_name + "."):
                del sys.modules[key]

    t0 = time.perf_counter()
    try:
        mod = importlib.import_module(module_name)
        cold = (time.perf_counter() - t0) * 1000
    except Exception as e:
        return (-1, -1)

    t1 = time.perf_counter()
    try:
        for key in list(sys.modules.keys()):
            if key == module_name or key.startswith(module_name + "."):
                del sys.modules[key]
        importlib.import_module(module_name)
        warm = (time.perf_counter() - t1) * 1000
    except Exception:
        warm = cold

    return (cold, warm)


def discover_modules(directory: Path, prefix: str) -> list[str]:
    """Tìm tất cả các module Python trong thư mục."""
    modules = []
    for fpath in sorted(directory.glob("*.py")):
        if fpath.name.startswith("_") or fpath.name.startswith("__"):
            continue
        name = fpath.stem
        modules.append(f"{prefix}.{name}")
    return modules


def main():
    os.chdir(str(ROOT))

    print("=" * 80)
    print("  VBSP-SCM — PROFILER HIỆU SUẤT TAB")
    print("=" * 80)

    # ── Step 1: Đo thời gian import module nền (baseline) ─────────────────
    print("\n[1] MODULE NỀN (baseline)")
    print("-" * 50)

    baseline_modules = [
        "config",
        "db",
        "auth",
        "utils",
        "state_manager",
        "logger",
    ]
    baseline_total = 0.0

    for m in baseline_modules:
        # Không clear vì đã được import khi import file đầu tiên
        t0 = time.perf_counter()
        for key in list(sys.modules.keys()):
            if key == m or key.startswith(m + "."):
                del sys.modules[key]
        importlib.import_module(m)
        elapsed = (time.perf_counter() - t0) * 1000
        baseline_total += elapsed
        print(f"  {m:<25} {elapsed:>8.1f} ms")

    print(f"  {'─' * 40}")
    print(f"  {'TỔNG module nền':<25} {baseline_total:>8.1f} ms")

    # ── Step 2: Đo thời gian import từng TAB ─────────────────────────────
    print("\n[2] TAB MODULES (cold import)")
    print("-" * 70)

    tab_modules = discover_modules(TABS_DIR, "tabs")
    results_tab = []

    for mod_name in tab_modules:
        short = mod_name.replace("tabs.", "")
        cold, warm = medida_import(mod_name, clear_first=True)
        status = "✅" if cold >= 0 else "❌"
        results_tab.append((short, cold, warm, status))
        print(f"  {status} {short:<40} cold={cold:>8.1f}ms  warm={warm:>8.1f}ms")

    # ── Step 3: Đo thời gian import SERVICES ────────────────────────────
    print("\n[3] SERVICE MODULES (cold import)")
    print("-" * 70)
    svc_modules = discover_modules(SERVICES_DIR, "services")
    results_svc = []

    for mod_name in svc_modules:
        short = mod_name.replace("services.", "")
        cold, warm = medida_import(mod_name, clear_first=True)
        status = "✅" if cold >= 0 else "❌"
        results_svc.append((short, cold, warm, status))
        print(f"  {status} {short:<40} cold={cold:>8.1f}ms  warm={warm:>8.1f}ms")

    # ── Step 4: Đo thời gian import WORKSPACES ──────────────────────────
    print("\n[4] WORKSPACE MODULES (cold import)")
    print("-" * 70)
    ws_modules = discover_modules(WORKSPACES_DIR, "workspaces")
    results_ws = []

    for mod_name in ws_modules:
        short = mod_name.replace("workspaces.", "")
        cold, warm = medida_import(mod_name, clear_first=True)
        status = "✅" if cold >= 0 else "❌"
        results_ws.append((short, cold, warm, status))
        print(f"  {status} {short:<40} cold={cold:>8.1f}ms  warm={warm:>8.1f}ms")

    # ── Step 5: Phân tích TỔNG HỢP ──────────────────────────────────────
    print("\n" + "=" * 80)
    print("  TỔNG HỢP — TOP-20 ĐIỂM NÓNG (COLD IMPORT)")
    print("=" * 80)

    all_results = []
    for row in results_tab:
        if row[1] >= 0:
            all_results.append(("TAB", row[0], row[1]))
    for row in results_svc:
        if row[1] >= 0:
            all_results.append(("SVC", row[0], row[1]))
    for row in results_ws:
        if row[1] >= 0:
            all_results.append(("WS", row[0], row[1]))

    all_results.sort(key=lambda x: x[2], reverse=True)

    print(f"  {'#':<4} {'Loại':<6} {'Module':<45} {'Cold(ms)':>10}")
    print(f"  {'─' * 70}")
    for i, (loai, name, cold) in enumerate(all_results[:20], 1):
        bar = "█" * int(cold / max(all_results[0][2] / 40, 0.1)) if all_results else ""
        print(f"  {i:<4} {loai:<6} {name:<45} {cold:>10.1f} {bar}")

    # ── Step 6: Tổng import estimate ────────────────────────────────────
    print("\n" + "=" * 80)
    print("  TỔNG IMPORT ESTIMATE")
    print("=" * 80)

    tab_total = sum(r[1] for r in results_tab if r[1] >= 0)
    svc_total = sum(r[1] for r in results_svc if r[1] >= 0)
    ws_total = sum(r[1] for r in results_ws if r[1] >= 0)

    print(f"  Tabs ({len(results_tab)} modules):       {tab_total:>8.1f} ms")
    print(f"  Services ({len(results_svc)} modules):   {svc_total:>8.1f} ms")
    print(f"  Workspaces ({len(results_ws)} modules):  {ws_total:>8.1f} ms")
    print(f"  Nền ({len(baseline_modules)} modules):               {baseline_total:>8.1f} ms")
    print(f"  {'─' * 45}")
    print(f"  TỔNG CỘNG:                         {tab_total + svc_total + ws_total + baseline_total:>8.1f} ms")
    print(f"\n  Lưu ý: Tổng > thực tế vì dependencies import chung (pip, etc.)")
    print(f"  Warm cache (lần 2+) nhanh hơn ~3-10× do Python sys.modules cache.")

    # ── Step 7: Kiểm tra các import nặng trong từng tab ─────────────────
    print("\n" + "=" * 80)
    print("  IMPORT NẶNG TRONG TỪNG TAB (phân tích dependencies)")
    print("=" * 80)

    heavy_modules = [
        "openpyxl", "pandas", "duckdb", "plotly", "graphviz",
        "matplotlib", "numpy", "python-docx", "docx2pdf",
        "streamlit", "PIL", "pyarrow",
    ]

    tab_cold_map = {r[0]: r[1] for r in results_tab}
    for short_name in sorted(tab_cold_map.keys())[:15]:
        cold = tab_cold_map[short_name]
        if cold <= 0:
            continue
        mod_name = "tabs." + short_name

        # Tìm dependencies nặng
        found = []
        for key in sorted(sys.modules.keys()):
            if key.startswith(mod_name):
                for hm in heavy_modules:
                    if hm.lower() in key.lower():
                        found.append(hm)
                        break

        if found:
            uniq = list(dict.fromkeys(found))
            print(f"  {short_name:<40} ({cold:>6.0f}ms) → {', '.join(uniq)}")


if __name__ == "__main__":
    main()
