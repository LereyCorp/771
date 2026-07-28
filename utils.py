import time
import random

def random_delay(min_sec=1.0, max_sec=3.0):
    time.sleep(random.uniform(min_sec, max_sec))

def format_time():
    return time.strftime("%H:%M:%S")