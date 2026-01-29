import os
import time
import re
import requests
from datetime import datetime
from playwright.sync_api import sync_playwright

class WeirdhostUltimate:
    def __init__(self):
        self.api_key = os.getenv('TWOCAPTCHA_API_KEY')
        self.cookie_value = os.getenv('REMEMBER_WEB_COOKIE')
        self.server_urls = [url.strip() for url in os.getenv('WEIRDHOST_SERVER_URLS', '').split(',') if url.strip()]
        self.tg_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.tg_chat_id = os.getenv('TELEGRAM_CHAT_ID')
        self.sitekey = "0x4AAAAAACJH5atUUlnM2w2u"
        self.results = []

    def send_tg_notification(self, message):
        if not self.tg_token or not self.tg_chat_id:
            print("⚠️ 未配置 TG Token 或 Chat ID。")
            return
        
        url = f"https://api.telegram.org/bot{self.tg_token}/sendMessage"
        payload = {"chat_id": self.tg_chat_id, "text": message, "parse_mode": "Markdown"}

        for i in range(3):
            try:
                response = requests.post(url, json=payload, timeout=30)
                if response.status_code == 200:
                    print("✅ TG 通知发送成功！")
                    return
                else:
                    print(f"⚠️ TG 响应异常 (尝试 {i+1}/3): {response.status_code}")
            except Exception as e:
                print(f"❌ 第 {i+1} 次发送 TG 通知失败: {e}")
                if i < 2: time.sleep(5) 
        print("🛑 TG 通知最终发送失败。")

    def get_remaining_days(self, page):
        try:
            target = page.get_by_text(re.compile(r"202\d-\d{2}-\d{2}")).first
            target.wait_for(state="visible", timeout=15000)
            
            raw_text = target.inner_text()
            match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', raw_text)
            if match:
                expiry_date = datetime.strptime(match.group(1), '%Y-%m-%d %H:%M:%S')
                return (expiry_date - datetime.now()).days, expiry_date
        except Exception as e:
            print(f"⚠️ 时间解析提示: {e}")
        return None, None
    
    def solve_turnstile(self, page, srv_id):
        print(f"🛡️ 正在请求 2captcha 破解... (服务器: {srv_id})")
        in_res = requests.post("https://2captcha.com/in.php", data={
            'key': self.api_key, 'method': 'turnstile',
            'sitekey': self.sitekey, 'pageurl': page.url, 'json': 1
        }).json()

        print(f"2captcha 提交响应: {in_res}")
        if in_res.get("status") != 1:
            print("提交任务失败")
            return False

        task_id = in_res.get("request")
        print(f"任务ID: {task_id}")

        for poll in range(30):
            time.sleep(5)
            res = requests.get(f"https://2captcha.com/res.php?key={self.api_key}&action=get&id={task_id}&json=1").json()
            print(f"轮询 {poll+1}/30: {res}")
            if res.get("status") == 1:
                token = res.get("request")
                print(f"成功获取 token (长度 {len(token)}): {token[:30]}...")

                # 关键：切换到 Turnstile iframe 并模拟点击 checkbox
                try:
                    # 更宽松匹配 iframe（turnstile 或 cloudflare 相关）
                    iframe_locator = page.frame_locator('iframe[src*="turnstile"], iframe[src*="cloudflare"], iframe[src*="challenges"]')
                    print("尝试切换到 Turnstile iframe...")

                    # 等待 iframe 加载 checkbox
                    checkbox = iframe_locator.locator('input[type="checkbox"], div.cf-turnstile-checkbox, label[for*="cf-turnstile"]')
                    checkbox.wait_for(state="visible", timeout=15000)
                    print("找到 checkbox 元素")

                    # 模拟点击 checkbox（点击左边区域也行，locator 会自动处理）
                    checkbox.click(position={"x": 10, "y": 10})  # 点击 checkbox 左上角 10px 位置，模拟你本地行为
                    print("已模拟点击 checkbox")

                    # 等待验证成功（看 checkbox 是否变绿或弹窗消失）
                    page.wait_for_timeout(8000)  # 给 Cloudflare 时间处理
                    checkbox_state = checkbox.evaluate('el => el.checked || el.getAttribute("aria-checked") === "true" || false')
                    print(f"checkbox 状态（是否选中/验证通过）: {checkbox_state}")

                    # 检查弹窗是否关闭（如果有 modal）
                    modal = page.locator('div[role="dialog"], div.cf-modal')
                    if modal.count() == 0:
                        print("弹窗已关闭 → 验证很可能成功")
                    else:
                        print("弹窗仍存在 → 验证可能失败")

                    # 最终检查 hidden input 是否有 token
                    hidden_token = page.evaluate('document.querySelector("[name=\'cf-turnstile-response\']")?.value || "未找到"')
                    print(f"最终 hidden token: {hidden_token[:30]}...")

                    # 保存最终状态截图
                    page.screenshot(path=f"after_checkbox_click_{srv_id}.png")
                    print(f"保存 checkbox 点击后截图: after_checkbox_click_{srv_id}.png")

                    return True

                except Exception as e:
                    print(f"iframe / checkbox 操作失败: {e}")
                    # fallback: 只注入 token + 触发事件（旧方式）
                    page.evaluate(f"""
                        var elem = document.querySelector("[name='cf-turnstile-response']");
                        if (elem) elem.value = "{token}";
                        if (typeof cfCallback === 'function') cfCallback();
                    """)
                    page.wait_for_timeout(5000)
                    return True  # 假设 fallback 可能有效

            if res.get("request") != "CAPCHA_NOT_READY":
                print(f"2captcha 异常: {res.get('request')}")
                break

        print("破解超时或失败")
        return False

    def run(self):
        playwright = None
        browser = None
        context = None
        page = None

        try:
            print("🌐 启动浏览器...")
            proxy_settings = {
                "server": "socks5://127.0.0.1:10808",
            }

            playwright = sync_playwright().start()  # 手动启动 playwright
            browser = playwright.chromium.launch(headless=True, args=['--disable-blink-features=AutomationControlled'])
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                proxy=proxy_settings,
            )

            context.add_cookies([{
                'name': 'remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d',
                'value': self.cookie_value,
                'domain': 'hub.weirdhost.xyz', 'path': '/', 'httpOnly': True, 'secure': True
            }])

            page = context.new_page()
            
            print("📡 验证代理出口 IP...")
            try:
                page.goto("https://api.ipify.org", timeout=30000)
                ip_text = page.inner_text("body").strip()
                print(f"当前出口 IP: {ip_text}")
                
                if "211.221" not in ip_text:
                    raise Exception(f"代理未生效！当前 IP: {ip_text} （期望包含 211.221）")
                print("✅ 代理验证通过")
            except Exception as e:
                print(f"❌ 代理验证失败: {e}")
                browser.close()
                raise

            # --- 业务逻辑开始 ---
            for url in self.server_urls:
                srv_id = url.split('/')[-1]
                msg_prefix = f"🖥 <b>服务器: {srv_id}</b>\n"
                try:
                    print(f"\n🚀 目标服务器: {url}")
                    page.goto(url, wait_until="domcontentloaded", timeout=60000)
                    time.sleep(5)

                    # 1. 检查到期时间
                    days_left, expiry_date = self.get_remaining_days(page)
                    expiry_info = f"📅 到期: {expiry_date if expiry_date else '未知'}\n"
                    
                    if days_left is not None:
                        print(f"📅 到期时间: {expiry_date}")
                        print(f"⏳ 剩余天数: {days_left} 天")
                        if days_left > 6:
                            print("✅ 剩余时间充裕 (>6天)，跳过续期。")
                            status = "✅ <b>无需续期</b> (剩余 > 6天)"
                            self.results.append(f"{msg_prefix}{expiry_info}状态: {status}")
                            continue
                    else:
                        print("⚠️ 未能识别到期时间，将尝试续期流程。")

                    # 2. 点击续期按钮
                    renew_btn = page.locator("button.bkrtgq").first
                    if renew_btn.is_visible():
                        print("鼠标 找到续期按钮，准备操作...")
                        renew_btn.click()
                        page.wait_for_timeout(3000)
                        
                        if page.locator("[name='cf-turnstile-response']").count() > 0:
                            print("🕒 检测到 Turnstile 验证槽位 (Invisible 模式)...")
                            if self.solve_turnstile(page):
                                print("⏳ 注入成功，等待系统响应...")
                                page.wait_for_timeout(7000)
                                print("🎉 续期操作已完成！")
                                status = "🎉 <b>续期成功!</b>"
                            else:
                                print("❌ 验证码破解失败或超时。")
                                status = "❌ <b>破解失败</b>"
                        else:
                            print("ℹ️ 未发现验证码输入框，可能已直接通过验证。")
                            status = "⚡️ <b>直接通过</b> (未触发盾)"
                            page.wait_for_timeout(3000)
                    else:
                        print("⏭️ 页面上未找到续期按钮。")
                        status = "⏭ <b>未找到按钮，请登录检查验证</b>"
                    
                    self.results.append(f"{msg_prefix}{expiry_info}状态: {status}")
                        
                except Exception as e:
                    self.results.append(f"{msg_prefix}❌ <b>运行异常</b>: {str(e)[:50]}")
            
            browser.close()
            print("\n🏁 所有任务执行完毕。")

            if self.results:
                full_message = "<b>🚀 Weirdhost 自动续期报告</b>\n\n" + "\n\n".join(self.results)
                self.send_tg_notification(full_message)

        except Exception as e:
            print(f"❌ 运行异常: {e}")
            if page:
                try:
                    page.screenshot(path="error_screenshot.png")
                    print("已保存错误截图: error_screenshot.png")
                except:
                    pass
            raise  # 让 workflow 标记失败

        finally:
            # 安全清理资源
            print("🧹 清理浏览器资源...")
            if page:
                try:
                    page.close()
                except:
                    pass
            if context:
                try:
                    context.close()
                except:
                    pass
            if browser:
                try:
                    browser.close()
                except:
                    pass
            if playwright:
                try:
                    playwright.stop()
                except:
                    pass

if __name__ == "__main__":
    bot = WeirdhostUltimate()
    bot.run()
