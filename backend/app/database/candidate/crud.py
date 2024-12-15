from typing import Optional, List, Dict
from sqlalchemy.future import select
from app.database.config import async_session_maker
from .model import CandidateModel

class CandidateCRUD:
    @staticmethod
    async def create_candidate(candidate_data: Dict) -> CandidateModel:
        return await CandidateModel.create(**candidate_data)

    @staticmethod
    async def get_candidate_by_phone(phone: str) -> Optional[CandidateModel]:
        return await CandidateModel.get_by_phone(phone)

    @staticmethod
    async def get_candidate_by_email(email: str) -> Optional[CandidateModel]:
        return await CandidateModel.get_by_email(email)

    @staticmethod
    async def get_all_candidates() -> List[CandidateModel]:
        async with async_session_maker() as session:
            async with session.begin():
                query = select(CandidateModel)
                result = await session.execute(query)
                return result.scalars().all()

    @staticmethod
    async def get_candidates_by_status(status: str) -> List[CandidateModel]:
        async with async_session_maker() as session:
            async with session.begin():
                query = select(CandidateModel).where(CandidateModel.status == status)
                result = await session.execute(query)
                return result.scalars().all()

    @staticmethod
    async def update_candidate_status(candidate_id: int, status: str) -> Optional[CandidateModel]:
        async with async_session_maker() as session:
            query = select(CandidateModel).where(CandidateModel.id == candidate_id)
            result = await session.execute(query)
            candidate = result.scalar_one_or_none()
            
            if candidate:
                candidate.status = status
                session.add(candidate)
                await session.commit()
                
                # Create a new session for refresh
                async with async_session_maker() as refresh_session:
                    query = select(CandidateModel).where(CandidateModel.id == candidate_id)
                    result = await refresh_session.execute(query)
                    return result.scalar_one_or_none()
                    
            return None