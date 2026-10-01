from typing import Optional

from pydantic import BaseModel


class COApproveBody(BaseModel):
    signer_name: str
    signature_data: str
    terms_accepted: bool


class CORejectBody(BaseModel):
    name: Optional[str] = None
    reason: Optional[str] = None


class COChangeRequestBody(BaseModel):
    message: str


class COSendRequest(BaseModel):
    to_email: str
    subject: Optional[str] = None
    message: Optional[str] = None
