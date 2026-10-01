from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ImportPreviewResponse(BaseModel):
    file_name: str
    total_rows: int
    importable_rows: int
    skipped_rows: int
    skip_reasons: Dict[str, int]
    potential_duplicates: int
    columns_detected: List[str]
    suggested_mappings: Dict[str, str]
    unmapped_columns: List[str]
    sample_rows: List[Dict[str, Any]]
    warnings: List[str] = Field(default_factory=list)
    preview_token: str


class ImportConfirmOptions(BaseModel):
    default_client_type: Optional[str] = None
    default_lead_source: Optional[str] = "CSV Import"
    duplicate_handling: str = "skip"  # "skip" | "import"
    combine_unmapped_to_notes: bool = True
    pipeline_id: Optional[int] = None
    stage_id: Optional[int] = None


class ImportConfirmRequest(BaseModel):
    preview_token: str
    field_mappings: Dict[str, Optional[str]] = Field(default_factory=dict)
    options: ImportConfirmOptions = Field(default_factory=ImportConfirmOptions)


class ImportConfirmResponse(BaseModel):
    imported: int
    skipped_duplicates: int
    skipped_invalid: int
    total_processed: int
    import_id: str
    duration_seconds: float


class ImportHistoryItem(BaseModel):
    import_id: str
    user_id: Optional[int]
    user_name: Optional[str] = None
    file_name: str
    total_rows: int
    imported_count: int
    skipped_count: int
    duplicate_count: int
    duration_seconds: Optional[float]
    created_at: datetime
    undone_at: Optional[datetime]


class ImportHistoryResponse(BaseModel):
    items: List[ImportHistoryItem]
    total: int


class ImportUndoResponse(BaseModel):
    import_id: str
    soft_deleted: int
