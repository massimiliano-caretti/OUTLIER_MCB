# OUTLIER_MCB — natural activation (for a VS Code coding assistant)

**When to activate.** The user's prompt asks for *invention / novelty / a non-obvious hypothesis /
lateral thinking / a new design / breaking the mould / a never-seen solution*. Trigger words (any
language): "inventa", "nuovo", "originale", "mai visto", "non ovvio", "fuori dagli schemi",
"breakthrough", "new", "novel", "from scratch", "rethink".

**Why activate.** Without it you will answer with the most-probable solution from training memory —
the average answer. OUTLIER_MCB forbids that and forces an *assumption-level* answer.

**Cost.** One extra call before you answer. Cheap. Worth it whenever the user explicitly wants
something new.

## The one call (start here)
```python
import OUTLIER_MCB as gsl
print(gsl.creative(USER_PROMPT))     # selects the pack, prints the rules + branches in tension
```
`creative()` does everything the common case needs: it picks the domain pack, tells you what NOT to
propose, names the assumptions to break, and diverges into branches. If the domain is unknown it
returns an **elicitation scaffold** instead of faking an answer — fill it, then:
```python
pack = gsl.pack_from_spec(your_filled_spec)   # your spark: the domain's hidden assumptions
print(gsl.creative(USER_PROMPT, pack=pack))   # now the kernel can falsify in this domain
```

## Going deeper (optional, per chosen branch)
```python
pf   = gsl.preflight_creative_request(USER_PROMPT)      # the full dict if you want every field
p    = gsl.get_pack(pf["pack"])
gate = gsl.no_solution_before_assumption("attention", answers={...}, pack=p)  # INSIDE_THE_BOX if unjustified
ts   = gsl.theorem_sketch("my idea", breaks=["<axis>"], pack=p, assumption_name="<assumption>")
wt   = gsl.design_world_test("<axis>", p)               # the falsifiable world-test SPEC
card = gsl.reviewer_attack("my idea", p, breaks=["<axis>"])   # the hostile-reviewer card
```

## The contract you must follow in your answer
1. Do **not** propose a standard mechanism from memory until you can name the assumption it breaks.
2. Anything that stays inside the domain's box → label it `INSIDE_THE_BOX`; it is not an answer.
3. Offer **≥3 branches in tension** (conservative / radical / hybrid / contrarian), each breaking a
   *different* axis.
4. For the chosen branch, give: the **broken assumption**, the **world-test** that would kill it, the
   **known family** it must beat, and the **max claim allowed** (never claim a paradigm without a
   demonstrated separation).
5. If `pf["missing_information"]["data_insufficient"]` is true: say so — a new combination cannot raise
   the ceiling; name the new information required.

**Honest stance.** The library does not invent the idea for you. It removes the average answer, forces
the method, and lets falsification — not naming — certify novelty. The spark (which assumption to
break) is yours; the rigor is the engine's.
