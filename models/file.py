# models/file.py
from sqlalchemy import Column, Integer, BigInteger, String, Text, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import ARRAY
from .base import Base

class File(Base):
    __tablename__ = 'files'
    
    code = Column(String, primary_key=True)
    message_id = Column(Integer, nullable=False)
    channel_id = Column(BigInteger, nullable=False)
    tags = Column(ARRAY(String), default=[])
    caption = Column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint('message_id', 'channel_id', name='uq_message_channel'),
        # Replicates the GIN index from your raw SQL for fast fuzzy searching
        Index('files_caption_trgm_idx', 'caption', postgresql_using='gin', postgresql_ops={'caption': 'gin_trgm_ops'}),
    )