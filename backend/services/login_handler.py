from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import json
import pickle
import time
import os
from typing import Dict, Optional, Any
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class LoginHandler:
    def __init__(self, selenium_url: Optional[str] = None, headless: bool = True):
        self.selenium_url = selenium_url
        self.headless = headless
        self.driver = None
        
    def init_driver(self):
        options = Options()
        if self.headless:
            options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36')
        
        if self.selenium_url:
            self.driver = webdriver.Remote(
                command_executor=self.selenium_url,
                options=options
            )
        else:
            self.driver = webdriver.Chrome(options=options)
        
        self.driver.implicitly_wait(10)
        return self.driver
    
    def close_driver(self):
        if self.driver:
            self.driver.quit()
            self.driver = None
    
    def login_with_password(
        self, 
        url: str, 
        username: str, 
        password: str,
        username_selector: str,
        password_selector: str,
        submit_selector: str,
        success_indicator: str,
        timeout: int = 30
    ) -> Dict[str, Any]:
        try:
            if not self.driver:
                self.init_driver()
            
            self.driver.get(url)
            wait = WebDriverWait(self.driver, timeout)
            
            username_input = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, username_selector))
            )
            username_input.clear()
            username_input.send_keys(username)
            
            password_input = self.driver.find_element(By.CSS_SELECTOR, password_selector)
            password_input.clear()
            password_input.send_keys(password)
            
            submit_button = self.driver.find_element(By.CSS_SELECTOR, submit_selector)
            submit_button.click()
            
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, success_indicator)))
            
            cookies = self.driver.get_cookies()
            
            return {
                "success": True,
                "cookies": cookies,
                "message": "登录成功"
            }
        except TimeoutException:
            return {
                "success": False,
                "cookies": None,
                "message": "登录超时，请检查选择器配置"
            }
        except Exception as e:
            logger.error(f"登录失败: {str(e)}")
            return {
                "success": False,
                "cookies": None,
                "message": f"登录失败: {str(e)}"
            }
    
    def login_with_cookie(
        self, 
        url: str, 
        cookies: list,
        test_url: Optional[str] = None
    ) -> Dict[str, Any]:
        try:
            if not self.driver:
                self.init_driver()
            
            self.driver.get(url)
            
            for cookie in cookies:
                self.driver.add_cookie(cookie)
            
            test_url = test_url or url
            self.driver.get(test_url)
            time.sleep(2)
            
            return {
                "success": True,
                "cookies": self.driver.get_cookies(),
                "message": "Cookie登录成功"
            }
        except Exception as e:
            logger.error(f"Cookie登录失败: {str(e)}")
            return {
                "success": False,
                "cookies": None,
                "message": f"Cookie登录失败: {str(e)}"
            }
    
    def handle_captcha(
        self,
        image_selector: str,
        input_selector: str,
        captcha_type: str = "image"
    ) -> Dict[str, Any]:
        try:
            if not self.driver:
                return {
                    "success": False,
                    "message": "Driver未初始化"
                }
            
            captcha_element = self.driver.find_element(By.CSS_SELECTOR, image_selector)
            captcha_screenshot = captcha_element.screenshot_as_png
            
            if captcha_type == "image":
                pass
            
            return {
                "success": True,
                "message": "验证码处理功能待实现",
                "captcha_image": captcha_screenshot
            }
        except Exception as e:
            logger.error(f"验证码处理失败: {str(e)}")
            return {
                "success": False,
                "message": f"验证码处理失败: {str(e)}"
            }
    
    def handle_qrcode_login(
        self,
        qrcode_selector: str,
        timeout: int = 120
    ) -> Dict[str, Any]:
        try:
            if not self.driver:
                self.init_driver()
            
            qrcode_element = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, qrcode_selector))
            )
            
            qrcode_screenshot = qrcode_element.screenshot_as_png
            
            return {
                "success": False,
                "message": "请扫描二维码登录",
                "qrcode_image": qrcode_screenshot
            }
        except Exception as e:
            logger.error(f"二维码登录失败: {str(e)}")
            return {
                "success": False,
                "message": f"二维码登录失败: {str(e)}"
            }
    
    def save_cookies(self, cookies: list, filepath: str):
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'wb') as f:
            pickle.dump(cookies, f)
    
    def load_cookies(self, filepath: str) -> Optional[list]:
        if os.path.exists(filepath):
            with open(filepath, 'rb') as f:
                return pickle.load(f)
        return None
