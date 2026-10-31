from unittest.mock import patch

import win_process_tuner.doctor as doctor_mod


def test_run_doctor_returns_list():
    checks = doctor_mod.run_doctor()
    assert isinstance(checks, list)
    names = [c[0] for c in checks]
    assert "psutil" in names
    assert "winmm" in names
    assert "python" in names


def test_run_doctor_structure():
    checks = doctor_mod.run_doctor()
    for c in checks:
        assert len(c) == 3
        assert isinstance(c[1], bool)