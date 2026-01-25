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
        try:
            requests.post(url, json={"chat_id": self.tg_chat_id, "text": f"🤖 **Weirdhost 续期助手**\n\n{message}", "parse_mode": "Markdown"}, timeout=10)
        except: pass

    def solve_cf_with_2captcha(self, driver):
        try:
            self.log("🛡️ 正在调用 2Captcha 辅助破解...")
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
                        driver.execute_script(f'document.querySelector("[name=cf-turnstile-response]").value = "{token}";')
                        driver.execute_script('if(typeof cfCallback === "function") cfCallback();')
                        driver.execute_script('if(typeof turnstileCallback === "function") turnstileCallback();')
                        return True
        except: pass
        return False

    def run(self):
        self.log("🌐 启动 SeleniumBase UC 模式...")
        # uc=True 抹除爬虫特征，headless2=True 模拟真实浏览器渲染
        driver = Driver(uc=True, headless2=True)
        
        try:
            for url in self.server_urls:
                srv_id = url.split('/')[-1]
                self.log(f"\n🚀 目标服务器: {srv_id}")
                
                # 1. 注入 Cookie
                driver.get("https://hub.weirdhost.xyz/")
                driver.add_cookie({'name': self.cookie_name, 'value': self.current_cookie, 'domain': 'hub.weirdhost.xyz'})
                
                # 2. 访问页面并过盾
                driver.get(url)
                time.sleep(10)
                
                if "Verify you are human" in driver.page_source:
                    if not self.solve_cf_with_2captcha(driver):
                        self.log("❌ 补刀失败")
                        continue
                    time.sleep(10)

                # 3. 核心：执行续期逻辑
                self.log("🧐 正在分析页面状态...")
                page_source = driver.page_source
                
                # 检查日期，确认是否真的进门了
                date_match = re.search(r'202\d-\d{2}-\d{2}', page_source)
                if date_match:
                    self.log(f"📅 发现到期时间: {date_match.group()}")
                    
                    # 尝试多种方式定位续期按钮
                    # 方式A: 包含指定文字的按钮
                    # 方式B: 截图显示的特定类名 .bkrtgq
                    btn_found = False
                    for selector in ['button:contains("시간추가")', 'button.bkrtgq', 'button:contains("Add Time")']:
                        if driver.is_element_visible(selector):
                            self.log(f"🔘 找到按钮 ({selector})，正在点击...")
                            driver.click(selector)
                            time.sleep(5)
                            # 点击后可能会有新的 CF 挑战，再次尝试过盾
                            if "Verify you are human" in driver.page_source:
                                self.solve_cf_with_2captcha(driver)
                                time.sleep(5)
                            self.results.append(f"🖥 `Server:{srv_id}`\n🎉 续期动作已执行")
                            btn_found = True
                            break
                    
                    if not btn_found:
                        self.results.append(f"🖥 `Server:{srv_id}`\n✅ 已进入后台，但未发现续期按钮（可能时间还充裕）")
                else:
                    self.log("❌ 未能在页面找到日期，可能破盾后未正确跳转")
                    driver.save_screenshot(f"ERROR_PAGE_{srv_id}.png")
                    self.results.append(f"🖥 `Server:{srv_id}`\n❌ 页面加载失败")

        except Exception as e:
            self.log(f"💥 运行异常: {e}")
        finally:
            driver.quit()
            if self.results:
                self.send_tg("\n\n".join(self.results))

if __name__ == "__main__":
    bot = WeirdhostUltimate()
    bot.run()
