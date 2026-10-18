"""Build the README / manual figures as SVG, one light and one dark file per figure, from a single source.

    python docs/assets/build_figures.py

Design rules (kept here so the figures stay consistent when edited):
  • two hues only, validated for colour-vision deficiency on both GitHub surfaces (white / #0d1117) with the
    dataviz palette validator: blue = an idea that leaves the box / OUTLIER's result, orange = the external test;
    everything else is ink and neutral grey. Survived / killed is carried by ✓ / ✗ and text, never by colour alone;
  • text is never smaller than ~14 px at GitHub's README width (viewBox 960 px wide → ~0.86 scale);
  • the only motion is one idea dot crossing the box in the hero, and it stops under prefers-reduced-motion;
  • the results chart reads its numbers from RESULTS below — copy them from evals/reports/<run>/summary.json.
"""
from __future__ import annotations
import os
from typing import Dict, List, Sequence, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans', Helvetica, Arial, sans-serif"
MONO = "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, monospace"

THEMES: Dict[str, Dict[str, str]] = {
    "light": {"ink": "#1f2328", "muted": "#59636e", "faint": "#d1d9e0", "panel": "#f6f8fa",
              "idea": "#2a78d6", "test": "#eb6834", "box": "#818b98"},
    "dark": {"ink": "#e6edf3", "muted": "#9198a1", "faint": "#3d444d", "panel": "#151b23",
             "idea": "#3987e5", "test": "#d95926", "box": "#6e7681"},
}

# A/B results (share of ideas that are still a variant of the model's own default answers; lower is better).
# Source: evals/reports/divergence_ab*/summary.json — 1 − tail_rate, with its paired-bootstrap 95% interval.
RESULTS: Dict[str, object] = {
    "model": "qwen3.5:4b, 12 requests, run 1",
    "rows": [("Direct answer (no OUTLIER)", 0.409, 0.227, 0.591),
             ("OUTLIER loop", 0.142, 0.021, 0.333),
             ("OUTLIER divergent phase", 0.086, 0.021, 0.188)],
}


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _wrap(text: str, size: float, width: float) -> List[str]:
    """Greedy word wrap with an average glyph width of 0.52 em (system sans) — good enough for short labels."""
    limit = max(1, int(width / (0.52 * size)))
    lines: List[str] = []
    for word in text.split():
        if lines and len(lines[-1]) + 1 + len(word) <= limit:
            lines[-1] += " " + word
        else:
            lines.append(word)
    return lines


def _text(x: float, y: float, text: str, size: float, fill: str, *, weight: int = 400, anchor: str = "start",
          width: float = 0.0, leading: float = 1.35, family: str = FONT) -> str:
    lines = _wrap(text, size, width) if width else [text]
    spans = "".join(f'<tspan x="{x}" dy="{0 if i == 0 else size * leading:.1f}">{_esc(l)}</tspan>'
                    for i, l in enumerate(lines))
    return (f'<text x="{x}" y="{y}" font-family="{family}" font-size="{size}" font-weight="{weight}" '
            f'fill="{fill}" text-anchor="{anchor}">{spans}</text>')


def _svg(width: int, height: int, body: str, title: str, desc: str, style: str = "") -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" '
            f'height="{height}" role="img" aria-labelledby="t d">'
            f'<title id="t">{_esc(title)}</title><desc id="d">{_esc(desc)}</desc>'
            f'{("<style>" + style + "</style>") if style else ""}{body}</svg>\n')


