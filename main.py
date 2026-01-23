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
        self.sitekey = "0x4AAAAAACJH5atUUlnM2w2u"
        # Telegram 配置
        self.tg_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.tg_chat_id = os.getenv('TELEGRAM_CHAT_ID')

    def send_tg_notification(self, message):
        """发送 Telegram 通知"""
        if not self.tg_token or not self.tg_chat_id:
            print("⚠️ 未配置 TG 通知变量，跳过推送。")
            return
        url = f"https://api.telegram.org/bot{self.tg_token}/sendMessage"
        payload = {"chat_id": self.tg_chat_id, "text": message, "parse_mode": "HTML"}
        try:
            requests.post(url, json=payload, timeout=10)
        except Exception as e:
            print(f"❌ TG 通知发送失败: {e}")

    def get_remaining_days(self, page):
        try:
            time_element = page.locator("p:has-text('202')").first
            raw_text = time_element.inner_text().strip()
            match = re.search(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', raw_text)
            if match:
                expiry_date = datetime.strptime(match.group(), '%Y-%m-%d %H:%M:%S')
                now = datetime.now()
                delta = expiry_date - now
                return delta.days, expiry_date
            return None, None
        except:
            return None, None

    def solve_turnstile(self, page):
        print(f"🛡️ 正在请求 2captcha 破解挑战...")
        try:
            in_res = requests.post("https://2captcha.com/in.php", data={
                'key': self.api_key, 'method': 'turnstile',
                'sitekey': self.sitekey, 'pageurl': page.url, 'json': 1
            }).json()
            if in_res.get("status") != 1: return False
            task_id = in_res.get("request")
            for _ in range(25):
                time.sleep(5)
                res = requests.get(f"https://2captcha.com/res.php?key={self.api_key}&action=get&id={task_id}&json=1").json()
                if res.get("status") == 1:
                    token = res.get("request")
                    page.evaluate(f'document.querySelector("[name=cf-turnstile-response]").value = "{token}";')
                    page.evaluate('if (typeof cfCallback === "function") { cfCallback(); }')
                    return True
                if res.get("request") != "CAPCHA_NOT_READY": break
            return False
        except:
            return False

    def run(self):
        results = []
        with sync_playwright() as p:
            print("🌐 启动浏览器...")
            browser = p.chromium.launch(headless=True, args=['--disable-blink-features=AutomationControlled'])
            context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            context.add_cookies([{
                'name': 'remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d',
                'value': self.cookie_value,
                'domain': 'hub.weirdhost.xyz', 'path': '/', 'httpOnly': True, 'secure': True
            }])

            page = context.new_page()
            
            for url in self.server_urls:
                server_id = url.split('/')[-1]
                msg_prefix = f"🖥 <b>服务器: {server_id}</b>\n"
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=60000)
                    time.sleep(5)

                    days_left, expiry_date = self.get_remaining_days(page)
                    expiry_info = f"📅 到期: {expiry_date if expiry_date else '未知'}\n"
                    
                    if days_left is not None and days_left > 6:
                        status = "✅ <b>无需续期</b> (剩余 > 6天)"
                        results.append(f"{msg_prefix}{expiry_info}状态: {status}")
                        continue

                    renew_btn = page.locator("button.bkrtgq").first
                    if renew_btn.is_visible():
                        renew_btn.click()
                        page.wait_for_timeout(3000)
                        
                        if page.locator("[name='cf-turnstile-response']").count() > 0:
                            if self.solve_turnstile(page):
                                page.wait_for_timeout(7000)
                                status = "🎉 <b>续期成功!</b>"
                            else:
                                status = "❌ <b>破解失败</b>"
                        else:
                            status = "⚡️ <b>直接通过</b> (未触发盾)"
                    else:
                        status = "⏭ <b>未找到按钮</b>"
                    
                    results.append(f"{msg_prefix}{expiry_info}状态: {status}")
                        
                except Exception as e:
                    results.append(f"{msg_prefix}❌ <b>运行异常</b>: {str(e)[:50]}")
            
            browser.close()
            
            # 发送汇总通知
            if results:
                full_message = "<b>🚀 Weirdhost 自动续期报告</b>\n\n" + "\n\n".join(results)
                self.send_tg_notification(full_message)

if __name__ == "__main__":
    bot = WeirdhostUltimate()
    bot.run()
