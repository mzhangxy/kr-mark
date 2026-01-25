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
                        self.log("✅ Token 已就绪，正在强制注入并触发回调...")
                        # 注入并触发所有可能的回调函数
                        driver.execute_script(f'''
                            document.querySelector("[name=cf-turnstile-response]").value = "{token}";
                            const callbacks = ["cfCallback", "turnstileCallback", "onSuccess", "on_success"];
                            callbacks.forEach(cb => {{
                                if (typeof window[cb] === "function") window[cb]("{token}");
                            }});
                        ''')
                        return True
        except: pass
        return False

    def run(self):
        self.log("🌐 启动 SeleniumBase UC 模式...")
        driver = Driver(uc=True, headless2=True)
        
        try:
            for url in self.server_urls:
                srv_id = url.split('/')[-1]
                self.log(f"\n🚀 目标服务器: {srv_id}")
                
                # 注入 Cookie
                driver.get("https://hub.weirdhost.xyz/")
                driver.add_cookie({'name': self.cookie_name, 'value': self.current_cookie, 'domain': 'hub.weirdhost.xyz'})
                
                # 访问
                driver.get(url)
                time.sleep(10)
                
                # 如果依然卡在盾牌
                if "Verify you are human" in driver.page_source or "cf-challenge" in driver.page_source:
                    if self.solve_cf_with_2captcha(driver):
                        self.log("⏳ 等待页面自动跳转...")
                        time.sleep(12)
                    
                    # 如果注入后还没跳转，强制刷新
                    if "Verify you are human" in driver.page_source:
                        self.log("🔄 页面未自动跳转，尝试强制刷新...")
                        driver.refresh()
                        time.sleep(10)

                # 判定状态
                self.log("🧐 正在解析页面内容...")
                source = driver.page_source
                
                # 1. 查找日期 (增强匹配)
                date_match = re.search(r'(\d{4}-\d{2}-\d{2})', source)
                
                if date_match or "시간추가" in source:
                    self.log(f"✅ 成功进入后台" + (f" (到期日期: {date_match.group(1)})" if date_match else ""))
                    
                    # 2. 尝试点击续期按钮
                    btn_clicked = False
                    for selector in ['button:contains("시간추가")', 'button.bkrtgq', 'button[type="submit"]']:
                        if driver.is_element_visible(selector):
                            # 过滤掉一些不相关的按钮，确保是“续期”按钮
                            if "시간추가" in driver.get_text(selector) or "bkrtgq" in selector:
                                self.log(f"🔘 点击按钮: {selector}")
                                driver.click(selector)
                                time.sleep(5)
                                self.results.append(f"🖥 `Server:{srv_id}`\n🎉 续期指令已下达")
                                btn_clicked = True
                                break
                    
                    if not btn_clicked:
                        self.results.append(f"🖥 `Server:{srv_id}`\n✅ 已进入后台，当前时间尚充裕，无需续期")
                else:
                    self.log("❌ 无法识别后台特征，可能依然被拦截")
                    driver.save_screenshot(f"STUCK_{srv_id}.png")
                    self.results.append(f"🖥 `Server:{srv_id}`\n❌ 破盾失败，卡在验证页")

        except Exception as e:
            self.log(f"💥 运行异常: {e}")
        finally:
            driver.quit()
            if self.results:
                self.send_tg("\n\n".join(self.results))

if __name__ == "__main__":
    bot = WeirdhostUltimate()
    bot.run()
