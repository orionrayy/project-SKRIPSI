"""PowerPoint authoring and verification helpers.

The Morph patcher itself uses only the Python standard library. Shape-authoring
helpers import python-pptx lazily and are available with the slides extra.
"""

from .morph import apply_morph, inspect_deck

__all__ = ["apply_morph", "inspect_deck"]
