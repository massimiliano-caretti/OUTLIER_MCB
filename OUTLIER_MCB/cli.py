"""OUTLIER_MCB CLI (domain-agnostic).
  python -m OUTLIER_MCB.cli creative  --problem problem.md          # the one-call brief
  python -m OUTLIER_MCB.cli preflight --problem problem.md [--pack coding] [--out runs/x]
  python -m OUTLIER_MCB.cli branch    --problem problem.md [-k 3]    # divergence
  python -m OUTLIER_MCB.cli graph     --problem problem.md          # the assumption graph
  python -m OUTLIER_MCB.cli packs                                    # list registered packs
  python -m OUTLIER_MCB.cli elicit    --problem problem.md          # build a pack for an unknown domain
"""
from __future__ import annotations
import argparse, json
from pathlib import Path


def _read(p):
    return Path(p).read_text() if p and Path(p).exists() else (p or "")


def cmd_creative(a):
    from .preflight import creative
    problem = _read(a.problem) or "invent a genuinely new solution for <describe your problem>"
    print(creative(problem, k=a.k))


def cmd_invent(a):
    from .invent import invent
    problem = _read(a.problem) or "invent a genuinely new solution for <describe your problem>"
    print(invent(problem, beam=a.beam, rounds=a.rounds).markdown())


def cmd_preflight(a):
    from .preflight import preflight_creative_request
    from .pack import get_pack
    problem = _read(a.problem) or "invent a genuinely new solution for <describe your problem>"
    pack = get_pack(a.pack) if getattr(a, "pack", None) else None
    pf = preflight_creative_request(problem, pack=pack)
    print(f"[domain pack selected: {pf['pack']}  · guard_ok={pf['domain_guard']['ok']}]\n")
    print(pf["instructions"])
    if a.out:
        rundir = Path(a.out); rundir.mkdir(parents=True, exist_ok=True)
        (rundir / "preflight.json").write_text(json.dumps(pf, indent=2, default=str))
        (rundir / "assistant_instructions.txt").write_text(pf["instructions"])
        print(f"\n[written] {rundir}/preflight.json + assistant_instructions.txt")


def cmd_branch(a):
    from .pack import select_pack
    from . import kernel
    problem = _read(a.problem)
    pack, hits = select_pack(problem)
    print(f"[pack: {pack.name} · hits={hits}]\nbranches in tension:")
    for b in kernel.branch_on_assumptions(problem, pack, k=a.k):
        print(f"  [{b['stance']:11s}] break '{b['assumption']}' on axis {b['axis']} → {b['negation']}")


def cmd_graph(a):
    from .pack import select_pack
    from . import kernel
    problem = _read(a.problem)
    pack, hits = select_pack(problem)
    g = kernel.graph_of(pack, problem)
    print(f"[pack: {pack.name} · hits={hits}]")
    print(g.ascii())
    print("\ncentral:", g.central(3), "\nbreakable:", g.breakable(), "\ndata requirements:", g.data_requirements())


def cmd_packs(a):
    from .pack import list_packs, get_pack
    from .pack_quality import pack_quality
    for name in list_packs():
        p = get_pack(name)
        print(f"  {name:9s} quality={pack_quality(p)['overall']} axes={list(p.axes)} | "
              f"families={p.known_families[:4]}{'…' if len(p.known_families) > 4 else ''}")


def cmd_openended(a):
    """FunSearch-style creative search → a QD map of diverse, externally-scored elites (Impl 3)."""
    from .creative_search import creative_search
    problem = _read(a.problem) or "invent a genuinely new solution for <describe your problem>"
    print(creative_search(problem, budget=a.budget).markdown())


def cmd_archive_report(a):
    """Illuminate the idea space into a MAP-Elites archive and print the coverage report (Impl 1)."""
    from .invent import illuminate
    from .pack import select_pack
    problem = _read(a.problem) or "invent a genuinely new solution"
    pack, _ = select_pack(problem)
    print(illuminate(pack, problem, iterations=a.budget).markdown())


def cmd_diverge(a):
    """Divergent-thinking engine: many distinct ideas + fluency/flexibility/originality/elaboration (Impl 4)."""
    from .divergence import diverge
    print(diverge(_read(a.problem) or "invent a genuinely new solution", n=a.n).markdown())


def cmd_self_improve(a):
    """The recursive central test: OUTLIER_MCB proposes improvements to itself, triaged by judge (Impl 9)."""
    from .self_improve import propose_self_improvements
    print(propose_self_improvements(budget=a.budget, repo_path=".").markdown())


