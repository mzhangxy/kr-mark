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
        # 使用你截图中最新的 Turnstile Sitekey
        self.sitekey = "0x4AAAAAACJH5atUUlnM2w2u"

    def get_remaining_days(self, page):
        """解析页面上的到期时间并计算剩余天数"""
        try:
            # 定位包含时间格式的元素 (例如: 2026-02-05 ...)
            time_element = page.locator("p:has-text('202')").first
            raw_text = time_element.inner_text().strip()
            
            # 使用正则提取标准时间格式
            match = re.search(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', raw_text)
            if match:
                expiry_date = datetime.strptime(match.group(), '%Y-%m-%d %H:%M:%S')
                now = datetime.now()
                delta = expiry_date - now
                return delta.days, expiry_date
            return None, None
        except Exception as e:
            print(f"⚠️ 无法解析时间: {e}")
            return None, None

    def solve_turnstile(self, page):
        """调用 2captcha 破解"""
        print(f"🛡️ 正在请求 2captcha 破解挑战...")
        in_res = requests.post("https://2captcha.com/in.php", data={
            'key': self.api_key,
            'method': 'turnstile',
            'sitekey': self.sitekey,
            'pageurl': page.url,
            'json': 1
        }).json()

        if in_res.get("status") != 1:
            print(f"❌ 2captcha 提交失败: {in_res.get('request')}")
            return False

        task_id = in_res.get("request")
        for _ in range(25):
            time.sleep(5)
            res = requests.get(f"https://2captcha.com/res.php?key={self.api_key}&action=get&id={task_id}&json=1").json()
            if res.get("status") == 1:
                token = res.get("request")
                print("✅ 验证码已破解，正在注入...")
                # 注入 Token 
                page.evaluate(f'document.querySelector("[name=cf-turnstile-response]").value = "{token}";')
                # 触发截图中显示的回调函数
                page.evaluate('if (typeof cfCallback === "function") { cfCallback(); }')
                return True
            elif res.get("request") == "CAPCHA_NOT_READY":
                continue
            else:
                break
        return False

    def run(self):
        with sync_playwright() as p:
            print("🌐 启动浏览器...")
            browser = p.chromium.launch(headless=True, args=['--disable-blink-features=AutomationControlled'])
            context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            
            # 注入 Cookie 跳过登录
            print("🍪 注入登录凭证...")
            context.add_cookies([{
                'name': 'remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d',
                'value': self.cookie_value,
                'domain': 'hub.weirdhost.xyz',
                'path': '/',
                'expires': int(time.time()) + 31536000,
                'httpOnly': True,
                'secure': True,
                'sameSite': 'Lax'
            }])

            page = context.new_page()
            
            for url in self.server_urls:
                try:
                    print(f"\n🚀 目标服务器: {url}")
                    page.goto(url, wait_until="domcontentloaded", timeout=60000)
                    time.sleep(5) # 等待韩文内容渲染

                    # 1. 检查到期时间
                    days_left, expiry_date = self.get_remaining_days(page)
                    if days_left is not None:
                        print(f"📅 到期时间: {expiry_date}")
                        print(f"⏳ 剩余天数: {days_left} 天")
                        if days_left > 10:
                            print("✅ 剩余时间充裕 (>6天)，跳过续期。")
                            continue
                    else:
                        print("⚠️ 未能识别到期时间，为安全起见将尝试续期流程。")

                    # 2. 点击续期按钮 (使用你截图中的蓝色按钮 Class)
                    # 定位：class 包含 bkrtgq 的第一个按钮
                    renew_btn = page.locator("button.bkrtgq").first
                    if renew_btn.is_visible():
                        print("🖱️ 找到续期按钮，准备操作...")
                        renew_btn.click()
                        
                        # 等待 Turnstile 响应输入框出现
                        try:
                            page.wait_for_selector("[name='cf-turnstile-response']", timeout=15000)
                            if self.solve_turnstile(page):
                                # 检查是否出现成功提示 (你的第7张截图文本)
                                # 由于是韩文环境，我们等待页面 URL 刷新或特定绿色提示
                                page.wait_for_timeout(5000)
                                print("🎉 续期流程已提交！")
                                page.screenshot(path=f"success_{int(time.time())}.png")
                        except Exception as e:
                            print(f"ℹ️ 未检测到盾牌挑战或已自动通过: {e}")
                    else:
                        print("⏭️ 页面上未找到续期按钮。")
                        
                except Exception as e:
                    print(f"💥 运行异常: {str(e)}")
            
            browser.close()
            print("\n🏁 所有任务执行完毕。")

if __name__ == "__main__":
    bot = WeirdhostUltimate()
    bot.run()

