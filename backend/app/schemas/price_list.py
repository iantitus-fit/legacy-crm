from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel


class PriceListCreate(BaseModel):
    name: str
    source_file: Optional[str] = None
    effective_date: Optional[date] = None
    expiration_date: Optional[date] = None


class PriceListUpdate(BaseModel):
    name: Optional[str] = None
    effective_date: Optional[date] = None
    expiration_date: Optional[date] = None


class PriceListResponse(BaseModel):
    id: int
    name: str
    source_file: Optional[str]
    effective_date: Optional[date]
    expiration_date: Optional[date]
    imported_at: Optional[datetime]
    imported_by_user_id: Optional[int]
    material_count: int = 0

    model_config = {"from_attributes": True}


class PriceListListResponse(BaseModel):
    items: List[PriceListResponse]
    total: int
