"""Shared test configuration — HA module stubs.

The integration uses Python 3.12+ syntax (type statements) and imports
HA internals not available in this test environment.  We pre-seed
sys.modules with stubs so individual modules can be imported.
"""

from __future__ import annotations

import importlib
import sys
from types import ModuleType
from unittest.mock import MagicMock

# -- Stub out all HA modules ------------------------------------------------
_HA_STUBS = [
    "homeassistant",
    "homeassistant.components",
    "homeassistant.components.binary_sensor",
    "homeassistant.components.button",
    "homeassistant.components.http",
    "homeassistant.components.sensor",
    "homeassistant.config_entries",
    "homeassistant.const",
    "homeassistant.core",
    "homeassistant.helpers",
    "homeassistant.helpers.aiohttp_client",
    "homeassistant.helpers.config_validation",
    "homeassistant.helpers.device_registry",
    "homeassistant.helpers.entity",
    "homeassistant.helpers.entity_platform",
    "homeassistant.helpers.update_coordinator",
    "homeassistant.loader",
    "homeassistant.util",
    "homeassistant.util.dt",
    "voluptuous",
]

for mod_name in _HA_STUBS:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()

# -- Stub the integration's own package to avoid __init__.py import chain ----
# __init__.py and data.py use Python 3.12+ syntax / heavy HA imports.
# We create a minimal package stub, then individually import the modules
# that our tests actually need (alerts.py, coordinator.py, const.py).

_PKG = "custom_components.prociv_madeira"
_PKG_PARTS = ["custom_components", _PKG]

for pkg in _PKG_PARTS:
    if pkg not in sys.modules:
        mod = ModuleType(pkg)
        mod.__path__ = []  # type: ignore[attr-defined]
        mod.__package__ = pkg
        sys.modules[pkg] = mod

# Ensure `custom_components` is a proper package
if not hasattr(sys.modules["custom_components"], "__path__"):
    sys.modules["custom_components"].__path__ = []  # type: ignore[attr-defined]

# Now import the actual modules we need, skipping __init__.py
_MOD_DIR = "/workspace/prociv_madeira/custom_components/prociv_madeira"

for mod_name in ("const", "alerts", "coordinator", "data", "entity"):
    full_name = f"{_PKG}.{mod_name}"
    if full_name not in sys.modules:
        try:
            spec = importlib.util.spec_from_file_location(
                full_name, f"{_MOD_DIR}/{mod_name}.py"
            )
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules[full_name] = module
                spec.loader.exec_module(module)
        except (SyntaxError, ImportError):
            # data.py uses `type` statement (3.12+); stub it out
            sys.modules[full_name] = MagicMock()
