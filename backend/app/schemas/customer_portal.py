from typing import Optional

from pydantic import BaseModel


class ChangeRequestBody(BaseModel):
    message: str


class RejectBody(BaseModel):
    name: str
    reason: Optional[str] = None


class ApproveBody(BaseModel):
    signer_name: str
    signature_data: str
    terms_accepted: bool
