import requests
import random
import time

class ProxyRotator:
    def __init__(self):
        # We will use the PubProxy API which provides free rotating proxies
        self.api_url = "http://pubproxy.com/api/proxy?format=json&type=http"
        self.current_proxy = None
        self.last_fetch = 0
        self.proxy_dict = None

    def _fetch_new_proxy(self):
        try:
            r = requests.get(self.api_url, timeout=5)
            if r.status_code == 200:
                data = r.json()
                if data and "data" in data and len(data["data"]) > 0:
                    ip_port = data["data"][0]["ipPort"]
                    self.current_proxy = f"http://{ip_port}"
                    self.proxy_dict = {
                        "http": self.current_proxy,
                        "https": self.current_proxy
                    }
                    self.last_fetch = time.time()
                    print(f"      [ProxyRotator] Acquired new proxy: {self.current_proxy}")
                    return True
        except Exception as e:
            print(f"      [ProxyRotator] Failed to fetch proxy: {e}")
        return False

    def get_proxy(self):
        # Fetch a new proxy every 2 minutes or if we don't have one
        if not self.proxy_dict or (time.time() - self.last_fetch > 120):
            self._fetch_new_proxy()
        return self.proxy_dict

rotator = ProxyRotator()

def get_current_proxy():
    return rotator.get_proxy()

def rotate_now():
    rotator._fetch_new_proxy()
    return rotator.get_proxy()
