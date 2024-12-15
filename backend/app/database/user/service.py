from typing import Optional
from uuid import UUID
from sqlmodel import select
from sqlalchemy import desc
from sqlalchemy.exc import NoResultFound

from app.database.base.service import BaseService
from app.util import AuthUtil
from .model import UserModel


class UserService(BaseService):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def add_user(self, user: UserModel):
        user.password = AuthUtil.get_password_hash(user.password)
        await user.save(db_session=self.db_session)
        return user
    
    async def get_users(self, uuid: Optional[UUID] = None):
        statement = select(UserModel)
        if uuid is not None:
            statement = statement.where(UserModel.uuid == uuid)

        try:
            results = await self.db_session.exec(statement)
            return results.all()
        except NoResultFound:
            return []
    
    async def update_user(self, user: UserModel):
        try:
            self.db_session.add(user)
            self.db_session.commit()
            self.db_session.refresh(user)
            return True
        except NoResultFound:
            return False
    
    async def delete_user(self, user_id: UUID):
        try:
            statement = select(UserModel).where(UserModel.uuid == user_id)
            result = await self.db_session.exec(statement)
            user = result.one()

            await self.db_session.delete(user)
            await self.db_session.commit()
            return True
        except NoResultFound:
            return False
        
    async def verify_user(self, email: str, password: str):
        statement = select(UserModel).where(UserModel.email == email)
        result = await self.db_session.exec(statement)
        user = result.first()
        
        if not user or not AuthUtil.verify_password(password, user.password):
            return False
        return user
