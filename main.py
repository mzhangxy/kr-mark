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

    def send_tg(self, message):
        if not self.tg_token: return
        url = f"https://api.telegram.org/bot{self.tg_token}/sendMessage"
        try:
            requests.post(url, json={"chat_id": self.tg_chat_id, "text": f"🤖 **Weirdhost 报告**\n\n{message}", "parse_mode": "Markdown"}, timeout=10)
        except: pass

    def run(self):
        self.log("🌐 启动 SeleniumBase (使用 10808 代理)...")
        # 强制开启代理
        driver = Driver(uc=True, headless2=True, proxy="127.0.0.1:10808")
        
        try:
            # 1. 验证代理连接
            self.log("📡 验证代理连接性...")
            try:
                driver.get("https://www.google.com/generate_204", timeout=15)
                self.log("✅ 代理网络连接正常")
            except Exception as e:
                self.log(f"❌ 代理连接失败: {e}")
                # 即使失败也继续尝试，有时只是 google 访问不了

            for url in self.server_urls:
                srv_id = url.split('/')[-1]
                self.log(f"\n🚀 开始处理服务器: {srv_id}")
                
                # --- 修复 Cookie Domain 错误的关键步骤 ---
                # A. 先打开目标域名的一个页面（甚至是 404 页也行）
                self.log("🔗 正在进入域名上下文...")
                driver.get("https://hub.weirdhost.xyz/login") 
                time.sleep(5)
                
                # B. 现在域名匹配了，注入 Cookie
                self.log("🔑 注入 Session Cookie...")
                try:
                    driver.add_cookie({
                        'name': self.cookie_name, 
                        'value': self.current_cookie, 
                        'domain': 'hub.weirdhost.xyz',
                        'path': '/'
                    })
                except Exception as e:
                    self.log(f"⚠️ Cookie 注入异常: {e}")

                # C. 再次跳转到具体的管理页面
                driver.get(url)
                time.sleep(12)
                
                # 2. 检查页面状态
                source = driver.page_source
                if "시간추가" in source or re.search(r'202\d-\d{2}-\d{2}', source):
                    self.log("✅ 已进入管理后台")
                    
                    # 查找续期按钮
                    for sel in ['button.bkrtgq', 'button:contains("시간추가")']:
                        if driver.is_element_visible(sel):
                            self.log("🔘 执行点击续期...")
                            driver.click(sel)
                            time.sleep(5)
                            self.results.append(f"🖥 `Server:{srv_id}`\n🎉 续期成功 (代理模式)")
                            break
                    else:
                        self.results.append(f"🖥 `Server:{srv_id}`\n✅ 状态正常，无需操作")
                else:
                    self.log("🛡️ 未见后台内容，可能触发了 CF 验证...")
                    driver.save_screenshot(f"FAIL_{srv_id}.png")
                    self.results.append(f"🖥 `Server:{srv_id}`\n🚫 进入后台失败，查看截图")

        except Exception as e:
            self.log(f"💥 运行异常: {e}")
            driver.save_screenshot("CRITICAL_ERROR.png")
        finally:
            driver.quit()
            if self.results:
                self.send_tg("\n\n".join(self.results))

if __name__ == "__main__":
    bot = WeirdhostProxyMaster()
    bot.run()
