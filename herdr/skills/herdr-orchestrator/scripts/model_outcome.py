#!/usr/bin/env python3
"""Model outcome tracker for the Herdr orchestrator.

Python-stdlib CLI. The orchestrator (never the worker) records one outcome per
reviewed worker stage; outcomes are stored as JSONL outside git at
~/.pi/agent/state/herdr-model-outcomes.jsonl (override with $HERDR_MODEL_OUTCOMES).

Records: UTC timestamp, model, thinking, category, green/yellow/red,
redirect count, short non-sensitive reason code. Never prompts, source
code, paths, secrets, or freeform text.

Subcommands:
  record   --model M --thinking T --category C --outcome green|yellow|red
            [--redirects N] --reason CODE
  recent   [MODEL] [--limit N]    recent outcomes (optionally per model)
  summary  [MODEL] [CATEGORY]    aggregate counts
  decision --model M --category C --outcome O [--reason CODE]
            [--redirects N] verdict JSON: switch with fallback, or one
            redirect first.
  --self-test              run assertions on temp storage.

Line-level corruption is tolerated (bad lines skipped, history never rewritten).
"""
import argparse
import datetime
import itertools
import json
import os
import sys
import tempfile

try:
    import fcntl
    _LOCK = True
except ImportError:  # pragma: no cover - non-POSIX
    fcntl = None
    _LOCK = False

DEFAULT_PATH = os.path.expanduser(
    "~/.pi/agent/state/herdr-model-outcomes.jsonl")

# Immediate-switch failure classes. Anything else gets one redirect first.
IMMEDIATE_CODES = {
    "provider_fail", "rate_limit", "context_limit", "tool_protocol",
}
VALID_CODES = IMMEDIATE_CODES | {
    "clean", "corrected_once", "repeated_fail", "scope_drift",
    "weak_tests", "unsupported_claim", "tool_loop", "poor_diff",
    "other",
}
OUTCOMES = ("green", "yellow", "red")

# Category -> preferred worker models in order (per SKILL.md Model routing).
FALLBACKS = {
    "docs": ["glm-5.3-flash", "kimi-k2.7-code", "deepseek-v4-flash"],
    "mechanical": ["glm-5.3-flash", "kimi-k2.7-code", "deepseek-v4-flash"],
    "coding": ["kimi-k2.7-code", "qwen3.7-plus", "deepseek-v4-flash"],
    "algorithm": ["kimi-k2.7-code", "qwen3.8-max", "glm-5.3"],
    "investigate": ["deepseek-v4-flash", "qwen3.7-plus", "kimi-k2.7-code"],
    "images": ["deepseek-v4-flash-vision-exp", "glm-5.3-flash"],
}
DEFAULT_CATEGORY = "coding"


def store_path():
    return os.environ.get("HERDR_MODEL_OUTCOMES", DEFAULT_PATH)


def now_utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(
        timespec="seconds")


def append(record, path=None):
    path = path or store_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    line = json.dumps(record, sort_keys=True) + "\n"
    # O_APPEND single small write is the atomic-append primitive; flock guards
    # interleaving where O_APPEND alone could split the write on odd filesystems.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        if _LOCK:
            fcntl.flock(fd, fcntl.LOCK_EX)
        os.write(fd, line.encode())
    finally:
        if _LOCK:
            fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def load(path=None):
    path = path or store_path()
    if not os.path.exists(path):
        return []
    records = []
    with open(path, "r", errors="replace") as fh:
        for line in fh:
            try:
                rec = json.loads(line)
                if isinstance(rec, dict) and rec.get("outcome") in OUTCOMES:
                    records.append(rec)
            except (json.JSONDecodeError, ValueError):
                continue  # skip corrupt line, preserve the rest
    return records


def pick_fallback(model, category):
    candidates = FALLBACKS.get(category, FALLBACKS[DEFAULT_CATEGORY])
    m = model.lower()
    for cand in candidates:
        if cand.lower() != m:
            return cand
    return candidates[0]


