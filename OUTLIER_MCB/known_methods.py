"""known_methods — a small, curated, CITED corpus of well-known methods, and an offline prior-art provider over
it. This raises the DEFAULT (no-network) novelty check from `LOCAL_ONLY` (compared only to a pack's own hand-
written families) to `OFFLINE_CORPUS_CHECKED`: even with no API key and no internet, a candidate is collided
against dozens of famous methods, so an idea that is just a rename of DeepSets, a token bucket, MAP-Elites, or
Tree-of-Thoughts is CAUGHT deterministically.

Honest by design: this corpus is BOUNDED and hand-curated, so it never unlocks the strongest online verdict —
finding no match here is reported as `OFFLINE_CORPUS_CHECKED`, a real but limited check, not proof of novelty.
Its second purpose is attribution: it documents prior art the project is aware of and engages with (a defence
against accidental reinvention), with a reference for each entry. It ships no third-party code — only names,
one-line summaries, and citations that are matters of public record.
"""
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import List

from .prior_art import PriorArtProvider, PriorArtResult
from .closures import _mentions          # whole-word matcher (avoids 'reactor'→'ReAct' substring hits)


@dataclass(frozen=True)
class KnownMethod:
    name: str
    aliases: str          # space-separated alias tokens for matching
    domain: str
    summary: str
    reference: str        # a public-record citation (author/venue/year or a stable identifier)


