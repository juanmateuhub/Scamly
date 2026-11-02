"""Evaluate Scamly on data/eval/listings.jsonl: precision, recall, F1 and confusion matrix.

Usage (from the repo root, with the backend virtualenv):
    backend/.venv/Scripts/python scripts/evaluate.py                 # rules only
    backend/.venv/Scripts/python scripts/evaluate.py --llm           # rules vs rules + LLM
    backend/.venv/Scripts/python scripts/evaluate.py --split test -v # held-out split, list errors

LLM findings are cached 24 h (backend/.cache), so the free daily quota can be spread over
several days: each run only spends calls on listings not yet cached (--max-llm-calls).
"""

import argparse
import statistics
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.config import settings
from app.evaluation import Confusion, EvalItem, confusion, load_dataset
from app.llm.cache import FindingsCache
from app.llm.client import LLMError, OpenAICompatibleClient
from app.llm.service import LlmTextService
from app.models.listing import Analysis
from app.rules.loader import (
    load_phrase_rules,
    load_reference_prices,
    load_scoring_config,
)
from app.scoring.analyzer import analyze_listing
from app.signals.text_llm import LlmFindings

THRESHOLDS = {"rojo": {"rojo"}, "amarillo+": {"amarillo", "rojo"}}


class BudgetedClient:
    """Wraps the real LLM client: counts real calls, times them and stops at a budget."""

    def __init__(self, inner: OpenAICompatibleClient, budget: int, delay_s: float) -> None:
        self.inner = inner
        self.budget = budget
        self.delay_s = delay_s  # pause between real calls (provider tokens-per-minute limit)
        self.latencies: list[float] = []
        self.failures = 0

    def complete_json(self, system: str, user: str) -> str:
        if len(self.latencies) >= self.budget:
            raise LLMError("call budget exhausted")
        if self.latencies:
            time.sleep(self.delay_s)
        start = time.perf_counter()
        try:
            return self.inner.complete_json(system, user)
        except LLMError:
            self.failures += 1
            raise
        finally:
            self.latencies.append(time.perf_counter() - start)


@dataclass
class Result:
    item: EvalItem
    analysis: Analysis


def score(item: EvalItem, findings: LlmFindings | None) -> Result:
    analysis = analyze_listing(
        item.listing,
        config=load_scoring_config(),
        phrases=load_phrase_rules(),
        reference=load_reference_prices(),
        llm_findings=findings,
        now=datetime.now(UTC),
    )
    return Result(item, analysis)


def matrix(results: list[Result], threshold: str) -> Confusion:
    levels = THRESHOLDS[threshold]
    return confusion((r.item.is_scam, r.analysis.level in levels) for r in results)


def print_table(rows: list[tuple[str, list[Result]]]) -> None:
    print("| Modo | n | Positivo si | Precisión | Recall | F1 | TP | FP | TN | FN |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for name, results in rows:
        for threshold in THRESHOLDS:
            m = matrix(results, threshold)
            print(
                f"| {name} | {len(results)} | {threshold} | {m.precision:.2f} | {m.recall:.2f} "
                f"| {m.f1:.2f} | {m.tp} | {m.fp} | {m.tn} | {m.fn} |"
            )


def print_scores(name: str, results: list[Result]) -> None:
    for label in ("sospechoso", "legitimo"):
        scores = [r.analysis.risk_score for r in results if r.item.label == label]
        if scores:
            print(
                f"  {name}, {label}: nota media {statistics.mean(scores):.0f}, "
                f"mediana {statistics.median(scores):.0f}"
            )


def print_errors(name: str, results: list[Result]) -> None:
    print(f"\nErrores ({name}, positivo = rojo):")
    for r in results:
        predicted = r.analysis.level == "rojo"
        if predicted != r.item.is_scam:
            kind = "FN" if r.item.is_scam else "FP"
            print(
                f"  {kind} {r.item.id} nota {r.analysis.risk_score:>3} "
                f"({r.analysis.level}): {r.item.listing.title} | {r.item.notes}"
            )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--split", choices=["all", "dev", "test"], default="all")
    parser.add_argument("--llm", action="store_true", help="also evaluate rules + LLM")
    parser.add_argument("--max-llm-calls", type=int, default=40, help="real LLM calls per run")
    parser.add_argument(
        "--delay-s", type=float, default=0.0, help="pause between real LLM calls (rate limits)"
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="list misclassified items")
    args = parser.parse_args()

    items = [i for i in load_dataset() if args.split in ("all", i.split)]
    print(
        f"Dataset: {len(items)} anuncios (split={args.split}), sintéticos: métricas orientativas\n"
    )

    start = time.perf_counter()
    rules = [score(item, None) for item in items]
    rules_ms = (time.perf_counter() - start) / len(items) * 1000
    rows: list[tuple[str, list[Result]]] = [("Solo reglas", rules)]

    budgeted: BudgetedClient | None = None
    with_llm: list[Result] = []
    if args.llm:
        if not settings.llm_enabled:
            sys.exit("LLM_API_KEY no configurada en .env")
        budgeted = BudgetedClient(
            OpenAICompatibleClient(
                settings.llm_base_url,
                settings.llm_model,
                settings.llm_api_key.get_secret_value(),
                timeout_s=settings.llm_timeout_s,
                fallback_models=settings.llm_fallback_list,
                disable_reasoning=settings.llm_disable_reasoning,
                reasoning_effort=settings.llm_reasoning_effort,
            ),
            budget=args.max_llm_calls,
            delay_s=args.delay_s,
        )
        cache = FindingsCache(settings.cache_path, ttl=timedelta(hours=settings.cache_ttl_hours))
        service = LlmTextService(budgeted, cache, model_id=settings.llm_model)
        covered_rules = []
        for item, rule_result in zip(items, rules, strict=True):
            findings = service.findings_for(item.listing, datetime.now(UTC))
            if findings is not None:
                with_llm.append(score(item, findings))
                covered_rules.append(rule_result)
        # Compare both modes on the same listings (those the LLM could analyse).
        rows = [("Solo reglas", rules)]
        if with_llm:
            rows += [("Solo reglas (mismos)", covered_rules), ("Reglas + LLM", with_llm)]

    print_table(rows)
    print("\nNotas por etiqueta:")
    for name, results in rows:
        print_scores(name, results)
    print(f"\nTiempo medio solo reglas: {rules_ms:.1f} ms/anuncio")
    if budgeted is not None:
        print(
            f"LLM: {len(with_llm)}/{len(items)} anuncios con análisis LLM, "
            f"{len(budgeted.latencies)} llamadas reales en esta ejecución"
        )
        if budgeted.latencies:
            print(
                f"Latencia LLM: mediana {statistics.median(budgeted.latencies):.1f} s, "
                f"máx. {max(budgeted.latencies):.1f} s"
            )
    if args.verbose:
        for name, results in rows:
            if name != "Solo reglas (mismos)":
                print_errors(name, results)


if __name__ == "__main__":
    main()
