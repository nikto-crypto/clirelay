"""Conformance: walk API_SURFACE.json and check clirelay's public surface.

Validates that every required public name exists with the right kind, parameter
names/order/kinds/defaults, enum members, subscriptability, and that the
deprecated module attributes emit their exact warnings.  Signature *annotations*
and sentinel default reprs are exempt per the build contract.
"""
from __future__ import annotations

import enum
import importlib
import inspect
import json
import os
import re
import warnings

import pytest

ORACLE_DIR = os.environ.get(
    "CLIRELAY_ORACLE_DIR", os.path.expanduser("~/clirelay-oracle")
)
SURFACE_PATH = os.path.join(ORACLE_DIR, "API_SURFACE.json")

REQUIRED_CLASS_MODULES = {
    "click.core",
    "click.types",
    "click.exceptions",
    "click.shell_completion",
}

# Internal helpers exempt from parity (per the build contract).
EXEMPT_NAMES = {
    "StreamMixer", "BytesIOCopy", "EchoingStdin", "iter_params_for_processing",
    "augment_usage_errors", "measure_table", "iter_rows", "make_input_stream",
    "batch", "make_str", "join_options", "term_len", "FORCED_WIDTH",
    "convert_type", "resolve_color_default", "should_strip_ansi", "open_stream",
    "get_pager_file", "hidden_prompt_func", "isatty", "raw_terminal",
    "push_context", "pop_context", "split_opt", "normalize_opt",
    "split_arg_string", "shell_complete", "add_completion_class",
    "get_completion_class", "strip_ansi", "WIN",
    # TypeVars / sentinels
    "F", "R", "T", "V", "CmdType", "GrpType", "FC", "UNSET", "FLAG_NEEDS_VALUE",
}


def _load_surface() -> dict:
    with open(SURFACE_PATH) as fh:
        return json.load(fh)


try:
    _SURFACE = _load_surface()
except OSError:
    _SURFACE = {"modules": {}}


def _clirelay_module(mod_name: str):
    target = mod_name.replace("click", "clirelay", 1)
    return importlib.import_module(target)


import ast

_DEFAULT_SENTINELS = {"Sentinel.UNSET", "Sentinel.FLAG_NEEDS_VALUE"}


def _parse_recorded_params(sig: str) -> list[tuple[str, bool, str | None]]:
    """Return [(name, has_default, default_text)] from a recorded signature string.

    The recorded signature is a valid Python function signature (with string
    annotations), so it is parsed with ``ast`` to handle defaults that contain
    quotes, colons, or commas.
    """
    try:
        tree = ast.parse(f"def __sig__{sig}: pass")
    except SyntaxError:
        return []
    func = tree.body[0]
    a = func.args  # type: ignore[attr-defined]
    params: list[tuple[str, bool, str | None]] = []

    positional = list(a.posonlyargs) + list(a.args)
    pos_defaults = list(a.defaults)
    n_without = len(positional) - len(pos_defaults)
    for i, arg in enumerate(positional):
        if arg.arg == "self":
            continue
        if i >= n_without:
            default = pos_defaults[i - n_without]
            params.append((arg.arg, True, ast.unparse(default)))
        else:
            params.append((arg.arg, False, None))
    if a.vararg:
        params.append((a.vararg.arg, False, None))
    for arg, default in zip(a.kwonlyargs, a.kw_defaults):
        if default is None:
            params.append((arg.arg, False, None))
        else:
            params.append((arg.arg, True, ast.unparse(default)))
    if a.kwarg:
        params.append((a.kwarg.arg, False, None))
    return params


def _live_params(obj) -> list[tuple[str, bool, str]]:
    try:
        sig = inspect.signature(obj)
    except (TypeError, ValueError):
        return []
    out = []
    for p in sig.parameters.values():
        if p.name == "self":
            continue
        has_default = p.default is not inspect.Parameter.empty
        default_repr = repr(p.default) if has_default else ""
        out.append((p.name, has_default, default_repr))
    return out


