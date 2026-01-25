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
            self.log("🛡️ 正在通过 2Captcha 获取补丁 Token...")
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
                        self.log("✅ Token 已就绪，执行物理模拟过盾...")
                        
                        # 1. 注入 Token
                        driver.execute_script(f'document.querySelector("[name=cf-turnstile-response]").value = "{token}";')
                        
                        # 2. 模拟点击验证框 (有些盾必须点击才能触发校验)
                        try:
                            if driver.is_element_visible("iframe[src*='challenges']"):
                                driver.click("iframe[src*='challenges']")
                        except: pass
                        
                        # 3. 触发回调
                        driver.execute_script(f'''
                            const cb = window.cfCallback || window.turnstileCallback || window.onSuccess;
                            if (typeof cb === "function") cb("{token}");
                        ''')
                        return True
        except: pass
        return False

    def run(self):
        self.log("🌐 启动 SeleniumBase UC 模式...")
        # 严格对齐你成功脚本的启动方式
        driver = Driver(uc=True, headless2=True)
        
        try:
            for url in self.server_urls:
                srv_id = url.split('/')[-1]
                self.log(f"\n🚀 目标服务器: {srv_id}")
                
                # 注入 Cookie 以维持登录态
                driver.get("https://hub.weirdhost.xyz/")
                driver.add_cookie({'name': self.cookie_name, 'value': self.current_cookie, 'domain': 'hub.weirdhost.xyz'})
                
                # 访问目标页
                driver.get(url)
                time.sleep(12) # 给 UC 模式充足的时间自启动验证
                
                # 判定是否被拦截
                if "Verify you are human" in driver.page_source or driver.is_element_visible("iframe[src*='challenges']"):
                    self.log("🛡️ 触发补丁程序...")
                    if self.solve_cf_with_2captcha(driver):
                        time.sleep(10)
                    
                    # 如果还没跳，尝试点击页面任意空白处触发 JS 事件
                    if "Verify you are human" in driver.page_source:
                        driver.click("body")
                        time.sleep(5)
                        
                    # 最后尝试：如果还没进后台，强制重载
                    if "Verify you are human" in driver.page_source:
                        self.log("🔄 执行最后重载...")
                        driver.refresh()
                        time.sleep(10)

                # 解析阶段
                self.log("🧐 解析后台数据...")
                source = driver.page_source
                
                if "시간추가" in source or re.search(r'\d{4}-\d{2}-\d{2}', source):
                    self.log("✅ 成功进入管理后台")
                    
                    # 查找续期按钮 (增加对 .bkrtgq 类的优先匹配)
                    btn_selector = None
                    for sel in ['button.bkrtgq', 'button:contains("시간추가")', 'button:contains("Add Time")']:
                        if driver.is_element_visible(sel):
                            btn_selector = sel
                            break
                            
                    if btn_selector:
                        self.log(f"🔘 执行点击续期: {btn_selector}")
                        driver.click(btn_selector)
                        time.sleep(3)
                        self.results.append(f"🖥 `Server:{srv_id}`\n🎉 续期成功")
                    else:
                        self.results.append(f"🖥 `Server:{srv_id}`\n✅ 状态正常，无需操作")
                else:
                    self.log("❌ 最终识别失败")
                    driver.save_screenshot(f"FINAL_STUCK_{srv_id}.png")
                    self.results.append(f"🖥 `Server:{srv_id}`\n❌ 无法越过验证页")

        except Exception as e:
            self.log(f"💥 运行异常: {e}")
        finally:
            driver.quit()
            if self.results:
                self.send_tg("\n\n".join(self.results))

if __name__ == "__main__":
    bot = WeirdhostUltimate()
    bot.run()