def decide(model, category, outcome, reason, redirects=0):
    """switch (now) > redirect-once (then switch on second red) > continue.

    Fields: model = current; recommended_model = model to use next;
    fallback = escalation-only model used if redirect_once fails again
    (never assigned preemptively).
    """
    history = [r for r in load() if r.get("model", "").lower() == model.lower()
               and r.get("category") == category]
    verdict = {"model": model, "category": category, "outcome": outcome,
               "reason": reason, "redirects": redirects}
    if outcome == "red" and reason in IMMEDIATE_CODES:
        verdict.update(action="switch", immediate=True,
                       fallback=pick_fallback(model, category),
                       recommended_model=pick_fallback(model, category),
                       rule="failure_class_requires_immediate_switch")
    elif outcome == "red" and sum(
            h["outcome"] == "red" for h in history[-3:]) >= 2:
        verdict.update(action="switch", immediate=True,
                       fallback=pick_fallback(model, category),
                       recommended_model=pick_fallback(model, category),
                       rule="2_red_in_last_3_stages")
    elif outcome == "red" and redirects >= 1:
        verdict.update(action="switch", immediate=True,
                       fallback=pick_fallback(model, category),
                       recommended_model=pick_fallback(model, category),
                       rule="correction_already_failed")
    elif outcome == "red":
        verdict.update(action="redirect_once",
                       fallback=pick_fallback(model, category),
                       recommended_model=model,
                       rule="first_red_gets_one_evidence_based_redirect")
    elif outcome == "yellow":
        verdict.update(action="continue", recommended_model=model,
                       rule="one_successful_correction")
    else:
        verdict.update(action="continue", recommended_model=model,
                       rule="no_material_correction")
    return verdict


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--path", help="override storage path")
    r = sub.add_parser("record", parents=[common])
    r.add_argument("--model", required=True)
    r.add_argument("--thinking", default="off")
    r.add_argument("--category", required=True)
    r.add_argument("--outcome", required=True, choices=OUTCOMES)
    r.add_argument("--redirects", type=int, default=0)
    r.add_argument("--reason", required=True, choices=sorted(VALID_CODES))
    rec = sub.add_parser("recent", parents=[common])
    rec.add_argument("model", nargs="?", default=None)
    rec.add_argument("--limit", type=int, default=10)
    s = sub.add_parser("summary", parents=[common])
    s.add_argument("model", nargs="?", default=None)
    s.add_argument("category", nargs="?", default=None)
    d = sub.add_parser("decision", parents=[common])
    d.add_argument("--model", required=True)
    d.add_argument("--category", required=True)
    d.add_argument("--outcome", required=True, choices=OUTCOMES)
    d.add_argument("--reason", default="clean")
    d.add_argument("--redirects", type=int, default=0)
    args = p.parse_args(argv)
    path = args.path or store_path()

    if args.cmd == "record":
        rec = {"ts": now_utc(), "model": args.model,
               "thinking": args.thinking, "category": args.category,
               "outcome": args.outcome, "redirects": args.redirects,
               "reason": args.reason}
        append(rec, path)
        print(json.dumps(rec, sort_keys=True))
    elif args.cmd == "recent":
        rows = load(path)
        if args.model:
            rows = [r for r in rows
                    if r.get("model", "").lower() == args.model.lower()]
        for r in rows[-args.limit:]:
            print(json.dumps(r, sort_keys=True))
    elif args.cmd == "summary":
        rows = load(path)
        if args.model:
            rows = [r for r in rows
                    if r.get("model", "").lower() == args.model.lower()]
        if args.category:
            rows = [r for r in rows if r.get("category") == args.category]
        counts = {o: sum(r["outcome"] == o for r in rows)
                  for o in OUTCOMES}
        print(json.dumps({"model": args.model, "category": args.category,
                          "stages": len(rows), "outcomes": counts}))
    elif args.cmd == "decision":
        print(json.dumps(decide(args.model, args.category, args.outcome,
                                args.reason, args.redirects), sort_keys=True))
    else:
        p.print_help()
    return 0


