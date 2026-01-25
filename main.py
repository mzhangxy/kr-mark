import os
import time
import re
import requests
from datetime import datetime
from playwright.sync_api import sync_playwright

class WeirdhostUltimate:
    def __init__(self):
        self.api_key = os.getenv('TWOCAPTCHA_API_KEY')
        self.tg_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.tg_chat_id = os.getenv('TELEGRAM_CHAT_ID')
        self.server_urls = [url.strip() for url in os.getenv('WEIRDHOST_SERVER_URLS', '').split(',') if url.strip()]
        self.sitekey = "0x4AAAAAACJH5atUUlnM2w2u"
        
        self.cookie_file = "session_cookie.txt"
        self.cookie_name = 'remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d'
        self.results = []
        
        if os.path.exists(self.cookie_file):
            with open(self.cookie_file, "r") as f:
                self.current_cookie = f.read().strip()
                self.log(f"📂 使用本地文件 Cookie (前8位: {self.current_cookie[:8]})")
        else:
            self.current_cookie = os.getenv('REMEMBER_WEB_COOKIE', '')
            self.log(f"🔑 使用 Secrets 初始 Cookie (前8位: {self.current_cookie[:8]})")

    def log(self, msg):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

    def send_tg_notification(self, message):
        if not self.tg_token or not self.tg_chat_id: return
        url = f"https://api.telegram.org/bot{self.tg_token}/sendMessage"
        for i in range(3):
            try:
                res = requests.post(url, json={"chat_id": self.tg_chat_id, "text": message, "parse_mode": "Markdown"}, timeout=30)
                if res.status_code == 200: return
            except: time.sleep(5)

    def get_remaining_days(self, page):
        try:
            # 增加对日期元素的显式等待
            target = page.get_by_text(re.compile(r"202\d-\d{2}-\d{2}")).first
            target.wait_for(state="visible", timeout=10000)
            raw_text = target.inner_text()
            match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', raw_text)
            if match:
                expiry_date = datetime.strptime(match.group(1), '%Y-%m-%d %H:%M:%S')
                return (expiry_date - datetime.now()).days, expiry_date
        except: pass
        return None, None

    def run(self):
        with sync_playwright() as p:
            self.log("🌐 启动浏览器...")
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={'width': 1280, 'height': 800}
            )
            context.add_cookies([{
                'name': self.cookie_name, 'value': self.current_cookie,
                'domain': 'hub.weirdhost.xyz', 'path': '/',
                'expires': int(time.time()) + 31536000,
                'httpOnly': True, 'secure': True, 'sameSite': 'Lax'
            }])
            page = context.new_page()
            
            for url in self.server_urls:
                srv_id = url.split('/')[-1]
                try:
                    self.log(f"\n🚀 访问目标: {url}")
                    # 使用 domcontentloaded 提高兼容性
                    page.goto(url, wait_until="domcontentloaded", timeout=60000)
                    page.wait_for_timeout(8000) 
                    
                    self.log(f"🔗 当前页面 URL: {page.url}")
                    
                    # 诊断：是否被重定向到登录页
                    if "login" in page.url.lower():
                        self.log("❌ 警告: 页面被重定向至登录页，Cookie 可能已失效！")
                        page.screenshot(path=f"login_detected_{srv_id}.png")
                        self.results.append(f"🖥 `Server:{srv_id}`\n🚫 *Cookie 已失效*，请重新获取。")
                        continue

                    # 1. 检测时间
                    days_left, expiry_date = self.get_remaining_days(page)
                    
                    if days_left is not None:
                        time_str = expiry_date.strftime('%Y-%m-%d %H:%M')
                        self.log(f"📅 剩余 {days_left} 天 (到期: {time_str})")
                        if days_left > 6:
                            self.log("✅ 剩余时间充裕，跳过操作。")
                            self.results.append(f"🖥 `Server:{srv_id}`\n📅 到期:{time_str}\n✅ 剩余{days_left}天，无需操作")
                            continue
                    
                    # 2. 尝试寻找按钮
                    self.log("🖱️ 正在寻找续期按钮...")
                    renew_btn = page.locator("button:has-text('시간추가')").first
                    if not renew_btn.is_visible():
                        renew_btn = page.locator("button.bkrtgq").first

                    if renew_btn.is_visible():
                        self.log("🔘 点击按钮并检查验证码...")
                        renew_btn.click()
                        page.wait_for_timeout(5000)
                        # ... (续期逻辑保持不变) ...
                    else:
                        self.log("⏭️ 无法定位到按钮，保存截图...")
                        page.screenshot(path=f"missing_btn_{srv_id}.png")
                        self.results.append(f"🖥 `Server:{srv_id}`\n❓ 未发现续期按钮，请检查截图。")

                except Exception as e:
                    self.log(f"💥 异常: {e}")
                    page.screenshot(path=f"exception_{srv_id}.png")
                    self.results.append(f"🖥 `Server:{srv_id}`\n💥 异常: {str(e)[:40]}")

            # 检查 Cookie 变化并保存 (逻辑不变)
            for ck in context.cookies():
                if ck['name'] == self.cookie_name and ck['value'] != self.current_cookie:
                    with open(self.cookie_file, "w") as f: f.write(ck['value'])
                    self.results.append("🔄 *Cookie 已自动更新并保存*")

            browser.close()
            if self.results:
                self.send_tg_notification("🤖 *Weirdhost 调试报告*\n\n" + "\n\n".join(self.results))
