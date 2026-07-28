import os
import json

class Config:
    def __init__(self, config_file="config.json"):
        self.config_file = config_file
        self.data = self._load()
    
    def _load(self):
        if os.path.exists(self.config_file):
            with open(self.config_file, "r") as f:
                return json.load(f)
        return {}
    
    def save(self, email, password, sctg_key, proxy):
        self.data = {
            "email": email,
            "password": password,
            "sctg_key": sctg_key,
            "proxy": proxy
        }
        with open(self.config_file, "w") as f:
            json.dump(self.data, f, indent=4)
    
    def get(self, key, default=""):
        return self.data.get(key, default)