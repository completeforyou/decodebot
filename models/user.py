# models/user.py
from sqlalchemy import Column, BigInteger, String, Boolean, Integer, Date, ForeignKey, DateTime
from sqlalchemy.sql import func
from .base import Base

class User(Base):
    __tablename__ = 'users'
    
    user_id = Column(BigInteger, primary_key=True)
    username = Column(String)
    is_premium = Column(Boolean, default=False)
    trial_started_at = Column(DateTime, default=func.now())
    search_credits = Column(Integer, default=5)
    last_checkin = Column(Date, nullable=True)
    referred_by = Column(BigInteger, ForeignKey('users.user_id'), nullable=True)
    is_active = Column(Boolean, default=True)