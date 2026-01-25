import os
import time
import re
import requests
from datetime import datetime
from playwright.sync_api import sync_playwright

class WeirdhostUltimate:
    def __init__(self):
        # 基础配置
        self.api_key = os.getenv('TWOCAPTCHA_API_KEY')
        self.tg_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.tg_chat_id = os.getenv('TELEGRAM_CHAT_ID')
        self.server_urls = [url.strip() for url in os.getenv('WEIRDHOST_SERVER_URLS', '').split(',') if url.strip()]
        self.sitekey = "0x4AAAAAACJH5atUUlnM2w2u"
        
        self.cookie_file = "session_cookie.txt"
        self.cookie_name = 'remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d'
        self.results = []
        self.base_path = os.path.dirname(os.path.abspath(__file__))
        
        # 加载 Cookie
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

    def safe_screenshot(self, page, name):
        filename = f"{name}_{int(time.time())}.png"
        path = os.path.join(self.base_path, filename)
        try:
            page.screenshot(path=path, full_page=True)
            self.log(f"📸 诊断截图已保存: {path}")
        except Exception as e:
            self.log(f"⚠️ 截图失败: {e}")

    def get_remaining_days(self, page):
        try:
            # 这里的正则匹配截图中的日期格式
            target = page.get_by_text(re.compile(r"202\d-\d{2}-\d{2}")).first
            target.wait_for(state="visible", timeout=10000)
            raw_text = target.inner_text()
            self.log(f"📄 提取到文本: {raw_text}")
            match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', raw_text)
            if match:
                expiry_date = datetime.strptime(match.group(1), '%Y-%m-%d %H:%M:%S')
                days = (expiry_date - datetime.now()).days
                return days, expiry_date
        except: pass
        return None, None

    def solve_turnstile(self, page):
        """破解 Cloudflare Turnstile"""
        self.log("🛡️ 正在通过 2captcha 破解挑战盾...")
        try:
            in_res = requests.post("https://2captcha.com/in.php", data={
                'key': self.api_key, 'method': 'turnstile', 'sitekey': self.sitekey,
                'pageurl': page.url, 'json': 1
            }).json()
            if in_res.get("status") != 1: 
                self.log(f"❌ 2Captcha 任务创建失败: {in_res.get('request')}")
                return False
            
            task_id = in_res.get("request")
            for _ in range(40): # 延长等待时间
                time.sleep(5)
                res = requests.get(f"https://2captcha.com/res.php?key={self.api_key}&action=get&id={task_id}&json=1").json()
                if res.get("status") == 1:
                    token = res.get("request")
                    self.log("✅ 破解成功，正在提交验证...")
                    # 针对进门盾和按钮盾的通用注入
                    page.evaluate(f'document.querySelector("[name=cf-turnstile-response]").value = "{token}";')
                    # 尝试触发回调，不同页面回调函数名可能不同
                    page.evaluate('if (typeof cfCallback === "function") { cfCallback(); }')
                    page.evaluate('if (typeof turnstileCallback === "function") { turnstileCallback(); }')
                    return True
                if res.get("request") == "CAPCHA_NOT_READY": continue
                break
        except Exception as e:
            self.log(f"💥 破解逻辑异常: {e}")
        return False

    def run(self):
        with sync_playwright() as p:
            self.log("🌐 启动浏览器...")
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
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
                    self.log(f"\n🚀 目标: {url}")
                    page.goto(url, wait_until="domcontentloaded", timeout=60000)
                    page.wait_for_timeout(5000) 

                    # --- 核心修改：检测开门盾 ---
                    if page.locator("iframe[src*='challenges']").count() > 0 or "Verify you are human" in page.content():
                        self.log("🛡️ 检测到访问被 Cloudflare 拦截，正在破盾...")
                        if self.solve_turnstile(page):
                            self.log("✅ 破盾成功，等待页面跳转中...")
                            page.wait_for_timeout(10000) 
                        else:
                            self.log("❌ 无法通过访问拦截")
                            self.safe_screenshot(page, f"CF_FAIL_{srv_id}")
                            continue

                    self.log(f"🔗 落地 URL: {page.url}")
                    
                    # 检查是否重定向到登录页
                    if "login" in page.url.lower():
                        self.log("❌ Cookie 已失效！")
                        self.results.append(f"🖥 `Server:{srv_id}`\n🚫 *Cookie 已失效*")
                        continue

                    # 1. 检查天数
                    days_left, expiry_date = self.get_remaining_days(page)
                    if days_left is not None:
                        time_str = expiry_date.strftime('%Y-%m-%d %H:%M')
                        if days_left > 6:
                            self.results.append(f"🖥 `Server:{srv_id}`\n📅 到期:{time_str}\n✅ 剩余{days_left}天，跳过")
                            continue
                    
                    # 2. 续期按钮
                    self.log("🖱️ 查找续期按钮...")
                    renew_btn = page.locator("button:has-text('시간추가')").first
                    if renew_btn.is_visible():
                        renew_btn.click()
                        page.wait_for_timeout(5000)
                        # 如果点击后还有盾，再次破解
                        if page.locator("[name='cf-turnstile-response']").count() > 0:
                            self.solve_turnstile(page)
                            page.wait_for_timeout(8000)
                        self.results.append(f"🖥 `Server:{srv_id}`\n🎉 续期操作执行完毕")
                    else:
                        self.safe_screenshot(page, f"NOT_FOUND_{srv_id}")
                        self.results.append(f"🖥 `Server:{srv_id}`\n❓ 未发现续期按钮")

                except Exception as e:
                    self.log(f"💥 异常: {e}")
                    self.results.append(f"🖥 `Server:{srv_id}`\n💥 异常")

            # 3. Cookie 同步
            for ck in context.cookies():
                if ck['name'] == self.cookie_name and ck['value'] != self.current_cookie:
                    with open(os.path.join(self.base_path, self.cookie_file), "w") as f:
                        f.write(ck['value'])
                    self.results.append("🔄 *Cookie 已更新同步*")

            browser.close()
            if self.results:
                self.send_tg_notification("🤖 *Weirdhost 运行报告*\n\n" + "\n\n".join(self.results))

if __name__ == "__main__":
    bot = WeirdhostUltimate()
    bot.run()
