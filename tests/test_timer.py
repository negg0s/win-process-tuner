from unittest.mock import MagicMock, patch

import pytest

import win_process_tuner.timer as timer_mod


def test_apply_dry_run():
    res = timer_mod.apply_timer_resolution(5, dry_run=True, hold_seconds=2)
    assert res["dry_run"] is True
    assert "timeBeginPeriod(5)" in res["would_call"]
    assert "timeEndPeriod(5)" in res["would_call"]


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


def test_apply_calls_begin_and_end():
    fake_dll = MagicMock()
    fake_dll.timeBeginPeriod.return_value = 0
    fake_dll.timeEndPeriod.return_value = 0
    with patch.object(timer_mod, "_winmm", return_value=fake_dll):
        res = timer_mod.apply_timer_resolution(1, hold_seconds=0)
    assert res["success"] is True
    assert res["ended"] is True
    fake_dll.timeBeginPeriod.assert_called_once_with(1)
    fake_dll.timeEndPeriod.assert_called_once_with(1)


def test_apply_holds_then_ends():
    fake_dll = MagicMock()
    fake_dll.timeBeginPeriod.return_value = 0
    fake_dll.timeEndPeriod.return_value = 0
    with patch.object(timer_mod, "_winmm", return_value=fake_dll):
        with patch.object(timer_mod.time, "sleep") as sleep:
            res = timer_mod.apply_timer_resolution(2, hold_seconds=3)
    sleep.assert_called_once_with(3)
    assert res["end_success"] is True


def test_apply_does_not_end_when_begin_fails():
    fake_dll = MagicMock()
    fake_dll.timeBeginPeriod.return_value = 97
    with patch.object(timer_mod, "_winmm", return_value=fake_dll):
        res = timer_mod.apply_timer_resolution(2)
    assert res["success"] is False
    assert res["ended"] is False
    fake_dll.timeEndPeriod.assert_not_called()


def test_apply_reports_end_failure():
    fake_dll = MagicMock()
    fake_dll.timeBeginPeriod.return_value = 0
    fake_dll.timeEndPeriod.return_value = 5
    with patch.object(timer_mod, "_winmm", return_value=fake_dll):
        res = timer_mod.apply_timer_resolution(2)
    assert res["ended"] is True
    assert res["success"] is False
    assert res["end_code"] == 5


def test_apply_invalid_ms():
    with pytest.raises(ValueError):
        timer_mod.apply_timer_resolution(0, dry_run=True)
    with pytest.raises(ValueError):
        timer_mod.apply_timer_resolution(17, dry_run=True)


def test_apply_invalid_hold():
    with pytest.raises(ValueError):
        timer_mod.apply_timer_resolution(2, dry_run=True, hold_seconds=-1)


def test_end_period():
    fake_dll = MagicMock()
    fake_dll.timeEndPeriod.return_value = 0
    with patch.object(timer_mod, "_winmm", return_value=fake_dll):
        success, code = timer_mod.end_period(5)
    assert success is True
    fake_dll.timeEndPeriod.assert_called_with(5)
