import os
import time
import re
import requests
import zipfile
import io
import shutil
from datetime import datetime
from seleniumbase import SB

class WeirdhostUltimateBot:
    def __init__(self):
        self.api_key_2captcha = os.getenv('TWOCAPTCHA_API_KEY')
        self.cookie_name = 'remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d'
        self.cookie_value = os.getenv('REMEMBER_WEB_COOKIE', '')
        self.server_urls = [url.strip() for url in os.getenv('WEIRDHOST_SERVER_URLS', '').split(',') if url.strip()]
        self.tg_token = os.getenv('TG_BOT_TOKEN') or os.getenv('TELEGRAM_BOT_TOKEN')
        self.tg_chat_id = os.getenv('TG_CHAT_ID') or os.getenv('TELEGRAM_CHAT_ID')
        self.sitekey = "0x4AAAAAACJH5atUUlnM2w2u"
        self.ext_url = "https://github.com/NopeCHALLC/nopecha-extension/releases/download/0.5.5/chromium_automation.zip"
        self.ext_dir = "nopecha_extension"
        self.results = []

    def log(self, msg):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

    def setup_extension(self):
        if os.path.exists(self.ext_dir): shutil.rmtree(self.ext_dir)
        try:
            r = requests.get(self.ext_url, timeout=30)
            with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                z.extractall(self.ext_dir)
            self.log("✅ 插件准备就绪")
            return os.path.abspath(self.ext_dir)
        except Exception as e:
            self.log(f"❌ 插件下载失败: {e}")
            return None

    def solve_with_2captcha(self, page_url):
        if not self.api_key_2captcha: return None
        self.log("💰 正在启动 2Captcha 有偿破解...")
        try:
            resp = requests.post("http://2captcha.com/in.php", data={
                'key': self.api_key_2captcha, 'method': 'turnstile',
                'sitekey': self.sitekey, 'pageurl': page_url, 'json': 1
            }, timeout=20).json()
            if resp.get('status') != 1: return None
            task_id = resp.get('request')
            for _ in range(30):
                time.sleep(5)
                res = requests.get(f"http://2captcha.com/res.php?key={self.api_key_2captcha}&action=get&id={task_id}&json=1").json()
                if res.get('status') == 1: return res.get('request')
            return None
        except: return None

    def get_remaining_days(self, sb):
        try:
            source = sb.get_page_source()
            match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', source)
            if match:
                expiry = datetime.strptime(match.group(1), '%Y-%m-%d %H:%M:%S')
                return (expiry - datetime.now()).days, expiry
            return None, None
        except: return None, None

    def run(self):
        ext_path = self.setup_extension()
        # 强制设置代理和无头模式
        with SB(uc=True, xvfb=True, headless2=True, proxy="127.0.0.1:10808", extension_dir=ext_path) as sb:
            for url in self.server_urls:
                srv_id = url.split('/')[-1]
                self.log(f"\n🚀 处理服务器: {srv_id}")
                
                sb.uc_open("https://hub.weirdhost.xyz/login")
                time.sleep(3)
                sb.add_cookie({'name': self.cookie_name, 'value': self.cookie_value, 'domain': 'hub.weirdhost.xyz'})
                sb.refresh()
                sb.get(url)
                time.sleep(5)
                
                days_left, old_expiry = self.get_remaining_days(sb)
                if days_left is not None and days_left > 30:
                    self.results.append(f"🖥 {srv_id}: ✅ 天数充足")
                    continue

                try:
                    renew_btn = 'button.bkrtgq'
                    if sb.is_element_visible(renew_btn):
                        sb.click(renew_btn)
                        self.log("🔄 已触发续期弹窗，开始破解 CF 盾...")
                        time.sleep(5)
                        
                        token_input = '[name="cf-turnstile-response"]'
                        solved = False
                        
                        # 1. Iframe 尝试
                        try:
                            iframes = sb.find_elements("iframe")
                            for frame in iframes:
                                if "cloudflare" in (frame.get_attribute("src") or ""):
                                    sb.switch_to_frame(frame)
                                    sb.click_if_visible("#challenge-stage")
                                    sb.switch_to_default_content()
                                    break
                        except: sb.switch_to_default_content()
                        
                        # 2. 等待扩展
                        for _ in range(30):
                            token = sb.get_attribute(token_input, "value")
                            if token and len(token) > 20:
                                solved = True; break
                            time.sleep(1)
                        
                        # 3. 2Captcha 保底 (修复注入逻辑)
                        if not solved:
                            api_token = self.solve_with_2captcha(sb.get_current_url())
                            if api_token:
                                # 核心修复：使用参数化注入，避免 SyntaxError
                                sb.execute_script('document.getElementsByName("cf-turnstile-response")[0].value = arguments[0];', api_token)
                                self.log("✅ 2Captcha Token 已安全注入")
                                solved = True

                        if solved:
                            # 强制提交
                            sb.execute_script("document.querySelector('form')?.submit();")
                            time.sleep(10)
                            sb.refresh()
                            _, new_expiry = self.get_remaining_days(sb)
                            status = "🎉 成功" if new_expiry and old_expiry and new_expiry > old_expiry else "❌ 失败"
                        else:
                            status = "❌ 验证未过"
                        
                        self.results.append(f"🖥 <b>{srv_id}</b>: {status}")
                except Exception as e:
                    self.log(f"⚠️ 异常: {e}")

        if self.results and self.tg_token:
            report = "<b>🚀 续期报告</b>\n\n" + "\n".join(self.results)
            requests.post(f"https://api.telegram.org/bot{self.tg_token}/sendMessage", 
                          json={"chat_id": self.tg_chat_id, "text": report, "parse_mode": "HTML"})

if __name__ == "__main__":
    WeirdhostUltimateBot().run()