# ── hero: the box, ideas leaving it, the test they must survive ──
def hero(theme: Dict[str, str]) -> str:
    t = theme
    body: List[str] = [
        _text(0, 70, "OUTLIER_MCB", 54, t["ink"], weight=700),
        _text(2, 118, "Push a language model out of its default answers,", 23, t["muted"]),
        _text(2, 150, "and keep only the ideas that survive a test.", 23, t["muted"]),
        _text(2, 208, "pure Python · zero dependencies · every verdict capped by evidence · local models "
                      "(Ollama, llama.cpp, vLLM) and online models (Claude, OpenAI, Gemini, …)",
              16, t["muted"], width=500, leading=1.45),
    ]
    # the box
    bx, by, bw, bh = 560, 40, 170, 230
    body.append(f'<rect x="{bx}" y="{by}" width="{bw}" height="{bh}" rx="18" fill="{t["panel"]}" '
                f'stroke="{t["box"]}" stroke-width="2" stroke-dasharray="7 6"/>')
    body.append(_text(bx + bw / 2, by + bh + 32, "the box: the model's", 15, t["muted"], anchor="middle"))
    body.append(_text(bx + bw / 2, by + bh + 52, "own default answers", 15, t["muted"], anchor="middle"))
    dots = [(600, 90), (625, 120), (590, 150), (640, 160), (615, 190), (660, 105), (650, 215), (595, 235),
            (685, 140), (670, 185), (700, 230), (630, 245), (700, 75), (580, 205)]
    body += [f'<circle cx="{x}" cy="{y}" r="7" fill="{t["box"]}" opacity="0.55"/>' for x, y in dots]
    # the test gate
    gx = 850
    body.append(f'<line x1="{gx}" y1="40" x2="{gx}" y2="270" stroke="{t["test"]}" stroke-width="4" '
                f'stroke-linecap="round"/>')
    body.append(_text(gx, 300, "external test", 15, t["test"], anchor="middle", weight=600))
    body.append(_text(gx, 320, "prior art · RED→GREEN · prover", 13, t["muted"], anchor="middle"))
    # three ideas leaving the box: two survive, one is killed at the gate
    paths = [("M690 120 C760 90 800 80 850 78", True), ("M700 170 C770 170 800 160 850 158", False),
             ("M680 220 C760 245 800 240 850 238", True)]
    for d, survives in paths:
        body.append(f'<path d="{d}" fill="none" stroke="{t["idea"]}" stroke-width="2.5" '
                    f'stroke-dasharray="{"none" if survives else "5 5"}" opacity="{1 if survives else 0.55}"/>')
    body.append(f'<circle cx="905" cy="78" r="9" fill="{t["idea"]}"/>'
                + _text(925, 84, "✓", 20, t["ink"], weight=700))
    body.append(f'<circle cx="905" cy="238" r="9" fill="{t["idea"]}"/>'
                + _text(925, 244, "✓", 20, t["ink"], weight=700))
    body.append(_text(878, 165, "✗", 22, t["muted"], weight=700))
    # one idea in motion along the first path (stops under reduced motion)
    body.append(f'<circle class="mover" r="7" fill="{t["idea"]}"/>')
    style = ('.mover{offset-path:path("M640 130 C700 110 760 85 850 78 L905 78");'
             'animation:leave 6s ease-in-out infinite;}'
             '@keyframes leave{0%,15%{offset-distance:0%;opacity:0}25%{opacity:1}'
             '85%{offset-distance:100%;opacity:1}100%{offset-distance:100%;opacity:0}}'
             '@media (prefers-reduced-motion: reduce){.mover{animation:none;opacity:0}}')
    return _svg(960, 340, "".join(body), "OUTLIER_MCB",
                "Ideas leave the box of the model's default answers; at an external test two survive and one "
                "is killed.", style)


# ── the method in six steps (Z-reading: two rows of three) ──
STEPS: Sequence[Tuple[str, str, str]] = (
    ("Name the box", "The model states its own default answers. They become the box every idea must leave.",
     "idea"),
    ("Break an assumption", "Find a hidden assumption the standard solutions share and name the axis it sits on.",
     "idea"),
    ("Diverge", "Independent calls, distant points of view, the model's full distribution: short intents, "
                "not solutions.", "idea"),
    ("Converge", "Develop each intent at low temperature. If it drifts back to a default, retry once.", "idea"),
    ("Falsify", "Prior-art search, a test that must go RED→GREEN, or a prover. External, never self-judged.",
     "test"),
    ("Honest claim", "Only what survived is claimed, capped by the evidence: from INSIDE_THE_BOX up to "
                     "verified, useful novelty.", "test"),
)


