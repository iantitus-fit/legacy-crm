from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class DocumentResponse(BaseModel):
    id: int
    job_id: Optional[int] = None
    contact_id: Optional[int] = None
    estimate_id: Optional[int] = None
    filename: str
    original_filename: str
    content_type: str
    file_size: int
    folder: str = "General"
    description: Optional[str] = None
    is_photo: bool = False
    show_in_work_order: bool = False
    show_in_estimate: bool = False
    uploaded_by: Optional[int] = None
    uploader_name: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    items: List[DocumentResponse]
    total: int


class DocumentUpdate(BaseModel):
    folder: Optional[str] = None
    description: Optional[str] = None
    is_photo: Optional[bool] = None
    show_in_work_order: Optional[bool] = None
    show_in_estimate: Optional[bool] = None


class FolderSummary(BaseModel):
    name: str
    file_count: int
    photo_count: int


class FolderListResponse(BaseModel):
    items: List[FolderSummary]
    total_files: int
