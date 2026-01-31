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
        # 从 Secrets 获取配置
        self.api_key_2captcha = os.getenv('TWOCAPTCHA_API_KEY')
        self.cookie_name = 'remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d'
        self.cookie_value = os.getenv('REMEMBER_WEB_COOKIE', '')
        self.server_urls = [url.strip() for url in os.getenv('WEIRDHOST_SERVER_URLS', '').split(',') if url.strip()]
        self.tg_token = os.getenv('TG_BOT_TOKEN') or os.getenv('TELEGRAM_BOT_TOKEN')
        self.tg_chat_id = os.getenv('TG_CHAT_ID') or os.getenv('TELEGRAM_CHAT_ID')
        
        # 站点元数据（用于 2Captcha 保底）
        self.sitekey = "0x4AAAAAACJH5atUUlnM2w2u"
        self.ext_url = "https://github.com/NopeCHALLC/nopecha-extension/releases/download/0.5.5/chromium_automation.zip"
        self.ext_dir = "nopecha_extension"
        self.results = []

    def log(self, msg):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

    def setup_extension(self):
        if os.path.exists(self.ext_dir):
            shutil.rmtree(self.ext_dir)
        try:
            r = requests.get(self.ext_url, timeout=30)
            with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                z.extractall(self.ext_dir)
            return os.path.abspath(self.ext_dir)
        except Exception as e:
            self.log(f"❌ 下载扩展失败: {e}")
            return None

    def solve_with_2captcha(self, page_url):
        """2Captcha 保底方案：当扩展和点击都失效时调用"""
        if not self.api_key_2captcha:
            self.log("⚠️ 未配置 2Captcha API Key，跳过保底方案")
            return None
        self.log("💰 正在启动 2Captcha 有偿破解...")
        try:
            # 1. 提交任务
            post_url = "http://2captcha.com/in.php"
            params = {
                'key': self.api_key_2captcha,
                'method': 'turnstile',
                'sitekey': self.sitekey,
                'pageurl': page_url,
                'json': 1
            }
            resp = requests.post(post_url, data=params, timeout=20).json()
            if resp.get('status') != 1: return None
            
            task_id = resp.get('request')
            # 2. 轮询结果
            for _ in range(20):
                time.sleep(5)
                res_url = f"http://2captcha.com/res.php?key={self.api_key_2captcha}&action=get&id={task_id}&json=1"
                res_resp = requests.get(res_url, timeout=20).json()
                if res_resp.get('status') == 1:
                    return res_resp.get('request')
            return None
        except Exception as e:
            self.log(f"❌ 2Captcha 异常: {e}")
            return None

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
        
        with SB(uc=True, xvfb=True, headless2=True, proxy="127.0.0.1:10808", extension_dir=ext_path) as sb:
            for url in self.server_urls:
                srv_id = url.split('/')[-1]
                self.log(f"\n🚀 处理服务器: {srv_id}")
                
                # 注入登录状态
                sb.uc_open("https://hub.weirdhost.xyz/login")
                sb.add_cookie({'name': self.cookie_name, 'value': self.cookie_value, 'domain': 'hub.weirdhost.xyz'})
                sb.refresh()
                sb.get(url)
                time.sleep(5)
                
                days_left, old_expiry = self.get_remaining_days(sb)
                if days_left is not None and days_left > 30: # 测试时设大，正式建议设为 4
                    self.results.append(f"🖥 {srv_id}: ✅ 天数充足")
                    continue

                try:
                    renew_btn = 'button.bkrtgq'
                    sb.wait_for_element_visible(renew_btn, timeout=10)
                    sb.click(renew_btn)
                    self.log("🔄 已触发续期弹窗，开始攻克 CF 盾...")
                    time.sleep(5)

                    solved = False
                    token_input = '[name="cf-turnstile-response"]'

                    # 阶段 A：穿透 Iframe 物理点击 (触发扩展工作)
                    try:
                        iframes = sb.find_elements("iframe")
                        for frame in iframes:
                            src = frame.get_attribute("src")
                            if src and "cloudflare" in src:
                                sb.switch_to_frame(frame)
                                # 尝试点击三个可能的区域
                                for selector in ["#challenge-stage", ".mark", "input[type='checkbox']"]:
                                    if sb.is_element_visible(selector):
                                        sb.click(selector)
                                        self.log(f"🖱 已物理点击 iframe 内部: {selector}")
                                        break
                                sb.switch_to_default_content()
                                break
                    except: sb.switch_to_default_content()

                    # 阶段 B：等待 30 秒看扩展/点击是否生效
                    for i in range(30):
                        token = sb.get_attribute(token_input, "value")
                        if token and len(token) > 20:
                            self.log(f"✅ 免费方案破解成功 (耗时 {i}s)")
                            solved = True
                            break
                        time.sleep(1)

                    # 阶段 C：2Captcha API 最终保底
                    if not solved:
                        self.log("⚠️ 免费方案失效，正在调用 2Captcha...")
                        api_token = self.solve_with_2captcha(sb.get_current_url())
                        if api_token:
                            sb.execute_script(f'document.querySelector("{token_input}").value = "{api_token}";')
                            self.log("✅ 2Captcha Token 已强制注入")
                            solved = True

                    if solved:
                        sb.execute_script("document.querySelector('form')?.submit() || document.querySelector('button.bkrtgq')?.click();")
                        time.sleep(10)
                        sb.refresh()
                        time.sleep(5)
                        _, new_expiry = self.get_remaining_days(sb)
                        status = "🎉 <b>续期成功</b>" if new_expiry and old_expiry and new_expiry > old_expiry else "❌ <b>点击成功但日期未变</b>"
                    else:
                        status = "❌ <b>所有方案均未能破解 CF 盾</b>"
                        sb.save_screenshot(f"ultimate_fail_{srv_id}.png")

                    self.results.append(f"🖥 <b>{srv_id}</b>\n状态: {status}")

                except Exception as e:
                    self.log(f"⚠️ 过程异常: {e}")

        # 发送 TG 通知
        if self.results:
            report = "<b>🚀 Weirdhost 终极续期报告</b>\n\n" + "\n\n".join(self.results)
            requests.post(f"https://api.telegram.org/bot{self.tg_token}/sendMessage", 
                          json={"chat_id": self.tg_chat_id, "text": report, "parse_mode": "HTML"})

if __name__ == "__main__":
    WeirdhostUltimateBot().run()
