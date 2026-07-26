"""Regression tests cho launcher Windows VBSP-SCM."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from scripts.validate_dependency_lock import validate_lock


ROOT = Path(__file__).resolve().parents[1]
MAIN_LAUNCHER = ROOT / "Chay_VBSP_SCM.bat"
COMPAT_LAUNCHER = ROOT / "run.bat"
SETUP_SCRIPT = ROOT / "setup_env.bat"
DIRECT_REQUIREMENTS = ROOT / "requirements.txt"
LOCK_REQUIREMENTS = ROOT / "requirements.lock.txt"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def test_chay_vbsp_scm_is_the_only_real_launcher() -> None:
    main = _read(MAIN_LAUNCHER)
    compat = _read(COMPAT_LAUNCHER)

    assert "-m streamlit run app.py" in main
    assert "call \"%~dp0Chay_VBSP_SCM.bat\" %*" in compat
    assert "-m streamlit" not in compat


def test_port_process_is_verified_before_force_kill() -> None:
    content = _read(MAIN_LAUNCHER)

    assert "call :is_vbsp_process %%p" in content
    assert "Get-CimInstance Win32_Process" in content
    assert '/C:"%PY_EXE%"' in content
    assert '/C:"streamlit"' in content
    assert '/C:"app.py"' in content
    assert "REFUSE: PID %%p is not verified as VBSP-SCM" in content
    assert "taskkill /F /IM python" not in content


def test_dependency_lock_is_installed_and_synced_by_combined_sha256() -> None:
    content = _read(MAIN_LAUNCHER)

    assert 'SETUP_DONE_FILE=%TMP_DIR%\\.vbsp_setup_done' in content
    assert 'REQUIREMENTS_LOCK_FILE=%ROOT%\\requirements.lock.txt' in content
    assert "hashlib.sha256" in content
    assert "src.read_bytes()+b'\\0'+lock.read_bytes()" in content
    assert "call :sync_requirements" in content
    assert '-m pip install --no-deps -r "%REQUIREMENTS_LOCK_FILE%"' in content
    assert "scripts\\validate_dependency_lock.py" in content
    assert '-m pip install "pip==%PIP_VERSION%"' in content
    assert "-m pip check" in content
    assert "--force-reinstall" not in content


def test_setup_uses_lockfile_without_unpinned_reinstall() -> None:
    content = _read(SETUP_SCRIPT)

    assert 'LOCK_FILE=%ROOT%requirements.lock.txt' in content
    assert '-m pip install --no-deps -r "%LOCK_FILE%"' in content
    assert "if not exist \"%LOCK_FILE%\" goto :lock_missing" in content
    assert "scripts\\validate_dependency_lock.py" in content
    assert "--force-reinstall" not in content


def test_lockfile_exactly_pins_direct_and_transitive_packages() -> None:
    direct = [
        line.strip()
        for line in _read(DIRECT_REQUIREMENTS).splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    locked = [
        line.strip()
        for line in _read(LOCK_REQUIREMENTS).splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    lock_by_name = {
        line.split("==", 1)[0].lower().replace("_", "-"): line
        for line in locked
    }

    assert len(locked) > len(direct)
    assert all(line.count("==") == 1 for line in locked)
    for requirement in direct:
        name = requirement.split("==", 1)[0].lower().replace("_", "-")
        assert lock_by_name[name].lower() == requirement.lower()
    assert validate_lock(DIRECT_REQUIREMENTS, LOCK_REQUIREMENTS) == []


def test_lock_validator_rejects_missing_or_mismatched_direct_pin(
    tmp_path: Path,
) -> None:
    direct = tmp_path / "requirements.txt"
    locked = tmp_path / "requirements.lock.txt"
    direct.write_text("alpha==1.0\nbeta==2.0\n", encoding="utf-8")
    locked.write_text("alpha==1.1\ngamma==3.0\ndelta==4.0\n", encoding="utf-8")

    errors = validate_lock(direct, locked)

    assert any("alpha version mismatch" in error for error in errors)
    assert any("beta==2.0 is missing" in error for error in errors)


def test_launcher_rotates_and_expires_old_logs() -> None:
    content = _read(MAIN_LAUNCHER)

    assert "launcher_last.log" in content
    assert 'launcher_%RUN_STAMP%.log' in content
    assert "LOG_RETENTION_DAYS=30" in content
    assert 'forfiles /p "%LOG_DIR%" /m "launcher_*.log"' in content


def test_launcher_keeps_project_runtime_contract() -> None:
    content = _read(MAIN_LAUNCHER)

    assert 'PORT=8502' in content
    assert 'PY_EXE=%ROOT%\\venv\\Scripts\\python.exe' in content
    assert "--server.headless false" in content
    assert "start powershell" not in content.lower()


@pytest.mark.skipif(sys.platform != "win32", reason="cmd.exe only available on Windows")
def test_launcher_self_test_runs_without_starting_app() -> None:
    result = subprocess.run(
        [
            "cmd.exe",
            "/d",
            "/v:on",
            "/c",
            str(MAIN_LAUNCHER),
            "--self-test",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "LAUNCHER SELF-TEST OK" in result.stdout


@pytest.mark.skipif(sys.platform != "win32", reason="CRLF guarantee only relevant on Windows")
def test_batch_files_stay_ascii_crlf_for_cmd_compatibility() -> None:
    for path in (MAIN_LAUNCHER, COMPAT_LAUNCHER, SETUP_SCRIPT):
        raw = path.read_bytes()
        assert all(byte < 128 for byte in raw)
        assert b"\n" not in raw.replace(b"\r\n", b"")
