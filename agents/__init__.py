"""
Agents package — re-exports openai-agents SDK and provides local agent definitions.

Resolves naming conflict between the local agents/ directory and the installed
openai-agents SDK.
"""

import sys as _sys
import importlib as _importlib

_site_packages = next((p for p in _sys.path if "site-packages" in p.lower()), None)
if _site_packages:
    _our_mod = _sys.modules.pop("agents", None)
    _sys.path.insert(0, _site_packages)
    _sdk_agents = _importlib.import_module("agents")
    _sys.path.remove(_site_packages)
    _sys.modules["agents"] = _our_mod  # type: ignore[assignment]
    for _name in getattr(_sdk_agents, "__all__", []):
        if not _name.startswith("_"):
            globals()[_name] = getattr(_sdk_agents, _name)
