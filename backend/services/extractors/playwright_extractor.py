"""
Playwright数据提取器
使用Playwright进行动态页面数据提取（Selenium的现代替代方案）
"""
from playwright.sync_api import sync_playwright, Page, Browser
import pandas as pd
from typing import Dict, Any, Optional, List
import logging
import time
from .base import BaseExtractor

logger = logging.getLogger(__name__)


class PlaywrightExtractor(BaseExtractor):
    """
    Playwright数据提取器 - 用于需要JavaScript渲染的动态页面
    
    优势：
    - 比Selenium快2-3倍
    - 原生支持ARM64架构
    - 自动等待和智能重试
    - 镜像体积小（~400MB vs Selenium ~1.2GB）
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.headless = config.get('headless', True) if config else True
    
    def _init_browser(self):
        """初始化浏览器"""
        if not self.browser:
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(headless=self.headless)
            self.page = self.browser.new_page()
            logger.info("Playwright浏览器初始化完成")
    
    def extract(self, source_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        提取动态页面数据
        
        Args:
            source_config: {
                'url': str,
                'table_selector': str,
                'wait_time': int (可选),
                'wait_for_selector': str (可选),
                'pagination': dict (可选),
                'actions': list (可选，执行的操作序列)
            }
        """
        try:
            self._init_browser()
            
            url = source_config['url']
            table_selector = source_config.get('table_selector', 'table')
            wait_time = source_config.get('wait_time', 2000)
            wait_for_selector = source_config.get('wait_for_selector')
            pagination = source_config.get('pagination')
            actions = source_config.get('actions', [])
            
            logger.info(f"Playwright提取: {url}")
            
            self.page.goto(url, wait_until='networkidle')
            
            if wait_for_selector:
                self.page.wait_for_selector(wait_for_selector, timeout=wait_time)
            else:
                self.page.wait_for_timeout(wait_time)
            
            for action in actions:
                self._execute_action(action)
            
            if pagination and pagination.get('enabled'):
                return self._extract_with_pagination(table_selector, pagination)
            else:
                return self._extract_single_page(table_selector)
                
        except Exception as e:
            logger.error(f"Playwright提取失败: {e}")
            return {
                'success': False,
                'data': None,
                'message': f'Playwright提取失败: {str(e)}',
                'metadata': {}
            }
    
    def _extract_single_page(self, table_selector: str) -> Dict[str, Any]:
        """提取单页数据"""
        try:
            table = self.page.query_selector(table_selector)
            
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
                    'url': self.page.url
                }
            }
            
        except Exception as e:
            logger.error(f"单页提取失败: {e}")
            return {
                'success': False,
                'data': None,
                'message': f'单页提取失败: {str(e)}',
                'metadata': {}
            }
    
    def _extract_with_pagination(
        self, 
        table_selector: str, 
        pagination: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        提取分页数据
        
        Args:
            pagination: {
                'next_button_selector': str,
                'max_pages': int,
                'wait_between_pages': int (毫秒)
            }
        """
        all_data = []
        current_page = 1
        max_pages = pagination.get('max_pages', 10)
        next_button_selector = pagination.get('next_button_selector')
        wait_between_pages = pagination.get('wait_between_pages', 1000)
        
        while current_page <= max_pages:
            logger.info(f"提取第{current_page}页...")
            
            table = self.page.query_selector(table_selector)
            if table:
                df = self._parse_table(table)
                if len(df) > 0:
                    all_data.append(df)
                else:
                    break
            
            if not next_button_selector:
                break
            
            next_button = self.page.query_selector(next_button_selector)
            if not next_button:
                break
            
            is_disabled = next_button.get_attribute('disabled')
            if is_disabled:
                break
            
            next_button.click()
            self.page.wait_for_timeout(wait_between_pages)
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
        rows = table.query_selector_all('tr')
        headers = []
        data = []
        
        for i, row in enumerate(rows):
            cells = row.query_selector_all('th, td')
            row_data = [cell.inner_text().strip() for cell in cells]
            
            if i == 0 and not headers:
                if row.query_selector('th'):
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
    
    def _execute_action(self, action: Dict[str, Any]):
        """
        执行页面操作
        
        Args:
            action: {
                'type': 'click' | 'fill' | 'select' | 'wait',
                'selector': str,
                'value': str (可选),
                'timeout': int (可选)
            }
        """
        action_type = action['type']
        selector = action['selector']
        value = action.get('value')
        timeout = action.get('timeout', 5000)
        
        if action_type == 'click':
            self.page.click(selector, timeout=timeout)
        elif action_type == 'fill':
            self.page.fill(selector, value, timeout=timeout)
        elif action_type == 'select':
            self.page.select_option(selector, value, timeout=timeout)
        elif action_type == 'wait':
            self.page.wait_for_selector(selector, timeout=timeout)
    
    def login(self, login_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        登录网站
        
        Args:
            login_config: {
                'url': str,
                'username': str,
                'password': str,
                'username_selector': str,
                'password_selector': str,
                'submit_selector': str,
                'success_selector': str,
                'wait_time': int (可选)
            }
        """
        try:
            self._init_browser()
            
            url = login_config['url']
            username = login_config['username']
            password = login_config['password']
            username_selector = login_config['username_selector']
            password_selector = login_config['password_selector']
            submit_selector = login_config['submit_selector']
            success_selector = login_config['success_selector']
            wait_time = login_config.get('wait_time', 5000)
            
            logger.info(f"Playwright登录: {url}")
            
            self.page.goto(url)
            
            self.page.fill(username_selector, username)
            self.page.fill(password_selector, password)
            self.page.click(submit_selector)
            
            self.page.wait_for_selector(success_selector, timeout=wait_time)
            
            cookies = self.page.context.cookies()
            cookies_dict = {cookie['name']: cookie['value'] for cookie in cookies}
            
            return {
                'success': True,
                'cookies': cookies_dict,
                'message': '登录成功'
            }
            
        except Exception as e:
            logger.error(f"登录失败: {e}")
            return {
                'success': False,
                'cookies': None,
                'message': f'登录失败: {str(e)}'
            }
    
    def screenshot(self, save_path: str, full_page: bool = False) -> str:
        """
        截图
        
        Args:
            save_path: 保存路径
            full_page: 是否全页面截图
        """
        if self.page:
            self.page.screenshot(path=save_path, full_page=full_page)
            return save_path
        return ""
    
    def close(self):
        """关闭浏览器"""
        if self.page:
            self.page.close()
            self.page = None
        
        if self.browser:
            self.browser.close()
            self.browser = None
        
        if self.playwright:
            self.playwright.stop()
            self.playwright = None
        
        logger.info("Playwright浏览器已关闭")
