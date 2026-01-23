import os
import sys
import time
import requests
from playwright.sync_api import sync_playwright, TimeoutError

class WeirdhostUltimate:
    def __init__(self):
        self.api_key = os.getenv('TWOCAPTCHA_API_KEY')
        self.cookie_value = os.getenv('REMEMBER_WEB_COOKIE')
        self.server_urls = [url.strip() for url in os.getenv('WEIRDHOST_SERVER_URLS', '').split(',') if url.strip()]
        self.sitekey = "0x4AAAAAAAVp6E7zXFfS629p" # 来源于你的截图

    def solve_turnstile(self, page):
        """调用 2captcha 破解 Turnstile 盾"""
        print(f"🛡️ 发现 Turnstile 挑战，正在请求 2captcha 破解...")
        page_url = page.url
        
        # 1. 提交任务
        in_res = requests.post("https://2captcha.com/in.php", data={
            'key': self.api_key,
            'method': 'turnstile',
            'sitekey': self.sitekey,
            'pageurl': page_url,
            'json': 1
        }).json()

        if in_res.get("status") != 1:
            print(f"❌ 2captcha 提交失败: {in_res.get('request')}")
            return False

        task_id = in_res.get("request")
        
        # 2. 轮询结果 (最多等2分钟)
        for _ in range(24):
            time.sleep(5)
            res = requests.get(f"https://2captcha.com/res.php?key={self.api_key}&action=get&id={task_id}&json=1").json()
            if res.get("status") == 1:
                token = res.get("request")
                print("✅ 2captcha 破解成功，正在注入 Token...")
                
                # 3. 注入 Token 并触发截图中的回调函数
                page.evaluate(f'document.querySelector("[name=cf-turnstile-response]").value = "{token}";')
                page.evaluate('if (typeof cfCallback === "function") { cfCallback(); }')
                return True
            elif res.get("request") == "CAPCHA_NOT_READY":
                continue
            else:
                print(f"❌ 破解异常: {res.get('request')}")
                break
        return False

    def run(self):
        with sync_playwright() as p:
            # 启动浏览器，使用与原代码一致的伪装参数
            browser = p.chromium.launch(headless=True, args=['--disable-blink-features=AutomationControlled'])
            context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            
            # 第一步：注入 Cookie 跳过登录
            # 注意：这里的 domain 需根据你的 URL 调整，通常是 .weirdhost.xyz
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
                    print(f"\n🚀 正在处理服务器: {url}")
                    page.goto(url, wait_until="networkidle", timeout=60000)
                    
                    # 点击续期按钮
                    renew_btn = page.get_by_role("button", name="Renew Server")
                    if renew_btn.is_visible():
                        renew_btn.click()
                        print("🖱️ 已点击续期按钮，等待盾牌弹出...")
                        
                        # 等待盾牌容器出现 (基于你的截图 ID)
                        try:
                            page.wait_for_selector("[name='cf-turnstile-response']", timeout=10000)
                            if self.solve_turnstile(page):
                                # 等待成功提示 (你的第7张截图内容)
                                page.wait_for_selector("text=Your server has been renewed", timeout=20000)
                                print("🎉 续期成功！")
                            else:
                                print("⚠️ 破解失败，请检查 2captcha 余额或 Key")
                        except:
                            print("ℹ️ 未检测到验证码，可能已自动通过或失效")
                    else:
                        print("⏭️ 未找到续期按钮，可能已续期")
                        
                except Exception as e:
                    print(f"❌ 处理出错: {str(e)}")
                    page.screenshot(path=f"error_{int(time.time())}.png")
            
            browser.close()

if __name__ == "__main__":
    bot = WeirdhostUltimate()
    bot.run()
