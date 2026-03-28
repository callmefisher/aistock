"""
数据提取器基类
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class BaseExtractor(ABC):
    """数据提取器基类"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.session = None
    
    @abstractmethod
    def extract(self, source_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        提取数据
        
        Args:
            source_config: 数据源配置
        
        Returns:
            {
                'success': bool,
                'data': DataFrame or None,
                'message': str,
                'metadata': dict
            }
        """
        pass
    
    @abstractmethod
    def login(self, login_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        登录
        
        Args:
            login_config: 登录配置
        
        Returns:
            {
                'success': bool,
                'cookies': dict or None,
                'message': str
            }
        """
        pass
    
    def close(self):
        """清理资源"""
        if self.session:
            self.session.close()
            self.session = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