# ponytail: naive last-3 red scan, per-model list scan is O(n) file read; fine
# at conversation scale. Replace with sqlite only if history grows unbounded.
def self_test():
    root = tempfile.mkdtemp(prefix="herdr-model-outcome-test-")
    path = os.path.join(root, "outcomes.jsonl")
    os.environ["HERDR_MODEL_OUTCOMES"] = path
    os.environ.pop("PYTHONDONTWRITEBYTECODE", None)  # irrelevant; no imports cached

    # record + corrupt-line tolerance
    append({"ts": "x", "model": "kimi-k2.7-code", "thinking": "medium",
            "category": "coding", "outcome": "green", "redirects": 0,
            "reason": "clean"}, path)
    with open(path, "a") as fh:
        fh.write("{corrupt\n")
    append({"ts": "y", "model": "kimi-k2.7-code", "thinking": "medium",
            "category": "coding", "outcome": "red", "redirects": 0,
            "reason": "repeated_fail"}, path)
    rows = load(path)
    assert len(rows) == 2 and rows[1]["outcome"] == "red", rows

    # immediate switch on failure class
    v = decide("m1", "coding", "red", "rate_limit")
    assert v["action"] == "switch" and v["immediate"]
    assert v["recommended_model"] == v["fallback"] != "m1", v

    # first red -> one redirect on the SAME model; fallback is escalation-only
    v = decide("m2", "coding", "red", "repeated_fail", redirects=0)
    assert v["action"] == "redirect_once" and v["recommended_model"] == "m2", v
    assert v["fallback"] != "m2", v
    # a red that already had a redirect in the same stage switches immediately
    v = decide("m2b", "coding", "red", "repeated_fail", redirects=1)
    assert v["action"] == "switch" and v["rule"] == "correction_already_failed", v
    assert v["recommended_model"] == v["fallback"] != "m2b", v
    assert v["fallback"] != "m2", v
    append({"ts": "z", "model": "m2", "thinking": "off",
            "category": "coding", "outcome": "red",
            "redirects": 0, "reason": "repeated_fail"}, path)
    append({"ts": "z", "model": "m2", "thinking": "off",
            "category": "coding", "outcome": "red",
            "redirects": 1, "reason": "repeated_fail"}, path)
    v = decide("m2", "coding", "red", "repeated_fail")
    assert v["action"] == "switch" and v["immediate"]
    assert v["recommended_model"] == v["fallback"] != "m2", v

    # continue keeps the current model even if it is not the category default
    v = decide("qwen3.7-plus", "investigate", "green", "clean")
    assert v["action"] == "continue"
    assert v["recommended_model"] == "qwen3.7-plus", v
    assert "fallback" not in v

    # yellow/continue
    assert decide("m3", "docs", "yellow", "corrected_once")["action"] == "continue"
    assert decide("m3", "docs", "green", "clean")["action"] == "continue"

    # falls back to default category for unknown categories
    assert decide("m1", "unknown-cat", "red", "rate_limit")["fallback"]
    # parallel append interleaving
    import subprocess
    procs = [subprocess.Popen(
        [sys.executable, "-u", __file__, "record", "--model", "p", "--thinking",
         "off", "--category", "coding", "--outcome", "green", "--reason",
         "clean", "--path", path]) for _ in range(8)]
    for proc in procs:
        proc.wait()
    all_rows = load(path)
    assert sum(r.get("model") == "p" for r in all_rows) == 8, len(all_rows)

    print("model_outcome self-test passed")
    import shutil
    shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--self-test":
        self_test()
        sys.exit(0)
    sys.exit(main())
