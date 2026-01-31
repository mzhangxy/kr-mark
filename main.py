import os
import time
import re
import requests
import zipfile
import io
import shutil
from datetime import datetime, timedelta
from seleniumbase import SB

class WeirdhostPureSB:
    def __init__(self):
        self.cookie_name = 'remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d'
        self.cookie_value = os.getenv('REMEMBER_WEB_COOKIE', '')
        self.server_urls = [url.strip() for url in os.getenv('WEIRDHOST_SERVER_URLS', '').split(',') if url.strip()]
        self.tg_token = os.getenv('TG_BOT_TOKEN') or os.getenv('TELEGRAM_BOT_TOKEN')
        self.tg_chat_id = os.getenv('TG_CHAT_ID') or os.getenv('TELEGRAM_CHAT_ID')
        self.results = []
        
        # 扩展配置
        self.ext_url = "https://github.com/NopeCHALLC/nopecha-extension/releases/download/0.5.5/chromium_automation.zip"
        self.ext_dir = "nopecha_extension"

    def log(self, msg):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

    def download_and_extract_extension(self):
        if os.path.exists(self.ext_dir):
            shutil.rmtree(self.ext_dir)
        
        self.log(f"⬇️ 正在下载 NopeCHA 扩展...")
        try:
            r = requests.get(self.ext_url, timeout=30)
            with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                z.extractall(self.ext_dir)
            self.log("✅ 扩展下载并解压成功")
            return os.path.abspath(self.ext_dir)
        except Exception as e:
            self.log(f"❌ 扩展下载失败: {e}")
            return None

    def send_tg_notification(self, message):
        if not self.tg_token or not self.tg_chat_id:
            return
        try:
            requests.post(
                f"https://api.telegram.org/bot{self.tg_token}/sendMessage",
                json={"chat_id": self.tg_chat_id, "text": message, "parse_mode": "HTML"},
                timeout=10
            )
        except Exception as e:
            self.log(f"❌ TG 发送失败: {e}")

    def get_remaining_days(self, sb):
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
        ext_path = self.download_and_extract_extension()
        if not ext_path:
            return

        self.log("🌐 启动 SeleniumBase UC 模式 (带扩展)...")
        # 增加 incognito=True 有时能避开部分缓存检测，但在扩展模式下慎用（有些扩展不支持）
        with SB(uc=True, xvfb=True, headless2=True, proxy="127.0.0.1:10808", extension_dir=ext_path) as sb:
            
            # 验证代理
            try:
                sb.get("https://api.ipify.org")
                time.sleep(2)
                self.log(f"📡 代理 IP: {sb.get_text('body').strip()}")
            except:
                pass

            for url in self.server_urls:
                srv_id = url.split('/')[-1]
                msg_prefix = f"🖥 <b>服务器: {srv_id}</b>\n"
                
                # 登录流程
                self.log(f"\n🚀 处理服务器: {srv_id}")
                sb.uc_open("https://hub.weirdhost.xyz/login")
                time.sleep(5)
                sb.add_cookie({'name': self.cookie_name, 'value': self.cookie_value, 'domain': 'hub.weirdhost.xyz'})
                sb.refresh()
                
                sb.get(url)
                time.sleep(8)
                
                # 初始状态检查
                days_left, old_expiry = self.get_remaining_days(sb)
                if old_expiry:
                    self.log(f"📅 当前到期: {old_expiry}")
                
                if days_left is not None and days_left > 4:
                    self.results.append(f"{msg_prefix}状态: ✅ 无需续期 (剩余 {days_left} 天)")
                    continue

                # 执行续期
                try:
                    renew_sel = 'button.bkrtgq'
                    if not sb.is_element_visible(renew_sel):
                        self.log("❌ 未找到续期按钮")
                        self.results.append(f"{msg_prefix}状态: ❌ 未找到按钮")
                        continue

                    sb.click(renew_sel)
                    self.log("🔄 已点击续期按钮，等待处理...")
                    time.sleep(5)

                    # ----------------------
                    # 新的过盾逻辑 (混合模式)
                    # ----------------------
                    turnstile_sel = '[name="cf-turnstile-response"]'
                    if sb.is_element_present(turnstile_sel):
                        self.log("🛡️ 检测到 Turnstile，开始混合破解...")
                        
                        solved = False
                        # 阶段1: 等待扩展自动处理 (20秒)
                        for i in range(20):
                            val = sb.get_attribute(turnstile_sel, "value")
                            if val and len(val) > 20:
                                self.log("✅ 扩展自动破解成功！")
                                solved = True
                                break
                            time.sleep(1)
                        
                        # 阶段2: 如果扩展没动静，尝试“手动”点击 iframe 中心唤醒它
                        if not solved:
                            self.log("⚠️ 扩展响应慢，尝试物理唤醒 (UC GUI Click)...")
                            try:
                                sb.uc_gui_click_captcha() # SB 自带的 CV 识别点击
                                time.sleep(5)
                            except:
                                pass
                        
                        # 阶段3: 继续等待 (再等 60秒)
                        if not solved:
                            self.log("⏳ 等待最终结果...")
                            for i in range(60):
                                # 检查 Token
                                val = sb.get_attribute(turnstile_sel, "value")
                                if val and len(val) > 20:
                                    self.log("✅ 最终获取到 Token！")
                                    solved = True
                                    break
                                # 检查是否已经跳过验证（元素消失）
                                if not sb.is_element_present(turnstile_sel):
                                    self.log("✅ 验证框消失，可能已通过")
                                    solved = True
                                    break
                                time.sleep(1)

                        if solved:
                            # 确保提交
                            time.sleep(2)
                            sb.execute_script("document.querySelector('form')?.submit() || document.querySelector('button.bkrtgq')?.click();")
                            time.sleep(10)
                        else:
                            self.log("❌ 最终破解失败 (超时)")
                            sb.save_screenshot(f"fail_{srv_id}.png")
                            status = "❌ <b>Turnstile 超时</b>"
                    else:
                        self.log("⚡️ 未触发验证，直接通过")
                        time.sleep(3)

                except Exception as e:
                    self.log(f"⚠️ 执行异常: {e}")
                    status = "⚠️ <b>脚本错误</b>"

                # ----------------------
                # 严格的验证逻辑
                # ----------------------
                self.log("🔍 验证最终结果...")
                sb.refresh()
                time.sleep(8)
                _, new_expiry = self.get_remaining_days(sb)
                
                if new_expiry and old_expiry:
                    self.log(f"📅 新的到期时间: {new_expiry}")
                    # 只有时间确实增加了才算成功
                    if new_expiry > old_expiry:
                        status = "🎉 <b>续期成功</b>"
                    elif new_expiry == old_expiry:
                        status = "⚠️ <b>续期失败 (时间未变)</b>"
                        sb.save_screenshot(f"fail_renew_{srv_id}.png")
                    else:
                        status = "❓ <b>状态未知</b>"
                else:
                    status = "⚠️ <b>无法读取新日期</b>"

                self.results.append(f"{msg_prefix}状态: {status}")

        if self.results:
            self.send_tg_notification("<b>🚀 Weirdhost 续期报告 (Ext版)</b>\n\n" + "\n\n".join(self.results))
            
if __name__ == "__main__":
    WeirdhostPureSB().run()
