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

        for i in range(3):  # 最多尝试 3 次
            try:
                # 增加 timeout 到 30 秒以应对网络波动
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
            # 增加显式等待，确保日期文字渲染完成
            target = page.get_by_text(re.compile(r"202\d-\d{2}-\d{2}")).first
            target.wait_for(state="visible", timeout=15000)
            
            raw_text = target.inner_text()
            match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', raw_text)
            if match:
                expiry_date = datetime.strptime(match.group(1), '%Y-%m-%d %H:%M:%S')
                now = datetime.now()
                delta = expiry_date - now
                return delta.days, expiry_date
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

    def run(self):
        with sync_playwright() as p:
            print("🌐 启动浏览器...")
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={'width': 1280, 'height': 800}
            )
            
            # 注入 Cookie
            context.add_cookies([{
                'name': 'remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d',
                'value': self.cookie_value,
                'domain': 'hub.weirdhost.xyz',
                'path': '/',
                'expires': int(time.time()) + 31536000,
                'httpOnly': True, 'secure': True, 'sameSite': 'Lax'
            }])

            page = context.new_page()
            
            for url in self.server_urls:
                srv_id = url.split('/')[-1]
                try:
                    print(f"\n🚀 目标服务器: {url}")
                    page.goto(url, wait_until="networkidle", timeout=60000)
                    page.wait_for_timeout(5000) 

                    # 1. 检查到期时间
                    days_left, expiry_date = self.get_remaining_days(page)
                    time_str = expiry_date.strftime('%Y-%m-%d') if expiry_date else "未知"
                    
                    if days_left is not None:
                        print(f"📅 到期: {time_str}, 剩余: {days_left}天")
                        if days_left > 6:
                            print("✅ 剩余时间充裕，跳过续期。")
                            self.results.append(f"🖥 `Server:{srv_id}`\n📅 到期:{time_str}\n✅ 剩余{days_left}天，无需操作")
                            continue
                    
                    # 2. 点击续期按钮 (优先匹配图片中的文字 "시간추가")
                    renew_btn = page.locator("button:has-text('시간추가')").first
                    if not renew_btn.is_visible():
                        renew_btn = page.locator("button.bkrtgq").first # 备用定位

                    if renew_btn.is_visible():
                        print("🖱️ 找到续期按钮，执行点击...")
                        renew_btn.click()
                        page.wait_for_timeout(3000) 
                        
                        if page.locator("[name='cf-turnstile-response']").count() > 0:
                            if self.solve_turnstile(page):
                                page.wait_for_timeout(7000)
                                self.results.append(f"🖥 `Server:{srv_id}`\n📅 到期:{time_str}\n🎉 续期操作成功 (已破盾)")
                            else:
                                self.results.append(f"🖥 `Server:{srv_id}`\n❌ 验证码破解失败")
                        else:
                            self.results.append(f"🖥 `Server:{srv_id}`\n✅ 续期完成 (免验证)")
                    else:
                        print("⏭️ 未找到续期按钮。")
                        page.screenshot(path=f"missing_btn_{srv_id}.png")
                        self.results.append(f"🖥 `Server:{srv_id}`\n❌ 未找到续期按钮 (已截图)")
                        
                except Exception as e:
                    print(f"💥 运行异常: {e}")
                    self.results.append(f"🖥 `Server:{srv_id}`\n💥 异常: {str(e)[:50]}")
            
            browser.close()
            
            if self.results:
                report = "🤖 *Weirdhost 自动续期报告*\n\n" + "\n\n".join(self.results)
                self.send_tg_notification(report)

if __name__ == "__main__":
    bot = WeirdhostUltimate()
    bot.run()
