from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Theme(StrictModel):
    id: str
    name: str
    description: str


class Taxonomy(StrictModel):
    themes: list[Theme]


class Classification(StrictModel):
    text_key: str
    sentiment: Literal['positive', 'neutral', 'negative', 'mixed']
    substantive: bool
    theme_id: str | None
    fee_issue: str | None
    fee_confusion_quote: str | None


class ClassificationBatch(StrictModel):
    items: list[Classification]


class QuoteChoice(StrictModel):
    review_key: str
    text: str


class FeeChoice(StrictModel):
    issue: str
    fee_name: str
    supporting_review_keys: list[str]
    supporting_excerpts: list[QuoteChoice]
    rationale: str


class EvidenceChoice(StrictModel):
    quotes: list[QuoteChoice]
    fee: FeeChoice


class PulseDraft(StrictModel):
    summary: str
    observation: str
    actions: list[str]


class FeeBullet(StrictModel):
    text: str
    source_ids: list[str]
    supporting_passages: list[str]


class ExplainerDraft(StrictModel):
    bullets: list[FeeBullet]


class FeeFactCheck(StrictModel):
    supported: bool = Field(description='True when every actual customer-facing bullet is factually supported by the sources.')
    concerns: list[str] = Field(description='Only factual errors or misleading omissions in actual bullet text; identify the bullet and offending claim. Empty if supported. Do not propose an alternative explainer.')


class Source(StrictModel):
    id: str
    title: str
    url: str
    checked_at: str
    text: str


class ReviewAssignment(StrictModel):
    review_key: str
    text_key: str
    sentiment: Literal['positive', 'neutral', 'negative', 'mixed']
    substantive: bool
    theme_id: str | None
    fee_issue: str | None


class ReviewIntelligence(StrictModel):
    """Phase 2 artifact. Contains no generated pulse, fee facts, or tool actions."""
    schema_version: int = 1
    run_id: str
    product: str = 'Groww'
    date: str
    dataset_sha256: str
    mode: Literal['openai_live'] = 'openai_live'
    model: str
    audit: dict
    themes: list[dict]
    sentiment_counts: dict[str, int]
    non_substantive_count: int
    quotes: list[dict]
    identified_fee_issue: str
    fee_name: str
    fee_rationale: str
    fee_evidence: list[dict]
    assignments: list[ReviewAssignment]
    checks: list[str] = Field(default_factory=list)


class Bundle(StrictModel):
    schema_version: int = 1
    run_id: str
    product: str = 'Groww'
    date: str
    dataset_sha256: str
    mode: Literal['openai_live', 'reference_preview']
    model: str
    intelligence_run_id: str = ''
    intelligence_fingerprint: str = ''
    fee_name: str = ''
    pulse_edited: bool = False
    audit: dict
    themes: list[dict]
    sentiment_counts: dict
    non_substantive_count: int
    quotes: list[dict]
    identified_fee_issue: str
    fee_evidence: list[dict]
    weekly_pulse: str
    explanation_bullets: list[str]
    source_links: list[str]
    sources: list[Source]
    last_checked: str
    fee_grounding: list[dict] = Field(default_factory=list)
    fee_fact_check: dict = Field(default_factory=dict)
    checks: list[str] = Field(default_factory=list)

    def entry(self) -> dict:
        return {key: value for key, value in {
            'date': self.date,
            'top_themes': [{key: theme[key] for key in ('id', 'name', 'count')} for theme in self.themes[:3]],
            'weekly_pulse': self.weekly_pulse,
            'identified_fee_issue': self.identified_fee_issue,
            'explanation_bullets': self.explanation_bullets,
            'source_links': self.source_links,
        }.items()}
