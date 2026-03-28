from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ThreadPoolExecutor
from typing import Dict, Optional, Any, Callable
import logging
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)


class TaskScheduler:
    def __init__(self, database_url: str):
        jobstores = {
            'default': SQLAlchemyJobStore(url=database_url)
        }
        executors = {
            'default': ThreadPoolExecutor(20)
        }
        job_defaults = {
            'coalesce': False,
            'max_instances': 3
        }
        
        self.scheduler = AsyncIOScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults
        )
        self.jobs = {}
    
    def start(self):
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("任务调度器已启动")
    
    def shutdown(self):
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("任务调度器已关闭")
    
    def add_cron_job(
        self,
        job_id: str,
        func: Callable,
        cron_expression: str,
        **kwargs
    ) -> Dict[str, Any]:
        try:
            parts = cron_expression.split()
            if len(parts) == 5:
                minute, hour, day, month, day_of_week = parts
            else:
                return {
                    "success": False,
                    "message": "Cron表达式格式错误，应为5位：分 时 日 月 周"
                }
            
            trigger = CronTrigger(
                minute=minute,
                hour=hour,
                day=day,
                month=month,
                day_of_week=day_of_week
            )
            
            self.scheduler.add_job(
                func,
                trigger=trigger,
                id=job_id,
                kwargs=kwargs,
                replace_existing=True
            )
            
            return {
                "success": True,
                "job_id": job_id,
                "message": f"成功添加定时任务：{job_id}"
            }
        except Exception as e:
            logger.error(f"添加定时任务失败: {str(e)}")
            return {
                "success": False,
                "message": f"添加定时任务失败: {str(e)}"
            }
    
    def add_interval_job(
        self,
        job_id: str,
        func: Callable,
        interval_seconds: int,
        **kwargs
    ) -> Dict[str, Any]:
        try:
            trigger = IntervalTrigger(seconds=interval_seconds)
            
            self.scheduler.add_job(
                func,
                trigger=trigger,
                id=job_id,
                kwargs=kwargs,
                replace_existing=True
            )
            
            return {
                "success": True,
                "job_id": job_id,
                "message": f"成功添加间隔任务：{job_id}，间隔{interval_seconds}秒"
            }
        except Exception as e:
            logger.error(f"添加间隔任务失败: {str(e)}")
            return {
                "success": False,
                "message": f"添加间隔任务失败: {str(e)}"
            }
    
    def add_one_time_job(
        self,
        job_id: str,
        func: Callable,
        run_date: datetime,
        **kwargs
    ) -> Dict[str, Any]:
        try:
            from apscheduler.triggers.date import DateTrigger
            
            trigger = DateTrigger(run_date=run_date)
            
            self.scheduler.add_job(
                func,
                trigger=trigger,
                id=job_id,
                kwargs=kwargs,
                replace_existing=True
            )
            
            return {
                "success": True,
                "job_id": job_id,
                "message": f"成功添加一次性任务：{job_id}，执行时间：{run_date}"
            }
        except Exception as e:
            logger.error(f"添加一次性任务失败: {str(e)}")
            return {
                "success": False,
                "message": f"添加一次性任务失败: {str(e)}"
            }
    
    def remove_job(self, job_id: str) -> Dict[str, Any]:
        try:
            self.scheduler.remove_job(job_id)
            return {
                "success": True,
                "message": f"成功移除任务：{job_id}"
            }
        except Exception as e:
            logger.error(f"移除任务失败: {str(e)}")
            return {
                "success": False,
                "message": f"移除任务失败: {str(e)}"
            }
    
    def pause_job(self, job_id: str) -> Dict[str, Any]:
        try:
            self.scheduler.pause_job(job_id)
            return {
                "success": True,
                "message": f"成功暂停任务：{job_id}"
            }
        except Exception as e:
            logger.error(f"暂停任务失败: {str(e)}")
            return {
                "success": False,
                "message": f"暂停任务失败: {str(e)}"
            }
    
    def resume_job(self, job_id: str) -> Dict[str, Any]:
        try:
            self.scheduler.resume_job(job_id)
            return {
                "success": True,
                "message": f"成功恢复任务：{job_id}"
            }
        except Exception as e:
            logger.error(f"恢复任务失败: {str(e)}")
            return {
                "success": False,
                "message": f"恢复任务失败: {str(e)}"
            }
    
    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        try:
            job = self.scheduler.get_job(job_id)
            if job:
                return {
                    "id": job.id,
                    "func": str(job.func),
                    "trigger": str(job.trigger),
                    "next_run_time": job.next_run_time,
                    "pending": job.pending
                }
            return None
        except Exception as e:
            logger.error(f"获取任务失败: {str(e)}")
            return None
    
    def get_all_jobs(self) -> list:
        try:
            jobs = self.scheduler.get_jobs()
            return [
                {
                    "id": job.id,
                    "func": str(job.func),
                    "trigger": str(job.trigger),
                    "next_run_time": job.next_run_time,
                    "pending": job.pending
                }
                for job in jobs
            ]
        except Exception as e:
            logger.error(f"获取所有任务失败: {str(e)}")
            return []
    
    def run_job_now(self, job_id: str) -> Dict[str, Any]:
        try:
            job = self.scheduler.get_job(job_id)
            if job:
                job.modify(next_run_time=datetime.now())
                return {
                    "success": True,
                    "message": f"任务 {job_id} 已触发立即执行"
                }
            else:
                return {
                    "success": False,
                    "message": f"任务 {job_id} 不存在"
                }
        except Exception as e:
            logger.error(f"立即执行任务失败: {str(e)}")
            return {
                "success": False,
                "message": f"立即执行任务失败: {str(e)}"
            }
