from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON, Float, LargeBinary, UniqueConstraint
from sqlalchemy.dialects.mysql import LONGBLOB
from sqlalchemy.sql import func
from core.database import Base


class DataSource(Base):
    __tablename__ = "data_sources"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, comment="数据源名称")
    website_url = Column(String(500), nullable=False, comment="网站URL")
    login_type = Column(String(50), nullable=False, comment="登录类型: password/captcha/qrcode/cookie")
    login_config = Column(JSON, comment="登录配置")
    data_format = Column(String(50), comment="数据格式: excel/table/api")
    extraction_config = Column(JSON, comment="数据提取配置")
    cookies = Column(Text, comment="Cookie数据")
    is_active = Column(Boolean, default=True, comment="是否启用")
    last_login_time = Column(DateTime, comment="最后登录时间")
    last_fetch_time = Column(DateTime, comment="最后抓取时间")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class Rule(Base):
    __tablename__ = "rules"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, comment="规则名称")
    description = Column(Text, comment="规则描述")
    natural_language = Column(Text, nullable=False, comment="自然语言规则")
    excel_formula = Column(Text, comment="转换后的Excel公式")
    filter_conditions = Column(JSON, comment="筛选条件")
    priority = Column(Integer, default=0, comment="优先级")
    is_active = Column(Boolean, default=True, comment="是否启用")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class Task(Base):
    __tablename__ = "tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, comment="任务名称")
    data_source_ids = Column(JSON, comment="数据源ID列表")
    rule_ids = Column(JSON, comment="规则ID列表")
    schedule_type = Column(String(50), default="manual", comment="调度类型: manual/cron/interval")
    schedule_config = Column(JSON, comment="调度配置")
    status = Column(String(50), default="pending", comment="任务状态: pending/running/completed/failed")
    last_run_time = Column(DateTime, comment="最后运行时间")
    next_run_time = Column(DateTime, comment="下次运行时间")
    is_active = Column(Boolean, default=True, comment="是否启用")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class ExecutionLog(Base):
    __tablename__ = "execution_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, nullable=False, index=True, comment="任务ID")
    status = Column(String(50), nullable=False, comment="执行状态")
    start_time = Column(DateTime, comment="开始时间")
    end_time = Column(DateTime, comment="结束时间")
    duration = Column(Float, comment="执行时长(秒)")
    records_processed = Column(Integer, comment="处理记录数")
    error_message = Column(Text, comment="错误信息")
    output_file = Column(String(500), comment="输出文件路径")
    details = Column(JSON, comment="执行详情")
    created_at = Column(DateTime, server_default=func.now())


class StockPool(Base):
    __tablename__ = "stock_pools"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, comment="选股池名称")
    task_id = Column(Integer, index=True, comment="生成任务ID")
    file_path = Column(String(500), comment="Excel文件路径")
    total_stocks = Column(Integer, comment="股票总数")
    data = Column(JSON, comment="股票数据")
    is_active = Column(Boolean, default=True, comment="是否启用")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class Workflow(Base):
    __tablename__ = "workflows"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, comment="工作流名称")
    description = Column(Text, comment="工作流描述")
    workflow_type = Column(String(50), default="", comment="工作流类型: 空/并购重组/融资/...")
    steps = Column(JSON, comment="工作流步骤配置")
    status = Column(String(50), default="active", comment="状态: active/inactive/running/completed/failed")
    last_run_time = Column(DateTime, comment="最后运行时间")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class BatchExecution(Base):
    __tablename__ = "batch_executions"

    id = Column(String(64), primary_key=True, comment="批次任务ID")
    workflow_ids = Column(JSON, nullable=False, comment="工作流ID列表")
    status = Column(String(20), default="pending", comment="状态: pending/running/completed/partial/failed/cancelled")
    total = Column(Integer, default=0, comment="总数")
    completed = Column(Integer, default=0, comment="已完成数")
    failed = Column(Integer, default=0, comment="失败数")
    results = Column(JSON, comment="各工作流执行结果详情")
    started_at = Column(DateTime, comment="开始时间")
    finished_at = Column(DateTime, comment="结束时间")
    created_by = Column(String(50), comment="创建者")
    created_at = Column(DateTime, server_default=func.now())


class WorkflowResult(Base):
    __tablename__ = "workflow_results"
    __table_args__ = (
        UniqueConstraint('workflow_id', 'date_str', 'step_type', name='uk_wf_date_step'),
    )

    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(Integer, nullable=False, index=True, comment="工作流ID")
    workflow_type = Column(String(50), default="", index=True, comment="工作流类型")
    workflow_name = Column(String(100), comment="工作流名称")
    date_str = Column(String(20), nullable=False, index=True, comment="数据日期")
    step_type = Column(String(50), default="final", comment="步骤类型")
    row_count = Column(Integer, default=0, comment="数据行数")
    columns_json = Column(JSON, comment="列名列表")
    data_compressed = Column(LONGBLOB, comment="zlib压缩的完整JSON数据")
    preview_json = Column(JSON, comment="前50行预览数据")
    file_size = Column(Integer, default=0, comment="原始文件大小")
    created_at = Column(DateTime, server_default=func.now())
