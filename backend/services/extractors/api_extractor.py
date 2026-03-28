"""
API数据提取器
使用httpx进行异步API调用
"""
import httpx
import pandas as pd
import asyncio
from typing import Dict, Any, Optional, List
import logging
from .base import BaseExtractor

logger = logging.getLogger(__name__)


class APIExtractor(BaseExtractor):
    """API数据提取器 - 用于RESTful API接口"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.client = None
    
    async def _init_client(self):
        """初始化异步客户端"""
        if not self.client:
            self.client = httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=True,
                headers=self.config.get('headers', {})
            )
    
    async def extract_async(self, source_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        异步提取API数据
        
        Args:
            source_config: {
                'api_url': str,
                'method': 'GET' or 'POST',
                'headers': dict,
                'params': dict,
                'data': dict,
                'data_key': str (数据在响应中的key)
            }
        """
        await self._init_client()
        
        try:
            api_url = source_config['api_url']
            method = source_config.get('method', 'GET').upper()
            headers = source_config.get('headers', {})
            params = source_config.get('params')
            data = source_config.get('data')
            data_key = source_config.get('data_key')
            
            logger.info(f"请求API: {method} {api_url}")
            
            if method == 'GET':
                response = await self.client.get(api_url, params=params, headers=headers)
            else:
                response = await self.client.post(api_url, json=data, params=params, headers=headers)
            
            response.raise_for_status()
            
            json_data = response.json()
            
            if data_key and data_key in json_data:
                json_data = json_data[data_key]
            
            if isinstance(json_data, list):
                df = pd.DataFrame(json_data)
            elif isinstance(json_data, dict):
                df = pd.DataFrame([json_data])
            else:
                return {
                    'success': False,
                    'data': None,
                    'message': f'不支持的JSON数据格式: {type(json_data)}',
                    'metadata': {}
                }
            
            return {
                'success': True,
                'data': df,
                'message': f'成功获取{len(df)}条数据',
                'metadata': {
                    'status_code': response.status_code,
                    'url': str(response.url),
                    'elapsed': response.elapsed.total_seconds()
                }
            }
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP错误: {e}")
            return {
                'success': False,
                'data': None,
                'message': f'HTTP错误: {e.response.status_code}',
                'metadata': {'status_code': e.response.status_code}
            }
        except Exception as e:
            logger.error(f"API提取失败: {e}")
            return {
                'success': False,
                'data': None,
                'message': f'API提取失败: {str(e)}',
                'metadata': {}
            }
    
    def extract(self, source_config: Dict[str, Any]) -> Dict[str, Any]:
        """同步提取API数据"""
        return asyncio.run(self.extract_async(source_config))
    
    async def extract_multiple_async(self, sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        批量异步提取多个API数据
        
        Args:
            sources: 数据源配置列表
        """
        await self._init_client()
        tasks = [self.extract_async(source) for source in sources]
        return await asyncio.gather(*tasks)
    
    def login(self, login_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        API登录（通常是获取Token）
        
        Args:
            login_config: {
                'login_url': str,
                'username': str,
                'password': str,
                'token_key': str (Token在响应中的key)
            }
        """
        async def _login():
            await self._init_client()
            
            try:
                login_url = login_config['login_url']
                username = login_config['username']
                password = login_config['password']
                token_key = login_config.get('token_key', 'token')
                
                response = await self.client.post(
                    login_url,
                    json={'username': username, 'password': password}
                )
                response.raise_for_status()
                
                data = response.json()
                token = data.get(token_key)
                
                if token:
                    self.client.headers['Authorization'] = f'Bearer {token}'
                    return {
                        'success': True,
                        'cookies': {'token': token},
                        'message': 'API登录成功'
                    }
                else:
                    return {
                        'success': False,
                        'cookies': None,
                        'message': f'响应中未找到{token_key}'
                    }
                    
            except Exception as e:
                logger.error(f"API登录失败: {e}")
                return {
                    'success': False,
                    'cookies': None,
                    'message': f'API登录失败: {str(e)}'
                }
        
        return asyncio.run(_login())
    
    async def close_async(self):
        """异步关闭客户端"""
        if self.client:
            await self.client.aclose()
            self.client = None
    
    def close(self):
        """关闭客户端"""
        if self.client:
            asyncio.run(self.close_async())