def cmd_llm_search(a):
    """LLM-in-the-loop: propose → prior-art gate → materialize a failing test → run RED→GREEN → score."""
    import json as _json
    from .llm import SubprocessLLMProvider
    from .llm_loop import llm_openended_search
    if not a.llm_cmd:
        print("error: --llm-cmd is required (a CLI that reads a prompt on stdin and prints candidates as JSON)")
        return
    llm = SubprocessLLMProvider(a.llm_cmd)
    r = llm_openended_search(
        _read(a.problem) or "invent a genuinely new solution", llm,
        repo_path=a.repo_path, budget=a.budget, samples_per_round=a.samples_per_round,
        execute=a.execute, materialize=a.materialize, timeout=a.timeout,
        max_json_repairs=a.max_json_repairs, max_test_repairs=a.max_test_repairs,
        max_impl_repairs=a.max_impl_repairs, keep_failed=a.keep_failed, dry_run=a.dry_run)
    print(_json.dumps(r.to_dict(), indent=2) if a.json else r.markdown())


def cmd_readiness(a):
    from .readiness import readiness_report, markdown
    print(markdown(readiness_report(run_tests=getattr(a, "tests", False))))


def cmd_readiness_discovery(a):
    """The discovery-readiness gate. Without --online it can only reach LOCAL_ONLY_READY (it does not fake
    a global-novelty claim); pass --online to probe live providers (network + possible rate limits)."""
    from .readiness_discovery import readiness_discovery_report, markdown
    provider = None
    if getattr(a, "online", False):
        from .prior_art import CompositePriorArtProvider, ArxivPriorArtProvider, OpenAlexProvider, GitHubPriorArtProvider
        provider = CompositePriorArtProvider([ArxivPriorArtProvider(), OpenAlexProvider(), GitHubPriorArtProvider()])
    print(markdown(readiness_discovery_report(online_provider=provider)))


def cmd_elicit(a):
    from .elicit import elicit_pack
    e = elicit_pack(_read(a.problem))
    print(f"source={e['source']} confidence={e['confidence']} pack={e['pack'].name}")
    if e["request"]:
        print("\nELICITATION REQUIRED — fill this scaffold (the spark), then pack_from_spec + kernel falsifies:")
        for i, q in enumerate(e["request"]["questions"], 1):
            print(f"  {i}. {q}")


def cmd_evolve_task(a):
    """Run the evolutionary invention loop on the built-in VERIFIABLE task (objective evaluator + baseline)."""
    from .evolve import symbolic_invention_task, evolve_invention
    task = symbolic_invention_task()
    res = evolve_invention(task["problem"], task["evaluator"], budget=getattr(a, "budget", 14),
                           pack=task["pack"], mode=getattr(a, "mode", "breadth"))
    print(res.markdown())
    if getattr(a, "memory_out", None):
        res.memory.save_jsonl(a.memory_out)
        print(f"\n[saved {len(res.memory.records)} records → {a.memory_out}]")


def cmd_evolution_report(a):
    """Print an auditable report from a saved evolution memory (JSONL)."""
    from .evolution_memory import EvolutionMemory
    mem = EvolutionMemory.load_jsonl(a.memory)
    print(mem.markdown())
    for r in mem.top_k(5):
        print(f"- [{r.id}] {r.candidate_name} · score {r.score} · verified={r.verified} · "
              f"Δbaseline={r.improvement_over_baseline} · scope={r.novelty_scope or '—'}")


def cmd_self_evolve(a):
    """Propose improvements to a target module (engine on itself). DRY-RUN by default: nothing is applied."""
    from .self_evolve import self_evolve
    res = self_evolve(a.target, budget=getattr(a, "budget", 5), dry_run=not getattr(a, "apply", False))
    print(res.markdown())


def cmd_activate(a):
    """Print the provider-agnostic activation block to drop into AGENTS.md / CLAUDE.md / .cursorrules."""
    from .activation import activation_snippet
    print(activation_snippet())


def cmd_brief(a):
    """The one-call standing brief for a request — rules + which assumption to break."""
    from .activation import assistant_brief
    print(assistant_brief(_read(a.problem)))


def cmd_route(a):
    """Compact per-turn route for assistants that call the library continuously."""
    from .activation import assistant_route
    route = assistant_route(_read(a.problem), full_brief=getattr(a, "full_brief", False))
    print(json.dumps(route.as_dict(), indent=2) if getattr(a, "json", False) else route.markdown())


def cmd_explore(a):
    """The single front door: route → generate → settle externally → audit → one honest report."""
    from .studio import explore
    print(explore(_read(a.problem), budget=getattr(a, "budget", 16)).markdown())


