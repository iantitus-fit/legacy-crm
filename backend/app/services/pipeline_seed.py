import logging
import os
import secrets

from sqlalchemy.orm import Session

from app.models.automation import AutomationSequence, AutomationStep
from app.models.pipeline import Pipeline
from app.models.pipeline_stage import PipelineStage
from app.models.user import User
from app.utils.auth import hash_password

logger = logging.getLogger("legacy_crm.seed")

DEFAULT_PIPELINES = [
    {
        "name": "Leads",
        "slug": "leads",
        "description": "Track incoming leads and inquiries",
        "display_order": 1,
        "stages": [
            {"name": "Cold Leads", "sort_order": 1, "color": "#3B82F6"},
            {"name": "Warm Leads", "sort_order": 2, "color": "#F59E0B"},
            {"name": "No Answer", "sort_order": 3, "color": "#6B7280"},
            {"name": "Angi Leads", "sort_order": 4, "color": "#10B981"},
            {"name": "Website Inquiry", "sort_order": 5, "color": "#8B5CF6"},
        ],
    },
    {
        "name": "Sales",
        "slug": "sales",
        "description": "Manage estimates and proposals",
        "display_order": 2,
        "stages": [
            {"name": "Draft", "sort_order": 1, "color": "#6B7280"},
            {"name": "Estimate Sent", "sort_order": 2, "color": "#3B82F6"},
            {"name": "Cold Proposals", "sort_order": 3, "color": "#93C5FD"},
            {"name": "Warm Proposals", "sort_order": 4, "color": "#F59E0B"},
            {"name": "Hot Proposals", "sort_order": 5, "color": "#EF4444"},
        ],
    },
    {
        "name": "Jobs",
        "slug": "jobs",
        "description": "Active jobs and scheduling",
        "display_order": 3,
        "stages": [
            {"name": "Pending Schedule", "sort_order": 1, "color": "#F59E0B"},
            {"name": "Scheduled", "sort_order": 2, "color": "#3B82F6"},
            {"name": "In Progress", "sort_order": 3, "color": "#10B981"},
            {"name": "Complete", "sort_order": 4, "color": "#22C55E"},
            {"name": "Warranty", "sort_order": 5, "color": "#8B5CF6"},
            {"name": "Closed", "sort_order": 6, "color": "#6B7280"},
        ],
    },
]


def seed_pipelines(db: Session) -> None:
    """Seed default pipelines, stages, and staff users if the pipelines table is empty."""
    count = db.query(Pipeline).count()
    if count > 0:
        return

    for pipeline_data in DEFAULT_PIPELINES:
        pipeline = Pipeline(
            name=pipeline_data["name"],
            slug=pipeline_data["slug"],
            description=pipeline_data["description"],
            display_order=pipeline_data["display_order"],
        )
        db.add(pipeline)
        db.flush()

        for stage_data in pipeline_data["stages"]:
            stage = PipelineStage(
                pipeline_id=pipeline.id,
                name=stage_data["name"],
                sort_order=stage_data["sort_order"],
                color=stage_data["color"],
            )
            db.add(stage)

    db.commit()

    # Seed Marcus user
    existing = db.query(User).filter(User.email == "marcus@legacy-roofing.example").first()
    if not existing:
        marcus = User(
            email="marcus@legacy-roofing.example",
            full_name="Marcus",
            # No default password in the repo: set SEED_STAFF_PASSWORD, or a random one is used.
            password_hash=hash_password(
                os.environ.get("SEED_STAFF_PASSWORD") or secrets.token_urlsafe(16)
            ),
            role="staff",
        )
        db.add(marcus)
        db.commit()


