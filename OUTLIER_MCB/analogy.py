"""analogy — the cross-domain analogy engine: transfer a mechanism from a DISTANT domain (the move behind
much human invention). Genetic algorithm = evolution ⊕ search; simulated annealing = metallurgy ⊕ optimization.

It reuses the engine's own domains (registered DomainPacks ARE the domains it knows — numeric, causal,
coding, math, meta; elicit more for biology/economics/etc.) and the disciplined transport operator. For a
target domain it ranks source domains by DISTANCE (far = more lateral), maps a source mechanism onto a
target axis, and emits a TESTABLE transfer claim — the analogy GENERATES, it never certifies: the
transported idea enters with zero novelty credit and must beat the target's baseline on a world-test.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class Analogy:
    source_domain: str
    target_domain: str
    source_mechanism: str            # the source assumption/principle whose break is transferred
    target_axis: str
    analogy_distance: float          # semantic distance between the two domains' boxes (far = more lateral)
    transfer_claim: str              # the falsifiable claim the transfer makes
    candidate: object = None         # the transported Candidate (still must die on the target's world-test)
    source_url: str = ""             # provenance when the mechanism came from an online source

    def markdown(self) -> str:
        return (f"- **{self.source_domain} → {self.target_domain}** (distance {self.analogy_distance}) · "
                f"transfer '{self.source_mechanism}' onto axis {self.target_axis}"
                + (f" [{self.source_url}]" if self.source_url else "") + f"\n    - {self.transfer_claim}")


# distant domains to mine for mechanisms — the farther from software, the more lateral the analogy.
DISTANT_DOMAINS = ("biology", "ecology", "economics", "physics", "game theory", "control theory",
                   "evolution", "network science", "thermodynamics", "immunology", "linguistics")


@dataclass
class OnlineMechanism:
    domain: str
    mechanism: str                   # the principle, as a phrase (title/abstract from a real source)
    url: str = ""
    source_type: str = "web"


class OnlineCrossDomainAnalogyEngine:
    """Mine mechanisms from DISTANT real domains via an online provider (any PriorArtProvider: arXiv /
    OpenAlex / GitHub / a web CallableOnlineProvider), then transfer each PRINCIPLE into the target problem
    as a TESTABLE claim. The internal-pack engine is a small space; the real world is the lateral one.
    Honest: a transfer GENERATES — it must be prior-art-checked AND pass a world-test before it counts."""
    def __init__(self, provider, domains: Optional[List[str]] = None):
        self.provider = provider
        self.domains = list(domains) if domains is not None else list(DISTANT_DOMAINS)

    def mine_mechanisms(self, problem: str, per_domain: int = 1) -> List[OnlineMechanism]:
        out: List[OnlineMechanism] = []
        for domain in self.domains:
            try:
                res = self.provider.research(f"{problem} {domain} mechanism principle") or {}
            except Exception:
                continue
            for mtch in (res.get("matches") or res.get("sources") or [])[:per_domain]:   # accept both provider shapes
                mech = (mtch.get("title") or "")[:120] + (f" — {mtch.get('summary', '')[:120]}" if mtch.get("summary") else "")
                if mech.strip():
                    out.append(OnlineMechanism(domain=domain, mechanism=mech, url=mtch.get("url", ""),
                                               source_type=mtch.get("source_type", "web")))
        return out

    def _transfer_claim(self, problem: str, mech: OnlineMechanism) -> str:
        return (f"by analogy to {mech.domain} (where «{mech.mechanism}» is a known mechanism): port that "
                f"PRINCIPLE into «{problem}» — it enters with ZERO novelty credit and must (1) pass a prior-art "
                f"check (is this transfer already done?) and (2) beat the baseline on a world-test where the "
                f"box fails; if the analogy doesn't transfer, it dies.")

    def analogies(self, problem: str, k: int = 5, embedder=None) -> List[Analogy]:
        """Top-k FARTHEST online analogies (distance = how unlike the problem the source mechanism is)."""
        from .embeddings import semantic_distance
        mechs = self.mine_mechanisms(problem)
        out = [Analogy(source_domain=mch.domain, target_domain=problem[:40], source_mechanism=mch.mechanism,
                       target_axis="—", analogy_distance=round(semantic_distance(mch.mechanism, problem, embedder=embedder), 3),
                       transfer_claim=self._transfer_claim(problem, mch), source_url=mch.url)
               for mch in mechs]
        return sorted(out, key=lambda a: -a.analogy_distance)[:k]


class CrossDomainAnalogyEngine:
    """For `target_pack`, find distant source domains and transfer their mechanisms. `source_packs` defaults
    to every registered pack except the target and 'generic'."""
    def __init__(self, target_pack, source_packs: Optional[List] = None):
        from .pack import list_packs, get_pack
        self.target = target_pack
        self.sources = source_packs if source_packs is not None else [
            get_pack(n) for n in list_packs() if n not in (target_pack.name, "generic")]

    def source_domains(self) -> List[str]:
        return [p.name for p in self.sources]

    def analogy_distance(self, source_pack) -> float:
        """Distance between the two domains (their box descriptions). Far domains → more lateral analogies."""
        from .embeddings import semantic_distance
        return round(semantic_distance(source_pack.box_name, self.target.box_name), 3)

    def transfer(self, source_pack, assumption_name: str = "") -> Optional[Analogy]:
        """Transport one source mechanism onto the target via the disciplined transport operator."""
        from .generators import transport_break
        cand = transport_break(source_pack, self.target, assumption_name)
        if cand is None:
            return None
        src = cand.assumptions[0] if cand.assumptions else "?"
        axis = cand.breaks[0] if cand.breaks else "—"
        return Analogy(source_domain=source_pack.name, target_domain=self.target.name, source_mechanism=src,
                       target_axis=axis, analogy_distance=self.analogy_distance(source_pack),
                       transfer_claim=cand.discipline, candidate=cand)

    def map(self) -> List[Analogy]:
        """One analogy per source domain (the top mechanism), each a disciplined, falsifiable transfer."""
        return [a for a in (self.transfer(p) for p in self.sources) if a is not None]

    def best_analogies(self, k: int = 3) -> List[Analogy]:
        """The FARTHEST analogies first — distance is the lateral-thinking signal (a near domain is mundane;
        a far one is where invention hides). Each still owes its death to the target's world-test."""
        return sorted(self.map(), key=lambda a: -a.analogy_distance)[:k]


