"""Sprint 19d — seed_automations tests.

Verifies that the 5 pre-built sequences land correctly, the function is
idempotent on rerun, and pipeline-stage triggers resolve their target
stage IDs by name when the pipelines exist.
"""
import pytest

from app.models.automation import AutomationSequence, AutomationStep
from app.models.pipeline import Pipeline
from app.models.pipeline_stage import PipelineStage
from app.services.pipeline_seed import (
    DEFAULT_AUTOMATIONS,
    seed_automations,
    seed_pipelines,
)


@pytest.fixture()
def pipelines(db_session):
    seed_pipelines(db_session)
    return db_session


def test_seed_creates_five_sequences(db_session, pipelines):
    seed_automations(db_session)
    sequences = (
        db_session.query(AutomationSequence)
        .order_by(AutomationSequence.id)
        .all()
    )
    names = [s.name for s in sequences]
    assert names == [
        "New Lead Nurture",
        "Estimate Follow-Up",
        "Cold Proposal Re-Engagement",
        "Job Complete - Review Request",
        "1-Year Anniversary Check-In",
    ]
    for seq in sequences:
        assert seq.is_active is True


def test_seed_is_idempotent(db_session, pipelines):
    seed_automations(db_session)
    first_count = db_session.query(AutomationSequence).count()
    seed_automations(db_session)
    second_count = db_session.query(AutomationSequence).count()
    assert first_count == second_count == 5


def test_cold_proposal_resolves_stage_id(db_session, pipelines):
    seed_automations(db_session)
    seq = (
        db_session.query(AutomationSequence)
        .filter(AutomationSequence.name == "Cold Proposal Re-Engagement")
        .first()
    )
    cold_stage = (
        db_session.query(PipelineStage)
        .join(Pipeline)
        .filter(Pipeline.slug == "sales", PipelineStage.name == "Cold Proposals")
        .first()
    )
    assert seq.trigger_type == "pipeline_stage_change"
    assert seq.trigger_config["pipeline_slug"] == "sales"
    assert seq.trigger_config["to_stage_id"] == cold_stage.id


def test_job_complete_sequences_resolve_stage_id(db_session, pipelines):
    seed_automations(db_session)
    complete_stage = (
        db_session.query(PipelineStage)
        .join(Pipeline)
        .filter(Pipeline.slug == "jobs", PipelineStage.name == "Complete")
        .first()
    )
    review = (
        db_session.query(AutomationSequence)
        .filter(AutomationSequence.name == "Job Complete - Review Request")
        .first()
    )
    anniversary = (
        db_session.query(AutomationSequence)
        .filter(AutomationSequence.name == "1-Year Anniversary Check-In")
        .first()
    )
    for seq in (review, anniversary):
        assert seq.trigger_type == "pipeline_stage_change"
        assert seq.trigger_config["pipeline_slug"] == "jobs"
        assert seq.trigger_config["to_stage_id"] == complete_stage.id


def test_seed_skips_sequences_with_missing_stages(db_session, caplog):
    # No pipelines exist — Cold Proposals + Complete cannot resolve.
    seed_automations(db_session)
    sequences = db_session.query(AutomationSequence).all()
    # The two stage-triggered ones should be skipped; we keep only the
    # three with empty trigger_config (contact_created, estimate_sent, and
    # neither of the job-complete sequences).
    names = {s.name for s in sequences}
    assert "New Lead Nurture" in names
    assert "Estimate Follow-Up" in names
    assert "Cold Proposal Re-Engagement" not in names
    assert "Job Complete - Review Request" not in names
    assert "1-Year Anniversary Check-In" not in names


def test_step_counts_per_sequence(db_session, pipelines):
    seed_automations(db_session)
    expected = {
        "New Lead Nurture": 4,
        "Estimate Follow-Up": 3,
        "Cold Proposal Re-Engagement": 3,
        "Job Complete - Review Request": 2,
        "1-Year Anniversary Check-In": 1,
    }
    for name, count in expected.items():
        seq = (
            db_session.query(AutomationSequence)
            .filter(AutomationSequence.name == name)
            .first()
        )
        assert seq is not None
        assert len(seq.steps) == count


def test_new_lead_step_one_contains_expected_tokens(db_session, pipelines):
    seed_automations(db_session)
    seq = (
        db_session.query(AutomationSequence)
        .filter(AutomationSequence.name == "New Lead Nurture")
        .first()
    )
    step1 = sorted(seq.steps, key=lambda s: s.step_order)[0]
    assert step1.channel == "sms"
    assert step1.delay_minutes == 0
    assert "{first_name}" in step1.template_body
    assert "{rep_name}" in step1.template_body
    assert "{company_phone}" in step1.template_body


def test_email_steps_have_subjects(db_session, pipelines):
    seed_automations(db_session)
    email_steps = (
        db_session.query(AutomationStep)
        .filter(AutomationStep.channel == "email")
        .all()
    )
    # Sequences 1 and 3 each include one email step → 2 total.
    assert len(email_steps) == 2
    for step in email_steps:
        assert step.template_subject
        assert "{first_name}" in step.template_subject


def test_default_automations_constants_unchanged():
    """Smoke check on the module-level DEFAULT_AUTOMATIONS list — five
    entries, in the documented order."""
    names = [d["name"] for d in DEFAULT_AUTOMATIONS]
    assert names == [
        "New Lead Nurture",
        "Estimate Follow-Up",
        "Cold Proposal Re-Engagement",
        "Job Complete - Review Request",
        "1-Year Anniversary Check-In",
    ]
