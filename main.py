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
        
        # 优先级：本地文件 > 环境变量
        if os.path.exists(self.cookie_file):
            with open(self.cookie_file, "r") as f:
                self.current_cookie = f.read().strip()
                self.log(f"📂 从本地文件加载 Cookie (前8位: {self.current_cookie[:8]})")
        else:
            self.current_cookie = os.getenv('REMEMBER_WEB_COOKIE')
            self.log(f"🔑 从 Secrets 加载初始 Cookie (前8位: {self.current_cookie[:8]})")

    def log(self, msg):
        now = datetime.now().strftime("%H:%M:%S")
        print(f"[{now}] {msg}")

    def send_tg_notification(self, message):
        if not self.tg_token or not self.tg_chat_id:
            self.log("⚠️ 未配置 TG Token，跳过通知。")
            return
        url = f"https://api.telegram.org/bot{self.tg_token}/sendMessage"
        payload = {"chat_id": self.tg_chat_id, "text": message, "parse_mode": "Markdown"}
        for i in range(3):
            try:
                response = requests.post(url, json=payload, timeout=30)
                if response.status_code == 200:
                    self.log("✅ TG 通知发送成功！")
                    return
                self.log(f"⚠️ TG 响应异常 (尝试 {i+1}/3): {response.status_code}")
            except Exception as e:
                self.log(f"❌ 第 {i+1} 次发送 TG 通知失败: {e}")
                time.sleep(5)

    def get_remaining_days(self, page):
        try:
            self.log("🕵️ 正在查找日期元素...")
            target = page.get_by_text(re.compile(r"202\d-\d{2}-\d{2}")).first
            target.wait_for(state="visible", timeout=15000)
            raw_text = target.inner_text()
            self.log(f"📄 原始文本: {raw_text}")
            match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', raw_text)
            if match:
                expiry_date = datetime.strptime(match.group(1), '%Y-%m-%d %H:%M:%S')
                days = (expiry_date - datetime.now()).days
                return days, expiry_date
        except Exception as e:
            self.log(f"⚠️ 时间解析异常: {e}")
        return None, None

    def solve_turnstile(self, page):
        self.log("🛡️ 正在请求 2captcha 破解...")
        in_res = requests.post("https://2captcha.com/in.php", data={
            'key': self.api_key, 'method': 'turnstile', 'sitekey': self.sitekey,
            'pageurl': page.url, 'json': 1
        }).json()
        if in_res.get("status") != 1:
            self.log(f"❌ 2captcha 提交失败: {in_res.get('request')}")
            return False
        task_id = in_res.get("request")
        for _ in range(30):
            time.sleep(5)
            res = requests.get(f"https://2captcha.com/res.php?key={self.api_key}&action=get&id={task_id}&json=1").json()
            if res.get("status") == 1:
                token = res.get("request")
                self.log("✅ 破解成功，注入 Token...")
                page.evaluate(f'document.querySelector("[name=cf-turnstile-response]").value = "{token}";')
                page.evaluate('if (typeof cfCallback === "function") { cfCallback(); }')
                return True
            if res.get("request") != "CAPCHA_NOT_READY": break
        return False

    def run(self):
        with sync_playwright() as p:
            self.log("🌐 启动 Chromium...")
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
                # 尝试次数
                max_retries = 2
                for attempt in range(max_retries):
                    try:
                        self.log(f"\n🚀 目标: {url} (尝试 {attempt + 1}/{max_retries})")
                        # 降低等待级别，增加容错
                        page.goto(url, wait_until="domcontentloaded", timeout=60000)
                        self.log("⏳ 页面基础 HTML 已加载，等待渲染...")
                        page.wait_for_timeout(8000) # 强制等待 8 秒确保 JS 执行完毕

                        # 1. 检测时间
                        days_left, expiry_date = self.get_remaining_days(page)
                        if days_left is None and expiry_date is None:
                            # 如果没认出时间，可能是没加载完，再多等几秒
                            self.log("🤔 未识别到时间，尝试额外等待...")
                            page.wait_for_timeout(5000)
                            days_left, expiry_date = self.get_remaining_days(page)

                        time_str = expiry_date.strftime('%Y-%m-%d %H:%M') if expiry_date else "未知"
                        
                        if days_left is not None:
                            self.log(f"📅 剩余 {days_left} 天 (到期: {time_str})")
                            if days_left > 6:
                                self.log("✅ 时间充足，跳过续期。")
                                self.results.append(f"🖥 `Server:{srv_id}`\n📅 到期:{time_str}\n✅ 剩余{days_left}天，无需操作")
                                break # 成功处理，跳出重试循环
                        
                        # 2. 定位并点击续期按钮
                        self.log("🖱️ 正在定位 '시간추가' 按钮...")
                        renew_btn = page.locator("button:has-text('시간추가')").first
                        if not renew_btn.is_visible():
                            renew_btn = page.locator("button.bkrtgq").first

                        if renew_btn.is_visible():
                            self.log("🔘 点击按钮...")
                            renew_btn.click()
                            page.wait_for_timeout(3000) 
                            if page.locator("[name='cf-turnstile-response']").count() > 0:
                                self.log("🕒 触发验证码破解...")
                                if self.solve_turnstile(page):
                                    page.wait_for_timeout(7000)
                                    self.log("🎉 续期指令发送完成。")
                                    self.results.append(f"🖥 `Server:{srv_id}`\n📅 到期:{time_str}\n🎉 续期操作成功")
                            else:
                                self.results.append(f"🖥 `Server:{srv_id}`\n✅ 续期完成 (免验证)")
                        else:
                            # 即使没找到按钮，只要识别到了时间且>6天，逻辑其实也是对的
                            # 但如果没识别到时间也找不到按钮，就需要截图诊断
                            self.log("⏭️ 未找到按钮，截图诊断。")
                            page.screenshot(path=f"diag_{srv_id}_{int(time.time())}.png")
                            self.results.append(f"🖥 `Server:{srv_id}`\n❌ 未找到续期按钮 (已截图诊断)")
                        
                        break # 成功完成本服务器逻辑，跳出重试循环

                    except Exception as e:
                        self.log(f"💥 第 {attempt + 1} 次尝试失败: {e}")
                        # 异常时立即截图
                        diag_path = f"error_{srv_id}_retry_{attempt+1}.png"
                        page.screenshot(path=diag_path)
                        self.log(f"📸 已保存异常截图: {diag_path}")
                        
                        if attempt == max_retries - 1:
                            self.results.append(f"🖥 `Server:{srv_id}`\n💥 访问超时/异常: {str(e)[:40]}")

            # --- 检查并保存新 Cookie ---
            self.log("\n🔍 检查 Cookie 变化...")
            for ck in context.cookies():
                if ck['name'] == self.cookie_name:
                    if ck['value'] != self.current_cookie:
                        self.log("🔄 发现新 Cookie，写入文件...")
                        with open(self.cookie_file, "w") as f:
                            f.write(ck['value'])
                        self.results.append(f"🔄 *Cookie 已更新并保存到本地*")
                    else:
                        self.log("✅ Cookie 无需更新。")
            
            browser.close()
            if self.results:
                report = "🤖 *Weirdhost 调试报告*\n\n" + "\n\n".join(self.results)
                self.send_tg_notification(report)

if __name__ == "__main__":
    bot = WeirdhostUltimate()
    bot.run()
