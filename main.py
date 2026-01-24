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
        self.tg_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.tg_chat_id = os.getenv('TELEGRAM_CHAT_ID')
        self.sitekey = "0x4AAAAAACJH5atUUlnM2w2u"
        self.results = []

    def send_tg_notification(self, message):
        if not self.tg_token or not self.tg_chat_id:
            print("⚠️ 未配置 TG 通知变量。")
            return
        url = f"https://api.telegram.org/bot{self.tg_token}/sendMessage"
        try:
            requests.post(url, json={"chat_id": self.tg_chat_id, "text": message, "parse_mode": "Markdown"}, timeout=10)
        except Exception as e:
            print(f"❌ TG 发送失败: {e}")

    def get_remaining_days(self, page):
        try:
            # 使用更宽泛的正则，只要包含 202x-xx-xx 就能抓到
            # 增加 10 秒等待确保异步内容加载
            target = page.get_by_text(re.compile(r"202\d-\d{2}-\d{2}")).first
            target.wait_for(state="visible", timeout=10000)
            
            raw_text = target.inner_text()
            # 提取时间部分：2026-02-01 17:20:57
            match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', raw_text)
            if match:
                expiry_date = datetime.strptime(match.group(1), '%Y-%m-%d %H:%M:%S')
                now = datetime.now()
                delta = expiry_date - now
                return delta.days, expiry_date
        except Exception as e:
            print(f"⚠️ 时间解析提示: {e}")
        return None, None
    
    """
    def get_remaining_days(self, page):
        try:
            # 优化：直接寻找包含 202x-xx-xx 格式的文本节点
            time_text = page.locator("text=/202\d-\d{2}-\d{2}/").first.inner_text()
            match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', time_text)
            if match:
                expiry_date = datetime.strptime(match.group(1), '%Y-%m-%d %H:%M:%S')
                now = datetime.now()
                delta = expiry_date - now
                return delta.days, expiry_date
        except Exception as e:
            print(f"⚠️ 时间解析失败: {e}")
        return None, None
    """

    def solve_turnstile(self, page):
        print(f"🛡️ 正在请求 2captcha...")
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
            context = browser.new_context(viewport={'width': 1280, 'height': 800})
            
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
                srv_name = url.split('/')[-1]
                try:
                    print(f"\n🚀 访问: {url}")
                    page.goto(url, wait_until="networkidle", timeout=60000)
                    page.wait_for_timeout(5000) 

                    # 1. 检测时间
                    days_left, expiry_date = self.get_remaining_days(page)
                    time_info = f"📅 到期: {expiry_date.strftime('%Y-%m-%d')}" if expiry_date else "📅 时间获取失败"
                    
                    if days_left is not None and days_left > 6:
                        print(f"✅ 剩余 {days_left} 天，跳过。")
                        self.results.append(f"🖥 `{srv_name}`\n{time_info}\n✅ 剩余{days_left}天，无需操作")
                        continue

                    # 2. 定位续期按钮 (根据图片文字 "시간추가" 定位)
                    # 尝试多种方式：文字匹配、Class匹配
                    renew_btn = page.get_by_text("시간추가").first
                    if not renew_btn.is_visible():
                        renew_btn = page.locator("button.bkrtgq").first

                    if renew_btn.is_visible():
                        print("🖱️ 点击续期按钮 (시간추가)...")
                        renew_btn.click()
                        page.wait_for_timeout(3000)
                        
                        if page.locator("[name='cf-turnstile-response']").count() > 0:
                            if self.solve_turnstile(page):
                                page.wait_for_timeout(7000)
                                self.results.append(f"🖥 `{srv_name}`\n{time_info}\n🎉 续期成功 (已破盾)")
                            else:
                                self.results.append(f"🖥 `{srv_name}`\n❌ 验证码破解失败")
                        else:
                            self.results.append(f"🖥 `{srv_name}`\n✅ 续期完成 (免验证)")
                    else:
                        # 失败时截图
                        shot_path = f"fail_{srv_name}_{int(time.time())}.png"
                        page.screenshot(path=shot_path)
                        print(f"❌ 未找到按钮，已截图: {shot_path}")
                        self.results.append(f"🖥 `{srv_name}`\n❌ 未找到续期按钮")

                except Exception as e:
                    self.results.append(f"🖥 `{srv_name}`\n💥 异常: {str(e)[:50]}")
            
            browser.close()
            if self.results:
                self.send_tg_notification("🤖 *Weirdhost 自动续期报告*\n\n" + "\n\n".join(self.results))

if __name__ == "__main__":
    bot = WeirdhostUltimate()
    bot.run()
