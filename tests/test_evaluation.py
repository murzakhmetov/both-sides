"""Metrics, the evaluation report and the live check, without network."""

from __future__ import annotations

import pytest

from bothsides.matching.gemini import GeminiMatcher
from bothsides.matching.types import MatcherError, Tri
from evaluation import evaluate, live_check
from evaluation.metrics import auc, auc_interval, wilson

from .fakes import FakeGeminiClient, StubMatcher, gemini_reply, gemini_result


@pytest.mark.parametrize(
    ("positives", "negatives", "expected"),
    [([0.9, 0.8], [0.1, 0.2], 1.0), ([0.1], [0.9], 0.0), ([0.5], [0.5], 0.5), ([0.9, 0.1], [0.5], 0.5)],
)
def test_auc(positives: list[float], negatives: list[float], expected: float) -> None:
    assert auc(positives, negatives) == expected


def test_auc_needs_both_groups() -> None:
    with pytest.raises(ValueError):
        auc([], [0.5])


def test_auc_interval_holds_the_value_and_repeats() -> None:
    positives, negatives = [0.9, 0.8, 0.4, 0.7], [0.1, 0.5, 0.3]
    low, high = auc_interval(positives, negatives, rounds=300)
    assert low <= auc(positives, negatives) <= high
    assert (low, high) == auc_interval(positives, negatives, rounds=300)


def test_wilson() -> None:
    low, high = wilson(5, 10)
    assert low == pytest.approx(0.2366, abs=0.001) and high == pytest.approx(0.7634, abs=0.001)
    assert wilson(0, 10)[0] == 0.0 and wilson(10, 10)[1] == pytest.approx(1.0)
    with pytest.raises(ValueError):
        wilson(1, 0)


def test_pairs_have_all_groups_and_no_digits_that_look_like_accounts() -> None:
    pairs = evaluate.load_pairs()
    assert {pair["group"] for pair in pairs} == set(evaluate.GROUPS)
    assert len({pair["id"] for pair in pairs}) == len(pairs)
    for pair in pairs:
        assert not any(len(run) >= 8 for run in "".join(c if c.isdigit() else " " for c in pair["receiver"] + " " + pair["sender"]).split())


def test_limit_takes_every_group() -> None:
    limited = evaluate.load_pairs(limit=12)
    assert {pair["group"] for pair in limited} == set(evaluate.GROUPS)
    assert len(limited) < 20


def test_report_labels_every_number() -> None:
    pairs = evaluate.load_pairs(limit=12)
    rows = [evaluate.score(pair, StubMatcher(gemini_result(0.9 if pair["group"] == "honest" else 0.1))) for pair in pairs]
    summary = evaluate.summarize(rows)
    text = evaluate.report("test", summary)
    assert summary["label"] == "measured on simulated pairs"
    assert text.count("measured on simulated pairs") >= 2
    assert summary["auc"]["all others"]["auc"] == 1.0


def test_failed_request_counts_as_a_person() -> None:
    pair = evaluate.load_pairs(limit=4)[0]
    row = evaluate.score(pair, StubMatcher(MatcherError("timeout")))
    assert (row.outcome, row.failure, row.probability) == ("person", "timeout", None)


def test_offline_run_saves_a_file(tmp_path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(evaluate, "RESULTS", tmp_path / "results")
    monkeypatch.setattr(evaluate, "ROOT", tmp_path)
    assert evaluate.main([]) == 0
    assert (tmp_path / "results" / "offline.json").is_file()
    assert "measured on simulated pairs" in capsys.readouterr().out


def test_gemini_run_without_a_key_says_so(monkeypatch: pytest.MonkeyPatch, tmp_path, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(evaluate, "RESULTS", tmp_path / "results")
    monkeypatch.setattr(evaluate, "ROOT", tmp_path)
    monkeypatch.setenv("GEMINI_API_KEY", "")
    assert evaluate.main(["--gemini", "--limit", "8"]) == 2
    assert "Gemini was not measured" in capsys.readouterr().out
    assert not (tmp_path / "results" / "gemini.json").exists()


# -- live check ------------------------------------------------------------------


def test_there_are_exactly_ten_live_requests() -> None:
    assert len(live_check.CHECKS) == 10


def test_live_check_sends_ten_requests_and_prints_results(capsys: pytest.CaptureFixture[str]) -> None:
    client = FakeGeminiClient(gemini_reply(probability=0.9))
    lines, passed = live_check.run_checks(GeminiMatcher(client, "gemini-fake"), pause=0)
    assert len(client.interactions.calls) == len(lines) == 10
    assert 0 < passed < 10
    output = capsys.readouterr().out
    assert "WRONG" in output and "ok" in output


def test_live_check_survives_failures() -> None:
    lines, passed = live_check.run_checks(StubMatcher(MatcherError("rate_limited")), pause=0)
    assert passed == 0
    assert all("rate_limited" in line for line in lines)


def test_live_check_without_a_key_sends_nothing(monkeypatch: pytest.MonkeyPatch, tmp_path, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(live_check, "ROOT", tmp_path)
    monkeypatch.setenv("GEMINI_API_KEY", "")
    assert live_check.main([]) == 2
    assert "Nothing was sent" in capsys.readouterr().out


def test_expected_outcomes_follow_the_gate() -> None:
    good = live_check.CHECKS[0]
    line, passed = live_check._line(1, good, StubMatcher(gemini_result(0.95)), lambda: 0.0)
    assert passed and "release" in line
    sister = live_check.CHECKS[3]
    line, passed = live_check._line(4, sister, StubMatcher(gemini_result(0.02, Tri.FALSE, Tri.FALSE)), lambda: 0.0)
    assert passed and "hold" in line
