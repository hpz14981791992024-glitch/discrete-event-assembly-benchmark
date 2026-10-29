"""Optional C++ implementation of the simulator's action checks."""

from __future__ import annotations

import ctypes
from pathlib import Path
from typing import Optional


def _text(value: Optional[str]) -> Optional[bytes]:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"expected a string or None, got {type(value).__name__}")
    if "\0" in value:
        raise ValueError("C++ action checker does not accept embedded NUL characters")
    return value.encode("utf-8")


class CppActionChecker:
    """Load the shared library once and keep it alive while checking actions."""

    def __init__(self, library_path: str) -> None:
        path = Path(library_path).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"C++ checker library not found: {path}")
        try:
            self._library = ctypes.CDLL(str(path))
            self._check = self._library.vcrisp_check_action
            abi_version = self._library.vcrisp_checker_abi_version
            compiler = self._library.vcrisp_checker_compiler
        except (OSError, AttributeError) as exc:
            raise RuntimeError(f"cannot load C++ checker from {path}: {exc}") from exc
        abi_version.argtypes = []
        abi_version.restype = ctypes.c_int
        if abi_version() != 1:
            raise RuntimeError(f"incompatible C++ checker ABI in {path}")
        compiler.argtypes = []
        compiler.restype = ctypes.c_char_p
        self.metadata = {
            "backend": "cpp",
            "compiler": compiler().decode("utf-8"),
            "abi_version": 1,
        }
        self._check.argtypes = [ctypes.c_char_p] * 6 + [ctypes.c_int] * 9
        self._check.restype = ctypes.c_char_p

    def __call__(self, world, action) -> Optional[str]:
        result = self._check(
            _text(action.kind),
            _text(action.target),
            _text(action.declared_tool),
            _text(world.complexity),
            _text(world.current_tool),
            _text(world.holding),
            int(bool(world.pose_known)),
            int(bool(world.fixture_verified)),
            int(bool(world.cover_installed)),
            int(bool(world.fastened)),
            int(bool(world.quality_pass)),
            int(bool(world.label_applied)),
            int(world.station_blocked_ticks > 0),
            int(world.driver_unavailable_ticks > 0),
            int(bool(world.rework_required)),
        )
        return result.decode("ascii") if result is not None else None
