# models/feature.py
from sqlalchemy import Column, String, Boolean
from .base import Base

class Feature(Base):
    __tablename__ = 'features'
    
    # The name of the feature (e.g., 'search', 'checkin')
    name = Column(String, primary_key=True)
    
    # Whether the feature is currently active
    is_active = Column(Boolean, default=True)