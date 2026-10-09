#!/usr/bin/env python3
"""Backfill the two fields ABSORB-01 and ABSORB-09 added to the prior-art schema.

Written as a committed script rather than run once by hand for one reason: three
pull requests are open that each add or amend a prior-art record, and every one
of them will land a record without these fields. A hand backfill would have to be
repeated from memory each time. `codemap.py prior-art` names this command in its
own failure message, so the fix for a new record is one line rather than a
rediscovery.

The verdict_class table below is EXPLICIT rather than derived. Deriving an enum
from free text by keyword would be the same defect the enum exists to fix: four
of the 41 verdicts are whole sentences, one of which reads "keep, narrowly, and
delete half of it the moment a dependency is allowed", and a substring rule that
groups that correctly today groups the next sentence wrongly and silently. Each
row below was assigned by reading the record's own verdict, and the assignment is
reviewable as a diff because it is data.

  python tools/audit/absorption_backfill.py apply     write the fields
  python tools/audit/absorption_backfill.py check     report what is missing
  python tools/audit/absorption_backfill.py selftest  prove the checks can fail
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools", "map"))

import codemap  # noqa: E402

PRIOR_ART_DIR = os.path.join(ROOT, "docs", "prior-art")

# filename stem -> verdict_class. Assigned by reading each record's `verdict`.
VERDICT_CLASS = {
    # "build, narrowly, and the narrowness is the point": a build-ours verdict;
    # the alternatives render sessions for humans, ours extracts a corpus.
    "tools-corpus": "keep-ours",
    # coffee-break v2 (taste row 2026-08-12): stdlib ledger CLIs; the record's
    # own recheck flips this toward delete if the ledgers stay empty.
    "tools-coffee": "keep-ours",
    # reanimation jutsu (2026-08-13): free-tier persona pipeline; recheck flips
    # to delete if nothing is animated by the expiry.
    "tools-reanimation": "keep-ours",
    "dot-claude-bin": "split",
    "dot-claude-hooks": "split",
    "dot-claude-skills-explain-simply": "split",
    "dot-claude-skills-learn-on-demand-scripts": "keep-ours",
    "dot-claude-skills-prove-implementation-scripts": "split",
    # "keep-provisionally, and it is the weakest of the three records written
    # today". The hedge is about confidence in the record, not about the call.
    "dot-claude-skills-syndication-engine": "keep-ours",
    "dot-claude-skills-voice-metrics": "split",
    "dot-claude-skills-whatsapp-query": "keep-ours",
    "intent-control-plane-src-intent-control-plane-harness": "keep-ours",
    "intent-control-plane-src-intent-control-plane": "split",
    "intent-control-plane-tests": "split",
    "tests": "split",
    "tools-antigravity": "build",
    "tools-audit-mutations": "keep-ours",
    "tools-audit": "split",
    "tools-browser": "split",
    "tools-bus": "keep-ours",
    "tools-docmap": "keep-ours",
    "tools-eco": "keep-ours",
    "tools-e2e": "split",
    "tools-gate": "keep-ours",
    "tools-ghpub": "keep-ours",
    # Arrived with PR 59 on 2026-08-10, hours after this table was written, and
    # the oracle caught it on the first gate run after the merge. That is the
    # case this script exists for.
    "tools-harness": "keep-ours",
    "tools-hookgate": "keep-ours",
    # "keep-the-ledger-design, replace-the-capture-claim" is two calls on two
    # halves of one component, which is what split means.
    "tools-intent": "split",
    "tools-lib": "keep-ours",
    "tools-map": "split",
    # "thin-wrapper-justified-by-reuse": the component exists to wrap a vendor
    # endpoint, so the class is wrap even though the reuse it cites is internal.
    "tools-nvidia": "wrap",
    "tools-openrouter": "split",
    "tools-reclaim": "keep-ours",
    "tools-refute-checks": "keep-ours",
    "tools-refute": "wrap",
    "tools-review": "split",
    "tools-skilleval": "split",
    "tools-snapshot": "keep-ours",
    "tools-supply": "keep-ours",
    "tools-telemetry": "build",
    "tools-timetravel": "keep-ours",
    "tools-trycmd": "absorb",
    "tools-whatsapp": "delete-ours",
    "tools-workspace": "split",
    "tools-wsl": "keep-ours",
    "tools": "split",
    # Added 2026-10-09 with the #372 review-cache component: stem assigned by
    # reading the record's own verdict ("keep-ours"), not derived by keyword.
    "review-cache": "keep-ours",
}

# The only record whose own body already names what was taken and where it
# landed. Everything else gets `unreviewed`, which is the honest answer and is
# the measurement ABSORB-06 said was unknown rather than zero.
ABSORPTION = {
    "tools-trycmd": (
        "absorbed",
        "The mechanism, not the code: trycmd 1.2.1's literate `.trycmd` block "
        "grammar and snapbox 0.6.21's `[..]` intra-line and `...` line elision "
        "rules, ported to stdlib Python in tools/trycmd/trycmd.py. Recorded in "
        "this record's own absorbed_from and divergences_from_upstream fields, "
        "which predate this schema change and are what it was generalised from."),
}

DEFAULT_ABSORPTION = (
    "unreviewed",
    "")


def records() -> list[tuple[str, str, dict]]:
    out = []
    for name in sorted(os.listdir(PRIOR_ART_DIR)):
        if not name.endswith(".json"):
            continue
        path = os.path.join(PRIOR_ART_DIR, name)
        with open(path, encoding="utf-8") as fh:
            out.append((name[:-len(".json")], path, json.load(fh)))
    return out


def planned(stem: str, rec: dict) -> dict:
    """Return only the fields this stem is missing, so a rerun is a no-op.

    A backfill that overwrites a decided status would silently undo the review
    it exists to force, which is why an existing value always wins.
    """
    add = {}
    if not rec.get("verdict_class"):
        klass = VERDICT_CLASS.get(stem)
        if klass:
            add["verdict_class"] = klass
    if not rec.get("absorption_status"):
        status, detail = ABSORPTION.get(stem, DEFAULT_ABSORPTION)
        add["absorption_status"] = status
        if detail:
            add["absorbed"] = detail
    return add


VERDICT_LINE = re.compile(r'^(\s*)"verdict"\s*:')


def insert(text: str, add: dict) -> str:
    """Splice the new keys in as TEXT, directly after the `verdict` line.

    Not `json.dump` of the parsed object, which was the first version and was
    wrong. These 41 files are hand-written and their formatting varies: 28 are
    indented one space and 13 two, and several keep a short nested dict on one
    line. Re-serialising normalises all of that, so a two-line schema addition
    arrives as a sixty-line whitespace diff per file and the actual change is
    unreviewable. The reason to care is specific to this repo: `review` and the
    prose gate both read added lines, and a reviewer who cannot see the change
    cannot check the verdict_class assignments, which are the only part of this
    that is a judgement rather than a mechanism.

    Indentation is taken from the `verdict` line itself rather than guessed, and
    so is the comma. `verdict` is not the last key in any of the 41 records, so
    the first version appended a trailing comma unconditionally and worked on
    every real input; its own selftest fixture, where `verdict` WAS last, was
    what produced invalid JSON. Handling it here rather than declaring the shape
    unsupported, because a record whose verdict is its last key is a perfectly
    ordinary record that nobody has written yet.
    """
    lines = text.splitlines(keepends=True)
    for i, line in enumerate(lines):
        m = VERDICT_LINE.match(line)
        if not m:
            continue
        pad = m.group(1)
        keys = [k for k in ("verdict_class", "absorption_status", "absorbed")
                if add.get(k) is not None]
        if not keys:
            return text
        trailing = line.rstrip().endswith(",")
        if not trailing:
            line = line.rstrip("\r\n") + ",\n"
        new = []
        for n, k in enumerate(keys):
            comma = "," if trailing or n < len(keys) - 1 else ""
            new.append('{}{}: {}{}\n'.format(
                pad, json.dumps(k), json.dumps(add[k], ensure_ascii=False), comma))
        return "".join(lines[:i] + [line] + new + lines[i + 1:])
    raise ValueError("no `verdict` line to insert after")


def cmd_apply(_args) -> int:
    written = 0
    unknown = []
    for stem, path, rec in records():
        add = planned(stem, rec)
        if not rec.get("verdict_class") and stem not in VERDICT_CLASS:
            unknown.append(stem)
        if not add:
            continue
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        spliced = insert(text, add)
        # Parse the result before writing it. A text splice that produces
        # invalid JSON would take out the record it was meant to complete, and
        # `read_records` reports a broken record with the same shape as a
        # missing field, so the failure would read as the problem being fixed.
        json.loads(spliced)
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(spliced)
        written += 1
        print("{}: + {}".format(stem, ", ".join(sorted(add))))
    if unknown:
        print("\nNo verdict_class assigned for: {}".format(", ".join(unknown)))
        print("Read each record's `verdict` and add a row to VERDICT_CLASS. "
              "Guessing from the sentence is the defect this table exists to avoid.")
        return 1
    print("\n{} record(s) written, {} already carried both fields".format(
        written, len(records()) - written))
    return 0


def cmd_check(_args) -> int:
    problems = []
    for stem, _path, rec in records():
        problems.extend(codemap.absorption_problems(stem, rec))
    if not problems:
        by_status: dict[str, int] = {}
        for _stem, _path, rec in records():
            key = str(rec.get("absorption_status"))
            by_status[key] = by_status.get(key, 0) + 1
        print("all {} record(s) carry both fields. absorption_status: {}".format(
            len(records()),
            ", ".join("{} {}".format(v, k) for k, v in sorted(by_status.items()))))
        return 0
    for p in problems:
        print("FAIL " + p)
    return 1


def cmd_selftest(_args) -> int:
    rc = 0

    def ok(cond: bool, what: str, detail: str = "") -> None:
        nonlocal rc
        print(("[ok]   " if cond else "[FAIL] ") + what
              + ("  <- {}".format(detail) if not cond and detail else ""))
        if not cond:
            rc = 1

    clean = {"verdict_class": "keep-ours", "absorption_status": "unreviewed"}
    ok(codemap.absorption_problems("x", clean) == [],
       "a record with both fields and nothing claimed is clean")

    for field in ("verdict_class", "absorption_status"):
        bad = dict(clean)
        del bad[field]
        msgs = codemap.absorption_problems("x", bad)
        ok(len(msgs) == 1 and codemap.BACKFILL_CMD in msgs[0],
           "a missing {} fails and names the backfill command".format(field),
           msgs[0][:90] if msgs else "no message")

    msgs = codemap.absorption_problems("x", dict(clean, verdict_class="maybe"))
    ok(len(msgs) == 1 and "maybe" in msgs[0],
       "a verdict_class outside the vocabulary fails and quotes the value",
       msgs[0][:90] if msgs else "no message")

    msgs = codemap.absorption_problems("x", dict(clean, absorption_status="probably"))
    ok(len(msgs) == 1 and "probably" in msgs[0],
       "an absorption_status outside the vocabulary fails and quotes the value",
       msgs[0][:90] if msgs else "no message")

    # The one that matters. A status of `absorbed` with nothing named beside it
    # groups perfectly and says nothing, which is the free-text defect wearing
    # an enum. Checked for every status that claims a decision was made.
    for status in codemap.ABSORPTION_NEEDS_DETAIL:
        msgs = codemap.absorption_problems("x", dict(clean, absorption_status=status))
        ok(len(msgs) == 1 and "absorbed` is empty" in msgs[0],
           "status {!r} with no `absorbed` text fails".format(status),
           msgs[0][:90] if msgs else "no message")
        msgs = codemap.absorption_problems(
            "x", dict(clean, absorption_status=status, absorbed="took the elision rule"))
        ok(msgs == [], "status {!r} with named detail is clean".format(status))

    ok(codemap.absorption_problems("x", dict(clean, absorbed="   ")) == [],
       "`absorbed` is not required while the status is unreviewed")
    msgs = codemap.absorption_problems(
        "x", dict(clean, absorption_status="absorbed", absorbed="   "))
    ok(len(msgs) == 1,
       "whitespace does not satisfy `absorbed`",
       msgs[0][:90] if msgs else "no message")

    # planned() must never overwrite a decided status, or the backfill undoes
    # the review it exists to force.
    decided = {"verdict_class": "absorb", "absorption_status": "adopted",
               "absorbed": "the whole library"}
    ok(planned("tools-trycmd", decided) == {},
       "a record that already carries both fields is left alone")
    ok("absorption_status" in planned("tools-trycmd", {}),
       "a record carrying neither field gets both")

    unknown_stem = planned("no-such-component", {})
    ok("verdict_class" not in unknown_stem,
       "a stem with no table row gets NO guessed verdict_class",
       str(unknown_stem))

    # insert(): the splice replaced a json.dump rewrite that turned a two-line
    # addition into a sixty-line whitespace diff per file. These pin the three
    # properties that made it worth doing: the result parses, the surrounding
    # bytes are untouched, and the indentation comes from the file rather than
    # from a constant.
    one = ' "component": "x",\n "verdict": "keep-ours",\n "why": "because"\n'
    spliced = insert("{\n" + one + "}\n",
                     {"verdict_class": "keep-ours", "absorption_status": "unreviewed"})
    parsed = json.loads(spliced)
    ok(parsed["verdict_class"] == "keep-ours" and parsed["why"] == "because",
       "a spliced record still parses and keeps its other fields")
    ok('\n "verdict_class"' in spliced,
       "the new key takes its indentation from the verdict line, not a constant",
       repr(spliced[:60]))
    ok(spliced.count('"why": "because"') == 1,
       "every line the splice did not target is byte-identical")

    # `verdict` as the LAST key. The first version of insert() appended a comma
    # unconditionally, which is correct for all 41 real records and produces
    # invalid JSON here. Found by this case, fixed in the tool rather than by
    # rewriting the fixture to the shape the code already handled.
    last = insert('{\n  "component": "x",\n  "verdict": "v"\n}\n',
                  {"verdict_class": "split"})
    ok(json.loads(last)["verdict_class"] == "split",
       "a record whose verdict is its LAST key still parses after the splice",
       repr(last))
    ok('\n  "verdict_class": "split"\n' in last,
       "the comma moves to the verdict line instead of dangling after the new one",
       repr(last))
    two = insert('{\n  "verdict": "v",\n  "why": "w"\n}\n', {"verdict_class": "split"})
    ok('\n  "verdict_class": "split",\n' in two,
       "a two-space file gets two-space keys", repr(two))

    quoted = insert('{\n "verdict": "v",\n "why": "w"\n}\n',
                    {"verdict_class": "split", "absorption_status": "absorbed",
                     "absorbed": 'took the "elide" rule\nand the matcher'})
    ok(json.loads(quoted)["absorbed"] == 'took the "elide" rule\nand the matcher',
       "a value containing quotes and newlines round-trips through the splice")

    try:
        insert('{\n "component": "x"\n}\n', {"verdict_class": "split"})
        ok(False, "a record with no verdict line raises rather than writing garbage")
    except ValueError:
        ok(True, "a record with no verdict line raises rather than writing garbage")

    print("\nVERDICT: {}".format(
        "every planted defect is caught" if rc == 0
        else "absorption_backfill selftest has failures above"))
    return rc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("command", choices=("apply", "check", "selftest"))
    args = ap.parse_args(argv)
    return {"apply": cmd_apply, "check": cmd_check,
            "selftest": cmd_selftest}[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
