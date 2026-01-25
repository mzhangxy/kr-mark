import os
import time
import re
import requests
from datetime import datetime
from playwright.sync_api import sync_playwright

class WeirdhostUltimate:
    def __init__(self):
        # 基础配置获取
        self.api_key = os.getenv('TWOCAPTCHA_API_KEY')
        self.tg_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.tg_chat_id = os.getenv('TELEGRAM_CHAT_ID')
        self.server_urls = [url.strip() for url in os.getenv('WEIRDHOST_SERVER_URLS', '').split(',') if url.strip()]
        self.sitekey = "0x4AAAAAACJH5atUUlnM2w2u"
        
        self.cookie_file = "session_cookie.txt"
        self.cookie_name = 'remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d'
        self.results = []
        
        # 确定当前绝对路径，确保文件保存位置可控
        self.base_path = os.path.dirname(os.path.abspath(__file__))
        
        # 加载 Cookie 逻辑
        if os.path.exists(self.cookie_file):
            with open(self.cookie_file, "r") as f:
                self.current_cookie = f.read().strip()
                self.log(f"📂 使用本地文件 Cookie (前8位: {self.current_cookie[:8]})")
        else:
            self.current_cookie = os.getenv('REMEMBER_WEB_COOKIE', '')
            self.log(f"🔑 使用 Secrets 初始 Cookie (前8位: {self.current_cookie[:8]})")

    def log(self, msg):
        """带时间戳的增强日志"""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

    def send_tg_notification(self, message):
        """带重试的 TG 发送"""
        if not self.tg_token or not self.tg_chat_id: return
        url = f"https://api.telegram.org/bot{self.tg_token}/sendMessage"
        for i in range(3):
            try:
                res = requests.post(url, json={"chat_id": self.tg_chat_id, "text": message, "parse_mode": "Markdown"}, timeout=30)
                if res.status_code == 200: 
                    self.log("✅ TG 报告发送成功")
                    return
            except: time.sleep(5)
        self.log("❌ TG 报告最终发送失败")

    def safe_screenshot(self, page, name):
        """确保截图保存成功并打印路径"""
        filename = f"{name}_{int(time.time())}.png"
        path = os.path.join(self.base_path, filename)
        try:
            page.screenshot(path=path, full_page=True)
            self.log(f"📸 诊断截图已保存: {path}")
        except Exception as e:
            self.log(f"⚠️ 截图失败: {e}")

    def get_remaining_days(self, page):
        """时间解析逻辑"""
        try:
            # 等待包含年份的文本出现
            target = page.get_by_text(re.compile(r"202\d-\d{2}-\d{2}")).first
            target.wait_for(state="visible", timeout=10000)
            raw_text = target.inner_text()
            self.log(f"📄 提取到文本: {raw_text}")
            match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', raw_text)
            if match:
                expiry_date = datetime.strptime(match.group(1), '%Y-%m-%d %H:%M:%S')
                days = (expiry_date - datetime.now()).days
                return days, expiry_date
        except Exception as e:
            self.log(f"⚠️ 时间定位超时或失败: {e}")
        return None, None

    def solve_turnstile(self, page):
        """2Captcha 破盾逻辑"""
        self.log("🛡️ 正在请求 2captcha 破解挑战...")
        try:
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
        except: pass
        return False

    def run(self):
        with sync_playwright() as p:
            self.log("🌐 启动 Chromium 浏览器...")
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
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
                    self.log(f"\n🚀 访问服务器详情: {url}")
                    # 使用 domcontentloaded 配合强制等待，防止 networkidle 超时
                    page.goto(url, wait_until="domcontentloaded", timeout=60000)
                    page.wait_for_timeout(10000) 
                    
                    self.log(f"🔗 最终落地 URL: {page.url}")
                    
                    # 诊断：是否跳到了登录页
                    if "login" in page.url.lower():
                        self.log("❌ 严重警告: Cookie 已失效，页面被重定向至登录页！")
                        self.safe_screenshot(page, f"LOGIN_EXPIRED_{srv_id}")
                        self.results.append(f"🖥 `Server:{srv_id}`\n🚫 *Cookie 已失效*，请更新 Secret。")
                        continue

                    # 1. 检查时间
                    days_left, expiry_date = self.get_remaining_days(page)
                    
                    if days_left is not None:
                        time_str = expiry_date.strftime('%Y-%m-%d %H:%M')
                        self.log(f"📅 状态: 剩余 {days_left} 天 (到期: {time_str})")
                        if days_left > 6:
                            self.log("✅ 剩余天数 > 6，无需操作。")
                            self.results.append(f"🖥 `Server:{srv_id}`\n📅 到期:{time_str}\n✅ 剩余{days_left}天，无需操作")
                            continue
                    else:
                        self.log("⚠️ 无法识别时间，保存截图检查页面状态...")
                        self.safe_screenshot(page, f"TIME_PARSE_FAIL_{srv_id}")

                    # 2. 寻找续期按钮
                    self.log("🖱️ 正在寻找续期按钮 '시간추가'...")
                    renew_btn = page.locator("button:has-text('시간추가')").first
                    if not renew_btn.is_visible():
                        renew_btn = page.locator("button.bkrtgq").first

                    if renew_btn.is_visible():
                        self.log("🔘 找到按钮，准备点击...")
                        renew_btn.click()
                        page.wait_for_timeout(5000)
                        
                        if page.locator("[name='cf-turnstile-response']").count() > 0:
                            self.log("🕒 检测到验证码，开始破解...")
                            if self.solve_turnstile(page):
                                page.wait_for_timeout(8000)
                                self.log("🎉 续期流程执行完毕。")
                                self.results.append(f"🖥 `Server:{srv_id}`\n🎉 续期操作成功 (已破盾)")
                                self.safe_screenshot(page, f"SUCCESS_{srv_id}")
                            else:
                                self.results.append(f"🖥 `Server:{srv_id}`\n❌ 验证码破解失败")
                        else:
                            self.log("ℹ️ 免验证续期或已点击。")
                            self.results.append(f"🖥 `Server:{srv_id}`\n✅ 续期完成 (免验证)")
                    else:
                        self.log("⏭️ 未发现续期按钮。")
                        self.safe_screenshot(page, f"MISSING_BTN_{srv_id}")
                        self.results.append(f"🖥 `Server:{srv_id}`\n❓ 未发现续期按钮")

                except Exception as e:
                    self.log(f"💥 异常: {e}")
                    self.safe_screenshot(page, f"ERROR_{srv_id}")
                    self.results.append(f"🖥 `Server:{srv_id}`\n💥 异常: {str(e)[:40]}")

            # 3. 检查 Cookie 更新
            for ck in context.cookies():
                if ck['name'] == self.cookie_name and ck['value'] != self.current_cookie:
                    self.log("🔄 检测到 Cookie 刷新，保存至本地...")
                    with open(os.path.join(self.base_path, self.cookie_file), "w") as f:
                        f.write(ck['value'])
                    self.results.append("🔄 *Cookie 已自动同步*")

            browser.close()
            if self.results:
                report = "🤖 *Weirdhost 自动续期报告*\n\n" + "\n\n".join(self.results)
                self.send_tg_notification(report)

if __name__ == "__main__":
    bot = WeirdhostUltimate()
    bot.run()
