import uuid
from uuid import UUID
from datetime import datetime
from typing import Any, Optional

from sqlmodel import SQLModel, Field
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy import event, Column, Integer, DateTime
from sqlalchemy.sql import func
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

class BaseModel(SQLModel):
    uuid: Optional[UUID] = Field(
        default_factory=uuid.uuid4, primary_key=True, index=True
    )
    __name__: str

    class Config:
        from_attributes = True

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if not hasattr(cls, "__tablename__"):
            cls.__tablename__ = cls.__name__.lower()

    async def save(self, db_session: AsyncSession):
        try:
            self.model_validate(self.model_dump())  # Validate the current instance
            # if not db_session.in_transaction():
            db_session.add(self)
            await db_session.commit()
        except (SQLAlchemyError, IntegrityError) as ex:
            await db_session.rollback()
            raise ex

    async def delete(self, db_session: AsyncSession):
        try:
            await db_session.delete(self)
            await db_session.commit()
        except SQLAlchemyError as ex:
            await db_session.rollback()
            raise ex

    async def update(self, db: AsyncSession, **kwargs):
        try:
            if not kwargs:
                return True

            updated_instance = self.model_copy(update=kwargs)
            updated_instance.model_validate(updated_instance.model_dump())

            for k, v in kwargs.items():
                setattr(self, k, v)

            await db.commit()
        except SQLAlchemyError as ex:
            await db.rollback()
            raise ex


class CreatedAtOnlyTimeStampMixin(SQLModel):
    created_at: datetime = Field(default_factory=datetime.now, nullable=False)


class TimeStampMixin(SQLModel):
    created_at: datetime = Field(default_factory=datetime.now, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.now, nullable=False)


# Register the event listener
@event.listens_for(TimeStampMixin, "before_update", propagate=True)
def timestamp_before_update(mapper, connection, target):
    target.updated_at = datetime.now()
