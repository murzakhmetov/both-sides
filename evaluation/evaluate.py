"""Measures the matchers on SIMULATED pairs. Not a claim about real customers.

    python evaluation/evaluate.py                     offline matcher, no network
    python evaluation/evaluate.py --gemini            Gemini, one request per pair, needs GEMINI_API_KEY
    python evaluation/evaluate.py --gemini --limit 20 a smaller, cheaper run

The pairs were written by language models that could not see the matcher, its
word list or its weights. The weights were fixed before the first run.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bothsides.decision.gate import GateInput, Outcome, decide  # noqa: E402
from bothsides.main import use_utf8_output  # noqa: E402
from bothsides.matching.denials import find_denial  # noqa: E402
from bothsides.matching.factory import build_matcher  # noqa: E402
from bothsides.matching.gemini import GeminiMatcher  # noqa: E402
from bothsides.matching.offline import OfflineMatcher  # noqa: E402
from bothsides.matching.types import Matcher, MatcherError, MatchResult  # noqa: E402
from bothsides.settings import SettingsError, load_env_file  # noqa: E402
from evaluation.metrics import auc, auc_interval, wilson  # noqa: E402

PAIRS_FILE = ROOT / "evaluation" / "pairs.json"
RESULTS = ROOT / "evaluation" / "results"
GROUPS = ("honest", "stranger", "other_transfer", "told_one_line")
TITLES = {
    "honest": "honest pairs",
    "stranger": "strangers (first name and amount only)",
    "other_transfer": "answers about another transfer",
    "told_one_line": "both told the story in one line",
}
LABEL = "measured on simulated pairs"


@dataclass(frozen=True, slots=True)
class Scored:
    """One pair with its score and the decision under calm bank facts."""

    id: str
    group: str
    probability: float | None
    outcome: str
    failure: str = ""


def load_pairs(limit: int | None = None) -> list[dict[str, Any]]:
    """Read the pairs; a limit takes the same share of every group."""
    pairs = json.loads(PAIRS_FILE.read_text(encoding="utf-8"))["pairs"]
    if limit is None or limit >= len(pairs):
        return pairs
    chosen: list[dict[str, Any]] = []
    for group in GROUPS:
        members = [pair for pair in pairs if pair["group"] == group]
        chosen += members[: max(1, round(limit * len(members) / len(pairs)))]
    return chosen


def _outcome(match: MatchResult | None, pair: dict[str, Any]) -> Outcome:
    if find_denial(pair["receiver"]) or find_denial(pair["sender"]):
        return Outcome.PERSON
    return decide(GateInput(match, pair["receiver"], pair["sender"], risky_facts=0, similar_receivers=0)).outcome


def score(pair: dict[str, Any], matcher: Matcher) -> Scored:
    """Score one pair. A matcher failure goes to a person, like in the app."""
    try:
        match: MatchResult | None = matcher.compare(pair["receiver"], pair["sender"])
        failure = ""
    except MatcherError as error:
        match, failure = None, error.code
    probability = match.probability if match else None
    return Scored(pair["id"], pair["group"], probability, _outcome(match, pair).value, failure)


def _group_summary(rows: Sequence[Scored]) -> dict[str, Any]:
    outcomes = Counter(row.outcome for row in rows)
    low, high = wilson(outcomes["release"], len(rows))
    return {
        "pairs": len(rows),
        "released": outcomes["release"],
        "release_rate": outcomes["release"] / len(rows),
        "release_interval": [low, high],
        "held": outcomes["hold"],
        "to_a_person": outcomes["person"],
        "failures": sum(1 for row in rows if row.failure),
    }


def summarize(rows: Sequence[Scored]) -> dict[str, Any]:
    """AUC of honest pairs against every other group, and release rates."""
    groups = {group: [row for row in rows if row.group == group] for group in GROUPS}
    scores = {group: [r.probability for r in rows if r.probability is not None] for group, rows in groups.items()}
    others = [value for group in GROUPS[1:] for value in scores[group]]
    aucs: dict[str, Any] = {}
    for name, negatives in [("all others", others), *((group, scores[group]) for group in GROUPS[1:])]:
        if scores["honest"] and negatives:
            low, high = auc_interval(scores["honest"], negatives)
            aucs[name] = {"auc": auc(scores["honest"], negatives), "interval": [low, high]}
    return {
        "label": LABEL,
        "bank_facts": "calm, no repeated story",
        "auc": aucs,
        "groups": {group: _group_summary(found) for group, found in groups.items() if found},
    }


def _percent(value: float) -> str:
    return f"{100 * value:.0f}%"


def report(name: str, summary: dict[str, Any]) -> str:
    """The text printed for one matcher."""
    lines = [f"{name} - {LABEL}, calm bank facts", ""]
    for target, item in summary["auc"].items():
        low, high = item["interval"]
        title = TITLES.get(target, target)
        lines.append(f"  AUC honest vs {title}: {item['auc']:.2f}  (95% interval {low:.2f} to {high:.2f})")
    lines.append("")
    for group, item in summary["groups"].items():
        low, high = item["release_interval"]
        lines.append(
            f"  released: {item['released']:>2} of {item['pairs']:>2} {TITLES[group]} = {_percent(item['release_rate'])}"
            f" (95% interval {_percent(low)} to {_percent(high)}), held {item['held']}, to a person {item['to_a_person']}"
            + (f", no answer {item['failures']}" if item["failures"] else "")
        )
    return "\n".join([*lines, "", f"  Every number above was {LABEL}.", ""])


def _save(name: str, rows: Sequence[Scored], summary: dict[str, Any], model: str) -> Path:
    RESULTS.mkdir(parents=True, exist_ok=True)
    target = RESULTS / f"{name}.json"
    data = {**summary, "matcher": name, "model": model, "rows": [asdict(row) for row in rows]}
    target.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    return target


def run_matcher(
    name: str, matcher: Matcher, pairs: Sequence[dict[str, Any]], pause: float, model: str = "", sample: bool = False
) -> None:
    """Score the pairs, print the report and save it. A sample never replaces the full measurement."""
    rows: list[Scored] = []
    for number, pair in enumerate(pairs, start=1):
        rows.append(score(pair, matcher))
        if pause:
            print(f"\r  {number} of {len(pairs)}", end="", flush=True)
            time.sleep(pause)
    if pause:
        print()
    summary = summarize(rows)
    print(report(f"{name} {model}".strip(), summary))
    file_name = f"{name}-sample" if sample else name
    print(f"  Saved to {_save(file_name, rows, summary, model).relative_to(ROOT)}\n")


def _run_gemini(pairs: Sequence[dict[str, Any]], pause: float, sample: bool) -> int:
    setup = build_matcher(offline=False, env=os.environ)
    matcher = setup.language_model
    if matcher is None:
        print(f"Gemini was not measured: {setup.status().reason}. Set GEMINI_API_KEY and install google-genai.")
        return 2
    setup.confirm_model()
    if isinstance(matcher, GeminiMatcher):
        matcher.use_model(matcher.model)  # no spare models: every answer belongs to the model in the report
    run_matcher("gemini", matcher, pairs, pause, setup.status().model, sample)
    return 0


def main(arguments: Sequence[str]) -> int:
    use_utf8_output()
    parser = argparse.ArgumentParser(description="Measure the matchers on simulated pairs.")
    parser.add_argument("--gemini", action="store_true", help="also measure Gemini (sends one request per pair)")
    parser.add_argument("--limit", type=int, default=None, help="use about this many pairs")
    parser.add_argument("--pause", type=float, default=0.5, help="seconds between Gemini requests")
    parsed = parser.parse_args(list(arguments))
    if parsed.limit is not None and parsed.limit < 1:
        parser.error("--limit must be at least 1")
    try:
        load_env_file(ROOT / ".env")
    except SettingsError as error:
        print(f"Cannot start: {error}", file=sys.stderr)
        return 2
    pairs = load_pairs(parsed.limit)
    sample = len(pairs) < len(load_pairs(None))
    print(f"{len(pairs)} simulated pairs, written without sight of the matcher.\n")
    run_matcher("offline", OfflineMatcher(), pairs, pause=0, sample=sample)
    return _run_gemini(pairs, parsed.pause, sample) if parsed.gemini else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
