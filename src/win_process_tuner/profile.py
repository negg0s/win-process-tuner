"""Process profiles (gaming) and physical core detection."""

import ctypes
import os
import struct

import psutil

from .processes import set_affinity, set_priority
from .safety import check_target

RELATION_PROCESSOR_CORE = 0


def _core_masks_windows():
    """Return [(group, mask)] for each physical core, or None on failure."""
    if os.name != "nt":
        return None
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        func = kernel32.GetLogicalProcessorInformationEx
        func.argtypes = [
            ctypes.c_int,
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_ulong),
        ]
        func.restype = ctypes.c_int
        length = ctypes.c_ulong(0)
        func(RELATION_PROCESSOR_CORE, None, ctypes.byref(length))
        if length.value == 0:
            return None
        buffer = ctypes.create_string_buffer(length.value)
        if not func(RELATION_PROCESSOR_CORE, buffer, ctypes.byref(length)):
            return None
        data = buffer.raw[: length.value]
    except Exception:
        return None

    ptr_size = struct.calcsize("P")
    mask_format = "<Q" if ptr_size == 8 else "<I"
    group_affinity_size = 16 if ptr_size == 8 else 12
    masks = []
    offset = 0
    try:
        while offset + 8 <= len(data):
            relation, size = struct.unpack_from("<II", data, offset)
            if size < 8 or offset + size > len(data):
                return None
            if relation == RELATION_PROCESSOR_CORE:
                group_count = struct.unpack_from("<H", data, offset + 30)[0]
                pos = offset + 32
                for _ in range(group_count):
                    mask = struct.unpack_from(mask_format, data, pos)[0]
                    group = struct.unpack_from("<H", data, pos + ptr_size)[0]
                    masks.append((group, mask))
                    pos += group_affinity_size
            offset += size
    except (struct.error, IndexError):
        return None
    return masks or None


def cpus_from_core_masks(masks):
    """Pick one logical CPU (lowest bit) from each core mask."""
    cpus = set()
    for _group, mask in masks:
        bit = 0
        while bit < 64 and not (mask >> bit) & 1:
            bit += 1
        if bit == 64:
            return []
        cpus.add(bit)
    return sorted(cpus)


def physical_core_cpus():
    """Return one logical CPU index per physical core.

    Falls back to every logical CPU when the topology is unknown, so the
    result never pins a process to a guessed set of processors.
    """
    logical = psutil.cpu_count(logical=True) or 1
    masks = _core_masks_windows()
    if not masks or logical > 64:
        return list(range(logical))
    if any(group != 0 for group, _mask in masks):
        return list(range(logical))
    cpus = cpus_from_core_masks(masks)
    physical = psutil.cpu_count(logical=False)
    if not cpus or (physical is not None and len(cpus) != physical):
        return list(range(logical))
    return cpus


def physical_cores_heuristic():
    """Backward compatible name for physical_core_cpus."""
    return physical_core_cpus()


def apply_gaming_profile(pid, dry_run=False, cpus=None, yes=False):
    """Set high priority and restrict affinity to physical cores."""
    proc = check_target(pid)
    if cpus is None:
        cpus = physical_core_cpus()
    result = {
        "pid": proc.pid,
        "profile": "gaming",
        "priority": "high",
        "affinity": list(cpus),
        "dry_run": dry_run,
    }
    if dry_run:
        return result
    set_priority(pid, "high", dry_run=False)
    set_affinity(pid, cpus, dry_run=False)
    result["applied"] = True
    return result
