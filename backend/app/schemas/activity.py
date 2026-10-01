from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ActivityEvent(BaseModel):
    type: str
    description: str
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    timestamp: datetime
    actor: Optional[str] = None
