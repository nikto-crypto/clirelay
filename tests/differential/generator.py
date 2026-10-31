"""Generate command specs and argv deterministically, build against both libs.

A *spec* is a plain data description of a command (its options and arguments).
``build_command(module, spec)`` constructs the equivalent command with either
clirelay or the oracle, so the same program can be compared.  ``argvs_for`` turns
a spec into a batch of argument vectors covering valid input, typos, missing
values, extras, ``--``/``=`` syntax, clustered shorts, unknown options, and bad
types.
"""
from __future__ import annotations

import random
import typing as t

OPTION_TYPES = [
    "str", "int", "float", "bool_flag", "flag_pair", "count",
    "choice", "intrange", "floatrange", "multiple", "nargs2", "uuid",
]


def _callback(module: t.Any):
    def cb(**kwargs: t.Any) -> None:
        parts = []
        for k in sorted(kwargs):
            v = kwargs[k]
            parts.append(f"{k}={v!r}:{type(v).__name__}")
        module.echo("|".join(parts))

    return cb


def build_command(module: t.Any, spec: dict) -> t.Any:
    params = []
    for o in spec["options"]:
        params.append(_build_option(module, o))
    for a in spec["arguments"]:
        params.append(_build_argument(module, a))
    return module.Command(
        spec.get("name", "cli"),
        params=params,
        callback=_callback(module),
        help=spec.get("help"),
    )


def _build_option(module: t.Any, o: dict) -> t.Any:
    kind = o["kind"]
    decls = list(o["decls"])
    kwargs: dict[str, t.Any] = {}
    if kind == "str":
        pass
    elif kind == "int":
        kwargs["type"] = module.INT
    elif kind == "float":
        kwargs["type"] = module.FLOAT
    elif kind == "bool_flag":
        kwargs["is_flag"] = True
    elif kind == "flag_pair":
        pass  # decls already contain --x/--no-x
    elif kind == "count":
        kwargs["count"] = True
    elif kind == "choice":
        kwargs["type"] = module.Choice(o["choices"])
    elif kind == "intrange":
        kwargs["type"] = module.IntRange(o["min"], o["max"])
    elif kind == "floatrange":
        kwargs["type"] = module.FloatRange(o["min"], o["max"])
    elif kind == "multiple":
        kwargs["multiple"] = True
    elif kind == "nargs2":
        kwargs["nargs"] = 2
        kwargs["type"] = module.INT
    elif kind == "uuid":
        kwargs["type"] = module.UUID
    if o.get("required"):
        kwargs["required"] = True
    if o.get("default") is not None:
        kwargs["default"] = o["default"]
    if o.get("envvar"):
        kwargs["envvar"] = o["envvar"]
    if o.get("help"):
        kwargs["help"] = o["help"]
    return module.Option(decls, **kwargs)


def _build_argument(module: t.Any, a: dict) -> t.Any:
    kwargs: dict[str, t.Any] = {}
    if a.get("nargs"):
        kwargs["nargs"] = a["nargs"]
    if a.get("type") == "int":
        kwargs["type"] = module.INT
    if "required" in a:
        kwargs["required"] = a["required"]
    return module.Argument([a["name"]], **kwargs)


_WORDS = ["alpha", "beta", "gamma", "src", "dst", "x", "y"]


def gen_spec(rng: random.Random, index: int) -> dict:
    n_opts = rng.randint(0, 4)
    n_args = rng.randint(0, 2)
    used_short = set()
    used_names = set()
    options = []
    for i in range(n_opts):
        kind = rng.choice(OPTION_TYPES)
        name = f"o{i}"
        while name in used_names:
            name = f"o{i}_{rng.randint(0, 9)}"
        used_names.add(name)
        decls = [f"--{name}"]
        if kind == "flag_pair":
            decls = [f"--{name}/--no-{name}"]
        elif rng.random() < 0.4:
            short = None
            for ch in name + "abcdefg":
                if ch.isalnum() and ch not in used_short:
                    short = ch
                    break
            if short:
                used_short.add(short)
                decls.append(f"-{short}")
        o: dict = {"kind": kind, "decls": decls}
        if kind == "choice":
            o["choices"] = rng.choice([["a", "b"], ["red", "green", "blue"]])
        if kind == "intrange":
            o["min"], o["max"] = 0, rng.choice([5, 10, 100])
        if kind == "floatrange":
            o["min"], o["max"] = 0, 1
        if kind not in ("bool_flag", "flag_pair", "count") and rng.random() < 0.3:
            o["required"] = True
        if kind in ("int",) and rng.random() < 0.3:
            o["default"] = rng.randint(0, 5)
        if kind == "str" and rng.random() < 0.3:
            o["default"] = rng.choice(_WORDS)
        if rng.random() < 0.15:
            o["envvar"] = f"APP_{name.upper()}"
        if rng.random() < 0.5:
            o["help"] = f"Option {name} does something useful."
        options.append(o)

    arguments = []
    for i in range(n_args):
        a: dict = {"name": rng.choice(["src", "dst", "items", "target"]) + str(i)}
        if rng.random() < 0.3:
            a["nargs"] = rng.choice([2, -1])
        if rng.random() < 0.3:
            a["type"] = "int"
        if rng.random() < 0.3:
            a["required"] = False
        arguments.append(a)

    help_text = None
    if rng.random() < 0.5:
        help_text = "A generated command.\n\nWith a second paragraph of description."
    return {"name": "cli", "options": options, "arguments": arguments, "help": help_text}


