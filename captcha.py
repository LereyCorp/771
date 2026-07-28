# ============================================
# captcha.py (без отладки)
# ============================================
import time
import requests
import re

class CaptchaSolver:
    def __init__(self, api_key, log_callback=None):
        self.api_key = api_key
        self.log_callback = log_callback
    
    def log(self, message):
        if self.log_callback:
            self.log_callback(message, "FAUCET")
    
    def solve_viefaucet(self, base64_image):
        url_in = "https://sctg.xyz/in.php"
        data = {"key": self.api_key, "method": "viefaucet", "body": base64_image}
        
        try:
            resp = requests.post(url_in, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
            if resp.status_code != 200:
                return None
            
            captcha_id = None
            if "|" in resp.text:
                status, captcha_id = resp.text.split("|", 1)
                if status != "OK":
                    return None
            else:
                captcha_id = resp.json().get("request")
            
            if not captcha_id:
                return None
            
            return self._poll_result(captcha_id)
        except:
            return None
    
    def solve_antibot(self, images):
        url_in = "https://sctg.xyz/in.php"
        
        data = {
            "key": self.api_key,
            "method": "antibot",
            "main": images.get("main", ""),
            "1": images.get("1", ""),
            "2": images.get("2", ""),
            "3": images.get("3", ""),
        }
        
        try:
            resp = requests.post(url_in, data=data, timeout=30)
            
            if resp.status_code != 200:
                return None
            
            result = resp.text.strip()
            
            if "|" in result:
                status, task_id = result.split("|", 1)
                if status != "OK":
                    return None
                return self._poll_result(task_id)
            else:
                return self._parse_result(result)
                
        except:
            return None
    
    def _poll_result(self, captcha_id):
        url_res = "https://sctg.xyz/res.php"
        
        for attempt in range(30):
            time.sleep(30)
            params = {
                "key": self.api_key,
                "action": "get",
                "id": captcha_id,
            }
            res = requests.get(url_res, params=params, timeout=30)
            
            if res.status_code != 200:
                continue
            
            response_text = res.text.strip()
            
            if "NOT_READY" in response_text or "CAPCHA_NOT_READY" in response_text:
                continue
            if "ERROR" in response_text:
                return None
            
            return self._parse_result(response_text)
        
        return None
    
    def _parse_result(self, result):
        if not result:
            return None
        
        match = re.search(r'x[=:](\d+),\s*y[=:](\d+)', result)
        if match:
            return {"x": int(match.group(1)), "y": int(match.group(2))}
        
        match = re.search(r'click[s]?[:=]\s*([\d,\s]+)', result, re.IGNORECASE)
        if match:
            return {"click": match.group(1).strip()}
        
        if re.match(r'^[\d,\s]+$', result):
            return {"click": result}
        
        numbers = re.findall(r'\d+', result)
        if len(numbers) == 2:
            return {"x": int(numbers[0]), "y": int(numbers[1])}
        elif len(numbers) > 2:
            return {"click": ",".join(numbers)}
        
        return result