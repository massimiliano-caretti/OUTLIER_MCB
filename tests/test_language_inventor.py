"""test_language_inventor — Point 3: invent a compact formal language (a primitive-set DSL) with a SOUND
interpreter, scored by external expressive power. A rename gains nothing (control), an unsolvable language
scores 0 (control), and soundness is a protected invariant. Deterministic and offline.
"""
import OUTLIER_MCB as gsl
from OUTLIER_MCB.language_inventor import (FormalLanguage, integer_baseline, invent_new_language,
                                              shortest_program, expressive_power, is_sound, _affine_problems)


def test_invented_language_is_more_expressive():
    base = integer_baseline()
    fam = _affine_problems()
    lang = invent_new_language(base, fam)
    assert lang.macros                                     # it abstracted a recurring sub-solution into a new word
    assert expressive_power(lang, base, fam) > 1.0         # and expresses the family more compactly


def test_rename_gives_no_gain():
    base = integer_baseline()
    assert expressive_power(base, base, _affine_problems()) == 1.0    # a rename is not more expressive


def test_unsolvable_language_scores_zero():
    crippled = FormalLanguage(name="crippled", primitives={"inc": lambda x: x + 1})   # missing 'double'
    assert expressive_power(crippled, integer_baseline(), _affine_problems()) == 0.0


def test_interpreter_is_sound():
    lang = invent_new_language(integer_baseline(), _affine_problems())
    assert is_sound(lang, [(("inc", "double"), 3, 8), (("inc", "inc", "double"), 1, 6)])
    # a wrong expected output must make soundness FAIL (the check really checks)
    assert not is_sound(lang, [(("inc", "double"), 3, 999)])


def test_language_soundness_is_a_protected_invariant():
    from OUTLIER_MCB.self_repair import verify_invariants, INVARIANT_REGISTRY
    assert "language_is_sound" in INVARIANT_REGISTRY
    rep = verify_invariants()
    assert rep.ok and "language_is_sound" in rep.passed_names


def test_expressive_power_dimension_benchmark():
    from evals.benchmarks.expressiveness import expressive_power_score, controls_pass
    assert controls_pass() is True
    assert expressive_power_score() > 1.0
