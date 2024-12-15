from datetime import datetime
from typing import Optional, Dict
from sqlmodel import Field
from app.database.base.model import BaseModel, TimeStampMixin
from sqlalchemy import select, func
from app.database.config import async_session_maker
import json
from uuid import UUID, uuid4

class CandidateModel(BaseModel, TimeStampMixin, table=True):
    __tablename__ = "candidates"

    id: Optional[int] = Field(default=None, primary_key=True, nullable=False)
    uuid: UUID = Field(default_factory=uuid4, nullable=False)  # Generate UUID automatically
    name: str = Field(nullable=False)
    phone: str = Field(nullable=False)
    email: str = Field(unique=True, index=True, nullable=False)
    status: str = Field(default="registered")
    current_question: int = Field(default=0)
    answers: str = Field(default='[]')  # Store answers as JSON string
    disqualification_reason: Optional[str] = Field(default=None)
    communication_method: Optional[str] = Field(default=None)

    class Config:
        from_attributes = True

    @classmethod
    async def create(cls, **kwargs) -> "CandidateModel":
        async with async_session_maker() as session:
            candidate = cls(**kwargs)
            session.add(candidate)
            await session.commit()
            await session.refresh(candidate)
            return candidate

    @classmethod
    async def get_by_phone(cls, phone: str) -> Optional["CandidateModel"]:
        # Normalize phone number by removing all non-digit and plus characters
        normalized_phone = ''.join(char for char in phone if char.isdigit() or char == '+')
        
        async with async_session_maker() as session:
            # Also normalize the stored phone numbers in the query
            query = select(cls).where(
                func.regexp_replace(cls.phone, '[^0-9+]', '', 'g') == normalized_phone
            )
            result = await session.execute(query)
            return result.scalar_one_or_none()

    @classmethod
    async def get_by_email(cls, email: str) -> Optional["CandidateModel"]:
        async with async_session_maker() as session:
            query = select(cls).where(cls.email == email)
            result = await session.execute(query)
            return result.scalar_one_or_none()

    async def save(self) -> None:
        async with async_session_maker() as session:
            session.add(self)
            await session.commit()
            await session.refresh(self)

    async def store_answer(self, question_number: int, answer: str) -> None:
        """Store candidate's answer as part of JSON string array"""
        try:
            # Parse current answers
            current_answers = json.loads(self.answers)
        except json.JSONDecodeError:
            current_answers = []
        
        # Add new answer
        current_answers.append({
            "question": question_number,
            "answer": answer,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Convert back to string
        self.answers = json.dumps(current_answers)
        await self.save()

    async def store_evaluation_scores(self, scores: Dict[str, float]) -> None:
        """Store AI evaluation scores"""
        try:
            current_answers = json.loads(self.answers)
            current_answers.append({
                "evaluation_scores": scores,
                "timestamp": datetime.utcnow().isoformat()
            })
            self.answers = json.dumps(current_answers)
            await self.save()
        except Exception as e:
            print(f"Error storing evaluation scores: {str(e)}")