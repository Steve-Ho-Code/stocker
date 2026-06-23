from sqlalchemy import Column, Integer, String, Boolean, BigInteger

from .database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(BigInteger, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True)
    is_admin = Column(Boolean, default=False)
