from typing import List, Optional

from pydantic import BaseModel


class PipelineBreakdown(BaseModel):
    leads: int = 0
    sales: int = 0
    jobs: int = 0


class LeadSourceMetrics(BaseModel):
    source: str
    lead_count: int
    lead_percentage: float
    estimate_count: int
    approved_count: int
    close_rate: float
    total_contract_value: float
    avg_job_value: float
    total_invoiced: float
    total_collected: float
    avg_days_to_close: Optional[float] = None
    pipeline_breakdown: PipelineBreakdown


class UnattributedBucket(BaseModel):
    lead_count: int
    note: str
    lead_percentage: Optional[float] = None
    estimate_count: Optional[int] = None
    approved_count: Optional[int] = None
    close_rate: Optional[float] = None
    total_contract_value: Optional[float] = None
    avg_job_value: Optional[float] = None
    total_invoiced: Optional[float] = None
    total_collected: Optional[float] = None
    avg_days_to_close: Optional[float] = None
    pipeline_breakdown: Optional[PipelineBreakdown] = None


class LeadSourceReportResponse(BaseModel):
    period: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    total_leads: int
    total_revenue: float
    sources: List[LeadSourceMetrics]
    unattributed: UnattributedBucket


class LeadSourceSummaryItem(BaseModel):
    source: str
    lead_count: int
    close_rate: float
    avg_job_value: float


class LeadSourceSummaryResponse(BaseModel):
    period: str
    total_leads: int
    sources: List[LeadSourceSummaryItem]
