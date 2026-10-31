import contextlib
from unittest.mock import MagicMock, patch

import psutil
import pytest

import win_process_tuner.processes as proc_mod
from win_process_tuner.safety import SafetyError


def _make_proc(pid, name, cpu, mem, status="running"):
    p = MagicMock()
    p.pid = pid
    p.name.return_value = name
    p.status.return_value = status
    p.cpu_percent.return_value = cpu
    p.memory_info.return_value = MagicMock(rss=mem)
    p.oneshot.return_value = contextlib.nullcontext()
    p.num_threads.return_value = 2
    p.cpu_affinity.return_value = [0, 1]
    p.nice.return_value = psutil.NORMAL_PRIORITY_CLASS
    p.create_time.return_value = 123.0
    p.exe.return_value = "C:\\x.exe"
    p.cmdline.return_value = ["x"]
    return p


def _make_denied(pid):
    p = MagicMock()
    p.pid = pid
    p.oneshot.return_value = contextlib.nullcontext()
    p.name.side_effect = psutil.AccessDenied(pid)
    return p


def test_list_processes_sort_cpu():
    procs = [_make_proc(1, "a", 10.0, 100), _make_proc(2, "b", 5.0, 200)]
    with patch.object(proc_mod.psutil, "process_iter", return_value=procs):
        res = proc_mod.list_processes(top=10, sort="cpu")
    assert [r["pid"] for r in res] == [1, 2]


def test_list_processes_stable_tie_break():
    procs = [
        _make_proc(9, "c", 5.0, 100),
        _make_proc(2, "b", 5.0, 100),
        _make_proc(5, "a", 5.0, 100),
    ]
    with patch.object(proc_mod.psutil, "process_iter", return_value=procs):
        res = proc_mod.list_processes(top=10, sort="cpu")
    assert [r["pid"] for r in res] == [2, 5, 9]


def test_list_processes_top():
    procs = [_make_proc(i, f"p{i}", float(i), i * 10) for i in range(5)]
    with patch.object(proc_mod.psutil, "process_iter", return_value=procs):
        res = proc_mod.list_processes(top=2, sort="cpu")
    assert len(res) == 2


def test_list_processes_sort_memory():
    procs = [_make_proc(1, "a", 1.0, 100), _make_proc(2, "b", 2.0, 200)]
    with patch.object(proc_mod.psutil, "process_iter", return_value=procs):
        res = proc_mod.list_processes(top=10, sort="memory")
    assert [r["pid"] for r in res] == [2, 1]


def test_list_processes_access_denied_row():
    procs = [_make_proc(1, "a", 1.0, 100), _make_denied(2)]
    with patch.object(proc_mod.psutil, "process_iter", return_value=procs):
        res = proc_mod.list_processes(top=10, sort="cpu")
    by_pid = {row["pid"]: row for row in res}
    assert by_pid[2]["denied"] is True
    assert by_pid[2]["name"] == "<access denied>"
    assert by_pid[2]["cpu"] is None


def test_list_processes_missing_process_is_skipped():
    missing = MagicMock()
    missing.pid = 77
    missing.oneshot.return_value = contextlib.nullcontext()
    missing.name.side_effect = psutil.NoSuchProcess(77)
    with patch.object(proc_mod.psutil, "process_iter", return_value=[missing]):
        assert proc_mod.list_processes() == []


def test_list_processes_rejects_unknown_sort():
    with pytest.raises(ValueError):
        proc_mod.list_processes(sort="name")


def test_inspect_process():
    p = _make_proc(5, "x", 1.0, 50)
    with patch.object(proc_mod.psutil, "Process", return_value=p):
        info = proc_mod.inspect_process(5)
    assert info["pid"] == 5
    assert info["name"] == "x"
    assert info["cpu_affinity"] == [0, 1]
    assert info["priority"] == "normal"


def test_set_priority_dry_run():
    p = _make_proc(5, "x", 1.0, 50)
    with patch.object(proc_mod, "check_target", return_value=p):
        res = proc_mod.set_priority(5, "high", dry_run=True)
    assert res["dry_run"] is True
    assert res["changed"] is True
    p.nice.assert_called_once_with()


def test_set_priority_apply():
    p = _make_proc(5, "x", 1.0, 50)
    with patch.object(proc_mod, "check_target", return_value=p):
        res = proc_mod.set_priority(5, "high", dry_run=False)
    assert res.get("applied") is True
    assert p.nice.call_args_list[-1].args == (psutil.HIGH_PRIORITY_CLASS,)


def test_set_priority_unknown_level():
    with pytest.raises(ValueError):
        proc_mod.set_priority(5, "extreme")


def test_set_affinity_dry_run():
    p = _make_proc(5, "x", 1.0, 50)
    with patch.object(proc_mod, "check_target", return_value=p):
        with patch.object(proc_mod.psutil, "cpu_count", return_value=8):
            res = proc_mod.set_affinity(5, [0, 2], dry_run=True)
    assert res["dry_run"] is True
    assert res["new"] == [0, 2]
    p.cpu_affinity.assert_called_once_with()


def test_set_affinity_apply():
    p = _make_proc(5, "x", 1.0, 50)
    with patch.object(proc_mod, "check_target", return_value=p):
        with patch.object(proc_mod.psutil, "cpu_count", return_value=8):
            res = proc_mod.set_affinity(5, [0, 2], dry_run=False)
    assert res.get("applied") is True
    assert p.cpu_affinity.call_args_list[-1].args == ([0, 2],)


def test_set_affinity_rejects_out_of_range():
    p = _make_proc(5, "x", 1.0, 50)
    with patch.object(proc_mod, "check_target", return_value=p):
        with patch.object(proc_mod.psutil, "cpu_count", return_value=4):
            with pytest.raises(ValueError):
                proc_mod.set_affinity(5, [0, 4], dry_run=True)


def test_set_priority_refuses_protected_pid():
    with pytest.raises(SafetyError):
        proc_mod.set_priority(4, "high", dry_run=True)


def test_set_affinity_refuses_protected_pid():
    with pytest.raises(SafetyError):
        proc_mod.set_affinity(0, [0], dry_run=True)


def test_parse_cpu_list():
    assert proc_mod.parse_cpu_list("0,2,4") == [0, 2, 4]
    assert proc_mod.parse_cpu_list(" 1 , 3 ") == [1, 3]
    assert proc_mod.parse_cpu_list("0,0,1") == [0, 1]


def test_parse_cpu_list_rejects_bad_values():
    with pytest.raises(ValueError):
        proc_mod.parse_cpu_list("")
    with pytest.raises(ValueError):
        proc_mod.parse_cpu_list("0,x")