# ── #5: a function API over real ONLINE sources — each transfer carries its own world-test + prior-art hook ──
@dataclass
class MechanismTransfer:
    source_domain: str
    target_problem: str
    source_mechanism: str
    claim: str                       # the falsifiable transfer claim
    world_test: str                  # the concrete test that would KILL the transfer
    source_url: str = ""
    distance: float = 0.0
    prior_art: object = None         # a NoveltyVerdict once analogy_prior_art_audit has run (else None)

    def markdown(self) -> str:
        return (f"- **{self.source_domain} → {self.target_problem}** (distance {self.distance})\n"
                f"    - mechanism: {self.source_mechanism}\n    - claim: {self.claim}\n"
                f"    - world-test: {self.world_test}" + (f"\n    - [{self.source_url}]" if self.source_url else ""))


def discover_remote_mechanisms(problem: str, provider, domains: Optional[List[str]] = None,
                               per_domain: int = 1) -> List[OnlineMechanism]:
    """Mine candidate mechanisms from DISTANT real domains (papers/GitHub/web via any PriorArtProvider)."""
    return OnlineCrossDomainAnalogyEngine(provider, domains=domains).mine_mechanisms(problem, per_domain=per_domain)


def transfer_mechanism(source_mechanism, target_problem: str, embedder=None) -> MechanismTransfer:
    """Port one source mechanism onto a target problem as a TESTABLE transfer (claim + world-test). Accepts an
    OnlineMechanism or a (domain, mechanism[, url]) tuple. The transfer enters with ZERO novelty credit."""
    from .embeddings import semantic_distance
    if isinstance(source_mechanism, OnlineMechanism):
        domain, mech, url = source_mechanism.domain, source_mechanism.mechanism, source_mechanism.url
    else:
        domain, mech = source_mechanism[0], source_mechanism[1]
        url = source_mechanism[2] if len(source_mechanism) > 2 else ""
    claim = (f"by analogy to {domain} (where «{mech}» is a known mechanism): port that PRINCIPLE into "
             f"«{target_problem}» — it must beat the baseline on a world-test AND pass a prior-art check, else it dies.")
    world_test = (f"construct an instance of «{target_problem}» where the standard solution fails and the ported "
                  f"«{mech}» mechanism provably does better; if it does not transfer, the analogy is refuted.")
    return MechanismTransfer(source_domain=domain, target_problem=target_problem, source_mechanism=mech,
                             claim=claim, world_test=world_test, source_url=url,
                             distance=round(semantic_distance(mech, target_problem, embedder=embedder), 3))


def testable_analogy_claim(transfer: MechanismTransfer) -> Dict:
    """The falsifiable content of a transfer: its claim and the world-test that would kill it."""
    return {"claim": transfer.claim, "world_test": transfer.world_test,
            "source_domain": transfer.source_domain, "source_mechanism": transfer.source_mechanism}


def analogy_prior_art_audit(transfer: MechanismTransfer, provider):
    """Has this transfer ALREADY been done? Run a real prior-art audit on the transfer claim; attach + return
    the NoveltyVerdict. An analogy that is already common prior art is not lateral, it is mundane."""
    from .novelty import prior_art_audit
    probe = f"{transfer.source_mechanism} applied to {transfer.target_problem}"
    verdict = prior_art_audit(probe, provider)
    transfer.prior_art = verdict
    return verdict


def analogy_online_ablation(provider, problem: str = "an adaptive rate limiter") -> Dict:
    """Ablation for #5: an ONLINE distant-domain transfer is farther (more lateral) than a local within-text
    variation, and yields a prior-art-checkable claim. Distant must beat local on distance."""
    from .embeddings import semantic_distance
    mechs = discover_remote_mechanisms(problem, provider)
    if not mechs:
        return {"ran": False, "reason": "provider returned no mechanisms"}
    transfer = transfer_mechanism(mechs[0], problem)
    local_variation = f"{problem} but slightly tuned"          # a mundane local move
    local_distance = round(semantic_distance(local_variation, problem), 3)
    has_world_test = bool(transfer.world_test) and "refuted" in transfer.world_test
    return {"ran": True, "distant_distance": transfer.distance, "local_distance": local_distance,
            "distant_more_lateral": transfer.distance > local_distance, "has_world_test": has_world_test,
            "earns_keep": transfer.distance > local_distance and has_world_test}
