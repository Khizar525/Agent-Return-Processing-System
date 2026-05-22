"""
Agents Package — Re-exports public symbols from the openai-agents SDK
so that local modules can use `from agents import Agent, function_tool, ...`
without the local package shadowing the SDK.

Strategy: Prepend the SDK's agents directory to our __path__ so that
relative imports inside the SDK resolve to SDK submodules, while local
submodules (e.g. agents.policy_agent) remain findable. Then execute the
SDK's __init__.py in this module's namespace to copy all public exports.
"""
import importlib.util
import os as _os
import site as _site
import sys as _sys

_our_dir = _os.path.dirname(__file__)
_sdk_dir = None

for _sp in _site.getsitepackages():
    _candidate = _os.path.join(_sp, "agents")
    if _os.path.isdir(_candidate) and _candidate != _our_dir:
        _sdk_dir = _candidate
        break

if _sdk_dir is None:
    msg = "openai-agents SDK not found in site-packages; run: pip install openai-agents"
    raise ImportError(msg)

# Prepend SDK dir to __path__ so relative imports in the SDK work
__path__.insert(0, _sdk_dir)

# Execute the SDK's __init__.py in our module namespace
_sdk_init = _os.path.join(_sdk_dir, "__init__.py")
with open(_sdk_init, encoding="utf-8") as _f:
    _code = _f.read()
exec(_code, globals())
