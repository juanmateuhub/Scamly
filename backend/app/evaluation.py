"""Evaluation dataset schema and classification metrics (used by scripts/evaluate.py)."""

import json
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.config import REPO_ROOT
from app.models.listing import Listing

DATASET_PATH = REPO_ROOT / "data" / "eval" / "listings.jsonl"


class EvalItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    # Real listings stay "sin_revisar" until the author labels them; they are left out of metrics.
    label: Literal["legitimo", "sospechoso", "sin_revisar"]
    # Tune weights on dev only; report test separately. "real": anonymized real listings,
    # never used for tuning, reported on their own.
    split: Literal["dev", "test", "real"]
    notes: str
    source: str
    listing: Listing

    @property
    def is_labeled(self) -> bool:
        return self.label != "sin_revisar"

    @property
    def is_scam(self) -> bool:
        return self.label == "sospechoso"


def load_dataset(path: Path = DATASET_PATH) -> list[EvalItem]:
    with path.open(encoding="utf-8") as file:
        items = [EvalItem.model_validate(json.loads(line)) for line in file if line.strip()]
    duplicated = [i for i, n in Counter(item.id for item in items).items() if n > 1]
    if duplicated:
        raise ValueError(f"duplicated ids in dataset: {duplicated}")
    return items


@dataclass(frozen=True, slots=True)
class Confusion:
    tp: int
    fp: int
    tn: int
    fn: int

    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if self.tp + self.fp else 0.0

    @property
    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if self.tp + self.fn else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if p + r else 0.0

    @property
    def accuracy(self) -> float:
        total = self.tp + self.fp + self.tn + self.fn
        return (self.tp + self.tn) / total if total else 0.0


def confusion(pairs: Iterable[tuple[bool, bool]]) -> Confusion:
    """Build a confusion matrix from (is_scam, predicted_scam) pairs."""
    counts = Counter(pairs)
    return Confusion(
        tp=counts[(True, True)],
        fp=counts[(False, True)],
        tn=counts[(False, False)],
        fn=counts[(True, False)],
    )
