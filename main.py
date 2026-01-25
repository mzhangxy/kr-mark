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
        self.base_path = os.path.dirname(os.path.abspath(__file__))
        
        if os.path.exists(self.cookie_file):
            with open(self.cookie_file, "r") as f:
                self.current_cookie = f.read().strip()
                self.log(f"📂 加载本地 Cookie (前8位: {self.current_cookie[:8]})")
        else:
            self.current_cookie = os.getenv('REMEMBER_WEB_COOKIE', '')
            self.log(f"🔑 加载 Secrets Cookie (前8位: {self.current_cookie[:8]})")

    def log(self, msg):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

    def safe_screenshot(self, page, name):
        filename = f"{name}_{int(time.time())}.png"
        path = os.path.join(self.base_path, filename)
        try:
            page.screenshot(path=path, full_page=True)
            self.log(f"📸 截图已存: {filename}")
        except: pass

    def is_cf_shield_present(self, page):
        """检查是否存在 CF 挑战"""
        return page.locator("iframe[src*='challenges']").count() > 0 or "Verify you are human" in page.content()

    def handle_cf_shield(self, page, srv_id):
        """智能破盾：先等待，后 API"""
        if not self.is_cf_shield_present(page):
            return True

        self.log("🛡️ 检测到 Cloudflare 挑战，尝试等待自动过盾...")
        time.sleep(7) # 按照建议等待 6-7 秒
        
        if not self.is_cf_shield_present(page):
            self.log("✅ 自动过盾成功。")
            return True

        self.log("🛡️ 自动过盾失败，启动 2captcha API 破解...")
        return self.solve_turnstile_api(page)

    def solve_turnstile_api(self, page):
        try:
            in_res = requests.post("https://2captcha.com/in.php", data={
                'key': self.api_key, 'method': 'turnstile', 'sitekey': self.sitekey,
                'pageurl': page.url, 'json': 1
            }).json()
            if in_res.get("status") != 1: return False
            
            task_id = in_res.get("request")
            for _ in range(40):
                time.sleep(5)
                res = requests.get(f"https://2captcha.com/res.php?key={self.api_key}&action=get&id={task_id}&json=1").json()
                if res.get("status") == 1:
                    token = res.get("request")
                    page.evaluate(f'document.querySelector("[name=cf-turnstile-response]").value = "{token}";')
                    page.evaluate('if (typeof cfCallback === "function") { cfCallback(); }')
                    page.evaluate('if (typeof turnstileCallback === "function") { turnstileCallback(); }')
                    self.log("✅ API 破解指令已提交。")
                    return True
        except: pass
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
                    self.log(f"\n🚀 访问: {url}")
                    page.goto(url, wait_until="domcontentloaded", timeout=60000)
                    
                    # 第一次破盾（进门）
                    self.handle_cf_shield(page, srv_id)
                    page.wait_for_timeout(5000)
                    
                    self.log(f"🔗 落地 URL: {page.url}")
                    if "login" in page.url.lower():
                        self.results.append(f"🖥 `Server:{srv_id}`\n🚫 *Cookie 已失效*")
                        continue

                    # 第二次确认（防止跳转后复现盾）
                    if self.is_cf_shield_present(page):
                        self.log("🛡️ 详情页再次出现盾，二次处理...")
                        self.handle_cf_shield(page, srv_id)
                        page.wait_for_timeout(5000)

                    # 1. 识别时间
                    try:
                        target = page.get_by_text(re.compile(r"202\d-\d{2}-\d{2}")).first
                        target.wait_for(state="visible", timeout=8000)
                        raw_text = target.inner_text()
                        match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', raw_text)
                        if match:
                            expiry_date = datetime.strptime(match.group(1), '%Y-%m-%d %H:%M:%S')
                            days_left = (expiry_date - datetime.now()).days
                            time_str = expiry_date.strftime('%Y-%m-%d %H:%M')
                            if days_left > 6:
                                self.results.append(f"🖥 `Server:{srv_id}`\n📅 到期:{time_str}\n✅ 剩余{days_left}天")
                                continue
                    except:
                        self.log("⚠️ 时间识别受阻，尝试直接找按钮...")

                    # 2. 寻找续期按钮
                    renew_btn = page.locator("button:has-text('시간추가')").first
                    if not renew_btn.is_visible():
                        renew_btn = page.locator("button.bkrtgq").first

                    if renew_btn.is_visible():
                        self.log("🔘 点击续期按钮...")
                        renew_btn.click()
                        page.wait_for_timeout(5000)
                        # 点击后的第三次确认（按钮挑战）
                        if self.is_cf_shield_present(page):
                            self.handle_cf_shield(page, srv_id)
                            page.wait_for_timeout(8000)
                        self.results.append(f"🖥 `Server:{srv_id}`\n🎉 续期指令已发出")
                    else:
                        self.log("⏭️ 未发现按钮")
                        self.safe_screenshot(page, f"FINAL_NOT_FOUND_{srv_id}")
                        self.results.append(f"🖥 `Server:{srv_id}`\n❓ 未发现续期按钮")

                except Exception as e:
                    self.log(f"💥 异常: {e}")
                    self.results.append(f"🖥 `Server:{srv_id}`\n💥 异常")

            # Cookie 更新逻辑
            for ck in context.cookies():
                if ck['name'] == self.cookie_name and ck['value'] != self.current_cookie:
                    with open(os.path.join(self.base_path, self.cookie_file), "w") as f:
                        f.write(ck['value'])
                    self.results.append("🔄 *Cookie 已自动同步*")

            browser.close()
            if self.results:
                msg = "🤖 *Weirdhost 续期报告*\n\n" + "\n\n".join(self.results)
                requests.post(f"https://api.telegram.org/bot{self.tg_token}/sendMessage", 
                             json={"chat_id": self.tg_chat_id, "text": msg, "parse_mode": "Markdown"})

if __name__ == "__main__":
    bot = WeirdhostUltimate()
    bot.run()
