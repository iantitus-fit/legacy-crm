from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

from app.schemas.pipeline_stage import PipelineStageResponse


class PipelineResponse(BaseModel):
    id: int
    name: str
    slug: str
    description: Optional[str] = None
    display_order: int

    model_config = {"from_attributes": True}


class PipelineListResponse(BaseModel):
    items: List[PipelineResponse]


class PipelineDetailResponse(PipelineResponse):
    stages: List[PipelineStageResponse]
