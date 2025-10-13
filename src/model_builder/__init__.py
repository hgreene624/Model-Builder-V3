"""Top-level package for model_builder service modules.

Exposes the core namespaces so downstream callers can rely on concise imports
such as `import model_builder.profiles` during the migration period.
"""

from . import profiles, optimization, analytics, ui

__all__ = ["profiles", "optimization", "analytics", "ui"]
