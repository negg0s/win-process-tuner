from unittest.mock import MagicMock, patch

import win_process_tuner.profile as profile_mod
from win_process_tuner.safety import SafetyError


def test_cpus_from_core_masks_picks_lowest_bit():
    masks = [(0, 0b0011), (0, 0b1100), (0, 0b01000000)]
    assert profile_mod.cpus_from_core_masks(masks) == [0, 2, 6]


def test_cpus_from_core_masks_rejects_empty_mask():
    assert profile_mod.cpus_from_core_masks([(0, 0)]) == []


def test_physical_core_cpus_uses_topology():
    masks = [(0, 0b0011), (0, 0b1100)]
    with patch.object(profile_mod, "_core_masks_windows", return_value=masks):
        with patch.object(profile_mod.psutil, "cpu_count") as count:
            count.side_effect = lambda logical=True: 4 if logical else 2
            assert profile_mod.physical_core_cpus() == [0, 2]


def test_physical_core_cpus_falls_back_when_unknown():
    with patch.object(profile_mod, "_core_masks_windows", return_value=None):
        with patch.object(profile_mod.psutil, "cpu_count", return_value=8):
            assert profile_mod.physical_core_cpus() == list(range(8))


def test_physical_core_cpus_falls_back_on_count_mismatch():
    masks = [(0, 0b0011)]
    with patch.object(profile_mod, "_core_masks_windows", return_value=masks):
        with patch.object(profile_mod.psutil, "cpu_count") as count:
            count.side_effect = lambda logical=True: 8 if logical else 4
            assert profile_mod.physical_core_cpus() == list(range(8))


def test_physical_core_cpus_falls_back_for_other_groups():
    masks = [(1, 0b0011)]
    with patch.object(profile_mod, "_core_masks_windows", return_value=masks):
        with patch.object(profile_mod.psutil, "cpu_count") as count:
            count.side_effect = lambda logical=True: 8 if logical else 2
            assert profile_mod.physical_core_cpus() == list(range(8))


def test_apply_gaming_dry_run():
    proc = MagicMock()
    proc.pid = 123
    with patch.object(profile_mod, "check_target", return_value=proc):
        res = profile_mod.apply_gaming_profile(123, dry_run=True, cpus=[0, 2, 4, 6])
    assert res["dry_run"] is True
    assert res["priority"] == "high"
    assert res["affinity"] == [0, 2, 4, 6]


def test_apply_gaming_apply_calls_both_settings():
    proc = MagicMock()
    proc.pid = 123
    with patch.object(profile_mod, "check_target", return_value=proc):
        with patch.object(profile_mod, "set_priority") as mock_priority:
            with patch.object(profile_mod, "set_affinity") as mock_affinity:
                res = profile_mod.apply_gaming_profile(123, dry_run=False, cpus=[0, 2])
    assert res["applied"] is True
    mock_priority.assert_called_once_with(123, "high", dry_run=False)
    mock_affinity.assert_called_once_with(123, [0, 2], dry_run=False)


def test_apply_gaming_refuses_protected_pid():
    with patch.object(profile_mod, "check_target", side_effect=SafetyError("protected")):
        try:
            profile_mod.apply_gaming_profile(4, dry_run=True)
            raised = False
        except SafetyError:
            raised = True
    assert raised


def test_physical_cores_heuristic_alias():
    with patch.object(profile_mod, "physical_core_cpus", return_value=[0, 1]):
        assert profile_mod.physical_cores_heuristic() == [0, 1]
