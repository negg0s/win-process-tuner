import contextlib

from unittest.mock import MagicMock, patch

import win_process_tuner.processes as proc_mod


def _make_proc(pid, name, cpu, mem, status="running"):
    p = MagicMock()
    p.pid = pid
    p.name.return_value = name
    p.status.return_value = status
    p.cpu_percent.return_value = cpu
    p.memory_info.return_value = MagicMock(rss=mem)
    p.oneshot.return_value.__enter__.return_value = None
    p.oneshot.return_value.__exit__.return_value = False
    p.num_threads.return_value = 2
    p.cpu_affinity.return_value = [0, 1]
    p.nice.return_value = 8
    p.create_time.return_value = 123.0
    p.exe.return_value = "C:\\x.exe"
    p.cmdline.return_value = ["x"]
    return p


def test_list_processes_sort_cpu():
    procs = [_make_proc(1, "a", 10.0, 100), _make_proc(2, "b", 5.0, 200)]
    with patch.object(proc_mod, "psutil") as m:
        m.process_iter.return_value = procs
        m.NoSuchProcess = Exception
        m.AccessDenied = Exception
        m.ZombieProcess = Exception
        res = proc_mod.list_processes(top=10, sort="cpu")
    assert [r["pid"] for r in res] == [1, 2]


def test_list_processes_top():
    procs = [_make_proc(i, f"p{i}", float(i), i * 10) for i in range(5)]
    with patch.object(proc_mod, "psutil") as m:
        m.process_iter.return_value = procs
        m.NoSuchProcess = Exception
        m.AccessDenied = Exception
        m.ZombieProcess = Exception
        res = proc_mod.list_processes(top=2, sort="cpu")
    assert len(res) == 2


def test_list_processes_sort_memory():
    procs = [_make_proc(1, "a", 1.0, 100), _make_proc(2, "b", 2.0, 200)]
    with patch.object(proc_mod, "psutil") as m:
        m.process_iter.return_value = procs
        m.NoSuchProcess = Exception
        m.AccessDenied = Exception
        m.ZombieProcess = Exception
        res = proc_mod.list_processes(top=10, sort="memory")
    assert [r["pid"] for r in res] == [2, 1]


def test_inspect_process():
    p = _make_proc(5, "x", 1.0, 50)
    with patch.object(proc_mod, "psutil") as m:
        m.Process.return_value = p
        info = proc_mod.inspect_process(5)
    assert info["pid"] == 5
    assert info["name"] == "x"
    assert info["cpu_affinity"] == [0, 1]


def test_set_priority_dry_run():
    p = _make_proc(5, "x", 1.0, 50)
    with patch.object(proc_mod, "psutil") as m:
        m.Process.return_value = p
        m.HIGH_PRIORITY_CLASS = 128
        m.ABOVE_NORMAL_PRIORITY_CLASS = 32768
        m.NORMAL_PRIORITY_CLASS = 32
        m.BELOW_NORMAL_PRIORITY_CLASS = 16384
        m.IDLE_PRIORITY_CLASS = 64
        res = proc_mod.set_priority(5, "high", dry_run=True)
    assert res["dry_run"] is True
    assert res["changed"] is True
    # only current read, no set
    assert p.nice.call_count == 1


def test_set_priority_apply():
    p = _make_proc(5, "x", 1.0, 50)
    with patch.object(proc_mod, "psutil") as m:
        m.Process.return_value = p
        m.HIGH_PRIORITY_CLASS = 128
        m.ABOVE_NORMAL_PRIORITY_CLASS = 32768
        m.NORMAL_PRIORITY_CLASS = 32
        m.BELOW_NORMAL_PRIORITY_CLASS = 16384
        m.IDLE_PRIORITY_CLASS = 64
        res = proc_mod.set_priority(5, "high", dry_run=False)
    assert res.get("applied") is True
    # last call sets
    assert p.nice.call_args_list[-1].args == (128,)


def test_set_affinity_dry_run():
    p = _make_proc(5, "x", 1.0, 50)
    with patch.object(proc_mod, "psutil") as m:
        m.Process.return_value = p
        res = proc_mod.set_affinity(5, [0, 2], dry_run=True)
    assert res["dry_run"] is True
    assert res["new"] == [0, 2]
    p.cpu_affinity.assert_called_once()  # read only


def test_set_affinity_apply():
    p = _make_proc(5, "x", 1.0, 50)
    with patch.object(proc_mod, "psutil") as m:
        m.Process.return_value = p
        res = proc_mod.set_affinity(5, [0, 2], dry_run=False)
    assert res.get("applied") is True
    assert p.cpu_affinity.call_args_list[-1].args == ([0, 2],)


def test_parse_cpus():
    assert proc_mod.parse_cpus("0,2,4") == [0, 2, 4]
    assert proc_mod.parse_cpus(" 1 , 3 ") == [1, 3]


def test_priority_levels_keys():
    assert "high" in proc_mod.PRIORITY_LEVELS
    assert "idle" in proc_mod.PRIORITY_LEVELS