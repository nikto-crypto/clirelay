"""Shell completion with a custom completer.

Enable (bash):
    eval "$(_COMPLETION_PY_COMPLETE=bash_source python examples/completion.py)"

Then type:
    python examples/completion.py deploy --env <TAB>
"""
from __future__ import annotations

import clirelay
from clirelay.shell_completion import CompletionItem


def complete_env(ctx, param, incomplete):
    envs = ["dev", "staging", "production"]
    return [CompletionItem(e) for e in envs if e.startswith(incomplete)]


@clirelay.group()
def cli():
    """A deployment tool with shell completion."""


@cli.command()
@clirelay.option("--env", shell_complete=complete_env, help="Target environment.")
@clirelay.argument("service", type=clirelay.Choice(["web", "api", "worker"]))
def deploy(env, service):
    """Deploy SERVICE to an environment."""
    clirelay.echo(f"Deploying {service} to {env}.")


if __name__ == "__main__":
    cli()
