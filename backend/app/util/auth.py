from datetime import datetime, timedelta
from typing import Union
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.config import constants

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class AuthUtil:

    @classmethod
    def create_access_token(self, data: dict, expires_delta: timedelta):
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=15)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, constants.SECRET_KEY, algorithm=constants.ALGORITHM)
        return encoded_jwt

    @classmethod
    def verify_token(self, token: str, credentials_exception):
        try:
            payload = jwt.decode(token, constants.SECRET_KEY, algorithms=[constants.ALGORITHM])
            email: str = payload.get("sub")
            if email is None:
                raise credentials_exception
            return email
        except JWTError:
            raise credentials_exception

    @classmethod
    def verify_password(self, plain_password, hashed_password):
        return pwd_context.verify(plain_password, hashed_password)

    @classmethod
    def get_password_hash(self, password):
        return pwd_context.hash(password)