# ---------------------------------------------------------------------------
# Sprint 19d — pre-built automation sequences
# ---------------------------------------------------------------------------
DEFAULT_AUTOMATIONS = [
    {
        "name": "New Lead Nurture",
        "description": "7-day welcome + follow-up sequence for new leads.",
        "trigger_type": "contact_created",
        "trigger_config": {},
        "steps": [
            {
                "channel": "sms",
                "delay_minutes": 0,
                "template_body": (
                    "Hi {first_name}, this is {rep_name} with Legacy Roofing "
                    "& Exteriors. We received your request and would love to "
                    "help. Are you available for a free inspection? Just "
                    "reply with a good time or call us at {company_phone}."
                ),
                "stop_on_reply": True,
                "stop_on_stage_change": True,
            },
            {
                "channel": "sms",
                "delay_minutes": 2880,  # 2 days
                "template_body": (
                    "Hey {first_name}, just following up on your roofing "
                    "inquiry. We'd love to get you on the schedule for a "
                    "free inspection. What does your week look like?"
                ),
                "stop_on_reply": True,
                "stop_on_stage_change": True,
            },
            {
                "channel": "sms",
                "delay_minutes": 7200,  # 5 days
                "template_body": (
                    "Hi {first_name}, {rep_name} here from Legacy Roofing. "
                    "I know life gets busy — just wanted to check if you "
                    "still need help with your roof. We're happy to work "
                    "around your schedule."
                ),
                "stop_on_reply": True,
                "stop_on_stage_change": True,
            },
            {
                "channel": "email",
                "delay_minutes": 10080,  # 7 days
                "template_subject": (
                    "Still thinking about your roof, {first_name}?"
                ),
                "template_body": (
                    "<p>Hi {first_name},</p>"
                    "<p>It's {rep_name} from Legacy Roofing & Exteriors. I "
                    "wanted to reach out one more time about your roofing "
                    "project. We've been serving Kokomo and the surrounding "
                    "area for years, with hundreds of happy homeowners.</p>"
                    "<p>If you're still considering a roof inspection or "
                    "replacement, we'd love to help. Reply to this email "
                    "or call us at {company_phone} to schedule a free, "
                    "no-pressure inspection.</p>"
                    "<p>If you've already gone another direction, no worries "
                    "— we appreciate you considering us.</p>"
                    "<p>Best,<br/>{rep_name}<br/>"
                    "Legacy Roofing &amp; Exteriors<br/>{company_phone}</p>"
                ),
                "stop_on_reply": True,
                "stop_on_stage_change": False,
            },
        ],
    },
    {
        "name": "Estimate Follow-Up",
        "description": "10-day nudge sequence after an estimate is sent.",
        "trigger_type": "estimate_sent",
        "trigger_config": {},
        "steps": [
            {
                "channel": "sms",
                "delay_minutes": 2880,
                "template_body": (
                    "Hi {first_name}, just checking in. Did you have a "
                    "chance to review the estimate we sent? Happy to answer "
                    "any questions — just reply here or call "
                    "{company_phone}."
                ),
                "stop_on_reply": True,
                "stop_on_stage_change": True,
            },
            {
                "channel": "sms",
                "delay_minutes": 7200,
                "template_body": (
                    "Hey {first_name}, wanted to make sure you received "
                    "everything you need to make a decision. Our estimate "
                    "is good for 30 days. Any questions at all?"
                ),
                "stop_on_reply": True,
                "stop_on_stage_change": True,
            },
            {
                "channel": "sms",
                "delay_minutes": 14400,
                "template_body": (
                    "Hi {first_name}, {rep_name} from Legacy Roofing "
                    "checking in one last time on your estimate. If the "
                    "timing isn't right, no worries — we'll be here when "
                    "you're ready."
                ),
                "stop_on_reply": True,
                "stop_on_stage_change": True,
            },
        ],
    },
    {
        "name": "Cold Proposal Re-Engagement",
        "description": "Quarterly rehash for proposals that went cold.",
        "trigger_type": "pipeline_stage_change",
        # trigger_config.pipeline_slug + to_stage_id filled in at seed time.
        "_target_pipeline": "sales",
        "_target_stage": "Cold Proposals",
        "steps": [
            {
                "channel": "sms",
                "delay_minutes": 43200,  # 30 days
                "template_body": (
                    "Hi {first_name}, {rep_name} from Legacy Roofing. It's "
                    "been a while since we talked about your roofing "
                    "project. Anything changed? We'd love to help if you're "
                    "still considering it."
                ),
                "stop_on_reply": True,
                "stop_on_stage_change": True,
            },
            {
                "channel": "sms",
                "delay_minutes": 86400,  # 60 days
                "template_body": (
                    "Hey {first_name}, just a quick note from Legacy "
                    "Roofing. If your roof is still on your mind, we're "
                    "running a seasonal special. Want me to update your "
                    "estimate?"
                ),
                "stop_on_reply": True,
                "stop_on_stage_change": True,
            },
            {
                "channel": "email",
                "delay_minutes": 129600,  # 90 days
                "template_subject": "It's been a while, {first_name}",
                "template_body": (
                    "<p>Hi {first_name},</p>"
                    "<p>It's been a while since we talked about your "
                    "roofing project — I just wanted to check in.</p>"
                    "<p>A lot has changed in roofing materials and pricing "
                    "over the past few months. If you'd like, I'm happy to "
                    "put together a fresh estimate that reflects today's "
                    "options.</p>"
                    "<p>Either way, thanks for considering Legacy Roofing. "
                    "Reach out any time at {company_phone}.</p>"
                    "<p>Best,<br/>{rep_name}<br/>"
                    "Legacy Roofing &amp; Exteriors</p>"
                ),
                "stop_on_reply": True,
                "stop_on_stage_change": True,
            },
        ],
    },
    {
        "name": "Job Complete - Review Request",
        "description": "Post-completion ask for a Google review.",
        "trigger_type": "pipeline_stage_change",
        "_target_pipeline": "jobs",
        "_target_stage": "Complete",
        "steps": [
            {
                "channel": "sms",
                "delay_minutes": 1440,  # 1 day
                "template_body": (
                    "Hi {first_name}, {rep_name} from Legacy Roofing. Hope "
                    "you're loving the new roof! If you have a minute, "
                    "we'd really appreciate a review — it helps other "
                    "homeowners find us. {review_link}"
                ),
                "stop_on_reply": True,
                "stop_on_stage_change": False,
            },
            {
                "channel": "sms",
                "delay_minutes": 10080,  # 7 days
                "template_body": (
                    "Hey {first_name}, just a quick reminder — if you're "
                    "happy with the work we did, a Google review would "
                    "mean the world to us. {review_link} Thanks!"
                ),
                "stop_on_reply": True,
                "stop_on_stage_change": False,
            },
        ],
    },
    {
        "name": "1-Year Anniversary Check-In",
        "description": "365-day post-completion touchpoint.",
        "trigger_type": "pipeline_stage_change",
        "_target_pipeline": "jobs",
        "_target_stage": "Complete",
        "steps": [
            {
                "channel": "sms",
                "delay_minutes": 525600,  # 365 days
                "template_body": (
                    "Hi {first_name}, it's been a year since Legacy "
                    "Roofing completed your project! How's everything "
                    "holding up? If you ever need anything — maintenance, "
                    "inspections, or a referral for a neighbor — we're "
                    "just a text away."
                ),
                "stop_on_reply": True,
                "stop_on_stage_change": False,
            },
        ],
    },
]


