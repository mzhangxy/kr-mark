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
        # 移除了 2Captcha API Key，因为不再需要
        self.cookie_name = 'remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d'
        self.cookie_value = os.getenv('REMEMBER_WEB_COOKIE', '')
        self.server_urls = [url.strip() for url in os.getenv('WEIRDHOST_SERVER_URLS', '').split(',') if url.strip()]
        self.tg_token = os.getenv('TG_BOT_TOKEN') or os.getenv('TELEGRAM_BOT_TOKEN')
        self.tg_chat_id = os.getenv('TG_CHAT_ID') or os.getenv('TELEGRAM_CHAT_ID')
        self.results = []
        
        # 插件下载配置
        self.ext_url = "https://github.com/NopeCHALLC/nopecha-extension/releases/download/0.5.5/chromium_automation.zip"
        self.ext_dir_name = "nopecha_extension"

    def log(self, msg):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

    def send_tg_notification(self, message):
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

    def setup_extension(self):
        """下载并解压 NopeCHA 扩展"""
        cwd = os.getcwd()
        ext_path = os.path.join(cwd, self.ext_dir_name)

        # 如果目录存在且有 manifest.json，假设已下载好
        if os.path.exists(ext_path) and os.path.exists(os.path.join(ext_path, "manifest.json")):
            self.log(f"✅ 检测到扩展目录: {ext_path}")
            return ext_path
        
        self.log("⬇️ 正在下载 NopeCHA 扩展...")
        try:
            # 清理旧目录（如果有）
            if os.path.exists(ext_path):
                shutil.rmtree(ext_path)
            
            resp = requests.get(self.ext_url, timeout=30)
            if resp.status_code == 200:
                with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
                    z.extractall(ext_path)
                self.log(f"✅ 扩展下载并解压成功: {ext_path}")
                return ext_path
            else:
                self.log(f"❌ 下载失败，状态码: {resp.status_code}")
                return None
        except Exception as e:
            self.log(f"❌ 扩展准备失败: {e}")
            return None

    def get_remaining_days(self, sb):
        try:
            source = sb.get_page_source()
            match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', source)
            if match:
                expiry_str = match.group(1)
                expiry = datetime.strptime(expiry_str, '%Y-%m-%d %H:%M:%S')
                days = (expiry - datetime.now()).days
                self.log(f"📅 从页面解析到期: {expiry_str}，剩余 {days} 天")
                return days, expiry
            self.log("⚠️ 页面上未找到日期格式文本")
            return None, None
        except Exception as e:
            self.log(f"⚠️ 时间解析异常: {str(e)[:80]}")
            return None, None

    def run(self):
        # 1. 准备扩展路径
        ext_path = self.setup_extension()
        if not ext_path:
            self.log("❌ 无法加载扩展，终止运行")
            return

        self.log("🌐 启动 SeleniumBase UC 模式 (带扩展)...")
        
        # 2. 在 SB 初始化中加入 extension_dir
        with SB(uc=True, xvfb=True, headless2=True, proxy="127.0.0.1:10808", extension_dir=ext_path) as sb:
            # 验证代理
            self.log("📡 验证出口 IP...")
            try:
                sb.get("https://api.ipify.org")
                time.sleep(5)
                ip = sb.get_text("body").strip()
                self.log(f"✅ 代理 IP: {ip}")
            except:
                self.log("⚠️ 无法获取 IP，继续尝试...")

            # 等待一小会儿让扩展初始化
            time.sleep(3)

            for url in self.server_urls:
                srv_id = url.split('/')[-1]
                msg_prefix = f"🖥 <b>服务器: {srv_id}</b>\n"
                self.log(f"\n🚀 处理服务器: {srv_id}")

                # 进入域名上下文
                self.log("🔗 进入域名中...")
                sb.uc_open("https://hub.weirdhost.xyz/login")  
                time.sleep(8)
                sb.wait_for_ready_state_complete(timeout=15)

                current_url_lower = sb.get_current_url().lower()
                if "weirdhost.xyz" not in current_url_lower:
                    self.log(f"⚠️ 域名不匹配: {sb.get_current_url()}")
                    sb.save_screenshot(f"proxy_err_{srv_id}.png")
                    self.results.append(f"{msg_prefix}状态: ❌ 代理/域名失败")
                    continue

                # 注入 Cookie
                self.log("🔑 注入 Cookie...")
                try:
                    sb.add_cookie({
                        'name': self.cookie_name,
                        'value': self.cookie_value,
                        'domain': 'hub.weirdhost.xyz',
                        'path': '/',
                        'httpOnly': True,
                        'secure': True
                    })
                    sb.refresh()
                    self.log("✅ Cookie 注入完成")
                except Exception as e:
                    self.log(f"❌ Cookie 注入失败: {e}")
                    self.results.append(f"{msg_prefix}状态: ❌ Cookie 注入失败")
                    continue

                # 访问目标服务器页
                sb.get(url)
                time.sleep(10)
                sb.wait_for_ready_state_complete(timeout=15)

                # 检查是否成功进入后台
                source = sb.get_page_source()
                if "시간추가" not in source and not re.search(r'202\d-\d{2}-\d{2}', source):
                    self.log("🛡️ 状态异常")
                    sb.save_screenshot(f"status_err_{srv_id}.png")
                    self.results.append(f"{msg_prefix}状态: ❌ 进入后台失败")
                    continue

                self.log("✅ 成功进入后台")

                # 解析剩余天数
                days_left, expiry = self.get_remaining_days(sb)
                expiry_info = f"📅 到期: {expiry.strftime('%Y-%m-%d %H:%M:%S') if expiry else '未知'}\n"

                if days_left is not None and days_left > 9:
                    self.log(f"⏳ 剩余 {days_left} 天 (>9)，跳过续期")
                    status = "✅ <b>无需续期</b> (剩余 > 9天)"
                    self.results.append(f"{msg_prefix}{expiry_info}状态: {status}")
                    continue

                # 尝试续期
                self.log("🔄 尝试续期...")
                renew_sel = 'button.bkrtgq'
                try:
                    sb.wait_for_element_visible(renew_sel, timeout=12)
                    sb.click(renew_sel)
                    time.sleep(5) # 给一点时间让弹窗或挑战出现

                    # 处理 Turnstile
                    turnstile_sel = '[name="cf-turnstile-response"]'
                    
                    # 检查是否存在 Turnstile 元素
                    if sb.is_element_present(turnstile_sel):
                        self.log("🕒 检测到 Turnstile，等待 NopeCHA 扩展自动处理...")
                        
                        # 这里我们不需要调用 API，而是等待扩展完成工作
                        # 扩展成功后，通常 token 输入框会有值，或者表单会自动提交
                        
                        max_wait = 40
                        solved = False
                        for i in range(max_wait):
                            # 方法1: 检查 token 是否已填入
                            token_val = sb.get_attribute(turnstile_sel, "value")
                            if token_val:
                                self.log(f"✅ 扩展已成功获取 Token (耗时 {i}s)")
                                solved = True
                                break
                            
                            # 方法2: 有时候扩展点完后页面直接刷新或跳转了，检查 Turnstile 是否消失
                            if not sb.is_element_present(turnstile_sel):
                                self.log("✅ Turnstile 元素消失，可能已通过")
                                solved = True
                                break
                                
                            time.sleep(1)

                        if solved:
                            time.sleep(2)
                            # 如果页面没有自动提交，尝试手动提交一次
                            self.log("🔄 尝试触发提交...")
                            sb.execute_script("document.querySelector('form')?.submit() || document.querySelector('button.bkrtgq')?.click();")
                            time.sleep(8)
                            status = "🎉 <b>续期成功 (Extension)</b>"
                        else:
                            self.log("❌ 扩展处理超时")
                            status = "❌ <b>Turnstile 处理超时</b>"
                            sb.save_screenshot(f"turnstile_fail_{srv_id}.png")

                    else:
                        self.log("ℹ️ 未触发 Turnstile，可能直接通过")
                        status = "⚡️ <b>直接通过</b> (未触发盾)"
                        time.sleep(3)

                except Exception as e:
                    self.log(f"⚠️ 续期按钮处理异常: {e}")
                    sb.save_screenshot(f"no_btn_{srv_id}.png")
                    status = "⏭ <b>未找到按钮或异常</b>"

                # 验证续期是否成功
                self.log("🔍 验证续期结果...")
                sb.refresh()
                time.sleep(8)
                sb.wait_for_ready_state_complete(timeout=20)
                new_days_left, new_expiry = self.get_remaining_days(sb)
                
                # 只有当日期确实增加了（或者原本失败了但现在有日期了）才算成功
                # 注意：如果原本剩余天数很少，续期后 new_days_left 应该变大
                if new_days_left is not None:
                     expiry_info = f"📅 新到期: {new_expiry.strftime('%Y-%m-%d %H:%M:%S') if new_expiry else '未知'}\n"
                     
                     if days_left is None or new_days_left >= days_left:
                         self.log("✅ 续期验证通过")
                     else:
                         # 日期反而变少了？不太可能，除非解析错误
                         status = "⚠️ <b>续期存疑（日期未增加）</b>"
                else:
                    self.log("⚠️ 无法获取新日期，可能续期失败")
                    sb.save_screenshot(f"post_renew_fail_{srv_id}.png")
                    status = "⚠️ <b>续期失败（验证未通过）</b>"

                self.results.append(f"{msg_prefix}{expiry_info}状态: {status}")

        if self.results:
            report = "<b>🚀 Weirdhost 自动续期报告 (Ext版)</b>\n\n" + "\n\n".join(self.results)
            self.send_tg_notification(report)
        self.log("🏁 所有任务执行完毕")

if __name__ == "__main__":
    bot = WeirdhostPureSB()
    bot.run()
