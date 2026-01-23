import os
import sys
import time
import requests
from playwright.sync_api import sync_playwright, TimeoutError

class WeirdhostUltimate:
    def __init__(self):
        self.api_key = os.getenv('TWOCAPTCHA_API_KEY')
        self.cookie_value = os.getenv('REMEMBER_WEB_COOKIE')
        # 支持多个URL，逗号分隔
        self.server_urls = [url.strip() for url in os.getenv('WEIRDHOST_SERVER_URLS', '').split(',') if url.strip()]
        self.sitekey = "0x4AAAAAAAVp6E7zXFfS629p"

    def check_login_status(self, page):
        """检测是否登录成功"""
        print("🔍 正在检查登录状态...")
        try:
            # 检查页面是否包含常见的登录后特征，比如“Logout”或“Dashboard”
            # 你可以根据你截图里的真实文本修改，这里先用常见的 Logout
            if page.get_by_role("link", name="Logout").is_visible() or page.get_by_text("Dashboard").is_visible():
                print("✅ 登录验证成功：已处于登录状态。")
                return True
            else:
                print("⚠️ 登录验证存疑：未找到登出按钮，可能 Cookie 已过期。")
                # 打印当前页面标题辅助判断
                print(f"📄 当前页面标题: {page.title()}")
                return False
        except:
            return False

    def solve_turnstile(self, page):
        print(f"🛡️ 发现 Turnstile 挑战，正在请求 2captcha 破解...")
        page_url = page.url
        
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
        print(f"⏳ 验证码任务 ID: {task_id}，等待返回...")
        
        for _ in range(24):
            time.sleep(5)
            res = requests.get(f"https://2captcha.com/res.php?key={self.api_key}&action=get&id={task_id}&json=1").json()
            if res.get("status") == 1:
                token = res.get("request")
                print("✅ 2captcha 破解成功，正在注入 Token...")
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
            print("🌐 启动浏览器...")
            browser = p.chromium.launch(headless=True, args=['--disable-blink-features=AutomationControlled'])
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={'width': 1280, 'height': 800}
            )
            
            # 注入 Cookie
            print("🍪 正在注入 Cookie...")
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
                    print(f"\n🚀 目标地址: {url}")
                    page.goto(url, wait_until="domcontentloaded", timeout=60000)
                    time.sleep(5) # 等待动态内容加载
                    
                    # 1. 检测登录
                    if not self.check_login_status(page):
                        page.screenshot(path="login_failed.png")
                        print("📸 已保存登录失败截图: login_failed.png")
                    
                    # 2. 检测续期按钮
                    renew_btn = page.get_by_role("button", name="Renew Server")
                    # 增加模糊匹配，防止大小写问题
                    if not renew_btn.is_visible():
                        renew_btn = page.locator("button:has-text('Renew')")

                    if renew_btn.is_visible():
                        print("🖱️ 找到续期按钮，准备点击...")
                        renew_btn.click()
                        
                        # 等待验证码
                        try:
                            print("🕒 等待 Turnstile 验证框...")
                            page.wait_for_selector("[name='cf-turnstile-response']", timeout=15000)
                            if self.solve_turnstile(page):
                                # 等待成功通知
                                print("⏳ 等待网页成功反馈...")
                                success_msg = page.wait_for_selector("text=renewed for 1 day", timeout=30000)
                                if success_msg:
                                    print("🎉 恭喜！续期完成。")
                            else:
                                print("❌ 验证码破解逻辑未成功触发")
                        except Exception as e:
                            print(f"ℹ️ 流程中断或无需验证: {str(e)}")
                            page.screenshot(path="process_info.png")
                    else:
                        print("⏭️ 当前页面未发现续期按钮。")
                        # 看看是不是按钮还没到期，或者页面结构变了
                        page.screenshot(path="no_button_found.png")
                        
                except Exception as e:
                    print(f"💥 运行异常: {str(e)}")
                    page.screenshot(path=f"error_log.png")
            
            browser.close()
            print("\n🏁 任务结束。")

if __name__ == "__main__":
    bot = WeirdhostUltimate()
    bot.run()
