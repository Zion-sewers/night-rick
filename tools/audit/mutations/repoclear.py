"""Mutation spec for tools/repoclear/scan.py.

Repo Clear is a ratchet: it fails only when a count grows past the baseline.
Every failure mode here ends with the ratchet passing when it should fail,
which is the one direction that silently re-admits rot. A mutation that
survives names a detector the gate trusts but that cannot see.
"""

TARGET = "tools/repoclear/scan.py"
ARGV = ["selftest"]

MUTATIONS = [
    (
        "empty-dir detector blind",
        "A new empty directory lands and the check passes, because the "
        "emptiness computation always answers False.",
        "        empty[rel] = (not has_files) and all(empty.get(s, True) for s in subdirs)",
        "        empty[rel] = False",
    ),
    (
        "tracked-artifact matcher blind",
        "A tracked __pycache__/*.pyc (or any other build artifact) lands and "
        "the check passes, because no tracked file ever matches.",
        "    return sorted(p for p in _git_files(project) if _is_artifact(p))",
        "    return sorted(p for p in _git_files(project) if False)",
    ),
    (
        "baseline comparison inverted",
        "Growth reads as shrinkage: the check passes exactly when a count "
        "grew past the baseline, and fails when the tree improved.",
        "        if counts[k] > baseline[k]",
        "        if counts[k] < baseline[k]",
    ),
    (
        "stale-destination resolver accepts missing paths",
        "A prompt names a destination directory that does not exist and the "
        "check passes, because the existence test never runs: the exact "
        "2026-07-27 defect (~/docs/research/) recurring silently.",
        "            if not checked.is_dir():",
        "            if False:",
    ),
    (
        "duplicate groups not counted",
        "pile.py still finds the duplicate groups, but repoclear drops them "
        "on the floor, so the duplicate half of the ratchet never fires.",
        '    docs = [r for r in rows if r.get("kind") == "duplicate-doc"]',
        "    docs = [r for r in rows if False]",
    ),
]