def pipeline(theme: Dict[str, str]) -> str:
    t = theme
    cw, ch, gap, top = 290, 196, 43, 20
    body: List[str] = []
    for i, (title, text, hue) in enumerate(STEPS):
        row, col = divmod(i, 3)
        x, y = col * (cw + gap) + 2, top + row * (ch + 70)
        body.append(f'<rect x="{x}" y="{y}" width="{cw}" height="{ch}" rx="14" fill="{t["panel"]}" '
                    f'stroke="{t["faint"]}" stroke-width="1.5"/>')
        body.append(f'<rect x="{x}" y="{y}" width="6" height="{ch}" rx="3" fill="{t[hue]}"/>')
        body.append(f'<circle cx="{x + 38}" cy="{y + 40}" r="17" fill="{t[hue]}"/>'
                    + _text(x + 38, y + 47, str(i + 1), 18, "#ffffff", weight=700, anchor="middle"))
        body.append(_text(x + 66, y + 47, title, 19, t["ink"], weight=700))
        body.append(_text(x + 24, y + 92, text, 16, t["muted"], width=cw - 44, leading=1.4))
        if col < 2:                                            # arrow to the next card in the row
            ax = x + cw + 8
            body.append(f'<path d="M{ax} {y + ch / 2} h{gap - 18}" stroke="{t["muted"]}" stroke-width="2" '
                        f'marker-end="url(#arrow)"/>')
    # row 1 → row 2 connector (end of step 3 to start of step 4)
    x3, y3 = 2 * (cw + gap) + 2 + cw / 2, top + ch + 6
    x4, y4 = 2 + cw / 2, top + ch + 64
    body.append(f'<path d="M{x3} {y3} V{y3 + 26} H{x4} V{y4 - 2}" fill="none" stroke="{t["muted"]}" '
                f'stroke-width="2" marker-end="url(#arrow)"/>')
    body.append(_text(480, y3 + 15, "the box is left behind — now the ideas must survive", 14, t["muted"],
                      anchor="middle"))
    defs = (f'<defs><marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" '
            f'orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 z" fill="{t["muted"]}"/></marker></defs>')
    return _svg(960, top + 2 * ch + 90, defs + "".join(body), "The method in six steps",
                "1 name the box, 2 break an assumption, 3 diverge, 4 converge, 5 falsify, 6 claim only what "
                "survived.")


# ── results: share of ideas still inside the box, per condition (single series, lower is better) ──
def results(theme: Dict[str, str]) -> str:
    t = theme
    rows = RESULTS["rows"]
    left, right, top, bar_h, step = 300, 900, 92, 30, 66
    scale = (right - left) / 0.7                                  # x axis 0 … 70 %
    body: List[str] = [
        _text(0, 30, "Ideas that are still a variant of the model's default answers", 21, t["ink"], weight=700),
        _text(0, 58, f"lower is better · bars: mean, whiskers: 95% interval · {RESULTS['model']}", 15, t["muted"]),
    ]
    for tick in (0.0, 0.2, 0.4, 0.6):
        x = left + tick * scale
        body.append(f'<line x1="{x}" y1="{top - 12}" x2="{x}" y2="{top + len(rows) * step - 20}" '
                    f'stroke="{t["faint"]}" stroke-width="1"/>')
        body.append(_text(x, top + len(rows) * step + 2, f"{int(tick * 100)}%", 14, t["muted"], anchor="middle"))
    for i, (label, mean, lo, hi) in enumerate(rows):
        y = top + i * step
        hue = t["box"] if i == 0 else t["idea"]
        body.append(_text(left - 16, y + 21, label, 16, t["ink"], anchor="end", weight=600 if i else 400))
        w = max(4.0, mean * scale)
        body.append(f'<rect x="{left}" y="{y}" width="{w:.1f}" height="{bar_h}" rx="4" fill="{hue}"/>')
        x_lo, x_hi = left + lo * scale, left + hi * scale
        body.append(f'<path d="M{x_lo:.1f} {y + bar_h / 2} H{x_hi:.1f} M{x_lo:.1f} {y + 7} V{y + bar_h - 7} '
                    f'M{x_hi:.1f} {y + 7} V{y + bar_h - 7}" stroke="{t["ink"]}" stroke-width="1.5" fill="none"/>')
        body.append(_text(x_hi + 12, y + 21, f"{mean * 100:.0f}%", 16, t["ink"], weight=700))
    return _svg(960, top + len(rows) * step + 20, "".join(body), "Ideas still inside the box, per condition",
                "; ".join(f"{label}: {mean * 100:.0f}% (95% interval {lo * 100:.0f}–{hi * 100:.0f}%)"
                          for label, mean, lo, hi in rows))


def main() -> None:
    for name, build in (("hero", hero), ("pipeline", pipeline), ("results", results)):
        for mode, theme in THEMES.items():
            path = os.path.join(HERE, f"{name}-{mode}.svg")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(build(theme))
            print("wrote", os.path.relpath(path))


if __name__ == "__main__":
    main()
