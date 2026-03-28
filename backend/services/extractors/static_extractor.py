"""
静态页面数据提取器
使用requests + BeautifulSoup提取静态HTML页面数据
"""
import requests
from bs4 import BeautifulSoup
import pandas as pd
from typing import Dict, Any, Optional, List
import logging
from .base import BaseExtractor

logger = logging.getLogger(__name__)


class StaticExtractor(BaseExtractor):
    """静态页面数据提取器 - 用于静态HTML页面"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.session = requests.Session()
        
        if config and 'headers' in config:
            self.session.headers.update(config['headers'])
        
        default_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        self.session.headers.update(default_headers)
    
    def extract(self, source_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        提取静态页面数据
        
        Args:
            source_config: {
                'url': str,
                'table_selector': str (表格CSS选择器),
                'wait_time': int (可选),
                'pagination': dict (可选)
            }
        """
        try:
            url = source_config['url']
            table_selector = source_config.get('table_selector', 'table')
            pagination = source_config.get('pagination')
            
            logger.info(f"提取静态页面: {url}")
            
            if pagination and pagination.get('enabled'):
                return self._extract_with_pagination(url, table_selector, pagination)
            else:
                return self._extract_single_page(url, table_selector)
                
        except Exception as e:
            logger.error(f"静态页面提取失败: {e}")
            return {
                'success': False,
                'data': None,
                'message': f'静态页面提取失败: {str(e)}',
                'metadata': {}
            }
    
    def _extract_single_page(self, url: str, table_selector: str) -> Dict[str, Any]:
        """提取单页数据"""
        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'lxml')
        table = soup.select_one(table_selector)
        
        if not table:
            return {
                'success': False,
                'data': None,
                'message': f'未找到表格: {table_selector}',
                'metadata': {}
            }
        
        df = self._parse_table(table)
        
        return {
            'success': True,
            'data': df,
            'message': f'成功提取{len(df)}行数据',
            'metadata': {
                'url': url,
                'status_code': response.status_code
            }
        }
    
    def _extract_with_pagination(
        self, 
        url: str, 
        table_selector: str, 
        pagination: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        提取分页数据
        
        Args:
            pagination: {
                'next_button_selector': str,
                'max_pages': int,
                'page_param': str (可选，URL参数分页)
            }
        """
        all_data = []
        current_page = 1
        max_pages = pagination.get('max_pages', 10)
        next_button_selector = pagination.get('next_button_selector')
        page_param = pagination.get('page_param')
        
        while current_page <= max_pages:
            logger.info(f"提取第{current_page}页...")
            
            if page_param:
                page_url = f"{url}?{page_param}={current_page}"
                response = self.session.get(page_url)
            else:
                response = self.session.get(url) if current_page == 1 else None
            
            if response:
                soup = BeautifulSoup(response.text, 'lxml')
                table = soup.select_one(table_selector)
                
                if table:
                    df = self._parse_table(table)
                    if len(df) > 0:
                        all_data.append(df)
                    else:
                        break
            
            if next_button_selector and not page_param:
                soup = BeautifulSoup(response.text, 'lxml')
                next_button = soup.select_one(next_button_selector)
                
                if not next_button or 'disabled' in next_button.get('class', []):
                    break
                
                next_link = next_button.get('href')
                if next_link:
                    url = next_link
                else:
                    break
            
            current_page += 1
        
        if all_data:
            final_df = pd.concat(all_data, ignore_index=True)
            return {
                'success': True,
                'data': final_df,
                'message': f'成功提取{len(final_df)}行数据，共{current_page-1}页',
                'metadata': {
                    'total_pages': current_page - 1,
                    'total_rows': len(final_df)
                }
            }
        else:
            return {
                'success': False,
                'data': None,
                'message': '未提取到任何数据',
                'metadata': {}
            }
    
    def _parse_table(self, table) -> pd.DataFrame:
        """解析HTML表格"""
        rows = table.find_all('tr')
        headers = []
        data = []
        
        for i, row in enumerate(rows):
            cells = row.find_all(['th', 'td'])
            row_data = [cell.get_text(strip=True) for cell in cells]
            
            if i == 0 and not headers:
                if row.find('th'):
                    headers = row_data
                else:
                    headers = [f'Column_{j}' for j in range(len(row_data))]
                    data.append(row_data)
            else:
                if row_data:
                    data.append(row_data)
        
        if not headers and data:
            headers = [f'Column_{j}' for j in range(len(data[0]))]
        
        return pd.DataFrame(data, columns=headers) if data else pd.DataFrame()
    
    def login(self, login_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        登录网站
        
        Args:
            login_config: {
                'login_url': str,
                'username': str,
                'password': str,
                'username_field': str,
                'password_field': str,
                'additional_fields': dict (可选)
            }
        """
        try:
            login_url = login_config['login_url']
            username = login_config['username']
            password = login_config['password']
            username_field = login_config.get('username_field', 'username')
            password_field = login_config.get('password_field', 'password')
            additional_fields = login_config.get('additional_fields', {})
            
            logger.info(f"登录网站: {login_url}")
            
            login_data = {
                username_field: username,
                password_field: password,
                **additional_fields
            }
            
            response = self.session.post(login_url, data=login_data, timeout=30)
            response.raise_for_status()
            
            cookies = dict(self.session.cookies)
            
            return {
                'success': True,
                'cookies': cookies,
                'message': '登录成功'
            }
            
        except Exception as e:
            logger.error(f"登录失败: {e}")
            return {
                'success': False,
                'cookies': None,
                'message': f'登录失败: {str(e)}'
            }
    
    def download_excel(
        self, 
        url: str, 
        save_path: str,
        cookies: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        下载Excel文件
        
        Args:
            url: 下载链接
            save_path: 保存路径
            cookies: Cookie字典
        """
        try:
            logger.info(f"下载Excel: {url}")
            
            if cookies:
                self.session.cookies.update(cookies)
            
            response = self.session.get(url, timeout=60)
            response.raise_for_status()
            
            with open(save_path, 'wb') as f:
                f.write(response.content)
            
            df = pd.read_excel(save_path)
            
            return {
                'success': True,
                'data': df,
                'file_path': save_path,
                'message': f'成功下载Excel，共{len(df)}行',
                'metadata': {
                    'file_size': len(response.content),
                    'url': url
                }
            }
            
        except Exception as e:
            logger.error(f"Excel下载失败: {e}")
            return {
                'success': False,
                'data': None,
                'message': f'Excel下载失败: {str(e)}',
                'metadata': {}
            }
    
    def close(self):
        """关闭Session"""
        if self.session:
            self.session.close()
            self.session = None
