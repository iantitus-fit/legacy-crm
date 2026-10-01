from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel


class RecentJobResponse(BaseModel):
    id: int
    contact_id: Optional[int] = None
    contact_name: Optional[str] = None
    property_address: Optional[str] = None
    stage_name: Optional[str] = None
    pipeline_name: Optional[str] = None
    work_type: Optional[str] = None
    contract_value: Optional[Decimal] = None
    created_at: datetime


class TaskDueResponse(BaseModel):
    id: int
    title: str
    due_date: Optional[date] = None
    job_id: Optional[int] = None
    job_address: Optional[str] = None
    is_overdue: bool = False
    assigned_to_user_id: Optional[int] = None
    assigned_to_name: Optional[str] = None


class EmployeeTaskCount(BaseModel):
    user_id: int
    full_name: str
    open_count: int
    due_today_count: int


class OpenInvoiceResponse(BaseModel):
    id: int
    invoice_number: str
    contact_name: Optional[str] = None
    total: Decimal
    balance: Decimal
    due_date: Optional[date] = None
    status: str


class DashboardStatsResponse(BaseModel):
    new_leads_count: int
    active_proposals_count: int
    jobs_in_progress_count: int
    contact_count: int
    open_tasks: int
    pipeline_value: Decimal
    overdue_task_count: int
    recent_jobs: List[RecentJobResponse]
    tasks_due_today: List[TaskDueResponse]
    tasks_due_this_week: List[TaskDueResponse]
    tasks_past_due: List[TaskDueResponse] = []
    tasks_today: List[TaskDueResponse] = []
    tasks_future: List[TaskDueResponse] = []
    my_tasks_today: List[TaskDueResponse] = []
    employee_task_counts: List[EmployeeTaskCount] = []
    upcoming_this_week: list = []
    open_invoices: List[OpenInvoiceResponse] = []
    # Sprint 15c — new-model counts alongside the legacy job-based ones
    new_leads_count_v2: int = 0
    active_proposals_count_v2: int = 0
    jobs_in_progress_count_v2: int = 0
    pipeline_value_v2: Decimal = Decimal("0")
