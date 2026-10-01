from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel


class MaterialCreate(BaseModel):
    price_list_id: int
    item_number: str
    description: str
    unit_price: Decimal
    uom: Optional[str] = None
    category: str
    ocr_flag: Optional[str] = None


class MaterialUpdate(BaseModel):
    item_number: Optional[str] = None
    description: Optional[str] = None
    unit_price: Optional[Decimal] = None
    uom: Optional[str] = None
    category: Optional[str] = None
    ocr_flag: Optional[str] = None
    is_active: Optional[bool] = None


class MaterialResponse(BaseModel):
    id: int
    price_list_id: int
    item_number: str
    description: str
    unit_price: Decimal
    uom: Optional[str]
    category: str
    ocr_flag: Optional[str]
    is_active: bool
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    price_list_name: Optional[str] = None

    model_config = {"from_attributes": True}


class MaterialListResponse(BaseModel):
    items: List[MaterialResponse]
    total: int
    page: int
    per_page: int


class CategoryCount(BaseModel):
    category: str
    count: int


class MaterialImportResponse(BaseModel):
    price_lists_created: int
    materials_imported: int
    errors: List[str]
