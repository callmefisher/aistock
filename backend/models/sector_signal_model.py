"""板块信号榜持久化模型（独立文件，不影响 models.py）。"""
from sqlalchemy import Column, Integer, String, DateTime, JSON
from sqlalchemy.sql import func
from core.database import Base


class SectorSignal(Base):
    """一天一行：全量板块分 + 两榜 Top N + 权重快照。"""
    __tablename__ = "sector_signal"

    id = Column(Integer, primary_key=True, index=True)
    date_str = Column(String(10), nullable=False, unique=True, index=True, comment="YYYY-MM-DD")

    source_file = Column(String(500), nullable=False, comment="源 public Excel 路径")
    source_mtime = Column(DateTime, nullable=True, comment="源文件 mtime，mtime 失效策略预留")

    sector_count = Column(Integer, nullable=False, comment="有效板块总数 N")
    window_long_days = Column(Integer, nullable=False, comment="实际长窗口天数")
    window_recent_days = Column(Integer, nullable=False, comment="实际短窗口天数")

    all_sectors = Column(JSON, nullable=False, comment="全量板块分")
    top_strong = Column(JSON, nullable=False, comment="持续强势榜 Top 30")
    top_reversal = Column(JSON, nullable=False, comment="低位启动榜 Top 30")

    config_snapshot = Column(JSON, nullable=False, comment="当时生效的权重/窗口/阈值")

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
