"""A repository-style tool that passes an object down the command tree.

Run:
    python examples/repo.py --repo-home /tmp/r clone https://example.com/x.git
    python examples/repo.py commit -m "msg"
"""
from __future__ import annotations

import os

import clirelay


class Repo:
    def __init__(self, home):
        self.home = home
        self.config = {}

    def __repr__(self):
        return f"<Repo {self.home}>"


pass_repo = clirelay.make_pass_decorator(Repo)


@clirelay.group()
@clirelay.option("--repo-home", default=".repo", help="Repository directory.")
@clirelay.option("--config", "-c", nargs=2, multiple=True, help="Config key/value.")
@clirelay.pass_context
def cli(ctx, repo_home, config):
    """A git-like repository tool."""
    ctx.obj = Repo(os.path.abspath(repo_home))
    for key, value in config:
        ctx.obj.config[key] = value


@cli.command()
@clirelay.argument("url")
@pass_repo
def clone(repo, url):
    """Clone URL into the repository home."""
    clirelay.echo(f"Cloning {url} into {repo.home}")


@cli.command()
@clirelay.option("-m", "--message", required=True, help="Commit message.")
@pass_repo
def commit(repo, message):
    """Record a commit."""
    clirelay.echo(f"[{repo.home}] commit: {message}")


if __name__ == "__main__":
    cli()