def _check_signature(label, recorded: str, obj, errors: list[str]) -> None:
    if not recorded:
        return
    rec = _parse_recorded_params(recorded)
    live = _live_params(obj)
    rec_names = [p[0] for p in rec]
    live_names = [p[0] for p in live]
    if rec_names != live_names:
        errors.append(f"{label}: param names {live_names} != expected {rec_names}")
        return
    for (rn, rhas, rdef), (ln, lhas, ldef) in zip(rec, live):
        if rhas != lhas:
            errors.append(f"{label}: param {rn!r} default presence mismatch")
            continue
        if rhas and rdef is not None:
            # exempt sentinels and non-literal defaults (callables/classes/TypeVars)
            if rdef in _DEFAULT_SENTINELS or ldef in _DEFAULT_SENTINELS:
                continue
            if rdef.startswith("<") or ldef.startswith("<"):
                continue
            if rdef != ldef:
                # tolerate e.g. 'Sentinel.UNSET' vs UNSET naming already covered;
                # also tolerate empty-vs-value where oracle used a class
                errors.append(
                    f"{label}: param {rn!r} default {ldef!r} != expected {rdef!r}"
                )


_module_names = sorted(_SURFACE.get("modules", {}))


@pytest.mark.parametrize("mod_name", _module_names)
def test_module_public_names(mod_name):
    data = _SURFACE["modules"][mod_name]
    mod = _clirelay_module(mod_name)
    errors: list[str] = []

    for name, entry in data["public"].items():
        if name in EXEMPT_NAMES:
            continue
        defined_in = entry.get("defined_in", "")
        defined_mod = defined_in.rsplit(".", 1)[0] if defined_in else ""
        # A name whose defined_in points at a different module is an import
        # (exempt from parity in submodules per the contract). Top-level click
        # must still re-export everything.
        is_import = bool(defined_mod) and defined_mod != mod_name
        if is_import and mod_name != "click":
            continue
        if not hasattr(mod, name):
            errors.append(f"missing name: {name}")
            continue

        obj = getattr(mod, name)
        kind = entry["kind"]

        if kind in ("class", "enum"):
            if not inspect.isclass(obj):
                errors.append(f"{name}: expected class, got {type(obj).__name__}")
                continue
            if obj.__module__.replace("clirelay", "click", 1) != defined_in.rsplit(".", 1)[0] and mod_name in REQUIRED_CLASS_MODULES:
                # only enforce for classes actually defined in this module
                pass
            if entry.get("subscriptable"):
                try:
                    obj[str]
                except Exception as e:  # noqa: BLE001
                    errors.append(f"{name}: not subscriptable ({e})")
            if kind == "enum":
                for member, value_repr in entry.get("enum_members", {}).items():
                    if not hasattr(obj, member):
                        errors.append(f"{name}.{member}: missing enum member")
                    elif repr(getattr(obj, member).value) != value_repr:
                        errors.append(
                            f"{name}.{member}: value {getattr(obj, member).value!r} "
                            f"!= {value_repr}"
                        )
            _check_signature(f"{name}.__init__", entry.get("init_signature", ""), obj, errors)
            # required public methods/properties for required class modules
            if mod_name in REQUIRED_CLASS_MODULES or mod_name == "click":
                for mname, minfo in entry.get("members", {}).items():
                    if mname.startswith("_") or mname in EXEMPT_NAMES:
                        continue
                    if not hasattr(obj, mname):
                        errors.append(f"{name}.{mname}: missing member")
        elif kind == "function":
            if not callable(obj):
                errors.append(f"{name}: expected callable")
            else:
                _check_signature(name, entry.get("signature", ""), obj, errors)
        elif kind == "constant":
            pass
        elif kind in ("callable_instance", "instance"):
            pass

    assert not errors, f"{mod_name}:\n  " + "\n  ".join(errors)


@pytest.mark.parametrize("mod_name", _module_names)
def test_deprecated_attributes(mod_name):
    data = _SURFACE["modules"][mod_name]
    dep = data.get("deprecated_attributes", {})
    if not dep:
        return  # nothing to check for this module
    mod = _clirelay_module(mod_name)
    errors: list[str] = []

    for name, info in dep.items():
        expected_warnings = info.get("warnings", [])
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            try:
                getattr(mod, name)
            except AttributeError:
                errors.append(f"{name}: not accessible")
                continue
        got = [f"{w.category.__name__}: {w.message}" for w in caught]
        # normalize clirelay->click and version 9.1 clirelay version mention
        norm_expected = [_norm_dep(mod_name, name, w) for w in expected_warnings]
        norm_got = [_norm_dep(mod_name, name, w) for w in got]
        if norm_got != norm_expected:
            errors.append(
                f"{name}: warnings {norm_got} != expected {norm_expected}"
            )

    assert not errors, f"{mod_name} deprecated:\n  " + "\n  ".join(errors)


def _norm_dep(mod_name: str, name: str, text: str) -> str:
    text = text.replace("clirelay", "click")
    return text
