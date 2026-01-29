import os
import time
import re
import requests
from datetime import datetime
from seleniumbase import Driver

class WeirdhostProxyMaster:
    def __init__(self):
        self.api_key = os.getenv('TWOCAPTCHA_API_KEY')
        self.tg_token = os.getenv('TG_BOT_TOKEN')
        self.tg_chat_id = os.getenv('TG_CHAT_ID')
        self.server_urls = [url.strip() for url in os.getenv('WEIRDHOST_SERVER_URLS', '').split(',') if url.strip()]
        
        self.cookie_name = 'remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d'
        self.current_cookie = os.getenv('REMEMBER_WEB_COOKIE', '')
        self.results = []

    def log(self, msg):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

    def run(self):
        self.log("🌐 启动 SeleniumBase (10808 代理)...")
        driver = Driver(uc=True, headless2=True, proxy="127.0.0.1:10808")
        
        try:
            # 1. 验证代理
            self.log("📡 验证出口 IP...")
            try:
                driver.get("https://api.ipify.org")
                time.sleep(5)
                ip = driver.get_text("body")
                self.log(f"✅ 代理已通，当前 IP: {ip}")
            except Exception:
                self.log("❌ 代理请求失败，尝试直接访问目标...")

            for url in self.server_urls:
                srv_id = url.split('/')[-1]
                self.log(f"\n🚀 处理服务器: {srv_id}")
                
                # 2. 强力进入域名上下文
                self.log("🔗 进入域名中...")
                driver.get("https://hub.weirdhost.xyz/login")
                time.sleep(8)
                
                # 检查是否真的进入了该域名（防止代理报错页）
                if "weirdhost.xyz" not in driver.current_url:
                    self.log(f"⚠️ 域名不匹配: {driver.current_url}")
                    # 如果代理不通，这里很可能是 chrome-error://...
                
                # 3. 注入 Cookie
                self.log("🔑 注入 Cookie...")
                try:
                    driver.add_cookie({
                        'name': self.cookie_name, 
                        'value': self.current_cookie, 
                        'domain': 'hub.weirdhost.xyz'
                    })
                    self.log("✅ Cookie 注入尝试完成")
                except Exception as e:
                    self.log(f"❌ Cookie 注入失败: {e}")

                # 4. 再次访问目标
                driver.get(url)
                time.sleep(10)
                
                # 5. 判定
                source = driver.page_source
                if "시간추가" in source or re.search(r'202\d-\d{2}-\d{2}', source):
                    self.log("✅ 成功进入后台")
                    for sel in ['button.bkrtgq', 'button:contains("시간추가")']:
                        if driver.is_element_visible(sel):
                            driver.click(sel)
                            time.sleep(5)
                            self.results.append(f"🖥 `{srv_id}`: 续期成功")
                            break
                    else:
                        self.results.append(f"🖥 `{srv_id}`: 已进后台，无需续期")
                else:
                    self.log("🛡️ 状态异常")
                    driver.save_screenshot(f"STATUS_{srv_id}.png")
                    self.results.append(f"🖥 `{srv_id}`: 失败 (代理/验证问题)")

        except Exception as e:
            self.log(f"💥 异常: {e}")
        finally:
            driver.quit()
            if self.results:
                msg = "\n".join(self.results)
                if self.tg_token:
                    requests.post(f"https://api.telegram.org/bot{self.tg_token}/sendMessage", 
                                 json={"chat_id": self.tg_chat_id, "text": msg})

if __name__ == "__main__":
    bot = WeirdhostProxyMaster()
    bot.run()
