"""
智能数据提取器
根据数据源类型自动选择最合适的提取方式
"""
import pandas as pd
from typing import Dict, Any, Optional, List
import logging
from .base import BaseExtractor
from .api_extractor import APIExtractor
from .static_extractor import StaticExtractor
from .playwright_extractor import PlaywrightExtractor

logger = logging.getLogger(__name__)


class UniversalExtractor(BaseExtractor):
    """
    智能数据提取器 - 根据场景自动选择最佳提取方式
    
    选择策略：
    1. API接口 → APIExtractor (最快、异步)
    2. 静态页面 → StaticExtractor (快速、轻量)
    3. 需要登录 → StaticExtractor + Session (轻量、稳定)
    4. JavaScript渲染 → PlaywrightExtractor (强大、跨平台)
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.extractors = {
            'api': APIExtractor(config),
            'static': StaticExtractor(config),
            'playwright': PlaywrightExtractor(config)
        }
        self.current_extractor = None
    
    def extract(self, source_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        智能提取数据
        
        Args:
            source_config: {
                'extraction_method': 'auto' | 'api' | 'static' | 'playwright',
                'fallback_method': str (可选),
                'api_url': str (API接口),
                'url': str (网页URL),
                'requires_js': bool (是否需要JavaScript渲染),
                'requires_login': bool (是否需要登录),
                ... 其他配置
            }
        """
        try:
            method = source_config.get('extraction_method', 'auto')
            fallback_method = source_config.get('fallback_method')
            
            if method == 'auto':
                method = self._detect_method(source_config)
            
            logger.info(f"使用提取方式: {method}")
            
            self.current_extractor = self.extractors[method]
            result = self.current_extractor.extract(source_config)
            
            if not result['success'] and fallback_method:
                logger.warning(f"{method}提取失败，尝试备选方案: {fallback_method}")
                self.current_extractor = self.extractors[fallback_method]
                result = self.current_extractor.extract(source_config)
            
            return result
            
        except Exception as e:
            logger.error(f"智能提取失败: {e}")
            return {
                'success': False,
                'data': None,
                'message': f'智能提取失败: {str(e)}',
                'metadata': {}
            }
    
    def _detect_method(self, source_config: Dict[str, Any]) -> str:
        """
        自动检测最佳提取方式
        
        优先级：
        1. 有api_url → api
        2. requires_js = True → playwright
        3. 其他 → static
        """
        if source_config.get('api_url'):
            return 'api'
        
        if source_config.get('requires_js'):
            return 'playwright'
        
        return 'static'
    
    def login(self, login_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        智能登录
        
        Args:
            login_config: {
                'login_method': 'auto' | 'session' | 'playwright',
                ... 其他配置
            }
        """
        try:
            login_method = login_config.get('login_method', 'auto')
            
            if login_method == 'auto':
                login_method = self._detect_login_method(login_config)
            
            logger.info(f"使用登录方式: {login_method}")
            
            if login_method == 'playwright':
                extractor = self.extractors['playwright']
            else:
                extractor = self.extractors['static']
            
            return extractor.login(login_config)
            
        except Exception as e:
            logger.error(f"登录失败: {e}")
            return {
                'success': False,
                'cookies': None,
                'message': f'登录失败: {str(e)}'
            }
    
    def _detect_login_method(self, login_config: Dict[str, Any]) -> str:
        """
        自动检测登录方式
        
        优先级：
        1. 有验证码或二维码 → playwright
        2. 简单表单登录 → static
        """
        login_type = login_config.get('login_type', 'password')
        
        if login_type in ['captcha', 'qrcode']:
            return 'playwright'
        
        return 'static'
    
    def extract_multiple(
        self, 
        sources: List[Dict[str, Any]], 
        parallel: bool = False
    ) -> List[Dict[str, Any]]:
        """
        批量提取多个数据源
        
        Args:
            sources: 数据源配置列表
            parallel: 是否并行提取
        """
        results = []
        
        for i, source in enumerate(sources):
            logger.info(f"提取数据源 {i+1}/{len(sources)}: {source.get('name', '未命名')}")
            result = self.extract(source)
            results.append(result)
        
        return results
    
    def merge_results(
        self, 
        results: List[Dict[str, Any]], 
        merge_type: str = 'vertical'
    ) -> Dict[str, Any]:
        """
        合并多个提取结果
        
        Args:
            results: 提取结果列表
            merge_type: 'vertical' (纵向合并) 或 'horizontal' (横向合并)
        """
        try:
            successful_results = [r for r in results if r['success'] and r['data'] is not None]
            
            if not successful_results:
                return {
                    'success': False,
                    'data': None,
                    'message': '没有成功的提取结果',
                    'metadata': {}
                }
            
            dfs = [r['data'] for r in successful_results]
            
            if merge_type == 'vertical':
                merged_df = pd.concat(dfs, ignore_index=True)
            else:
                merged_df = dfs[0]
                for df in dfs[1:]:
                    merged_df = pd.merge(merged_df, df, how='outer')
            
            return {
                'success': True,
                'data': merged_df,
                'message': f'成功合并{len(dfs)}个数据源，共{len(merged_df)}行',
                'metadata': {
                    'merged_sources': len(dfs),
                    'total_rows': len(merged_df)
                }
            }
            
        except Exception as e:
            logger.error(f"合并结果失败: {e}")
            return {
                'success': False,
                'data': None,
                'message': f'合并结果失败: {str(e)}',
                'metadata': {}
            }
    
    def close(self):
        """关闭所有提取器"""
        for extractor in self.extractors.values():
            extractor.close()


def create_extractor(
    method: str = 'auto', 
    config: Optional[Dict[str, Any]] = None
) -> BaseExtractor:
    """
    工厂函数：创建数据提取器
    
    Args:
        method: 'auto' | 'api' | 'static' | 'playwright'
        config: 配置字典
    
    Returns:
        数据提取器实例
    """
    if method == 'auto':
        return UniversalExtractor(config)
    elif method == 'api':
        return APIExtractor(config)
    elif method == 'static':
        return StaticExtractor(config)
    elif method == 'playwright':
        return PlaywrightExtractor(config)
    else:
        raise ValueError(f"不支持的提取方式: {method}")
