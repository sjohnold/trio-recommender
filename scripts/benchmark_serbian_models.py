#!/usr/bin/env python3
"""Measure local Ollama candidates against the Serbian language gate."""

import argparse
import asyncio
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from statistics import quantiles

import httpx

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from trio.contracts import Language
from trio.language.contracts import LanguageLock, Script, SerbianVariant
from trio.language.detector import detect_language
from trio.language.script_detector import DetectedScript, detect_script
from trio.language.serbian import check_variant

OLLAMA_URL = "http://127.0.0.1:11434"
PROMPTS = (
    "Objasni detetu kakvo je lepo vreme i zašto.",
    "Napiši kratak razgovor o mleku i vremenu.",
    "Objasni kako sneg utiče na reku.",
    "Opiši čoveka koji voli pesme.",
    "Uporedi svet deteta i odraslog čoveka.",
    "Daj dva razloga zašto je mleko korisno.",
    "Napiši tri rečenice o lepom zimskom danu.",
    "Objasni vezu između reke, snega i vremena.",
    "Ispravi netačnu tvrdnju ljubaznim tonom.",
    "Iznesi argument i zatim mu prigovori.",
    "Sažmi ideju, navedi razlog i zaključak.",
    "Odgovori sagovorniku uz kratko priznanje njegove poente.",
)


def fraction(value: str) -> float:
    number = float(value)
    if not 0 <= number <= 1:
        raise argparse.ArgumentTypeError("rate must be between 0 and 1")
    return number


def positive(value: str) -> float:
    number = float(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("value must be positive")
    return number


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Run the local 12-prompt Serbian model gate")
    result.add_argument("--models", nargs="+", required=True)
    result.add_argument("--script", choices=("latn", "cyrl"), default="latn")
    result.add_argument("--variant", choices=("ekavian", "ijekavian"), default="ekavian")
    result.add_argument("--out", type=Path, default=Path("data/benchmarks/serbian_gate.json"))
    result.add_argument("--min-valid", type=fraction, default=0.9)
    result.add_argument("--min-language", type=fraction, default=0.8)
    result.add_argument("--min-script", type=fraction, default=0.9)
    result.add_argument("--min-variant", type=fraction, default=0.7)
    result.add_argument("--max-p95-s", type=positive, default=30.0)
    return result


async def run_model(client, model: str, lock: LanguageLock, digest: str | None) -> dict:
    observations = []
    instruction = f"Odgovori samo na srpskom; pismo={lock.script}; varijanta={lock.variant}. "
    expected_script = (
        DetectedScript.LATIN if lock.script is Script.LATIN else DetectedScript.CYRILLIC
    )
    for prompt in PROMPTS:
        started = time.perf_counter()
        try:
            response = await client.post(
                "/api/generate",
                json={"model": model, "prompt": instruction + prompt, "stream": False, "keep_alive": -1},
            )
            response.raise_for_status()
            text = response.json()["response"].strip()
            valid_response = bool(text)
            error = "empty_response"
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            text, valid_response = "", False
            error = f"{type(exc).__name__}: {exc}"
        latency = time.perf_counter() - started
        language = detect_language(text)
        script = detect_script(text, [])
        variant = check_variant(text, lock)
        observations.append(
            {
                "latency_s": round(latency, 3),
                "valid_response": valid_response,
                "language_ok": language.language is Language.SR,
                "script_ok": script.script is expected_script,
                "variant_ok": variant.conforms is True,
                **({"error": error} if not valid_response else {}),
            }
        )
    rate = lambda key: sum(item[key] for item in observations) / len(observations)
    latencies = [item["latency_s"] for item in observations]
    summary = {
        "valid_rate": rate("valid_response"),
        "language_rate": rate("language_ok"),
        "script_rate": rate("script_ok"),
        "variant_rate": rate("variant_ok"),
        "p95_latency_s": quantiles(latencies, n=20)[18],
    }
    return {"model": model, "digest": digest, "observations": observations, "summary": summary}


async def main() -> None:
    args = parser().parse_args()
    script = Script.LATIN if args.script == "latn" else Script.CYRILLIC
    lock = LanguageLock(language=Language.SR, script=script, variant=SerbianVariant(args.variant))
    thresholds = {key: getattr(args, key) for key in ("min_valid", "min_language", "min_script", "min_variant", "max_p95_s")}
    async with httpx.AsyncClient(base_url=OLLAMA_URL, timeout=120) as client:
        tags = (await client.get("/api/tags")).json().get("models", [])
        digests = {item.get("name"): item.get("digest") for item in tags}
        results = [await run_model(client, model, lock, digests.get(model)) for model in args.models]
    for result in results:
        summary = result["summary"]
        result["passed"] = all(
            (
                summary["valid_rate"] >= args.min_valid,
                summary["language_rate"] >= args.min_language,
                summary["script_rate"] >= args.min_script,
                summary["variant_rate"] >= args.min_variant,
                summary["p95_latency_s"] <= args.max_p95_s,
                result["digest"] is not None,
            )
        )
    report = {"schema_version": 1, "generated_at": datetime.now(UTC).isoformat(), "thresholds": thresholds, "prompts": list(PROMPTS), "models": results}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())
