from typing import List, Optional

from pydantic import BaseModel


class PipelineStageCreate(BaseModel):
    pipeline_id: int
    name: str
    sort_order: int
    color: Optional[str] = None
    is_closed_won: bool = False
    is_closed_lost: bool = False


class PipelineStageUpdate(BaseModel):
    name: Optional[str] = None
    sort_order: Optional[int] = None
    color: Optional[str] = None
    is_closed_won: Optional[bool] = None
    is_closed_lost: Optional[bool] = None


class PipelineStageResponse(BaseModel):
    id: int
    pipeline_id: int
    name: str
    sort_order: int
    color: Optional[str] = None
    is_closed_won: bool
    is_closed_lost: bool

    model_config = {"from_attributes": True}


class PipelineStageListResponse(BaseModel):
    items: List[PipelineStageResponse]


class StageReorderItem(BaseModel):
    id: int
    sort_order: int


class StageReorderRequest(BaseModel):
    stages: List[StageReorderItem]
