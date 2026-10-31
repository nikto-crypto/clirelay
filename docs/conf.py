"""Sphinx configuration for the clirelay documentation."""
from __future__ import annotations

import importlib.metadata

project = "clirelay"
author = "Nick Serapiglia"
copyright = "2026, Nick Serapiglia"

try:
    release = importlib.metadata.version("clirelay")
except importlib.metadata.PackageNotFoundError:
    release = "0.0.0"
version = release

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.intersphinx",
]

myst_enable_extensions = ["colon_fence", "deflist"]

source_suffix = {".md": "markdown", ".rst": "restructuredtext"}
master_doc = "index"

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

html_theme = "furo"
html_title = f"clirelay {release}"

autodoc_member_order = "bysource"
autodoc_typehints = "description"

intersphinx_mapping = {"python": ("https://docs.python.org/3", None)}

# Keep the docs build hermetic: don't import the oracle or require a network.
nitpicky = False
