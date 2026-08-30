"""Regression tests cho launcher Windows VBSP-SCM."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from scripts.validate_dependency_lock import validate_lock


ROOT = Path(__file__).resolve().parents[1]
MAIN_LAUNCHER = ROOT / "Chay_VBSP_SCM.bat"
DEV_LAUNCHER = ROOT / "Chay_DEV_VBSP_SCM.bat"
COMPAT_LAUNCHER = ROOT / "run.bat"
SETUP_SCRIPT = ROOT / "setup_env.bat"
DIRECT_REQUIREMENTS = ROOT / "requirements.txt"
LOCK_REQUIREMENTS = ROOT / "requirements.lock.txt"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def _label_section(content: str, label: str, next_label: str) -> str:
    start = content.index(f"\n:{label}\n")
    end = content.index(f"\n:{next_label}\n", start + 1)
    return content[start:end]


def test_chay_vbsp_scm_is_the_only_real_launcher() -> None:
    main = _read(MAIN_LAUNCHER)
    compat = _read(COMPAT_LAUNCHER)

    assert "-m streamlit run app.py" in main
    assert "call \"%~dp0Chay_VBSP_SCM.bat\" %*" in compat
    assert "-m streamlit" not in compat


def test_port_process_is_verified_before_force_kill() -> None:
    content = _read(MAIN_LAUNCHER)
    classifier = _label_section(content, "classify_pid_tier", "classify_fallback")

    # Port processes go through verification handler (never blind taskkill)
    assert "call :handle_port_pid %%p" in content
    assert "call :classify_pid_tier %PORT_PID%" in content
    assert "Get-CimInstance Win32_Process" in content
    assert "call :is_marked_vbsp_process_classify %CLASSIFY_PID%" in classifier
    assert 'APP_PID_FILE=%TMP_DIR%\\vbsp_streamlit.pid' in content
    # PID marker verifies exact ROOT + APP match (anti-spoof)
    assert 'if /I not "!MARKER_ROOT!"=="%ROOT%" exit /b 1' in content
    assert 'if /I not "!MARKER_APP!"=="%ROOT%\\app.py" exit /b 1' in content
    # Tier 0 requires exact executable equality plus both command-line markers.
    # Keep these assertions scoped to the generated classifier, not a loose substring
    # that could be satisfied by comments or another launcher section.
    assert "echo $v0A = $exeNorm -eq $pyExeNorm ;" in classifier
    assert (
        "echo $v0B = $cmdNorm.Contains('streamlit') "
        "-and $cmdNorm.Contains('app.py') ;"
    ) in classifier
    assert "$combined.Contains($pyExeNorm)" not in content
    # Tier 1 is still Python-only; a non-Python command mentioning app.py is Tier 3.
    assert "echo elseif ($isPython -and (" in classifier
    # Sloppy partial venv path check must NEVER exist (must match PY_EXE exact)
    assert '/C:"venv\\Scripts\\python.exe"' not in content
    # Every PID is logged with a tier classification — non-verified gets prompt not silent kill
    assert "classified as tier" in content
    # Wildcard /IM python.exe kill is FORBIDDEN — could terminate unrelated apps
    assert "taskkill /F /IM python" not in content


def test_launcher_deduplicates_pids_and_explains_refused_process() -> None:
    content = _read(MAIN_LAUNCHER)

    assert 'set "SEEN_PIDS="' in content
    assert "call :register_pid_once %%p" in content
    assert 'for %%s in (!SEEN_PIDS!) do if "%%s"=="%~1"' in content
    assert "LAUNCHER SELF-TEST FAILED: PID dedup duplicate" in content
    assert "call :show_process_info %PORT_PID%" in content
    assert "Ten: " in content
    assert "Duong dan: " in content


def test_launcher_removes_only_stale_runtime_marker() -> None:
    content = _read(MAIN_LAUNCHER)

    assert "call :cleanup_stale_pid_marker" in content
    assert ":cleanup_stale_pid_marker" in content
    assert "Get-Process -Id $parsed" in content
    assert 'del "%APP_PID_FILE%"' in content
    assert "Remove stale runtime PID marker" in content


def test_agent_guidance_reserves_production_port_for_launcher() -> None:
    agents = _read(ROOT / "AGENTS.md")

    assert "`8502` chỉ dành cho app thật/launcher" in agents
    assert "18502" in agents


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
    assert 'set "HEADLESS=false"' in content
    assert 'if /I "%~1"=="--no-browser" (' in content
    assert 'set "HEADLESS=true"' in content
    assert "--server.headless %HEADLESS%" in content
    assert "start powershell" not in content.lower()


def test_flag_loop_consumes_three_flags_and_port_value() -> None:
    content = _read(MAIN_LAUNCHER)
    parser = _label_section(content, "parse_flags", "flags_done")

    assert 'if /I "%~1"=="--no-browser" (' in parser
    assert 'if /I "%~1"=="--force-kill" (' in parser
    assert 'if /I "%~1"=="--port" (' in parser
    assert 'set "PORT=%~2"' in parser
    assert 'set "URL=http://localhost:%~2"' in parser
    assert "    shift\n    shift\n    goto :parse_flags" in parser
    assert content.index("\n:parse_flags\n") < content.index('set "RUN_STAMP=')
    assert 'if "%PORT%"=="%ALT_PORT%" set "ALT_PORT=8504"' in content


def test_prompt_defaults_and_force_kill_retry_are_state_safe() -> None:
    content = _read(MAIN_LAUNCHER)
    prompt_kill = _label_section(
        content, "prompt_user_kill", "prompt_user_kill_fallback"
    )
    prompt_kill_fallback = _label_section(
        content, "prompt_user_kill_fallback", "prompt_alt_port_or_exit"
    )
    alt_prompt = _label_section(content, "prompt_alt_port_or_exit", "calculate_requirements_hash")

    assert "choice /C YN /T %PK_TIMEOUT% /D %PK_DEFAULT%" in prompt_kill
    assert 'if "%PK_RC%"=="1" exit /b 0' in prompt_kill
    assert 'set "PK_ANSWER="\nset /P "PK_ANSWER=' in prompt_kill_fallback
    assert 'if "%PK_ANSWER%"=="" set "PK_ANSWER=%PK_DEFAULT%"' in prompt_kill_fallback
    assert 'if /I "%PK_ANSWER%"=="Y" exit /b 0' in prompt_kill_fallback
    assert 'set "PAP_ANSWER="\nset "PAP_RC=1"\nset /P "PAP_ANSWER=' in alt_prompt
    assert ':switch_to_alt_port\nset "FORCE_KILL=false"' in alt_prompt


@pytest.mark.skipif(sys.platform != "win32", reason="cmd.exe/PowerShell only available on Windows")
def test_generated_classifier_ps1_has_literal_pipe_and_valid_syntax(tmp_path: Path) -> None:
    content = _read(MAIN_LAUNCHER)
    classifier = _label_section(content, "classify_pid_tier", "classify_fallback")
    echo_lines = [
        line
        for line in classifier.splitlines()
        if line.startswith("echo ") and '"%CLASSIFY_PS1%"' in line
    ]
    ps1_path = tmp_path / "classifier.ps1"
    batch_path = tmp_path / "render_classifier.bat"
    wrapper_lines = [
        "@echo off",
        "setlocal EnableExtensions EnableDelayedExpansion",
        f'set "CLASSIFY_PID={os.getpid()}"',
        f'set "CLASSIFY_PS1={ps1_path}"',
        f'set "VBSP_CLASSIFY_PY_EXE={sys.executable}"',
        f'set "VBSP_CLASSIFY_ROOT={ROOT}"',
        *echo_lines,
        'powershell.exe -NoLogo -NoProfile -NonInteractive '
        '-ExecutionPolicy Bypass -File "%CLASSIFY_PS1%"',
    ]
    batch_path.write_bytes(("\r\n".join(wrapper_lines) + "\r\n").encode("ascii"))

    result = subprocess.run(
        ["cmd.exe", "/d", "/v:on", "/c", str(batch_path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    generated = ps1_path.read_text(encoding="ascii")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "$combined=($exeNorm + ' | ' + $cmdNorm) ;" in generated
    assert "^|" not in generated
    assert "MISSING" in result.stdout or "TIER=2" in result.stdout


@pytest.mark.skipif(sys.platform != "win32", reason="WMIC/findstr fallback is Windows-only")
def test_wmic_list_format_python_name_matches_findstr(tmp_path: Path) -> None:
    wmic_output = tmp_path / "wmic.txt"
    batch_path = tmp_path / "check_wmic.bat"
    payload = "\r\r\nName=python.exe\r\r\n\r\r\n".encode("utf-16-le")
    wmic_output.write_bytes(b"\xff\xfe" + payload)
    batch_path.write_bytes(
        (
            '@echo off\r\n'
            'type "%~dp0wmic.txt" 2>nul | more | '
            'findstr /I /L /C:"Name=python.exe"\r\n'
        ).encode("ascii")
    )

    result = subprocess.run(
        ["cmd.exe", "/d", "/c", str(batch_path)],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    assert result.returncode == 0
    assert "Name=python.exe" in result.stdout


def test_dev_launcher_reuses_browser_tab_without_opening_new_one() -> None:
    content = _read(DEV_LAUNCHER)

    assert 'call "%~dp0Chay_VBSP_SCM.bat" --no-browser' in content
    assert "khong mo them tab Chrome" in content
    assert "http://localhost:8502" in content


@pytest.mark.skipif(sys.platform != "win32", reason="cmd.exe only available on Windows")
def test_launcher_self_test_runs_without_starting_app() -> None:
    result = subprocess.run(
        [
            "cmd.exe",
            "/d",
            "/v:on",
            "/c",
            str(MAIN_LAUNCHER),
            "--no-browser",
            "--force-kill",
            "--port",
            "8503",
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
    assert (
        "LAUNCHER SELF-TEST CONFIG: PORT=8503 HEADLESS=true "
        "FORCE_KILL=true ALT_PORT=8504"
    ) in result.stdout


@pytest.mark.skipif(sys.platform != "win32", reason="CRLF guarantee only relevant on Windows")
def test_batch_files_stay_ascii_crlf_for_cmd_compatibility() -> None:
    for path in (MAIN_LAUNCHER, DEV_LAUNCHER, COMPAT_LAUNCHER, SETUP_SCRIPT):
        raw = path.read_bytes()
        assert all(byte < 128 for byte in raw)
        assert b"\n" not in raw.replace(b"\r\n", b"")
