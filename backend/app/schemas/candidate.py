from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime
from uuid import UUID

class CandidateBase(BaseModel):
    name: str
    phone: str
    email: EmailStr

    class Config:
        from_attributes = True

class CandidateCreate(CandidateBase):
    pass

class CandidateInDB(CandidateBase):
    id: Optional[int] = None
    uuid: Optional[UUID] = None
    status: str
    current_question: int
    answers: str
    created_at: datetime
    updated_at: datetime
    disqualification_reason: Optional[str] = None
    communication_method: Optional[str] = None

    class Config:
        from_attributes = True

class CandidateResponse(BaseModel):
    status: str
    message: str
    data: CandidateInDB

    class Config:
        from_attributes = True

class CandidateQualification(BaseModel):
    status: str
    completed_questions: int    
    total_questions: int
    qualified: bool