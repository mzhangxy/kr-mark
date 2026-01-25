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
            self.log(f"📸 截图存证: {filename}")
        except: pass

    def is_cf_shield_present(self, page):
        return "Verify you are human" in page.content() or page.locator("iframe[src*='challenges']").count() > 0

    def apply_stealth(self, page):
        """抹除自动化特征脚本"""
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.chrome = {runtime: {}};
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
        """)

    def solve_turnstile_and_jump(self, page, target_url):
        """核心：破盾后暴力跳转"""
        try:
            self.log("🛡️ 请求 2Captcha 破解...")
            res_submit = requests.post("https://2captcha.com/in.php", data={
                'key': self.api_key, 'method': 'turnstile', 'sitekey': self.sitekey,
                'pageurl': page.url, 'json': 1
            }).json()
            if res_submit.get("status") != 1: return False
            
            task_id = res_submit.get("request")
            for _ in range(40):
                time.sleep(5)
                res_get = requests.get(f"https://2captcha.com/res.php?key={self.api_key}&action=get&id={task_id}&json=1").json()
                if res_get.get("status") == 1:
                    token = res_get.get("request")
                    self.log("✅ Token 已获取，尝试注入并跳转...")
                    # 注入 Token
                    page.evaluate(f'document.querySelector("[name=cf-turnstile-response]").value = "{token}";')
                    # 尝试触发所有已知回调
                    page.evaluate('if (typeof cfCallback === "function") { cfCallback(); }')
                    # 关键补丁：如果 5秒内没自动跳，强行执行 JS 跳转
                    time.sleep(5)
                    if self.is_cf_shield_present(page):
                        self.log("🚀 盾牌未消失，强制重定向跳转...")
                        page.evaluate(f'window.location.href = "{target_url}";')
                    return True
        except: pass
        return False

    def run(self):
        with sync_playwright() as p:
            self.log("🌐 启动 Chromium...")
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
                viewport={'width': 1280, 'height': 800}
            )
            
            # 注入 stealth 脚本
            page = context.new_page()
            self.apply_stealth(page)

            context.add_cookies([{
                'name': self.cookie_name, 'value': self.current_cookie,
                'domain': 'hub.weirdhost.xyz', 'path': '/',
                'expires': int(time.time()) + 31536000,
                'httpOnly': True, 'secure': True, 'sameSite': 'Lax'
            }])
            
            for url in self.server_urls:
                srv_id = url.split('/')[-1]
                try:
                    self.log(f"\n🚀 任务开始: {url}")
                    page.goto(url, wait_until="domcontentloaded", timeout=60000)
                    time.sleep(8) # 等待 CF 盾牌渲染完成

                    if self.is_cf_shield_present(page):
                        self.log("🛡️ 检测到 Cloudflare，正在破盾...")
                        self.solve_turnstile_and_jump(page, url)
                        time.sleep(10)

                    self.log(f"🔗 落地 URL: {page.url}")
                    
                    # 检查是否成功进入后台
                    if self.is_cf_shield_present(page):
                        self.log("❌ 依旧卡在盾牌页。")
                        self.safe_screenshot(page, f"STUCK_AT_SHIELD_{srv_id}")
                    
                    # 查找按钮和时间
                    try:
                        renew_btn = page.locator("button:has-text('시간추가')").first
                        if renew_btn.is_visible():
                            self.log("🔘 发现按钮，点击续期...")
                            renew_btn.click()
                            time.sleep(5)
                            # 点击后续发的盾
                            if self.is_cf_shield_present(page):
                                self.solve_turnstile_and_jump(page, url)
                            self.results.append(f"🖥 `Server:{srv_id}`\n🎉 续期完成")
                        else:
                            self.log("⏭️ 未发现按钮，尝试解析时间...")
                            target = page.get_by_text(re.compile(r"202\d-\d{2}-\d{2}")).first
                            if target.is_visible():
                                self.results.append(f"🖥 `Server:{srv_id}`\n✅ 时间充裕，跳过")
                            else:
                                self.safe_screenshot(page, f"FINAL_FAIL_{srv_id}")
                                self.results.append(f"🖥 `Server:{srv_id}`\n❓ 解析失败")
                    except:
                        self.results.append(f"🖥 `Server:{srv_id}`\n💥 识别过程异常")

                except Exception as e:
                    self.log(f"💥 运行时异常: {e}")

            browser.close()
            if self.results:
                msg = "🤖 *Weirdhost 终极测试报告*\n\n" + "\n\n".join(self.results)
                requests.post(f"https://api.telegram.org/bot{self.tg_token}/sendMessage", 
                             json={"chat_id": self.tg_chat_id, "text": msg, "parse_mode": "Markdown"})

if __name__ == "__main__":
    bot = WeirdhostUltimate()
    bot.run()
