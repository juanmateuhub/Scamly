"""Load and validate the YAML rule files: scoring weights, Spanish phrases and reference prices.

All tunable numbers live in these files, never in the signal code.
"""

import re
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Literal, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

RULES_DIR = Path(__file__).parent
REPO_ROOT = RULES_DIR.parents[2]
SCORING_PATH = RULES_DIR / "scoring.yaml"
PHRASES_PATH = RULES_DIR / "phrases_es.yaml"
REFERENCE_PRICES_PATH = REPO_ROOT / "data" / "reference_prices.yaml"

Unit = Annotated[float, Field(ge=0, le=1)]
Weight = Annotated[float, Field(ge=0, le=100)]
Positive = Annotated[float, Field(gt=0)]

TextSignalName = Literal["pago_fuera_app", "contacto_externo", "urgencia"]
# Ordered from best to worst.
ConditionLevel = Literal["nuevo", "como_nuevo", "buen_estado", "aceptable", "danado"]
CONDITION_ORDER: tuple[ConditionLevel, ...] = (
    "nuevo",
    "como_nuevo",
    "buen_estado",
    "aceptable",
    "danado",
)


class _Rules(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


# --- scoring.yaml ---------------------------------------------------------------


class ComparablesConfig(_Rules):
    min_count: Annotated[int, Field(ge=1)]  # fewer similar listings -> use the reference table
    full_count: Positive  # similar listings needed for full confidence
    max_confidence: Unit  # live listings may include scams and variants: never fully trusted


class PriceConfig(_Rules):
    weight: Weight
    ratio_no_risk: Unit
    ratio_max_risk: Unit
    confidence_product: Unit
    confidence_category: Unit
    comparables: ComparablesConfig
    # A worn item can be cheap for a good reason: the price intensity is multiplied by this.
    condition_factors: dict[ConditionLevel | Literal["desconocido"], Unit]

    @model_validator(mode="after")
    def _check_condition_factors(self) -> Self:
        missing = {*CONDITION_ORDER, "desconocido"} - set(self.condition_factors)
        if missing:
            raise ValueError(f"condition_factors missing: {sorted(missing)}")
        return self

    @model_validator(mode="after")
    def _check_ratios(self) -> Self:
        if self.ratio_no_risk <= self.ratio_max_risk:
            raise ValueError("ratio_no_risk must be greater than ratio_max_risk")
        return self


class AccountAgeConfig(_Rules):
    weight: Weight
    decay_days: Positive


class HistoryConfig(_Rules):
    weight: Weight
    half_count: Positive


class BadRatingsConfig(_Rules):
    weight: Weight
    full_count: Positive  # ratings needed for full evidence
    avg_ok: Annotated[float, Field(ge=0, le=5)]  # at or above -> intensity 0
    avg_bad: Annotated[float, Field(ge=0, le=5)]  # at or below -> intensity 1

    @model_validator(mode="after")
    def _check_avg_range(self) -> Self:
        if self.avg_ok <= self.avg_bad:
            raise ValueError("avg_ok must be greater than avg_bad")
        return self


class ShortDescriptionConfig(_Rules):
    weight: Weight
    full_risk_words: Annotated[int, Field(ge=0)]  # at or below -> intensity 1
    no_risk_words: Annotated[int, Field(gt=0)]  # at or above -> intensity 0

    @model_validator(mode="after")
    def _check_words(self) -> Self:
        if self.no_risk_words <= self.full_risk_words:
            raise ValueError("no_risk_words must be greater than full_risk_words")
        return self


class TextSignalConfig(_Rules):
    weight: Weight


class LlmOnlySignalConfig(_Rules):
    weight: Weight
    confidence: Unit


class TextConfidenceConfig(_Rules):
    llm: Unit
    regex: Unit
    both: Unit


class SellerReputationConfig(_Rules):
    max_reduction: Unit
    full_count: Positive
    avg_floor: Annotated[float, Field(ge=0, le=5)]
    avg_ceiling: Annotated[float, Field(ge=0, le=5)]

    @model_validator(mode="after")
    def _check_avg_range(self) -> Self:
        if self.avg_ceiling <= self.avg_floor:
            raise ValueError("avg_ceiling must be greater than avg_floor")
        return self


class ShippingConfig(_Rules):
    max_reduction: Unit


class SignalsConfig(_Rules):
    precio_anomalo: PriceConfig
    cuenta_nueva: AccountAgeConfig
    sin_historial: HistoryConfig
    malas_valoraciones: BadRatingsConfig
    descripcion_pobre: ShortDescriptionConfig
    pago_fuera_app: TextSignalConfig
    contacto_externo: TextSignalConfig
    urgencia: TextSignalConfig
    texto_generico: LlmOnlySignalConfig

    def text_weights(self) -> dict[TextSignalName, TextSignalConfig]:
        return {
            "pago_fuera_app": self.pago_fuera_app,
            "contacto_externo": self.contacto_externo,
            "urgencia": self.urgencia,
        }


class MitigatorsConfig(_Rules):
    vendedor_con_historial: SellerReputationConfig
    envio_protegido: ShippingConfig


class LevelsConfig(_Rules):
    amarillo: Annotated[int, Field(ge=0, le=100)]
    rojo: Annotated[int, Field(ge=0, le=100)]


class ScoringConfig(_Rules):
    levels: LevelsConfig
    min_reason_points: Annotated[float, Field(ge=0)]
    min_mitigator_reduction: Unit
    text_confidence: TextConfidenceConfig
    signals: SignalsConfig
    mitigators: MitigatorsConfig

    @model_validator(mode="after")
    def _check_levels(self) -> Self:
        if not 0 < self.levels.amarillo < self.levels.rojo:
            raise ValueError("levels must satisfy 0 < amarillo < rojo")
        return self

    def total_risk_weight(self) -> float:
        s = self.signals
        return sum(
            signal.weight
            for signal in (
                s.precio_anomalo,
                s.cuenta_nueva,
                s.sin_historial,
                s.malas_valoraciones,
                s.descripcion_pobre,
                s.pago_fuera_app,
                s.contacto_externo,
                s.urgencia,
                s.texto_generico,
            )
        )


# --- phrases_es.yaml ------------------------------------------------------------


class Phrase(_Rules):
    pattern: str
    strength: Unit

    @field_validator("pattern")
    @classmethod
    def _check_regex(cls, value: str) -> str:
        re.compile(value)
        return value


class PhraseRules(_Rules):
    # Words that cancel a match when they appear just before it in the same clause.
    negations: frozenset[str]
    signals: dict[TextSignalName, list[Phrase]]
    # Regexes that cancel a signal's match when they appear anywhere in the same clause
    # (e.g. "bizum al recoger" is an in-person payment, not a payment outside the platform).
    exemptions: dict[TextSignalName, list[str]] = {}

    @field_validator("exemptions")
    @classmethod
    def _check_exemptions(cls, value: dict[str, list[str]]) -> dict[str, list[str]]:
        for patterns in value.values():
            for pattern in patterns:
                re.compile(pattern)
        return value


# --- reference_prices.yaml ------------------------------------------------------


class ReferenceProduct(_Rules):
    name: str
    category: str
    price_eur: Positive
    aliases: Annotated[list[str], Field(min_length=1)]
    exclude: list[str] = []


class ReferencePrices(_Rules):
    # Words in the TITLE that mean it is not the product itself (accessory, wanted ad).
    # Title only: "con funda de regalo" in a description must not hide the price signal.
    skip_words: list[str] = []
    # Phrases in the title OR description that explain a low price (broken, defect).
    defect_phrases: list[str] = []
    # Words that make a different model ("pro", "max"...): comparables must share the same set.
    variant_words: list[str] = []
    # Platform condition text -> level (matched without case or accents).
    conditions: dict[str, ConditionLevel] = {}
    # Wear mentioned in the description: the condition is at best "aceptable".
    wear_phrases: list[str] = []
    # Ordered: the first product whose alias matches (and no exclude word) wins.
    products: list[ReferenceProduct]
    # Fallback average price per category, used with lower confidence.
    categories: dict[str, Positive] = {}


# --- loaders --------------------------------------------------------------------


def _read_yaml(path: Path) -> Any:
    with path.open(encoding="utf-8") as file:
        return yaml.safe_load(file)


@lru_cache
def load_scoring_config(path: Path = SCORING_PATH) -> ScoringConfig:
    return ScoringConfig.model_validate(_read_yaml(path))


@lru_cache
def load_phrase_rules(path: Path = PHRASES_PATH) -> PhraseRules:
    return PhraseRules.model_validate(_read_yaml(path))


@lru_cache
def load_reference_prices(path: Path = REFERENCE_PRICES_PATH) -> ReferencePrices:
    return ReferencePrices.model_validate(_read_yaml(path))
