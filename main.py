import os
import time
import re
import requests
from datetime import datetime
from seleniumbase import Driver

class WeirdhostFinalBoss:
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
        try: requests.post(url, json={"chat_id": self.tg_chat_id, "text": f"🤖 **Weirdhost 终极报告**\n\n{message}", "parse_mode": "Markdown"}, timeout=10)
        except: pass

    def solve_cf_and_interact(self, driver):
        """核心：注入 Token 后模拟物理交互并检测跳转"""
        try:
            self.log("🛡️ 正在通过 API 获取绕过令牌...")
            sitekey = "0x4AAAAAACJH5atUUlnM2w2u"
            res = requests.post("https://2captcha.com/in.php", data={
                'key': self.api_key, 'method': 'turnstile', 'sitekey': sitekey,
                'pageurl': driver.current_url, 'json': 1
            }).json()
            
            if res.get("status") == 1:
                task_id = res.get("request")
                for _ in range(40):
                    time.sleep(5)
                    res_get = requests.get(f"https://2captcha.com/res.php?key={self.api_key}&action=get&id={task_id}&json=1").json()
                    if res_get.get("status") == 1:
                        token = res_get.get("request")
                        self.log("✅ 令牌已获取，模拟人类点击验证...")
                        
                        # 1. 注入 Token 到隐藏字段
                        driver.execute_script(f'document.querySelector("[name=cf-turnstile-response]").value = "{token}";')
                        
                        # 2. 模拟物理点击：点击 iframe 的中心位置触发内部校验
                        try:
                            driver.click("iframe[src*='challenges']", timeout=5)
                        except:
                            self.log("⚠️ 点击 iframe 失败，尝试点击页面中心...")
                            driver.click("body")
                        
                        # 3. 强制执行所有可能的回调
                        driver.execute_script(f'''
                            const cb = window.cfCallback || window.turnstileCallback || window.onSuccess;
                            if (typeof cb === "function") cb("{token}");
                        ''')
                        return True
        except Exception as e:
            self.log(f"💥 破解交互失败: {e}")
        return False

    def run(self):
        # 使用 uc=True 绕过检测
        self.log("🌐 启动 Undetected Driver...")
        driver = Driver(uc=True, headless2=True) 
        
        try:
            for url in self.server_urls:
                srv_id = url.split('/')[-1]
                self.log(f"\n🚀 处理服务器: {srv_id}")
                
                # 注入 Cookie
                driver.get("https://hub.weirdhost.xyz/")
                driver.add_cookie({'name': self.cookie_name, 'value': self.current_cookie, 'domain': 'hub.weirdhost.xyz'})
                
                driver.get(url)
                time.sleep(12)
                
                # 检查是否卡在盾牌
                if "Verify you are human" in driver.page_source or driver.is_element_visible("iframe"):
                    self.log("🛡️ 检测到盾牌，开始破解...")
                    if self.solve_cf_and_interact(driver):
                        # 注入后不再强制刷新，而是等待页面“变色”
                        self.log("⏳ 正在观察页面跳转...")
                        for _ in range(15):
                            if "시간추가" in driver.page_source or "202" in driver.page_source:
                                break
                            time.sleep(1)
                    
                    # 如果还没动，尝试最后一次强行重定向到原 URL
                    if "Verify you are human" in driver.page_source:
                        self.log("🔄 自动跳转失效，执行手动重定向...")
                        driver.execute_script(f'window.location.href = "{url}";')
                        time.sleep(10)

                # 判定结果
                source = driver.page_source
                if "시간추가" in source or re.search(r'202\d-\d{2}-\d{2}', source):
                    self.log("✅ 成功突入后台")
                    
                    # 尝试点击续期按钮
                    found = False
                    for btn in ['button.bkrtgq', 'button:contains("시간추가")']:
                        if driver.is_element_visible(btn):
                            self.log(f"🔘 发现续期按钮，执行点击...")
                            driver.click(btn)
                            time.sleep(5)
                            self.results.append(f"🖥 `Server:{srv_id}`\n🎉 续期指令发送成功")
                            found = True
                            break
                    if not found:
                        self.results.append(f"🖥 `Server:{srv_id}`\n✅ 状态良好，无需操作")
                else:
                    self.log("❌ 突围失败")
                    driver.save_screenshot(f"FAILED_{srv_id}.png")
                    self.results.append(f"🖥 `Server:{srv_id}`\n🚫 失败：无法通过验证")

        except Exception as e:
            self.log(f"💥 严重异常: {e}")
        finally:
            driver.quit()
            if self.results:
                self.send_tg("\n\n".join(self.results))

if __name__ == "__main__":
    bot = WeirdhostFinalBoss()
    bot.run()
