from unittest.mock import MagicMock, patch

import win_process_tuner.profile as profile_mod


def test_physical_cores_heuristic_no_ht():
    with patch("win_process_tuner.profile.psutil") as m:
        m.cpu_count.side_effect = lambda logical=True: 4 if logical else 4
        cpus = profile_mod.physical_cores_heuristic()
    assert cpus == [0, 1, 2, 3]


def test_physical_cores_heuristic_ht():
    def cpu_count(logical=True):
        return 8 if logical else 4
    with patch("win_process_tuner.profile.psutil") as m:
        m.cpu_count.side_effect = cpu_count
        cpus = profile_mod.physical_cores_heuristic()
    assert cpus == [0, 2, 4, 6]


def test_apply_gaming_dry_run():
    def cpu_count(logical=True):
        return 8 if logical else 4
    with patch("win_process_tuner.profile.psutil") as m:
        m.cpu_count.side_effect = cpu_count
        res = profile_mod.apply_gaming_profile(123, dry_run=True)
    assert res["dry_run"] is True
    assert res["priority"] == "high"
    assert res["affinity"] == [0, 2, 4, 6]


def test_apply_gaming_apply():
    def cpu_count(logical=True):
        return 4 if logical else 4
    p = MagicMock()
    p.nice.return_value = 8
    p.cpu_affinity.return_value = [0, 1, 2, 3]
    with patch("win_process_tuner.profile.psutil") as m:
        m.cpu_count.side_effect = cpu_count
        with patch("win_process_tuner.processes.psutil") as pm:
            pm.Process.return_value = p
            pm.HIGH_PRIORITY_CLASS = 128
            pm.ABOVE_NORMAL_PRIORITY_CLASS = 32768
            pm.NORMAL_PRIORITY_CLASS = 32
            pm.BELOW_NORMAL_PRIORITY_CLASS = 16384
            pm.IDLE_PRIORITY_CLASS = 64
            res = profile_mod.apply_gaming_profile(123, dry_run=False)
    assert res.get("applied") is True