# A deliberately small, high-recall corpus of famous methods across the domains this engine touches. Each entry
# is public record; the point is to CATCH obvious renames offline, not to be exhaustive.
KNOWN_METHODS: List[KnownMethod] = [
    # ── set / pooling / neural architectures ──
    KnownMethod("DeepSets", "deepsets deep sets permutation invariant pooling sum-decomposition rho phi", "ml",
                "permutation-invariant set functions as ρ(Σ φ(xᵢ))", "Zaheer et al., NeurIPS 2017"),
    KnownMethod("PointNet", "pointnet point cloud max pooling symmetric function", "ml",
                "permutation-invariant point-cloud network with a symmetric max-pool", "Qi et al., CVPR 2017"),
    KnownMethod("Set Transformer", "set transformer inter-instance attention induced set attention", "ml",
                "attention-based set functions with inter-instance interactions", "Lee et al., ICML 2019"),
    KnownMethod("Transformer / self-attention", "transformer attention self-attention query key value", "ml",
                "sequence model built on scaled dot-product self-attention", "Vaswani et al., NeurIPS 2017"),
    KnownMethod("Graph Neural Network", "gnn graph neural network message passing", "ml",
                "learning on graphs via neighbourhood message passing", "Scarselli et al. 2009; Gilmer et al. 2017"),
    KnownMethod("Variational Autoencoder", "vae variational autoencoder latent elbo", "ml",
                "latent-variable generative model trained with the ELBO", "Kingma & Welling, ICLR 2014"),
    KnownMethod("Generative Adversarial Network", "gan generative adversarial discriminator generator", "ml",
                "generator vs discriminator adversarial training", "Goodfellow et al., NeurIPS 2014"),
    KnownMethod("Diffusion model", "diffusion denoising score-based ddpm", "ml",
                "generative model via iterative denoising of noise", "Ho et al. 2020; Song et al. 2021"),
    # ── search / optimization / open-endedness / QD ──
    KnownMethod("MAP-Elites", "map-elites quality diversity illumination behavioural map elites", "search",
                "quality-diversity illumination over a behaviour map", "Mouret & Clune 2015"),
    KnownMethod("Novelty Search", "novelty search behavioural novelty without objective", "search",
                "search rewarding behavioural novelty rather than an objective", "Lehman & Stanley 2011"),
    KnownMethod("POET", "poet paired open-ended trailblazer co-evolution environments", "search",
                "open-ended co-evolution of environments and solvers", "Wang et al. 2019"),
    KnownMethod("CMA-ES", "cma-es covariance matrix adaptation evolution strategy", "search",
                "covariance-matrix-adaptation evolution strategy", "Hansen & Ostermeier 2001"),
    KnownMethod("Genetic algorithm / programming", "genetic algorithm programming evolutionary crossover mutation", "search",
                "population search via selection, crossover, mutation", "Holland 1975; Koza 1992"),
    KnownMethod("Simulated annealing", "simulated annealing temperature cooling metropolis", "search",
                "stochastic search with a cooling acceptance schedule", "Kirkpatrick et al. 1983"),
    KnownMethod("Monte Carlo Tree Search", "mcts monte carlo tree search ucb1 rollout", "search",
                "tree search guided by UCB over sampled rollouts", "Kocsis & Szepesvári 2006; Coulom 2006"),
    KnownMethod("Beam search", "beam search top-k pruning breadth", "search",
                "breadth-limited best-first search keeping the top-k", "classical"),
    # ── program synthesis / symbolic regression ──
    KnownMethod("DreamCoder", "dreamcoder library learning abstraction wake sleep", "synthesis",
                "program induction with learned reusable abstractions", "Ellis et al. 2021"),
    KnownMethod("FunSearch", "funsearch llm evaluator evolutionary programs", "synthesis",
                "LLM + evaluator evolutionary search over programs", "Romera-Paredes et al., Nature 2024"),
    KnownMethod("Symbolic regression", "symbolic regression eureqa pysr equation discovery", "synthesis",
                "search for closed-form equations fitting data", "Schmidt & Lipson 2009; Cranmer 2020"),
    # ── LLM reasoning scaffolds ──
    KnownMethod("Chain-of-Thought", "chain of thought cot step-by-step reasoning", "llm",
                "prompting a model to reason step by step", "Wei et al. 2022"),
    KnownMethod("Tree-of-Thoughts", "tree of thoughts tot deliberate search branches", "llm",
                "deliberate search over branching reasoning states", "Yao et al. 2023"),
    KnownMethod("Reflexion", "reflexion verbal self-reflection memory retry", "llm",
                "verbal self-reflection on failure to steer the next try", "Shinn et al. 2023"),
    KnownMethod("Self-Refine", "self-refine iterative self-feedback improvement", "llm",
                "iterative self-feedback to refine an output", "Madaan et al. 2023"),
    KnownMethod("ReAct", "react reason act tool interleave", "llm",
                "interleaving reasoning traces with tool actions", "Yao et al. 2022"),
    KnownMethod("DSPy", "dspy declarative pipeline optimize prompts", "llm",
                "declarative, optimizable LM pipelines", "Khattab et al. 2023"),
    KnownMethod("Retrieval-augmented generation", "rag retrieval augmented generation grounding", "llm",
                "condition generation on retrieved documents", "Lewis et al. 2020"),
    # ── rate limiting (a built-in coding pack domain) ──
    KnownMethod("Token bucket", "token bucket rate limiter refill burst", "coding",
                "rate limiting by consuming tokens refilled over time", "classical networking"),
    KnownMethod("Leaky bucket", "leaky bucket rate limiter queue drain", "coding",
                "rate limiting by draining a queue at a fixed rate", "Turner 1986"),
    KnownMethod("Sliding-window rate limit", "sliding window rate limit log counter", "coding",
                "rate limiting over a moving time window", "classical"),
    KnownMethod("Fixed-window counter", "fixed window counter rate limit reset", "coding",
                "rate limiting by counting within reset windows", "classical"),
    # ── creativity heuristics ──
    KnownMethod("TRIZ", "triz inventive principles contradictions altshuller", "creativity",
                "inventive principles derived from patent contradictions", "Altshuller 1946+"),
    KnownMethod("SCAMPER", "scamper substitute combine adapt modify eliminate reverse", "creativity",
                "checklist of transformations for ideation", "Eberle 1971"),
    KnownMethod("Lateral thinking", "lateral thinking de bono provocation", "creativity",
                "provocation-based non-linear ideation", "de Bono 1967"),
    KnownMethod("Conceptual blending", "conceptual blending bisociation cross-domain fusion", "creativity",
                "meaning from blending distant conceptual spaces", "Fauconnier & Turner 2002; Koestler 1964"),
    KnownMethod("Boden's three creativities", "combinatorial exploratory transformational creativity boden", "creativity",
                "combinatorial / exploratory / transformational creativity", "Boden 1990"),
    # ── math / number theory ──
    KnownMethod("Sieve methods", "sieve eratosthenes selberg brun parity", "math",
                "counting primes/structure by sieving; the parity barrier", "classical; Selberg; Brun"),
    KnownMethod("Generating functions", "generating function algebraic differential ogf egf", "math",
                "encode a sequence as coefficients of a formal series", "classical"),
    KnownMethod("Holonomic / P-recursive", "holonomic p-recursive polynomial coefficient recurrence", "math",
                "sequences satisfying a polynomial-coefficient recurrence", "Zeilberger 1990"),
    KnownMethod("Automated theorem proving", "z3 lean smt sat theorem prover certificate", "math",
                "machine-checked proof via SMT/ITP systems", "de Moura & Bjørner 2008; Lean/Isabelle"),
]

