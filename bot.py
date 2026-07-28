# ============================================
# bot.py (рабочий + Chrome из папки)
# ============================================
import os
import json
import time
import random
import re
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import StaleElementReferenceException, ElementClickInterceptedException
from config import Config
from browser import Browser
from captcha import CaptchaSolver
from utils import random_delay, format_time

class VieFaucetBot:
    def __init__(self, log_callback=None, balance_callback=None):
        self.config = Config()
        self.browser = Browser(self.config.get("proxy"), headless=True)
        self.captcha_solver = CaptchaSolver(self.config.get("sctg_key"), log_callback=log_callback)
        self.log_callback = log_callback
        self.balance_callback = balance_callback
        self.base_url = "https://viefaucet.com"
        self.running = True
        self.selected_types = ["window", "iframe", "youtube"]
        self.enable_faucet = False
        self.last_balance = "Неизвестно"
        self.logged_in = False
        self.auth_token = None
        self.cookies = None
        self.max_retries = 3
        self.faucet_count = 0
        self.faucet_timer = 260

    def log(self, message, level="INFO"):
        timestamp = format_time()
        formatted = f"[{timestamp}] {message}"
        if self.log_callback: self.log_callback(formatted, level)

    def update_balance_display(self):
        balance = self._get_balance()
        if self.balance_callback: self.balance_callback(balance)
        return balance

    def _get_balance(self):
        try:
            self.browser.find_element(By.CSS_SELECTOR, ".balance-exchange", timeout=5)
            time.sleep(0.5)
            select_elem = self.browser.find_element(By.CSS_SELECTOR, ".select-currency")
            if not select_elem: select_elem = self.browser.find_element(By.CSS_SELECTOR, "select.select-currency")
            if select_elem:
                self.browser.execute_script("""
                    var select = arguments[0];
                    for (var i = 0; i < select.options.length; i++) {
                        if (select.options[i].value === '612e584238797d4440a6aebf') {
                            select.value = select.options[i].value;
                            select.dispatchEvent(new Event('change', { bubbles: true }));
                            break;
                        }
                    }
                """, select_elem)
                time.sleep(0.5)
            balance_values = self.browser.driver.find_elements(By.CSS_SELECTOR, ".balance-value")
            if len(balance_values) >= 2:
                coins = balance_values[0].text.strip()
                ltc_value = balance_values[1].text.strip()
                currency = self.browser.execute_script("return arguments[0].options[arguments[0].selectedIndex].label;", select_elem) if select_elem else "LTC"
                if coins and ltc_value:
                    self.last_balance = f"{coins} монет = {ltc_value} {currency}"
                    return self.last_balance
        except: pass
        return self.last_balance

    def _is_logged_in(self):
        try:
            if "/login" in self.browser.current_url: return False
            self.browser.find_element(By.CSS_SELECTOR, ".balance-exchange, .user-info, .avatar", timeout=5)
            return True
        except: return False

    def _is_captcha_dialog_present(self):
        try:
            dialog = self.browser.driver.find_element(By.CSS_SELECTOR, ".el-dialog")
            return dialog.is_displayed()
        except: return False

    def _find_captcha_img(self):
        for selector in ["img.captcha-image", ".captcha-image"]:
            img = self.browser.find_element(By.CSS_SELECTOR, selector, timeout=5)
            if img:
                src = img.get_attribute("src")
                if src and src.startswith("data:image"): return img
        return None

    def _click_checkbox(self):
        checkbox = self.browser.wait_for_clickable(By.XPATH, "//span[contains(text(), 'I am not a robot')]", timeout=10)
        if checkbox: self.browser.click_js(checkbox); return True
        checkbox_div = self.browser.find_element(By.CSS_SELECTOR, ".request-captcha", timeout=5)
        if checkbox_div: self.browser.click_js(checkbox_div); return True
        return False

    def _click_captcha_by_coords(self, coords):
        captcha_img = self._find_captcha_img()
        if not captcha_img: return False
        self.browser.execute_script("arguments[0].scrollIntoView({block: 'center'});", captcha_img)
        time.sleep(0.5)
        img_width = captcha_img.size['width']; img_height = captcha_img.size['height']
        natural_size = self.browser.execute_script("""
            var img = arguments[0];
            return {naturalWidth: img.naturalWidth, naturalHeight: img.naturalHeight, clientWidth: img.clientWidth, clientHeight: img.clientHeight};
        """, captcha_img)
        if natural_size['naturalWidth'] > 0 and natural_size['clientWidth'] > 0:
            scale_x = natural_size['clientWidth'] / natural_size['naturalWidth']
            scale_y = natural_size['clientHeight'] / natural_size['naturalHeight']
            adjusted_x = int(coords['x'] * scale_x); adjusted_y = int(coords['y'] * scale_y)
        else: adjusted_x, adjusted_y = coords['x'], coords['y']
        time.sleep(random.uniform(2, 3))
        try:
            self.browser.execute_script(f"""
                var img = arguments[0]; var rect = img.getBoundingClientRect();
                var x = rect.left + {adjusted_x}; var y = rect.top + {adjusted_y};
                ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click'].forEach(function(type) {{
                    var event = type.startsWith('pointer') ? new PointerEvent(type, {{clientX: x, clientY: y, bubbles: true}}) : new MouseEvent(type, {{clientX: x, clientY: y, bubbles: true}});
                    img.dispatchEvent(event);
                }});
            """, captcha_img)
            return True
        except:
            try:
                actions = ActionChains(self.browser.driver)
                actions.move_to_element(captcha_img).move_by_offset(adjusted_x - img_width//2, adjusted_y - img_height//2).click().perform()
                return True
            except: pass
        return False

    def _check_invalid_captcha(self):
        try:
            return bool(self.browser.execute_script("""
                var messages = document.querySelectorAll('.el-message--error, .el-notification--error');
                for (var i = 0; i < messages.length; i++) {if (messages[i].textContent.toLowerCase().includes('captcha')) return true;}
                return false;
            """))
        except: return False

    def _check_antibot_error(self):
        try:
            return bool(self.browser.execute_script("""
                var messages = document.querySelectorAll('.el-message--error, .el-notification--error, .el-alert--error');
                for (var i = 0; i < messages.length; i++) {
                    var text = messages[i].textContent.toLowerCase();
                    if (text.includes('antibot') || text.includes('invalid antibot')) return true;
                }
                return false;
            """))
        except: return False

    def _verify_and_check(self):
        random_delay(1, 2); time.sleep(random.uniform(2, 3))
        if not self._is_captcha_dialog_present(): return True
        for selector in [".el-dialog .el-button--primary.center", ".el-dialog .el-button--primary", ".captchaDialog .el-button--primary", "button.el-button--primary"]:
            verify_btn = self.browser.wait_for_clickable(By.CSS_SELECTOR, selector, timeout=5)
            if verify_btn and verify_btn.is_displayed() and verify_btn.is_enabled():
                self.browser.click_js(verify_btn); time.sleep(3)
                if self._check_invalid_captcha(): return "invalid_captcha"
                return True
        if not self._is_captcha_dialog_present(): return True
        return False

    def _handle_captcha_flow(self, max_captcha_retries=3):
        for captcha_attempt in range(max_captcha_retries):
            self.log(f"[CAPTCHA] Попытка {captcha_attempt + 1}/{max_captcha_retries}")
            if not self._is_captcha_dialog_present():
                time.sleep(3)
                if not self._is_captcha_dialog_present(): return True
            self._click_checkbox(); random_delay(1, 2)
            captcha_img = self._find_captcha_img()
            if not captcha_img: time.sleep(3); captcha_img = self._find_captcha_img()
            if not captcha_img:
                if not self._is_captcha_dialog_present(): return True
                if captcha_attempt < max_captcha_retries - 1: continue
                return False
            try:
                src = captcha_img.get_attribute("src")
                if not src or not src.startswith("data:image"): time.sleep(2); continue
            except StaleElementReferenceException: continue
            coords = self.captcha_solver.solve_viefaucet(src.split(",")[1])
            if not coords:
                if captcha_attempt < max_captcha_retries - 1: time.sleep(2); continue
                return False
            if not self._click_captcha_by_coords(coords):
                if captcha_attempt < max_captcha_retries - 1: continue
                return False
            result = self._verify_and_check()
            if result == "invalid_captcha":
                if captcha_attempt < max_captcha_retries - 1: continue
            return result
        return False

    def _find_and_click_tab(self, tab_name):
        tab_name_cap = tab_name.capitalize()
        tabs = self.browser.driver.find_elements(By.CSS_SELECTOR, ".el-tabs__item")
        for t in tabs:
            if tab_name_cap.lower() in t.text.lower():
                try: self.browser.click_js(t); return True
                except: continue
        return False

    def _get_first_active_ad(self):
        try:
            ptc_blocks = self.browser.driver.find_elements(By.CSS_SELECTOR, ".ptc-ad")
            for block in ptc_blocks:
                try:
                    view_btn = block.find_element(By.CSS_SELECTOR, "button.claim-button")
                    if view_btn.get_attribute("disabled") is None:
                        try: timer_elem = block.find_element(By.CSS_SELECTOR, ".el-tag--warning .el-tag__content"); timer_text = timer_elem.text.lower()
                        except: timer_text = "10s"
                        numbers = re.findall(r'\d+', timer_text); timer = 10
                        if numbers: num = int(numbers[0]); timer = num * 60 if 'min' in timer_text else num
                        return {"element": view_btn, "timer": timer}
                except: continue
        except: pass
        return None

    def _safe_click(self, element, retries=3):
        for attempt in range(retries):
            try:
                self.browser.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                random_delay(0.3, 0.7); element.click(); return True
            except ElementClickInterceptedException:
                try:
                    close_btn = self.browser.driver.find_element(By.CSS_SELECTOR, ".el-overlay .el-dialog__close, .el-overlay .el-icon-close, .el-dialog__headerbtn")
                    if close_btn.is_displayed(): close_btn.click(); random_delay(0.5, 1)
                except: pass
                continue
            except StaleElementReferenceException: return False
            except: continue
        return False

    def _is_block_active(self, block):
        try:
            btn = block.find_element(By.CSS_SELECTOR, "button.claim-button")
            return btn.get_attribute("disabled") is None
        except: return False

    def _save_cookies(self):
        try:
            cookies = self.browser.driver.get_cookies()
            with open("cookies.json", "w") as f: json.dump(cookies, f)
        except: pass

    def _load_cookies(self):
        try:
            if os.path.exists("cookies.json"):
                with open("cookies.json", "r") as f:
                    cookies = json.load(f)
                for cookie in cookies:
                    try: self.browser.driver.add_cookie(cookie)
                    except: pass
                return True
        except: pass
        return False

    def login(self):
        self.log("[AUTH] Авторизация...")
        self.browser.start()
        
        # Пробуем восстановить сессию
        self.browser.get(self.base_url); time.sleep(2)
        if self._load_cookies():
            self.browser.get(self.base_url + "/app/ptc"); time.sleep(3)
            if self._is_logged_in():
                self.log("[OK] Сессия восстановлена"); self.update_balance_display()
                return True
        
        for attempt in range(1, 4):
            self.browser.get(self.base_url + "/login"); random_delay(2, 3)
            email_field = self.browser.find_element(By.CSS_SELECTOR, "input.el-input__inner[placeholder='Email']", timeout=10)
            if not email_field: return False
            email_field.click(); email_field.clear()
            for ch in self.config.get("email"): email_field.send_keys(ch); time.sleep(random.uniform(0.03, 0.1))
            password_field = self.browser.find_element(By.CSS_SELECTOR, "input.el-input__inner[placeholder='Password']")
            if not password_field: return False
            password_field.click(); password_field.clear()
            for ch in self.config.get("password"): password_field.send_keys(ch); time.sleep(random.uniform(0.03, 0.1))
            random_delay(0.5, 1.5); self._click_checkbox(); random_delay(1, 2)
            captcha_img = self._find_captcha_img()
            if captcha_img:
                coords = self.captcha_solver.solve_viefaucet(captcha_img.get_attribute("src").split(",")[1])
                if coords: self._click_captcha_by_coords(coords); random_delay(0.5, 1); time.sleep(random.uniform(1, 2))
            login_btn = self.browser.find_element(By.CSS_SELECTOR, "button.el-button--success.login-button")
            if not login_btn: return False
            self.browser.click_js(login_btn); random_delay(2, 4)
            if self._is_logged_in():
                self.log("[OK] Авторизация успешна"); self.update_balance_display()
                self._save_cookies()
                for _ in range(10):
                    for cookie in self.browser.driver.get_cookies():
                        if cookie['name'] == 'authToken': self.auth_token = cookie['value']; break
                    if self.auth_token: break
                    time.sleep(1)
                if self.auth_token:
                    self.cookies = {c['name']: c['value'] for c in self.browser.driver.get_cookies()}
                    self.logged_in = True; return True
            else: self.browser.driver.delete_all_cookies(); continue
        return False

    def process_faucet(self):
        for faucet_attempt in range(3):
            self.faucet_count += 1
            self.log(f"[FAUCET] #{self.faucet_count} (попытка {faucet_attempt + 1}/3)")
            self.browser.get(self.base_url + "/app/faucet"); random_delay(5, 7)
            try: WebDriverWait(self.browser.driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".antibot-container")))
            except: pass
            time.sleep(5)
            main_img = self.browser.find_element(By.CSS_SELECTOR, ".antibot-instruction img, img[alt='Instruction']", timeout=5)
            main_base64 = None
            if main_img:
                main_base64 = self.browser.execute_script("""
                    var img = arguments[0]; var canvas = document.createElement('canvas');
                    canvas.width = img.naturalWidth || 200; canvas.height = img.naturalHeight || 200;
                    canvas.getContext('2d').drawImage(img, 0, 0);
                    return canvas.toDataURL('image/png').split(',')[1];
                """, main_img)
            atblinks = self.browser.driver.find_elements(By.CSS_SELECTOR, ".atblink img")
            if main_base64 and len(atblinks) >= 3:
                images_data = {"main": main_base64}
                for i, img in enumerate(atblinks[:3]):
                    try:
                        b64 = self.browser.execute_script("""
                            var img = arguments[0]; var c = document.createElement('canvas');
                            c.width = img.naturalWidth || 200; c.height = img.naturalHeight || 200;
                            c.getContext('2d').drawImage(img, 0, 0);
                            return c.toDataURL('image/png').split(',')[1];
                        """, img)
                        if b64 and len(b64) > 100: images_data[str(i + 1)] = b64
                    except: continue
                if len(images_data) >= 4:
                    result = self.captcha_solver.solve_antibot(images_data)
                    if result:
                        clicks = result.get("click", "") if isinstance(result, dict) else (result if isinstance(result, str) else "")
                        if clicks:
                            if isinstance(clicks, str): clicks = [int(n) for n in re.findall(r'\d+', clicks)]
                            for ci in clicks:
                                idx = ci - 1
                                if 0 <= idx < len(atblinks):
                                    div = atblinks[idx].find_element(By.XPATH, "./..")
                                    self.browser.execute_script("arguments[0].scrollIntoView({block: 'center'});", div)
                                    time.sleep(0.3); div.click(); time.sleep(0.8)
            self.log("[FAUCET] viefaucet..."); time.sleep(2)
            self._click_checkbox(); random_delay(2, 3)
            captcha_img = self._find_captcha_img()
            if captcha_img:
                src = captcha_img.get_attribute("src")
                if src and src.startswith("data:image"):
                    coords = self.captcha_solver.solve_viefaucet(src.split(",")[1])
                    if coords:
                        self._click_captcha_by_coords(coords); time.sleep(2)
                        try:
                            btn = self.browser.driver.find_element(By.CSS_SELECTOR, ".claim-button, button.el-button--primary")
                            if btn and btn.is_enabled(): btn.click(); time.sleep(3)
                            if self._check_antibot_error():
                                if faucet_attempt < 2: continue
                        except: pass
            self.update_balance_display()
            self.log(f"[OK] Faucet #{self.faucet_count}"); return True
        return False

    def process_ad(self, timer):
        main_window = self.browser.window_handles[0] if self.browser.window_handles else self.browser.driver.current_window_handle
        wait_time = timer + random.randint(1, 3)
        start_time = time.time()
        time.sleep(1)
        if len(self.browser.window_handles) > 1:
            self.browser.switch_to_window(self.browser.window_handles[-1])
        current_url = self.browser.current_url

        if "/youtube/" in current_url:
            wait_time += 10
            self.log(f"[YT] Таймер: {wait_time}с")
            self.browser.wait_page_load(timeout=15); time.sleep(3)
            try:
                video_element = self.browser.driver.find_element(By.CSS_SELECTOR, "video")
                if video_element: ActionChains(self.browser.driver).move_to_element(video_element).click().perform()
                else:
                    s = self.browser.get_window_size()
                    ActionChains(self.browser.driver).move_by_offset(s['width']//2, s['height']//2).click().perform()
                    ActionChains(self.browser.driver).move_by_offset(-s['width']//2, -s['height']//2).perform()
            except: pass
            elapsed = time.time() - start_time; remaining = wait_time - elapsed
            if remaining > 0: time.sleep(remaining)
            result = self._handle_captcha_flow(3)
            self.browser.close_current_window()
            if self.browser.window_handles: self.browser.switch_to_window(main_window)
            self.update_balance_display(); return result

        if "/ptc/view/" in current_url or ("/ptc/" in current_url and "/app/ptc" not in current_url):
            self.log(f"[IFRAME] Таймер: {wait_time}с")
            elapsed = time.time() - start_time; remaining = wait_time - elapsed
            if remaining > 0: time.sleep(remaining)
            result = self._handle_captcha_flow(3)
            self.browser.close_current_window()
            if self.browser.window_handles: self.browser.switch_to_window(main_window)
            self.update_balance_display(); return result

        wait_time = timer + 2
        self.log(f"[WINDOW] Таймер: {wait_time}с")
        elapsed = time.time() - start_time; remaining = wait_time - elapsed
        if remaining > 0: time.sleep(remaining)
        self.browser.close_current_window()
        if self.browser.window_handles: self.browser.switch_to_window(main_window)
        time.sleep(3)
        result = self._handle_captcha_flow(3)
        self.update_balance_display(); return result

    def run_ptc_loop(self):
        self.log("[START] PTC-цикл")
        self.log(f"[INFO] Вкладки: {', '.join(self.selected_types)}")
        if self.enable_faucet: self.log(f"[INFO] Faucet: ВКЛЮЧЕН ({self.faucet_timer}с)")

        self.browser.get(self.base_url + "/app/ptc"); random_delay(2, 3); self.update_balance_display()
        last_faucet = 0
        if self.enable_faucet:
            self.process_faucet(); last_faucet = time.time()
            self.browser.get(self.base_url + "/app/ptc"); random_delay(2, 3)

        while self.running:
            if self.enable_faucet and time.time() - last_faucet >= self.faucet_timer:
                self.process_faucet(); last_faucet = time.time()
                self.browser.get(self.base_url + "/app/ptc"); random_delay(2, 3)

            if not self._is_logged_in():
                self.log("[WARN] Переавторизация...")
                if not self.login(): return
                self.browser.get(self.base_url + "/app/ptc"); random_delay(2, 3)

            any_ad = False
            for ad_type in self.selected_types:
                if not self.running: break
                if "/app/ptc" not in self.browser.current_url: self.browser.get(self.base_url + "/app/ptc"); random_delay(1, 2)
                if not self._find_and_click_tab(ad_type): continue
                random_delay(0.5, 1)
                self.browser.execute_script("window.scrollTo(0, document.body.scrollHeight);"); time.sleep(0.5)
                self.browser.execute_script("window.scrollTo(0, 0);"); time.sleep(0.5)
                active = sum(1 for b in self.browser.driver.find_elements(By.CSS_SELECTOR, ".ptc-ad") if self._is_block_active(b))
                if active == 0: continue
                any_ad = True; self.log(f"[TASK] {ad_type}: {active} заданий")
                n = 0; retry = 0
                while self.running:
                    ad = self._get_first_active_ad()
                    if not ad: self.log(f"[OK] {ad_type} завершено"); break
                    n += 1; self.log(f"[>] {ad_type} #{n} | Таймер: {ad['timer']}с")
                    if not self._safe_click(ad["element"]):
                        retry += 1
                        if retry >= 3: self.log(f"[ERROR] #{n} пропущено", "ERROR"); retry = 0; continue
                        self.log(f"[RETRY] ({retry}/3)", "WARN"); continue
                    result = self.process_ad(ad["timer"])
                    if result == "invalid_captcha":
                        retry += 1
                        if retry >= 3: self.log(f"[ERROR] #{n} пропущено", "ERROR"); retry = 0; continue
                        self.log(f"[RETRY] Captcha ({retry}/3)", "WARN")
                    elif result:
                        retry = 0; self.log(f"[OK] {ad_type} #{n} выполнено")
                        if "/app/ptc" not in self.browser.current_url: self.browser.get(self.base_url + "/app/ptc"); random_delay(1, 2)
                        self._find_and_click_tab(ad_type); random_delay(0.5, 1)
                        time.sleep(random.randint(3, 8))
                    else:
                        retry += 1
                        if retry >= 3: self.log(f"[ERROR] #{n} пропущено", "ERROR"); retry = 0; continue
                        self.log(f"[RETRY] ({retry}/3)", "WARN")
                    if "/app/ptc" not in self.browser.current_url: self.browser.get(self.base_url + "/app/ptc"); random_delay(1, 2)
                    self._find_and_click_tab(ad_type); random_delay(0.5, 1)

            if not any_ad:
                if self.enable_faucet and time.time() - last_faucet >= self.faucet_timer:
                    self.process_faucet(); last_faucet = time.time()
                    self.browser.get(self.base_url + "/app/ptc"); random_delay(2, 3)
                self.update_balance_display(); self.log("[WAIT] 120 сек...")
                for _ in range(12):
                    if not self.running: break
                    time.sleep(10)
            else: random_delay(2, 4)

    def run(self):
        try:
            if not self.login(): return
            if self.enable_faucet and not self.selected_types:
                while self.running:
                    self.process_faucet()
                    for _ in range(self.faucet_timer // 10):
                        if not self.running: break
                        time.sleep(10)
                return
            self.run_ptc_loop()
        except KeyboardInterrupt: self.log("[STOP]", "INFO")
        except Exception as e: self.log(f"[ERROR] {e}", "ERROR")
        finally: self.browser.quit()