"""Custom validation with callbacks and a custom ParamType.

Run:
    python examples/validation.py --port 8080 --url https://example.com
    python examples/validation.py --port 70000 --url https://example.com
"""
from __future__ import annotations

import clirelay


class URLParamType(clirelay.ParamType):
    name = "url"

    def convert(self, value, param, ctx):
        if not value.startswith(("http://", "https://")):
            self.fail(f"{value!r} is not a valid URL.", param, ctx)
        return value


URL = URLParamType()


def validate_even(ctx, param, value):
    if value is not None and value % 2 != 0:
        raise clirelay.BadParameter("must be an even number.")
    return value


@clirelay.command()
@clirelay.option("--port", type=clirelay.IntRange(1, 65535), required=True)
@clirelay.option("--url", type=URL, required=True)
@clirelay.option("--workers", type=int, callback=validate_even, default=2)
def cli(port, url, workers):
    """Serve URL on PORT with an even number of workers."""
    clirelay.echo(f"Serving {url} on port {port} with {workers} workers.")


if __name__ == "__main__":
    cli()
