"""packs/ — built-in DomainPacks. Importing this module registers them all.
Add your own with OUTLIER_MCB.pack.register_pack(...) or by elicitation (OUTLIER_MCB.elicit_pack).
"""
from . import coding, math, generic, numeric, causal, meta, number_theory, physics   # noqa: F401  (each registers on import)

BUILTIN = ["coding", "math", "generic", "numeric", "causal", "meta", "number_theory", "physics"]
