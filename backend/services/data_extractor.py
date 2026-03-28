import pandas as pd
import os
from typing import Dict, List, Optional, Any
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import requests
import json
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


class DataExtractor:
    def __init__(self, driver: Optional[webdriver.Chrome] = None):
        self.driver = driver
    
    def extract_from_table(
        self,
        url: str,
        table_selector: str,
        wait_time: int = 10,
        cookies: Optional[list] = None
    ) -> Dict[str, Any]:
        try:
            if not self.driver:
                return {
                    "success": False,
                    "data": None,
                    "message": "Driver未初始化"
                }
            
            self.driver.get(url)
            
            if cookies:
                for cookie in cookies:
                    self.driver.add_cookie(cookie)
                self.driver.get(url)
            
            wait = WebDriverWait(self.driver, wait_time)
            table = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, table_selector))
            )
            
            rows = table.find_elements(By.TAG_NAME, "tr")
            data = []
            headers = []
            
            for i, row in enumerate(rows):
                cells = row.find_elements(By.TAG_NAME, "th" if i == 0 else "td")
                row_data = [cell.text.strip() for cell in cells]
                
                if i == 0 and not headers:
                    headers = row_data
                else:
                    if row_data:
                        data.append(row_data)
            
            if not headers and data:
                headers = [f"Column_{i}" for i in range(len(data[0]))]
            
            df = pd.DataFrame(data, columns=headers)
            
            return {
                "success": True,
                "data": df,
                "message": f"成功提取{len(df)}行数据"
            }
        except Exception as e:
            logger.error(f"表格提取失败: {str(e)}")
            return {
                "success": False,
                "data": None,
                "message": f"表格提取失败: {str(e)}"
            }
    
    def download_excel(
        self,
        url: str,
        save_path: str,
        cookies: Optional[dict] = None
    ) -> Dict[str, Any]:
        try:
            headers = {}
            if cookies:
                headers['Cookie'] = '; '.join([f"{c['name']}={c['value']}" for c in cookies])
            
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            with open(save_path, 'wb') as f:
                f.write(response.content)
            
            df = pd.read_excel(save_path)
            
            return {
                "success": True,
                "data": df,
                "file_path": save_path,
                "message": f"成功下载并读取Excel，共{len(df)}行数据"
            }
        except Exception as e:
            logger.error(f"Excel下载失败: {str(e)}")
            return {
                "success": False,
                "data": None,
                "message": f"Excel下载失败: {str(e)}"
            }
    
    def fetch_api_data(
        self,
        url: str,
        method: str = "GET",
        headers: Optional[dict] = None,
        params: Optional[dict] = None,
        data_key: Optional[str] = None
    ) -> Dict[str, Any]:
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                timeout=30
            )
            response.raise_for_status()
            
            json_data = response.json()
            
            if data_key and data_key in json_data:
                json_data = json_data[data_key]
            
            df = pd.DataFrame(json_data)
            
            return {
                "success": True,
                "data": df,
                "message": f"成功获取API数据，共{len(df)}行"
            }
        except Exception as e:
            logger.error(f"API数据获取失败: {str(e)}")
            return {
                "success": False,
                "data": None,
                "message": f"API数据获取失败: {str(e)}"
            }
    
    def extract_with_pagination(
        self,
        url: str,
        table_selector: str,
        next_button_selector: str,
        max_pages: int = 10,
        cookies: Optional[list] = None
    ) -> Dict[str, Any]:
        try:
            if not self.driver:
                return {
                    "success": False,
                    "data": None,
                    "message": "Driver未初始化"
                }
            
            all_data = []
            
            for page in range(max_pages):
                result = self.extract_from_table(url, table_selector, cookies=cookies)
                
                if not result['success']:
                    break
                
                all_data.append(result['data'])
                
                try:
                    next_button = self.driver.find_element(By.CSS_SELECTOR, next_button_selector)
                    if 'disabled' in next_button.get_attribute('class'):
                        break
                    next_button.click()
                except:
                    break
            
            if all_data:
                final_df = pd.concat(all_data, ignore_index=True)
                return {
                    "success": True,
                    "data": final_df,
                    "message": f"成功提取{len(final_df)}行数据，共{len(all_data)}页"
                }
            else:
                return {
                    "success": False,
                    "data": None,
                    "message": "未能提取到任何数据"
                }
        except Exception as e:
            logger.error(f"分页提取失败: {str(e)}")
            return {
                "success": False,
                "data": None,
                "message": f"分页提取失败: {str(e)}"
            }
