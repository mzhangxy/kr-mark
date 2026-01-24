import os
import time
import re
import requests
from datetime import datetime
from playwright.sync_api import sync_playwright

class WeirdhostUltimate:
    def __init__(self):
        self.api_key = os.getenv('TWOCAPTCHA_API_KEY')
        self.cookie_value = os.getenv('REMEMBER_WEB_COOKIE')
        self.server_urls = [url.strip() for url in os.getenv('WEIRDHOST_SERVER_URLS', '').split(',') if url.strip()]
        # Telegram 配置
        self.tg_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.tg_chat_id = os.getenv('TELEGRAM_CHAT_ID')
        # 验证码 Sitekey
        self.sitekey = "0x4AAAAAACJH5atUUlnM2w2u"
        # 记录运行结果
        self.results = []

    def send_tg_notification(self, message):
        """发送 Telegram 通知 (带重试机制)"""
        if not self.tg_token or not self.tg_chat_id:
            print("⚠️ 未配置 TG Token 或 Chat ID。")
            return
        
        url = f"https://api.telegram.org/bot{self.tg_token}/sendMessage"
        payload = {"chat_id": self.tg_chat_id, "text": message, "parse_mode": "Markdown"}

        for i in range(3):
            try:
                response = requests.post(url, json=payload, timeout=30)
                if response.status_code == 200:
                    print("✅ TG 通知发送成功！")
                    return
                else:
                    print(f"⚠️ TG 响应异常 (尝试 {i+1}/3): {response.status_code}")
            except Exception as e:
                print(f"❌ 第 {i+1} 次发送 TG 通知失败: {e}")
                if i < 2: time.sleep(5) 
        print("🛑 TG 通知最终发送失败。")

    def get_remaining_days(self, page):
        """解析页面上的到期时间"""
        try:
            target = page.get_by_text(re.compile(r"202\d-\d{2}-\d{2}")).first
            target.wait_for(state="visible", timeout=15000)
            
            raw_text = target.inner_text()
            match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', raw_text)
            if match:
                expiry_date = datetime.strptime(match.group(1), '%Y-%m-%d %H:%M:%S')
                return (expiry_date - datetime.now()).days, expiry_date
        except Exception as e:
            print(f"⚠️ 时间解析提示: {e}")
        return None, None

    def solve_turnstile(self, page):
        """2captcha 破解逻辑"""
        print(f"🛡️ 正在请求 2captcha 破解...")
        in_res = requests.post("https://2captcha.com/in.php", data={
            'key': self.api_key, 'method': 'turnstile', 'sitekey': self.sitekey,
            'pageurl': page.url, 'json': 1
        }).json()

        if in_res.get("status") != 1: return False

        task_id = in_res.get("request")
        for _ in range(30):
            time.sleep(5)
            res = requests.get(f"https://2captcha.com/res.php?key={self.api_key}&action=get&id={task_id}&json=1").json()
            if res.get("status") == 1:
                token = res.get("request")
                page.evaluate(f'document.querySelector("[name=cf-turnstile-response]").value = "{token}";')
                page.evaluate('if (typeof cfCallback === "function") { cfCallback(); }')
                return True
            if res.get("request") != "CAPCHA_NOT_READY": break
        return False

    def run
