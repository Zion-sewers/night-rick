"""Mutations for tools/gate/gate.py.

gate.py is the file with the strongest claim in this estate and, until
2026-07-27, the least evidence for it. It decides whether anything may be called
done, and it had no mutation spec, so the sentence in its own header, "a domain
counts as covered only when a command exits zero", was itself uncovered.

Its module docstring states the rule this spec defends:

    "There is no state in which the gate passes because nobody got round to
     configuring a check, because that is exactly the state the setup was
     already in."

and, on waivers:

    "An expired waiver is a failure, not a skip, because a permanent waiver is
     just a disabled check with better manners."

Each mutation below turns one of those sentences back into a lie. Everything
here targets a guard the selftest already exercises, so a survivor means the
selftest is decorative rather than that the mutation is uninteresting.
"""

TARGET = "tools/gate/gate.py"
ARGV = ["selftest"]

MUTATIONS = [
    # ---- waiver expiry --------------------------------------------------
    ("an expired waiver stops being expired",
     "the exact 'disabled check with better manners' the docstring warns about: "
     "every waiver becomes permanent and no domain ever comes back",
     'return datetime.date.fromisoformat(until) < datetime.date.today()',
     'return False'),

    ("an unparseable until-date is treated as live rather than expired",
     "fail-open on a malformed date makes `until: soon` a permanent waiver, so "
     "the cheapest way to disable a domain forever is to typo the date",
     '    except Exception:\n        return True',
     '    except Exception:\n        return False'),

    ("a waiver expiring today reads as already expired",
     "`until` is inclusive, so the last day is a working day. Making the "
     "comparison <= fails a project on the morning of the deadline, which is "
     "exactly when someone is depending on the waiver they wrote",
     'return datetime.date.fromisoformat(until) < datetime.date.today()',
     'return datetime.date.fromisoformat(until) <= datetime.date.today()'),

    ("a far-future date is treated as expired",
     "inverting the comparison makes every live waiver read as expired, which "
     "fails a correct project and is how a gate stops being run at all",
     'return datetime.date.fromisoformat(until) < datetime.date.today()',
     'return datetime.date.fromisoformat(until) > datetime.date.today()'),

    # ---- waiver confirmation, added 2026-08-07 --------------------------
    # The expiry mutations above all attack `until`, which is the half of a
    # waiver that was already checked. These attack the half that was not: a
    # waiver's description of the measurement it is waiving.
    ("the confirm string is never checked",
     "restores the state measured on 2026-08-07: the gate prints a waiver whose "
     "own confirmation step fails and returns VERDICT: PASS, which is a false "
     "green produced by a check that was never run",
     '        if confirm in output:',
     '        if False:'),

    ("a stale waiver reports WAIVED instead of failing",
     "the confirmation runs, disagrees, and changes nothing. Worse than not "
     "running it, because the evidence then says the waiver was checked",
     '    return FAIL, ("waiver STALE: `{}` no longer reports {}, so the waiver describes a "',
     '    return WAIVED, ("waiver STALE: `{}` no longer reports {}, so the waiver describes a "'),

    ("a confirm string on a domain with no command passes silently",
     "a waiver naming a confirmation that can never run is indistinguishable "
     "from one that ran and held, so the cheapest way to defeat the check is to "
     "delete the domain's cmd",
     '        return FAIL, ("the waiver carries a confirm/command field and the domain names no "',
     '        return WAIVED, ("the waiver carries a confirm/command field and the domain names no "'),

    ("the confirmation is satisfied by any output at all",
     "an unconditional match makes every waiver self-confirming, which is the "
     "same disabled check the expiry mutations produce, reached from the other side",
     '    if confirm in output:',
     '    if True:'),

    # ---- the unmeasurable branch, added 2026-08-07 after CI ---------------
    # The three above attack the confirmation. These attack the exception to it,
    # which is the half that failed CI on the day the confirmation shipped.
    ("a host that cannot measure is called stale instead",
     "restores the bug that failed PR 55: the confirming command exits 2 because "
     "no live tree exists on the runner, the confirm string is absent for a reason "
     "that has nothing to do with the waiver, and the gate fails the branch",
     '''    if rc == CANNOT_MEASURE:
        return WAIVED, ("waiver NOT confirmed on this host:''',
     '''    if False:
        return WAIVED, ("waiver NOT confirmed on this host:'''),

    ("any exit code counts as unmeasurable",
     "the exception swallows the rule. A checker that fails for a real reason then "
     "reports its waiver as merely unconfirmable, which is the fail-open this "
     "branch exists to close",
     '''    if rc == CANNOT_MEASURE:
        return WAIVED, ("waiver NOT confirmed on this host:''',
     '''    if True:
        return WAIVED, ("waiver NOT confirmed on this host:'''),

    # The plain-runner copy of the same exception, added 2026-08-12 when the exit-2
    # convention was extended beyond waiver confirmation. Each direction has a
    # selftest case; these prove those cases can go red.
    ("a plain domain that cannot measure fails anyway",
     "restores the bug that failed PR 66 CI: skills_sync exits 2 on a runner with "
     "no live ~/.claude and the domain reads FAIL, so a satisfied waiver cannot be "
     "removed without breaking CI",
     '    if rc == CANNOT_MEASURE and "cannot run" in output:',
     '    if False:'),

    ("any plain failure counts as unmeasurable",
     "the exception swallows the rule for every unwaived domain: a checker that "
     "fails for a real reason reads as N/A and the gate goes green on a red check",
     '    if rc == CANNOT_MEASURE and "cannot run" in output:',
     '    if rc != 0:'),

    # ---- spec_linked, added 2026-08-30 -----------------------------------
    ("spec_linked passes when over threshold with no spec",
     "removes the enforcement half: any change passes regardless of whether a "
     "spec was written, which is the 'spec culture exists, enforcement does not' "
     "gap this domain exists to close",
     '    return FAIL, ("{} source file(s) changed but no spec in {} was created or updated. "',
     '    return PASS, ("{} source file(s) changed but no spec in {} was created or updated. "'),

    ("spec_linked threshold comparison is inverted",
     "flipping the comparison makes large changes pass and small ones fail, "
     "the inverse of the design: trivial fixes get blocked while features sail through",
     '    if len(code) <= threshold:',
     '    if len(code) > threshold:'),

    ("an unconfirmed waiver is recorded as an ordinary one",
     "the ledger stops distinguishing a PASS that confirmed its waivers from one "
     "that could not, so the run record claims more than the run measured",
     '        "waivers_unconfirmed": [r["domain"] for r in results',
     '        "waivers_unconfirmed": [] and [r["domain"] for r in results'),

    ("the unmeasurable state is not said out loud",
     "the domain still passes and the operator reading the output has no way to "
     "know the confirmation never ran",
     '                            cmd, CANNOT_MEASURE, indent(tail))), "unmeasurable"',
     '                            cmd, CANNOT_MEASURE, indent(tail))), "yes"'),
]

# Two mutations were removed on 2026-07-27 after they SURVIVED for the wrong
# reason. Both edited a message string rather than a branch:
#
#   "no test script found; a project with no tests cannot pass this gate" -> shorter text
#   "a leftover artifact is refreshed, not trusted, got {}"               -> reworded
#
# Neither changes behaviour, so neither could ever fail a selftest, and recording
# them as UNGUARDED would have blamed gate.py for a defect in this file. A
# mutation that cannot change an outcome is not evidence of a missing check; it is
# a badly written mutation. Kept here as a note because the distinction is easy to
# lose and expensive to relearn.
