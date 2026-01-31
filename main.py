import os
import time
import re
import requests
import zipfile
import io
import shutil
from datetime import datetime
from seleniumbase import SB

class WeirdhostPureSB:
    def __init__(self):
        # 环境变量获取
        self.cookie_name = 'remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d'
        self.cookie_value = os.getenv('REMEMBER_WEB_COOKIE', '')
        self.server_urls = [url.strip() for url in os.getenv('WEIRDHOST_SERVER_URLS', '').split(',') if url.strip()]
        self.tg_token = os.getenv('TG_BOT_TOKEN') or os.getenv('TELEGRAM_BOT_TOKEN')
        self.tg_chat_id = os.getenv('TG_CHAT_ID') or os.getenv('TELEGRAM_CHAT_ID')
        self.results = []
        
        # NopeCHA 扩展下载配置
        self.ext_url = "https://github.com/NopeCHALLC/nopecha-extension/releases/download/0.5.5/chromium_automation.zip"
        self.ext_dir = "nopecha_extension"

    def log(self, msg):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

    def download_and_extract_extension(self):
        """下载并准备浏览器扩展"""
        if os.path.exists(self.ext_dir):
            shutil.rmtree(self.ext_dir)
        
        self.log("⬇️ 正在下载 NopeCHA 扩展...")
        try:
            r = requests.get(self.ext_url, timeout=30)
            with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                z.extractall(self.ext_dir)
            self.log("✅ 扩展下载并解压成功")
            return os.path.abspath(self.ext_dir)
        except Exception as e:
            self.log(f"❌ 扩展准备失败: {e}")
            return None

    def send_tg_notification(self, message):
        """发送 Telegram 通知"""
        if not self.tg_token or not self.tg_chat_id:
            self.log("⚠️ TG 未配置，跳过通知")
            return
        try:
            requests.post(
                f"https://api.telegram.org/bot{self.tg_token}/sendMessage",
                json={"chat_id": self.tg_chat_id, "text": message, "parse_mode": "HTML"},
                timeout=10
            )
            self.log("📤 TG 通知已发送")
        except Exception as e:
            self.log(f"❌ TG 发送失败: {e}")

    def get_remaining_days(self, sb):
        """从页面解析剩余天数和到期时间"""
        try:
            source = sb.get_page_source()
            match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', source)
            if match:
                expiry_str = match.group(1)
                expiry = datetime.strptime(expiry_str, '%Y-%m-%d %H:%M:%S')
                days = (expiry - datetime.now()).days
                return days, expiry
            return None, None
        except:
            return None, None

    def run(self):
        # 1. 准备扩展
        ext_path = self.download_and_extract_extension()
        if not ext_path:
            self.log("❌ 无法加载扩展，退出程序")
            return

        self.log("🌐 启动 SeleniumBase UC 模式...")
        # 配置浏览器：开启 UC 模式，加载扩展，设置代理
        with SB(uc=True, xvfb=True, headless2=True, proxy="127.0.0.1:10808", extension_dir=ext_path) as sb:
            
            # 验证代理 IP
            try:
                sb.get("https://api.ipify.org")
                ip = sb.get_text("body").strip()
                self.log(f"📡 代理出口 IP: {ip}")
            except:
                self.log("⚠️ 无法获取出口 IP")

            for url in self.server_urls:
                srv_id = url.split('/')[-1]
                msg_prefix = f"🖥 <b>服务器: {srv_id}</b>\n"
                self.log(f"\n🚀 开始处理服务器: {srv_id}")

                # 登录与 Cookie 注入
                sb.uc_open("https://hub.weirdhost.xyz/login")
                time.sleep(5)
                sb.add_cookie({'name': self.cookie_name, 'value': self.cookie_value, 'domain': 'hub.weirdhost.xyz'})
                sb.refresh()
                
                # 访问具体服务器页面
                sb.get(url)
                time.sleep(8)
                
                # 获取初始到期时间
                days_left, old_expiry = self.get_remaining_days(sb)
                if old_expiry:
                    self.log(f"📅 当前到期: {old_expiry} (剩余 {days_left} 天)")
                
                # 这里的阈值设为 30 以便进行强制续期测试
                if days_left is not None and days_left > 30:
                    self.log(f"✅ 剩余天数充足，跳过")
                    self.results.append(f"{msg_prefix}状态: ✅ 无需续期")
                    continue

                # --- 尝试续期操作 ---
                try:
                    renew_sel = 'button.bkrtgq'
                    if not sb.is_element_visible(renew_sel):
                        self.log("❌ 未找到续期按钮")
                        sb.save_screenshot(f"no_btn_{srv_id}.png")
                        continue

                    sb.click(renew_sel)
                    self.log("🔄 已点击续期按钮，处理 Turnstile 验证中...")
                    time.sleep(5)

                    # --- 核心改进：穿透 Iframe 强制点击 ---
                    turnstile_input = '[name="cf-turnstile-response"]'
                    if sb.is_element_present(turnstile_input):
                        self.log("🛡️ 检测到 Turnstile 验证框...")
                        
                        try:
                            # 1. 寻找包含验证码的 iframe
                            iframes = sb.find_elements("iframe")
                            for frame in iframes:
                                src = frame.get_attribute("src")
                                if src and "cloudflare" in src and "turnstile" in src:
                                    sb.switch_to_frame(frame)
                                    self.log("📥 已进入 CF Iframe")
                                    
                                    # 2. 强制点击复选框区域
                                    # 尝试多个可能的 ID 和选择器
                                    clicked = False
                                    for selector in ["#challenge-stage", "input[type='checkbox']", ".mark", "#rc-anchor-container"]:
                                        if sb.is_element_visible(selector):
                                            sb.click(selector)
                                            self.log(f"🖱 已点击验证元素: {selector}")
                                            clicked = True
                                            break
                                    
                                    sb.switch_to_default_content()
                                    if clicked: break
                        except Exception as e:
                            self.log(f"⚠️ Iframe 穿透失败: {e}")
                            sb.switch_to_default_content()

                        # 3. 等待 Token 生成
                        solved = False
                        for i in range(45):
                            token = sb.get_attribute(turnstile_input, "value")
                            if token and len(token) > 20:
                                self.log(f"✅ 验证成功 (耗时 {i}s)！")
                                solved = True
                                break
                            time.sleep(1)

                        if solved:
                            # 提交表单
                            sb.execute_script("document.querySelector('form')?.submit() || document.querySelector('button.bkrtgq')?.click();")
                            time.sleep(10)
                        else:
                            self.log("❌ 最终破解失败 (超时)")
                            sb.save_screenshot(f"fail_click_{srv_id}.png")
                    else:
                        self.log("⚡️ 未触发验证，直接通过")
                        time.sleep(3)

                except Exception as e:
                    self.log(f"⚠️ 续期过程异常: {e}")

                # --- 最终结果验证 ---
                self.log("🔍 验证最终结果...")
                sb.refresh()
                time.sleep(8)
                _, new_expiry = self.get_remaining_days(sb)
                
                if new_expiry and old_expiry and new_expiry > old_expiry:
                    status = "🎉 <b>续期成功</b>"
                else:
                    status = "❌ <b>续期失败</b>"
                    sb.save_screenshot(f"final_fail_{srv_id}.png")
                
                self.results.append(f"{msg_prefix}状态: {status}\n📅 新到期: {new_expiry if new_expiry else '未知'}")

        # 发送报告
        if self.results:
            self.send_tg_notification("<b>🚀 Weirdhost 续期任务报告</b>\n\n" + "\n\n".join(self.results))

if __name__ == "__main__":
    WeirdhostPureSB().run()
