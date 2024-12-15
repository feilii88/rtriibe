from typing import Optional
from sqlmodel import Field
from app.database.base.model import BaseModel, TimeStampMixin


class UserModel(BaseModel, TimeStampMixin, table=True):
    """
    Represents a user in the database.

    Attributes:

        id: Primary key for the user.

        name: The name of the user.

        email: The email of the user.

        role: The role of the user.

        password: The password of the user.

    """

    __tablename__ = "users"
 
    name: Optional[str] = Field(default=None)
    email: Optional[str] = Field(default=None)
    role: Optional[str] = Field(default=None)
    password: Optional[str] = Field(default=None)

class UserCreate(BaseModel):
    name: str
    email: str  # This ensures that the email is correctly formatted
    role: str
    password: str

class UserUpdate(BaseModel):
    name: Optional[str]
    email: Optional[str]
    role: Optional[str]
    password: Optional[str]