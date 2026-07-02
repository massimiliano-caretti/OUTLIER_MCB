"""evaluators — pluggable EXTERNAL evaluators that settle a Candidate by something real.

FunSearch's discipline: the generator proposes, an external evaluator (never the generator) decides.
This package collects the non-repo settlers. Today:

  symbolic  — settle by the DATA: fit a formula in the hypothesis class the broken assumption unlocks,
              then falsify it by held-out residual + a shuffled-column negative control.
  causal    — settle by an INTERVENTION test: estimate treatment→outcome under the adjustment set the
              broken assumption selects, then falsify by placebo + confounding refutation (correlation ≠
              causation); latent confounding is reported HUMAN, never AUTO.

(The repo settler lives in creative_search.code_evaluator.)
"""
from .symbolic import (symbolic_evaluator, basis_from_candidate, expansions_for, least_squares,
                       Formula, Term, DEFAULT_BUILDERS)
from .causal import causal_evaluator
from .backends import pysr_backend, gplearn_backend, dowhy_backend
from .base import (EvaluationResult, BaseEvaluator, CallableEvaluator, PropertyEvaluator,
                   NoveltyEvaluator, PytestEvaluator, CompositeEvaluator)
from .hidden import HiddenEvaluator

__all__ = ["symbolic_evaluator", "basis_from_candidate", "expansions_for", "least_squares",
           "Formula", "Term", "DEFAULT_BUILDERS", "causal_evaluator", "pysr_backend", "gplearn_backend", "dowhy_backend",
           "EvaluationResult", "BaseEvaluator", "CallableEvaluator", "PropertyEvaluator",
           "NoveltyEvaluator", "PytestEvaluator", "CompositeEvaluator", "HiddenEvaluator"]
