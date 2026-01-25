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
        """检查页面是否处于 CF 验证状态"""
        return "Verify you are human" in page.content() or page.locator("iframe[src*='challenges']").count() > 0

    def handle_cf_shield(self, page, srv_id):
        """分阶段攻克 CF 盾"""
        if not self.is_cf_shield_present(page):
            return True

        self.log("🛡️ 发现 Cloudflare 挑战，先等待 8s (尝试自动放行)...")
        time.sleep(8)
        
        if not self.is_cf_shield_present(page):
            self.log("✅ 自动过盾成功。")
            return True

        self.log("🛡️ 自动过盾失败，调用 2Captcha API 破盾...")
        if self.solve_turnstile_api(page):
            self.log("⏳ Token 已注入，等待 12s 校验并尝试强刷...")
            time.sleep(12)
            
            # 如果还在盾牌页，强制刷新
            if self.is_cf_shield_present(page):
                self.log("🔄 页面未响应，强制刷新以应用 Session...")
                page.reload(wait_until="domcontentloaded")
                time.sleep(8)
            
            return not self.is_cf_shield_present(page)
        return False

    def solve_turnstile_api(self, page):
        """通过 API 破解并在页面上执行模拟点击"""
        try:
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
                    # 1. 注入 Token
                    page.evaluate(f'document.querySelector("[name=cf-turnstile-response]").value = "{token}";')
                    # 2. 模拟点击验证框中心 (这是物理过盾的关键)
                    try:
                        box = page.locator("iframe[src*='challenges']").bounding_box()
                        if box:
                            page.mouse.click(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
                    except: pass
                    # 3. 尝试所有已知回调
                    page.evaluate('''() => {
                        const callbacks = ['cfCallback', 'turnstileCallback', 'onSuccess'];
                        callbacks.forEach(cb => { if (window[cb]) window[cb](); });
                    }''')
                    return True
        except: pass
        return False

    def run(self):
        with sync_playwright() as p:
            self.log("🌐 启动 Chromium...")
            browser = p.chromium.launch(headless=True)
            # 使用较新的 UA 减少被针对几率
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
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
                    self.log(f"\n🚀 任务开始: {url}")
                    page.goto(url, wait_until="domcontentloaded", timeout=60000)
                    
                    # 多次尝试破盾，直到进入后台或失败
                    for i in range(2):
                        if not self.handle_cf_shield(page, srv_id):
                            self.log(f"🛡️ 破盾第 {i+1} 次尝试失败")
                        else: break

                    self.log(f"🔗 落地 URL: {page.url}")
                    
                    # 检查天数和续期按钮
                    try:
                        # 只要看到 202x 年份就说明进去了
                        target = page.get_by_text(re.compile(r"202\d-\d{2}-\d{2}")).first
                        target.wait_for(state="visible", timeout=10000)
                        raw_text = target.inner_text()
                        match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', raw_text)
                        if match:
                            expiry_date = datetime.strptime(match.group(1), '%Y-%m-%d %H:%M:%S')
                            days = (expiry_date - datetime.now()).days
                            if days > 6:
                                self.results.append(f"🖥 `Server:{srv_id}`\n📅 剩余{days}天，跳过")
                                continue
                    except:
                        self.log("🤔 没看清时间，直接尝试找续期按钮...")

                    # 寻找按钮
                    renew_btn = page.locator("button:has-text('시간추가')").first
                    if not renew_btn.is_visible():
                        renew_btn = page.locator("button.bkrtgq").first

                    if renew_btn.is_visible():
                        self.log("🔘 点击续期按钮...")
                        renew_btn.click()
                        time.sleep(5)
                        # 点击后若又出盾，再次处理
                        self.handle_cf_shield(page, srv_id)
                        self.results.append(f"🖥 `Server:{srv_id}`\n🎉 续期成功")
                    else:
                        self.log("❌ 最终未发现按钮，保存截图。")
                        self.safe_screenshot(page, f"FINAL_FAIL_{srv_id}")
                        self.results.append(f"🖥 `Server:{srv_id}`\n❓ 失败：未加载出后台界面")

                except Exception as e:
                    self.log(f"💥 运行时异常: {e}")
                    self.results.append(f"🖥 `Server:{srv_id}`\n💥 异常退出")

            # 同步最新 Cookie
            for ck in context.cookies():
                if ck['name'] == self.cookie_name and ck['value'] != self.current_cookie:
                    with open(os.path.join(self.base_path, self.cookie_file), "w") as f:
                        f.write(ck['value'])
                    self.results.append("🔄 *Cookie 已动态更新*")

            browser.close()
            if self.results:
                msg = "🤖 *Weirdhost 续期报告*\n\n" + "\n\n".join(self.results)
                requests.post(f"https://api.telegram.org/bot{self.tg_token}/sendMessage", 
                             json={"chat_id": self.tg_chat_id, "text": msg, "parse_mode": "Markdown"})

if __name__ == "__main__":
    bot = WeirdhostUltimate()
    bot.run()
