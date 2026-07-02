"""packs/coding — a NON-ML domain pack (systems/algorithms), to prove agnosticism.

Example domain: rate limiting / scheduling for a distributed service. No executable world_factory
(world_factory=None) — for a software domain the world-test is a property test / constructed trace,
which the kernel emits as a SPEC rather than runs. The verdicts here are HEURISTIC (clearly flagged),
not validated against a specific project.
"""
from __future__ import annotations
from ..core import Assumption
from ..pack import DomainPack, register_pack

A = [
    Assumption("time_windowed", "Rate is measured over temporal windows.",
               "Token/leaky/fixed/sliding windows are all time-based.",
               "Rate could be measured over a non-temporal resource (cost, concurrency, work units).",
               ["token_bucket", "fixed_window", "sliding_window"],
               "a trace where temporal-window limiters violate fairness but a cost-based one does not."),
    Assumption("tenant_independent", "Fairness is per-tenant and independent across tenants.",
               "Each tenant gets its own bucket; simplest to reason about.",
               "Fairness may be coupled (max-min across tenants sharing a bottleneck).",
               ["token_bucket", "gcra"],
               "a workload where independent buckets starve a tenant a coupled policy would protect."),
    Assumption("stateless_local", "The limiter decides locally/statelessly per node.",
               "Local decisions scale and avoid coordination latency.",
               "A small amount of shared state could give global fairness cheaply.",
               ["fixed_window", "sliding_window"],
               "a multi-node trace where local limiters over/under-admit vs a sketch-shared one."),
    Assumption("cost_uniform", "Every request costs the same.",
               "One token per request is the default accounting.",
               "Heterogeneous request cost changes who should be throttled.",
               ["token_bucket", "leaky_bucket"],
               "a mix of cheap/expensive requests where uniform accounting mis-prioritizes."),
    Assumption("sync_decision", "The admit/deny decision sits on the synchronous request path.",
               "Limiting is an inline gate.",
               "Decisions could be deferred/predictive, shaping before arrival.",
               ["gcra", "leaky_bucket"],
               "a bursty trace where inline gating thrashes but predictive shaping is smooth."),
]
_axes = {
    "REPRESENTATION": {"priority": 3, "verdict": "HEURISTIC: changing WHAT you measure (cost/concurrency vs time) is often the highest-leverage break — verify it is not just renaming."},
    "OBJECTIVE":      {"priority": 3, "verdict": "HEURISTIC: redefining the goal (coupled max-min fairness vs per-tenant) reframes the whole design."},
    "DECOMPOSITION":  {"priority": 2, "verdict": "HEURISTIC: moving the local/global boundary (shared sketch) can dominate; watch the coordination cost."},
    "COST_MODEL":     {"priority": 2, "verdict": "HEURISTIC: non-uniform cost accounting changes correctness of every policy above."},
    "INTERFACE":      {"priority": 1, "verdict": "HEURISTIC: deferred/predictive vs inline decision — powerful but easy to over-engineer."},
}
_dim = {"time_windowed": "REPRESENTATION", "tenant_independent": "OBJECTIVE",
        "stateless_local": "DECOMPOSITION", "cost_uniform": "COST_MODEL", "sync_decision": "INTERFACE"}
_edges = [
    ("cost_uniform", "blocks", "time_windowed", "uniform cost hides that windows mis-account heterogeneous work"),
    ("stateless_local", "implies", "tenant_independent", "purely local state makes cross-tenant coupling invisible"),
    ("time_windowed", "needs_new_data", "workload_distribution", "a non-temporal representation needs the arrival/cost distribution"),
    ("tenant_independent", "needs_new_data", "production_traces", "coupled fairness needs real multi-tenant traces"),
]

PACK = DomainPack(
    name="coding",
    keywords=["rate limit", "rate-limit", "scheduler", "scheduling", "throttle", "api gateway",
              "distributed", "fairness", "tenant", "latency", "queue", "load balanc", "backpressure",
              "algorithm for", "concurrency"],
    box_name="the standard token/leaky/window limiter family (per-request, per-tenant, time-windowed)",
    assumptions=A,
    relations=_edges,
    dimension_of=_dim,
    box_assumptions={"time_windowed", "tenant_independent", "cost_uniform"},
    axes=_axes,
    known_families=["token_bucket", "leaky_bucket", "fixed_window", "sliding_window", "gcra", "queue_theory"],
    info_kinds={"production_traces": "real multi-tenant arrival/cost traces → reveals where uniform policies fail.",
                "workload_distribution": "the arrival & cost distribution → enables a cost/concurrency representation.",
                "slo_targets": "explicit per-tenant SLOs → turns 'fairness' into a checkable objective.",
                "cost_telemetry": "per-request cost telemetry → makes non-uniform accounting possible."},
    failure_memory={},
    world_factory=None,
)
register_pack(PACK)