def argvs_for(rng: random.Random, spec: dict) -> list[list[str]]:
    """Produce a batch of argv variants for a spec."""
    argvs: list[list[str]] = [[], ["--help"]]

    # a valid-ish invocation
    valid: list[str] = []
    for o in spec["options"]:
        if rng.random() < 0.6:
            valid.extend(_sample_option_use(rng, o))
    for a in spec["arguments"]:
        valid.extend(_sample_argument_use(rng, a))
    argvs.append(valid)

    # typo of a known long option
    long_opts = [d for o in spec["options"] for d in o["decls"] if d.startswith("--")]
    if long_opts:
        base = rng.choice(long_opts).split("/")[0]
        if len(base) > 3:
            typo = base[:-1] + ("z" if base[-1] != "z" else "q")
            argvs.append([typo])

    # unknown option
    argvs.append(["--definitely-not-an-option"])

    # extra positional
    argvs.append([*valid, "extra_positional"])

    # '=' syntax and missing value
    value_opts = [
        o for o in spec["options"]
        if o["kind"] not in ("bool_flag", "flag_pair", "count")
    ]
    if value_opts:
        o = rng.choice(value_opts)
        decl = o["decls"][0].split("/")[0]
        argvs.append([f"{decl}=somevalue"])
        argvs.append([decl])  # missing value

    # clustered short flags
    shorts = [d[1:] for o in spec["options"] for d in o["decls"]
              if len(d) == 2 and d.startswith("-")
              and o["kind"] in ("bool_flag", "count")]
    if len(shorts) >= 2:
        argvs.append(["-" + "".join(shorts[:3])])

    # bad type
    int_opts = [o for o in spec["options"] if o["kind"] in ("int", "intrange")]
    if int_opts:
        argvs.append([int_opts[0]["decls"][0].split("/")[0], "notanumber"])

    # '--' terminator
    argvs.append(["--", "after", "dashes"])

    return argvs


def _sample_option_use(rng: random.Random, o: dict) -> list[str]:
    decl = o["decls"][0].split("/")[0]
    kind = o["kind"]
    if kind == "bool_flag":
        return [decl]
    if kind == "flag_pair":
        return [rng.choice(o["decls"][0].split("/"))]
    if kind == "count":
        return [decl] * rng.randint(1, 3)
    if kind == "choice":
        return [decl, rng.choice(o["choices"])]
    if kind == "int":
        return [decl, str(rng.randint(0, 20))]
    if kind == "intrange":
        return [decl, str(rng.randint(0, o["max"]))]
    if kind == "float":
        return [decl, str(round(rng.random() * 10, 2))]
    if kind == "floatrange":
        return [decl, str(round(rng.random(), 2))]
    if kind == "multiple":
        return [decl, "one", decl, "two"]
    if kind == "nargs2":
        return [decl, "1", "2"]
    if kind == "uuid":
        return [decl, "12345678-1234-5678-1234-567812345678"]
    return [decl, rng.choice(_WORDS)]


def _sample_argument_use(rng: random.Random, a: dict) -> list[str]:
    nargs = a.get("nargs", 1)
    is_int = a.get("type") == "int"

    def one() -> str:
        return str(rng.randint(0, 9)) if is_int else rng.choice(_WORDS)

    if nargs == -1:
        return [one() for _ in range(rng.randint(0, 3))]
    if nargs and nargs > 1:
        return [one() for _ in range(nargs)]
    return [one()]
