import os
import time
import re
import requests
from datetime import datetime
from seleniumbase import Driver

class WeirdhostUltimate:
    def __init__(self):
        self.api_key = os.getenv('TWOCAPTCHA_API_KEY')
        self.tg_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.tg_chat_id = os.getenv('TELEGRAM_CHAT_ID')
        self.server_urls = [url.strip() for url in os.getenv('WEIRDHOST_SERVER_URLS', '').split(',') if url.strip()]
        
        self.cookie_name = 'remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d'
        self.current_cookie = os.getenv('REMEMBER_WEB_COOKIE', '')
        self.results = []

    def log(self, msg):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

    def send_tg(self, message):
        if not self.tg_token: return
        url = f"https://api.telegram.org/bot{self.tg_token}/sendMessage"
        requests.post(url, json={"chat_id": self.tg_chat_id, "text": f"🤖 **Weirdhost 助手**\n\n{message}", "parse_mode": "Markdown"})

    def solve_cf_with_2captcha(self, driver):
        """如果 SeleniumBase 也没能自动过，就手动调用 2captcha 补刀"""
        try:
            self.log("🛡️ 尝试使用 2Captcha 辅助破盾...")
            # 获取当前页面的 sitekey (Weirdhost 固定为这个)
            sitekey = "0x4AAAAAACJH5atUUlnM2w2u"
            res = requests.post("https://2captcha.com/in.php", data={
                'key': self.api_key, 'method': 'turnstile', 'sitekey': sitekey,
                'pageurl': driver.current_url, 'json': 1
            }).json()
            
            if res.get("status") == 1:
                task_id = res.get("request")
                for _ in range(30):
                    time.sleep(5)
                    res_get = requests.get(f"https://2captcha.com/res.php?key={self.api_key}&action=get&id={task_id}&json=1").json()
                    if res_get.get("status") == 1:
                        token = res_get.get("request")
                        # 执行 JS 注入 Token 并回调
                        driver.execute_script(f'document.querySelector("[name=cf-turnstile-response]").value = "{token}";')
                        driver.execute_script('if(typeof cfCallback === "function") cfCallback();')
                        self.log("✅ 补刀 Token 已提交")
                        return True
        except Exception as e:
            self.log(f"⚠️ 2Captcha 辅助失败: {e}")
        return False

    def run(self):
        # 1. 启动具有 UC 模式的驱动
        self.log("🌐 启动 SeleniumBase UC 模式...")
        driver = Driver(uc=True, headless2=True)
        
        try:
            for url in self.server_urls:
                srv_id = url.split('/')[-1]
                self.log(f"\n🚀 目标: {url}")
                
                # 2. 先访问域名以建立上下文，然后注入 Cookie
                driver.get("https://hub.weirdhost.xyz/")
                driver.add_cookie({
                    'name': self.cookie_name, 
                    'value': self.current_cookie,
                    'domain': 'hub.weirdhost.xyz'
                })
                
                # 3. 访问具体服务器页面
                driver.get(url)
                time.sleep(10) # 给 UC 模式一点自动过盾的时间
                
                # 4. 检查是否还在盾牌页
                if "Verify you are human" in driver.page_source:
                    self.log("🛡️ UC 模式自动过盾未触发，启动 2Captcha 补刀...")
                    self.solve_cf_with_2captcha(driver)
                    time.sleep(8)
                
                # 5. 确认是否进入后台
                if "시간추가" in driver.page_source or "202" in driver.page_source:
                    self.log("✅ 已成功进入管理页面")
                    
                    # 检查是否需要续期 (寻找按钮)
                    if driver.is_element_visible('button:contains("시간추가")'):
                        self.log("🔘 点击续期按钮...")
                        driver.click('button:contains("시간추가")')
                        time.sleep(5)
                        self.results.append(f"🖥 `Server:{srv_id}`\n🎉 续期成功！")
                    else:
                        self.results.append(f"🖥 `Server:{srv_id}`\n✅ 状态正常，无需续期")
                else:
                    self.log("❌ 依旧无法越过 Cloudflare")
                    driver.save_screenshot(f"FAIL_{srv_id}.png")
                    self.results.append(f"🖥 `Server:{srv_id}`\n❌ 破盾失败")

        except Exception as e:
            self.log(f"💥 发生错误: {e}")
        finally:
            driver.quit()
            if self.results:
                self.send_tg("\n\n".join(self.results))

if __name__ == "__main__":
    bot = WeirdhostUltimate()
    bot.run()