def cmd_lint(a):
    """Epistemic honesty linter: rewrite scientific over-claims in files/docs. Exit code 1 if any are found
    (so it works as a pre-commit / CI gate)."""
    import sys
    from .linter import lint_file, lint_text, lint_report
    findings = []
    for path in (a.paths or []):
        findings += lint_file(path)
    if a.text:
        findings += lint_text(a.text)
    print(lint_report(findings))
    sys.exit(1 if findings else 0)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="OUTLIER_MCB"); sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("creative"); p.add_argument("--problem"); p.add_argument("-k", type=int, default=3); p.set_defaults(f=cmd_creative)
    p = sub.add_parser("invent"); p.add_argument("--problem"); p.add_argument("--beam", type=int, default=5); p.add_argument("--rounds", type=int, default=2); p.set_defaults(f=cmd_invent)
    p = sub.add_parser("preflight"); p.add_argument("--problem"); p.add_argument("--pack"); p.add_argument("--out"); p.set_defaults(f=cmd_preflight)
    p = sub.add_parser("branch"); p.add_argument("--problem"); p.add_argument("-k", type=int, default=3); p.set_defaults(f=cmd_branch)
    p = sub.add_parser("graph"); p.add_argument("--problem"); p.set_defaults(f=cmd_graph)
    p = sub.add_parser("packs"); p.set_defaults(f=cmd_packs)
    p = sub.add_parser("diverge"); p.add_argument("--problem"); p.add_argument("-n", type=int, default=8); p.set_defaults(f=cmd_diverge)
    p = sub.add_parser("self-improve"); p.add_argument("--budget", type=int, default=30); p.set_defaults(f=cmd_self_improve)
    p = sub.add_parser("llm-search"); p.add_argument("--problem"); p.add_argument("--repo-path", dest="repo_path", default=".")
    p.add_argument("--llm-cmd", dest="llm_cmd"); p.add_argument("--budget", type=int, default=30)
    p.add_argument("--samples-per-round", dest="samples_per_round", type=int, default=4)
    p.add_argument("--max-json-repairs", dest="max_json_repairs", type=int, default=0)
    p.add_argument("--max-test-repairs", dest="max_test_repairs", type=int, default=0)
    p.add_argument("--max-impl-repairs", dest="max_impl_repairs", type=int, default=0)
    p.add_argument("--timeout", type=int, default=60)
    p.add_argument("--keep-failed", dest="keep_failed", action="store_true")
    p.add_argument("--dry-run", dest="dry_run", action="store_true")
    p.add_argument("--json", action="store_true")
    p.add_argument("--execute", action="store_true"); p.add_argument("--materialize", action="store_true"); p.set_defaults(f=cmd_llm_search)
    p = sub.add_parser("openended"); p.add_argument("--problem"); p.add_argument("--budget", type=int, default=40); p.set_defaults(f=cmd_openended)
    p = sub.add_parser("archive-report"); p.add_argument("--problem"); p.add_argument("--budget", type=int, default=30); p.set_defaults(f=cmd_archive_report)
    p = sub.add_parser("readiness"); p.add_argument("--tests", action="store_true"); p.set_defaults(f=cmd_readiness)
    p = sub.add_parser("readiness-discovery"); p.add_argument("--online", action="store_true"); p.set_defaults(f=cmd_readiness_discovery)
    p = sub.add_parser("evolve-task"); p.add_argument("--budget", type=int, default=14)
    p.add_argument("--mode", default="breadth"); p.add_argument("--memory-out", dest="memory_out"); p.set_defaults(f=cmd_evolve_task)
    p = sub.add_parser("evolution-report"); p.add_argument("--memory", required=True); p.set_defaults(f=cmd_evolution_report)
    p = sub.add_parser("self-evolve"); p.add_argument("--target", required=True); p.add_argument("--budget", type=int, default=5)
    p.add_argument("--apply", action="store_true", help="actually apply (default: dry-run)"); p.set_defaults(f=cmd_self_evolve)
    p = sub.add_parser("activate"); p.set_defaults(f=cmd_activate)
    p = sub.add_parser("brief"); p.add_argument("--problem", required=True); p.set_defaults(f=cmd_brief)
    p = sub.add_parser("route"); p.add_argument("--problem", required=True)
    p.add_argument("--json", action="store_true"); p.add_argument("--full-brief", dest="full_brief", action="store_true")
    p.set_defaults(f=cmd_route)
    p = sub.add_parser("explore"); p.add_argument("--problem", required=True); p.add_argument("--budget", type=int, default=16); p.set_defaults(f=cmd_explore)
    p = sub.add_parser("elicit"); p.add_argument("--problem", required=True); p.set_defaults(f=cmd_elicit)
    p = sub.add_parser("lint"); p.add_argument("paths", nargs="*"); p.add_argument("--text"); p.set_defaults(f=cmd_lint)
    args = ap.parse_args(argv); args.f(args)


if __name__ == "__main__":
    main()
