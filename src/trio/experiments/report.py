"""Descriptive H1-H5 report artifacts with explicit uncertainty."""
import csv
import random
from dataclasses import dataclass
from io import StringIO
from math import sqrt
from statistics import fmean, median, stdev

HYPOTHESES = tuple(f"H{index}" for index in range(1, 6))
FIELDS = ("hypothesis", "metric", "status", "n", "missing", "mean", "median",
          "ci_low", "ci_high", "effect_size", "failures", "digests",
          "annotation_version")


@dataclass(frozen=True, slots=True)
class ReportArtifacts:
    markdown: str
    csv: str


def _numbers(values):
    return [float(value) for value in values if value is not None]


def _bootstrap(values):
    if len(values) < 2:
        return None, None
    rng = random.Random(0)
    means = sorted(
        fmean(rng.choice(values) for _ in values) for _ in range(1000)
    )
    return means[24], means[974]


def _effect(values, comparison):
    other = _numbers(comparison)
    if len(values) < 2 or len(other) < 2:
        return None
    pooled = sqrt((stdev(values) ** 2 + stdev(other) ** 2) / 2)
    return (fmean(values) - fmean(other)) / pooled if pooled else None


def _format(value):
    return "" if value is None else f"{value:.6g}" if isinstance(value, float) else value


def _row(hypothesis, result, digests, annotation):
    raw = result.get("values", []) if result else []
    values = _numbers(raw)
    measured = len(values) >= 2
    low, high = _bootstrap(values)
    return {
        "hypothesis": hypothesis,
        "metric": result.get("metric", "") if result else "",
        "status": "measured" if measured else "insufficient-data",
        "n": len(values),
        "missing": sum(value is None for value in raw),
        "mean": fmean(values) if measured else None,
        "median": median(values) if measured else None,
        "ci_low": low,
        "ci_high": high,
        "effect_size": _effect(values, result.get("comparison", []))
        if measured else None,
        "failures": result.get("failures", 0) if result else 0,
        "digests": ";".join(f"{key}={digests[key]}" for key in sorted(digests)),
        "annotation_version": annotation,
    }


def build_report(run_set) -> ReportArtifacts:
    annotation = run_set.get("annotation_version")
    if not isinstance(annotation, str) or not annotation.strip():
        raise ValueError("annotation_version is required")
    results, digests = run_set.get("results", {}), run_set.get("digests", {})
    if not isinstance(digests, dict) or not digests:
        raise ValueError("model digests are required")
    rows = [_row(key, results.get(key), digests, annotation) for key in HYPOTHESES]
    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows({key: _format(row[key]) for key in FIELDS} for row in rows)
    header = "| " + " | ".join(FIELDS) + " |"
    rule = "| " + " | ".join("---" for _ in FIELDS) + " |"
    body = ["| " + " | ".join(str(_format(row[key])) for key in FIELDS) + " |"
            for row in rows]
    markdown = "\n".join((
        "# Experiment results", f"Manual annotation: `{annotation}`",
        "", header, rule, *body,
    )) + "\n"
    return ReportArtifacts(markdown, output.getvalue())
