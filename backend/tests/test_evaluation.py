import json
import re
from collections import Counter
from pathlib import Path

import pytest

from app.evaluation import DATASET_PATH, Confusion, confusion, load_dataset
from app.signals.text_rules import normalize


def test_confusion_counts_each_cell() -> None:
    pairs = [(True, True), (True, True), (True, False), (False, True), (False, False)]

    assert confusion(pairs) == Confusion(tp=2, fp=1, tn=1, fn=1)


def test_metrics() -> None:
    matrix = Confusion(tp=8, fp=2, tn=6, fn=4)

    assert matrix.precision == pytest.approx(0.8)
    assert matrix.recall == pytest.approx(8 / 12)
    assert matrix.f1 == pytest.approx(2 * 0.8 * (8 / 12) / (0.8 + 8 / 12))
    assert matrix.accuracy == pytest.approx(0.7)


def test_metrics_without_positives_are_zero_not_errors() -> None:
    matrix = Confusion(tp=0, fp=0, tn=5, fn=0)

    assert (matrix.precision, matrix.recall, matrix.f1) == (0.0, 0.0, 0.0)


def test_duplicated_ids_are_rejected(tmp_path: Path) -> None:
    line = DATASET_PATH.read_text(encoding="utf-8").splitlines()[0]
    path = tmp_path / "dup.jsonl"
    path.write_text(f"{line}\n{line}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="duplicated"):
        load_dataset(path)


# --- the shipped dataset --------------------------------------------------------------


def test_dataset_is_valid_and_balanced() -> None:
    items = load_dataset()
    counts = Counter((item.label, item.split) for item in items)

    assert len(items) >= 100
    for split in ("dev", "test"):
        assert counts[("sospechoso", split)] == counts[("legitimo", split)] > 0


def test_dataset_uses_only_fictitious_contact_data() -> None:
    """Anonymisation: no real-looking phones or emails may end up in the repository."""
    text = DATASET_PATH.read_text(encoding="utf-8")
    listings = [json.loads(line)["listing"] for line in text.splitlines()]
    body = normalize(" ".join(f"{li['title']} {li['description']}" for li in listings))

    emails = re.findall(r"[\w.%+-]+@[\w.-]+\.[a-z]{2,}", body)
    phones = re.findall(r"(?<!\d)[6789](?:[\s.-]?\d){8}(?!\d)", body)

    assert all(email.endswith("@example.com") for email in emails)
    assert all(re.sub(r"\D", "", phone)[1:] in {"00000000", "99999999"} for phone in phones)
