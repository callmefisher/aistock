from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from pydantic import BaseModel
from datetime import datetime
from ..core.database import get_async_db
from ..models.models import Rule
from ..api.auth import get_current_user
from ..models.models import User
from ..services.rule_engine import RuleEngine
from ..core.config import settings

router = APIRouter()


class RuleCreate(BaseModel):
    name: str
    description: str = None
    natural_language: str


class RuleUpdate(BaseModel):
    name: str = None
    description: str = None
    natural_language: str = None
    is_active: bool = None


class RuleResponse(BaseModel):
    id: int
    name: str
    description: str
    natural_language: str
    excel_formula: str = None
    filter_conditions: dict = None
    priority: int
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


@router.post("/", response_model=RuleResponse)
async def create_rule(
    rule: RuleCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    rule_engine = RuleEngine(
        openai_api_key=settings.OPENAI_API_KEY,
        openai_api_base=settings.OPENAI_API_BASE
    )
    
    parse_result = rule_engine.parse_natural_language(rule.natural_language)
    
    db_rule = Rule(
        name=rule.name,
        description=rule.description,
        natural_language=rule.natural_language,
        excel_formula=parse_result['result'].get('excel_formula') if parse_result['success'] else None,
        filter_conditions=parse_result['result'].get('filter_conditions') if parse_result['success'] else None
    )
    
    db.add(db_rule)
    await db.commit()
    await db.refresh(db_rule)
    return db_rule


@router.get("/", response_model=List[RuleResponse])
async def list_rules(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(Rule).offset(skip).limit(limit)
    )
    return result.scalars().all()


@router.get("/{rule_id}", response_model=RuleResponse)
async def get_rule(
    rule_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(select(Rule).where(Rule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")
    return rule


@router.put("/{rule_id}", response_model=RuleResponse)
async def update_rule(
    rule_id: int,
    rule_update: RuleUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(select(Rule).where(Rule.id == rule_id))
    db_rule = result.scalar_one_or_none()
    
    if not db_rule:
        raise HTTPException(status_code=404, detail="规则不存在")
    
    update_data = rule_update.dict(exclude_unset=True)
    
    if 'natural_language' in update_data:
        rule_engine = RuleEngine(
            openai_api_key=settings.OPENAI_API_KEY,
            openai_api_base=settings.OPENAI_API_BASE
        )
        parse_result = rule_engine.parse_natural_language(update_data['natural_language'])
        if parse_result['success']:
            update_data['excel_formula'] = parse_result['result'].get('excel_formula')
            update_data['filter_conditions'] = parse_result['result'].get('filter_conditions')
    
    for field, value in update_data.items():
        setattr(db_rule, field, value)
    
    await db.commit()
    await db.refresh(db_rule)
    return db_rule


@router.delete("/{rule_id}")
async def delete_rule(
    rule_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(select(Rule).where(Rule.id == rule_id))
    db_rule = result.scalar_one_or_none()
    
    if not db_rule:
        raise HTTPException(status_code=404, detail="规则不存在")
    
    await db.delete(db_rule)
    await db.commit()
    return {"message": "规则已删除"}


@router.post("/{rule_id}/validate")
async def validate_rule(
    rule_id: int,
    columns: List[str],
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(select(Rule).where(Rule.id == rule_id))
    rule = result.scalar_one_or_none()
    
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")
    
    rule_engine = RuleEngine()
    validation = rule_engine.validate_rules(rule.filter_conditions or [], columns)
    
    return validation
