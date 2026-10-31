from unittest.mock import MagicMock, patch

import win_process_tuner.timer as timer_mod


def test_apply_dry_run():
    res = timer_mod.apply_timer_resolution(5, dry_run=True)
    assert res["dry_run"] is True
    assert "timeBeginPeriod(5)" in res["would_call"]


def test_begin_period_success():
    fake_dll = MagicMock()
    fake_dll.timeBeginPeriod.return_value = 0
    with patch.object(timer_mod, "_winmm", return_value=fake_dll):
        success, code = timer_mod.begin_period(5)
    assert success is True
    assert code == 0
    fake_dll.timeBeginPeriod.assert_called_with(5)


def test_begin_period_failure():
    fake_dll = MagicMock()
    fake_dll.timeBeginPeriod.return_value = 97
    with patch.object(timer_mod, "_winmm", return_value=fake_dll):
        success, code = timer_mod.begin_period(5)
    assert success is False
    assert code == 97


def test_apply_invalid_ms():
    try:
        timer_mod.apply_timer_resolution(0, dry_run=True)
        raised = False
    except ValueError:
        raised = True
    assert raised

    try:
        timer_mod.apply_timer_resolution(17, dry_run=True)
        raised = False
    except ValueError:
        raised = True
    assert raised


def test_end_period():
    fake_dll = MagicMock()
    fake_dll.timeEndPeriod.return_value = 0
    with patch.object(timer_mod, "_winmm", return_value=fake_dll):
        success, code = timer_mod.end_period(5)
    assert success is True
    fake_dll.timeEndPeriod.assert_called_with(5)