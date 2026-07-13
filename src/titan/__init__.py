"""TITAN platform — deterministic execution platform."""

from titan._core import version as _rust_version

__version__ = _rust_version()
