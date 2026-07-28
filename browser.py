# ============================================
# browser.py (АБСОЛЮТНО ТОЧНО исправлены отступы)
# ============================================
import os
import json
import shutil
import subprocess
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import *
from webdriver_manager.chrome import ChromeDriverManager

class Browser:
    def __init__(self, proxy="", headless=True):
        self.driver = None
        self.proxy = proxy
        self.headless = headless
        self.bot_dir = os.path.dirname(os.path.abspath(__file__))

    def _create_proxy_extension(self):
        if not self.proxy:
            return None
        ext_dir = os.path.join(self.bot_dir, "proxy_extension_v2")
        if os.path.exists(ext_dir):
            shutil.rmtree(ext_dir)
        os.makedirs(ext_dir)
        if "://" in self.proxy:
            protocol, rest = self.proxy.split("://", 1)
        else:
            protocol, rest = "http", self.proxy
        if "@" in rest:
            auth, host_port = rest.split("@", 1)
            username, password = (auth.split(":", 1) + [""])[:2]
        else:
            username, password = "", ""
            host_port = rest
        host, port = (host_port.split(":", 1) + ["80"])[:2]
        manifest = {"manifest_version": 2, "name": "Chrome Proxy", "version": "1.0.0", "permissions": ["proxy", "tabs", "unlimitedStorage", "storage", "<all_urls>", "webRequest", "webRequestBlocking"], "background": {"scripts": ["background.js"]}}
        with open(os.path.join(ext_dir, "manifest.json"), "w") as f:
            json.dump(manifest, f, indent=4)
        bg_js = f'var config = {{mode: "fixed_servers", rules: {{singleProxy: {{scheme: "{protocol}", host: "{host}", port: parseInt("{port}")}}, bypassList: ["localhost"]}}}};chrome.proxy.settings.set({{value: config, scope: "regular"}}, function() {{}});function callbackFn(details) {{return {{authCredentials: {{username: "{username}", password: "{password}"}}}};}}chrome.webRequest.onAuthRequired.addListener(callbackFn, {{urls: ["<all_urls>"]}}, ["blocking"]);'
        with open(os.path.join(ext_dir, "background.js"), "w") as f:
            f.write(bg_js)
        return ext_dir

    def _find_chrome(self):
        chrome_dir = os.path.join(self.bot_dir, "chrome")
        if os.path.exists(chrome_dir):
            for root, dirs, files in os.walk(chrome_dir):
                if "chrome.exe" in files:
                    return os.path.join(root, "chrome.exe")
        return None

    def start(self):
        chrome_path = self._find_chrome()
        if not chrome_path:
            return False
        wdm_dir = os.path.expanduser("~/.wdm")
        if os.path.exists(wdm_dir):
            try:
                shutil.rmtree(wdm_dir)
            except:
                pass
        try:
            driver_path = ChromeDriverManager().install()
        except:
            return False
        options = Options()
        options.binary_location = chrome_path
        if self.headless:
            options.add_argument("--headless=new")
        options.add_argument("--window-size=1366,768")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--log-level=3")
        options.add_argument("--mute-audio")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.page_load_strategy = 'eager'
        try:
            service = Service(driver_path)
            self.driver = webdriver.Chrome(service=service, options=options)
            self.driver.set_page_load_timeout(15)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            return True
        except:
            return False

    def quit(self):
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass

    def get(self, url):
        try:
            self.driver.get(url)
        except TimeoutException:
            try:
                self.driver.execute_script("window.stop();")
            except:
                pass

    def find_element(self, by, value, timeout=10):
        try:
            return WebDriverWait(self.driver, timeout).until(EC.presence_of_element_located((by, value)))
        except:
            return None

    def wait_for_clickable(self, by, value, timeout=10):
        try:
            return WebDriverWait(self.driver, timeout).until(EC.element_to_be_clickable((by, value)))
        except:
            return None

    def click_js(self, element):
        try:
            self.driver.execute_script("arguments[0].click();", element)
            return True
        except:
            return False

    @property
    def current_url(self):
        return self.driver.current_url

    @property
    def window_handles(self):
        return self.driver.window_handles

    def switch_to_window(self, handle):
        self.driver.switch_to.window(handle)

    def close_current_window(self):
        try:
            self.driver.close()
        except:
            pass

    def execute_script(self, script, *args):
        return self.driver.execute_script(script, *args)

    def get_window_size(self):
        return self.driver.get_window_size()

    def wait_page_load(self, timeout=15):
        try:
            WebDriverWait(self.driver, timeout).until(lambda d: d.execute_script("return document.readyState") == "complete")
        except:
            pass