def _resolve_stage_id(db: Session, pipeline_slug: str, stage_name: str):
    """Look up a stage by (pipeline_slug, stage_name). Returns id or None."""
    pipeline = (
        db.query(Pipeline).filter(Pipeline.slug == pipeline_slug).first()
    )
    if not pipeline:
        return None
    stage = (
        db.query(PipelineStage)
        .filter(
            PipelineStage.pipeline_id == pipeline.id,
            PipelineStage.name == stage_name,
        )
        .first()
    )
    return stage.id if stage else None


def seed_automations(db: Session) -> None:
    """Seed 5 default automation sequences if none exist.

    Idempotent: bails out when any AutomationSequence row is present, so
    re-running on a populated DB is a no-op and existing user-authored
    sequences aren't disturbed.

    Pipeline-stage triggers (`Cold Proposals`, `Complete`) resolve their
    target stage id by name. If the named stage doesn't exist (custom
    pipelines), the sequence is skipped with a log warning rather than
    raising.
    """
    if db.query(AutomationSequence).count() > 0:
        return

    for spec in DEFAULT_AUTOMATIONS:
        trigger_config = dict(spec.get("trigger_config") or {})
        target_pipeline = spec.get("_target_pipeline")
        target_stage = spec.get("_target_stage")
        if target_pipeline and target_stage:
            stage_id = _resolve_stage_id(db, target_pipeline, target_stage)
            if stage_id is None:
                logger.warning(
                    "seed_automations: skipping %s — could not resolve "
                    "stage %s in pipeline %s",
                    spec["name"],
                    target_stage,
                    target_pipeline,
                )
                continue
            trigger_config["pipeline_slug"] = target_pipeline
            trigger_config["to_stage_id"] = stage_id

        sequence = AutomationSequence(
            name=spec["name"],
            description=spec.get("description"),
            trigger_type=spec["trigger_type"],
            trigger_config=trigger_config,
            is_active=True,
        )
        db.add(sequence)
        db.flush()

        for idx, step_spec in enumerate(spec["steps"], start=1):
            step = AutomationStep(
                sequence_id=sequence.id,
                step_order=idx,
                channel=step_spec["channel"],
                delay_minutes=step_spec["delay_minutes"],
                template_body=step_spec["template_body"],
                template_subject=step_spec.get("template_subject"),
                stop_on_reply=step_spec.get("stop_on_reply", True),
                stop_on_stage_change=step_spec.get(
                    "stop_on_stage_change", True
                ),
                is_active=True,
            )
            db.add(step)

    db.commit()
    logger.info("seed_automations: created %d default sequences",
                db.query(AutomationSequence).count())
