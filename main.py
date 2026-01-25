import os
import time
import re
import requests
from datetime import datetime
from seleniumbase import Driver

class WeirdhostProxyMaster:
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
            requests.post(url, json={"chat_id": self.tg_chat_id, "text": f"🤖 **Weirdhost 代理版报告**\n\n{message}", "parse_mode": "Markdown"}, timeout=10)
        except: pass

    def solve_cf_with_2captcha(self, driver):
        """若代理下依然触发验证，则调用 2Captcha"""
        try:
            self.log("🛡️ 代理环境下仍检测到盾，启动 2Captcha 辅助...")
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
                        return True
        except: pass
        return False

    def run(self):
        self.log("🌐 启动 SeleniumBase (连接本地 10808 代理)...")
        # proxy 参数将所有流量导向 Xray
        driver = Driver(uc=True, headless2=True, proxy="127.0.0.1:10808")
        
        try:
            # 步骤 0: 验证代理是否生效
            try:
                driver.get("https://api.ipify.org")
                self.log(f"📍 出口 IP 确认: {driver.get_text('body')}")
            except:
                self.log("⚠️ 无法获取出口 IP，代理可能未就绪。")

            for url in self.server_urls:
                srv_id = url.split('/')[-1]
                self.log(f"\n🚀 开始处理服务器: {srv_id}")
                
                # 注入鉴权 Cookie
                driver.get("https://hub.weirdhost.xyz/")
                driver.add_cookie({'name': self.cookie_name, 'value': self.current_cookie, 'domain': 'hub.weirdhost.xyz'})
                
                # 访问目标页面
                driver.get(url)
                time.sleep(12) # 给予 UC 模式解析指纹的时间
                
                # 检查是否存在 CF 盾
                if "Verify you are human" in driver.page_source:
                    self.log("🛡️ 依然存在 CF 验证，执行破解...")
                    self.solve_cf_with_2captcha(driver)
                    time.sleep(10)

                # 解析页面状态
                source = driver.page_source
                if "시간추가" in source or re.search(r'202\d-\d{2}-\d{2}', source):
                    self.log("✅ 成功突入管理后台")
                    
                    # 查找并点击续期按钮
                    btn_found = False
                    for selector in ['button.bkrtgq', 'button:contains("시간추가")']:
                        if driver.is_element_visible(selector):
                            self.log(f"🔘 发现按钮，点击续期...")
                            driver.click(selector)
                            time.sleep(5)
                            self.results.append(f"🖥 `Server:{srv_id}`\n🎉 代理辅助续期成功")
                            btn_found = True
                            break
                    if not btn_found:
                        self.results.append(f"🖥 `Server:{srv_id}`\n✅ 已进入后台，无需续期")
                else:
                    self.log("❌ 突围失败")
                    driver.save_screenshot(f"PROXY_FAIL_{srv_id}.png")
                    self.results.append(f"🖥 `Server:{srv_id}`\n🚫 失败：代理下仍无法越过验证")

        except Exception as e:
            self.log(f"💥 运行异常: {e}")
        finally:
            driver.quit()
            if self.results:
                self.send_tg("\n\n".join(self.results))

if __name__ == "__main__":
    bot = WeirdhostProxyMaster()
    bot.run()
