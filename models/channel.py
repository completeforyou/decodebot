# models/channel.py
from sqlalchemy import Column, BigInteger, String
from .base import Base

class ApprovedChannel(Base):
    __tablename__ = 'approved_channels'
    
    # The Telegram Chat ID (usually starts with -100)
    channel_id = Column(BigInteger, primary_key=True)
    
    # A friendly name so admins know which channel is which
    channel_name = Column(String, nullable=False)