_ALIAS_SPLIT = re.compile(r"[^a-z0-9]+")


def _tokset(text: str) -> set:
    return {t for t in _ALIAS_SPLIT.split((text or "").lower()) if len(t) > 1}


def _match_score(query_tokens: set, method: KnownMethod, query_text: str = "") -> float:
    """How strongly the query evokes a known method: token overlap with its name+aliases, boosted to 1.0 when
    the method's name appears in the query text (a direct mention of a famous method is an unambiguous hit)."""
    keys = _tokset(method.name + " " + method.aliases)
    if not keys or not query_tokens:
        return 0.0
    low = (query_text or "").lower()
    # a direct, unambiguous mention = the FULL method name as a whole phrase (whole-word, not substring:
    # 'reactor safety' must not fire 'ReAct'; 'poetry generation model' must not fire 'Diffusion model')
    if _mentions(low, [method.name.lower()]):
        return 1.0
    return round(len(query_tokens & keys) / len(keys), 4)


class OfflineCorpusProvider(PriorArtProvider):
    """A deterministic, zero-network prior-art provider over the curated KNOWN_METHODS corpus. It catches renames
    of famous methods offline and reports the honest scope `OFFLINE_CORPUS_CHECKED` — a real but BOUNDED check
    (a hand-curated corpus), never the strongest online verdict."""
    name = "offline-corpus"
    is_online = False
    source_type = "docs"

    def __init__(self, threshold: float = 0.25, max_results: int = 5, corpus: List[KnownMethod] = None):
        self.threshold = threshold
        self.max_results = max_results
        self.corpus = corpus if corpus is not None else KNOWN_METHODS

    def search(self, query: str) -> List[PriorArtResult]:
        q = _tokset(query)
        scored = [(m, _match_score(q, m, query)) for m in self.corpus]
        hits = sorted([ms for ms in scored if ms[1] >= self.threshold], key=lambda ms: -ms[1])[:self.max_results]
        return [PriorArtResult(title=m.name, summary=f"{m.summary} [{m.domain}]", url="",
                               source=self.name, source_type="docs", similarity=s,
                               raw={"reference": m.reference, "domain": m.domain}) for m, s in hits]

    def research(self, query: str) -> dict:
        matches = [r.as_match() for r in self.search(query)]
        return {
            "matches": matches,
            # honest scope: a real check against a curated corpus, but bounded and offline — NOT the live web.
            "novelty_scope": "OFFLINE_CORPUS_CHECKED",
            "coverage_level": "CURATED_OFFLINE",
            "checked_sources": [{"provider": self.name, "online": False, "count": len(self.corpus)}],
            "failed_sources": [],
        }


def known_method_names() -> List[str]:
    return [m.name for m in KNOWN_METHODS]
