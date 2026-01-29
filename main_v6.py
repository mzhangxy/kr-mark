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
        self.results = []  # 必须在这里初始化

    def send_tg_notification(self, message):
        """发送 Telegram 通知 (带重试机制)"""
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

    def get_remaining_days(self, page, prefix=""):
        """解析页面上的到期时间"""
        try:
            target = page.get_by_text(re.compile(r"202\d-\d{2}-\d{2}")).first
            target.wait_for(state="visible", timeout=15000)
            
            raw_text = target.inner_text()
            match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', raw_text)
            if match:
                expiry_date = datetime.strptime(match.group(1), '%Y-%m-%d %H:%M:%S')
                days = (expiry_date - datetime.now()).days
                print(f"{prefix}解析到期时间: {expiry_date}，剩余约 {days} 天")
                return days, expiry_date
        except Exception as e:
            print(f"{prefix}时间解析失败: {e}")
        return None, None

    def solve_turnstile(self, page, srv_id):
        """2captcha 破解逻辑 + 详细调试"""
        print(f"🛡️ 正在请求 2captcha 破解... (服务器: {srv_id})")
        in_res = requests.post("https://2captcha.com/in.php", data={
            'key': self.api_key, 'method': 'turnstile', 'sitekey': self.sitekey,
            'pageurl': page.url, 'json': 1
        }).json()

        print(f"2captcha in.php 响应: {in_res}")
        if in_res.get("status") != 1:
            print("2captcha 提交任务失败")
            return False

        task_id = in_res.get("request")
        print(f"任务已提交，ID: {task_id}")

        for i in range(30):
            time.sleep(5)
            res = requests.get(f"https://2captcha.com/res.php?key={self.api_key}&action=get&id={task_id}&json=1").json()
            print(f"轮询 {i+1}/30: {res}")
            if res.get("status") == 1:
                token = res.get("request")
                print(f"成功获取 token (长度:{len(token)}): {token[:20]}...{token[-20:]}")

                # 注入 token
                page.evaluate(f'document.querySelector("[name=cf-turnstile-response]").value = "{token}";')
                page.evaluate('if (typeof cfCallback === "function") { cfCallback(); }')

                # 立即验证是否真的注入成功
                injected_value = page.evaluate('''() => {
                    const elem = document.querySelector("[name='cf-turnstile-response']");
                    return elem ? elem.value : "元素不存在或找不到";
                }''')
                print(f"注入后实际获取到的 token 值: {injected_value}")

                # 保存注入后截图
                page.screenshot(path=f"after_token_inject_{srv_id}.png")
                print(f"保存 token 注入后截图: after_token_inject_{srv_id}.png")

                return True
            if res.get("request") != "CAPCHA_NOT_READY":
                print(f"2captcha 返回异常状态: {res.get('request')}")
                break
        print("2captcha 破解超时或失败")
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

            playwright = sync_playwright().start()
            browser = playwright.chromium.launch(
                headless=True,
                args=['--disable-blink-features=AutomationControlled']
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                proxy=proxy_settings,
                viewport={'width': 1280, 'height': 800}
            )

            cookie_name = 'remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d'
            context.add_cookies([{
                'name': cookie_name,
                'value': self.cookie_value,
                'domain': 'hub.weirdhost.xyz',
                'path': '/',
                'expires': int(time.time()) + 31536000,
                'httpOnly': True, 'secure': True, 'sameSite': 'Lax'
            }])

            page = context.new_page()

            # 验证代理
            print("📡 验证代理出口 IP...")
            page.goto("https://api.ipify.org", wait_until="domcontentloaded", timeout=30000)
            ip_text = page.inner_text("body").strip()
            print(f"当前出口 IP: {ip_text}")

            if "211.221.75" not in ip_text:
                raise Exception(f"代理未生效！当前 IP: {ip_text}")

            print("✅ 代理验证通过")

            for url in self.server_urls:
                srv_id = url.split('/')[-1]
                print(f"\n🚀 处理服务器: {srv_id} → {url}")

                try:
                    print("访问目标页面...")
                    page.goto(url, wait_until="networkidle", timeout=60000)
                    page.wait_for_timeout(5000)
                    page.screenshot(path=f"page_loaded_{srv_id}.png")
                    print(f"保存页面加载完成截图: page_loaded_{srv_id}.png")

                    # 保存加载完成后的源码
                    with open(f"page_loaded_source_{srv_id}.html", "w", encoding="utf-8") as f:
                        f.write(page.content())
                    print(f"保存页面源码: page_loaded_source_{srv_id}.html")

                    # 检查到期时间
                    days_left, expiry_date = self.get_remaining_days(page, "初始加载 → ")
                    time_str = expiry_date.strftime('%Y-%m-%d') if expiry_date else "未知"

                    if days_left is not None and days_left > 6:
                        self.results.append(f"🖥 `Server:{srv_id}`\n📅 到期:{time_str}\n✅ 剩余{days_left}天，无需操作")
                        continue

                    # 查找续期按钮
                    renew_btn = page.locator("button:has-text('시간추가')").first
                    if not renew_btn.is_visible():
                        renew_btn = page.locator("button.bkrtgq").first

                    if renew_btn.is_visible():
                        print(f"找到续期按钮 → 准备点击")
                        page.screenshot(path=f"before_renew_click_{srv_id}.png")
                        print(f"保存点击续期按钮前截图: before_renew_click_{srv_id}.png")

                        renew_btn.click()
                        page.wait_for_timeout(4000)

                        page.screenshot(path=f"after_renew_click_{srv_id}.png")
                        print(f"保存点击续期按钮后截图: after_renew_click_{srv_id}.png")

                        turnstile_locator = page.locator("[name='cf-turnstile-response']")
                        if turnstile_locator.count() > 0:
                            print("检测到 Turnstile 元素")
                            print(f"Turnstile 元素数量: {turnstile_locator.count()}")
                            page.screenshot(path=f"turnstile_detected_{srv_id}.png")
                            print(f"保存检测到 Turnstile 截图: turnstile_detected_{srv_id}.png")

                            if self.solve_turnstile(page, srv_id):
                                page.wait_for_timeout(8000)
                                page.screenshot(path=f"after_renew_success_{srv_id}.png")
                                print(f"保存续期操作完成后截图: after_renew_success_{srv_id}.png")
                                self.results.append(f"🖥 `Server:{srv_id}`\n📅 到期:{time_str}\n🎉 续期操作成功")
                            else:
                                self.results.append(f"🖥 `Server:{srv_id}`\n❌ 验证码破解失败")
                        else:
                            print("未检测到 Turnstile 元素")
                            page.screenshot(path=f"no_turnstile_{srv_id}.png")
                            self.results.append(f"🖥 `Server:{srv_id}`\n✅ 续期完成 (免验证)")
                    else:
                        print("未找到续期按钮")
                        page.screenshot(path=f"missing_btn_{srv_id}.png")
                        self.results.append(f"🖥 `Server:{srv_id}`\n❌ 未找到续期按钮")

                    # 最终验证：刷新页面再看一次到期时间
                    print("最终验证：刷新页面检查到期时间...")
                    page.reload(wait_until="networkidle", timeout=30000)
                    page.wait_for_timeout(3000)
                    final_days, final_expiry = self.get_remaining_days(page, "最终验证 → ")
                    final_time = final_expiry.strftime('%Y-%m-%d %H:%M:%S') if final_expiry else "未知"
                    print(f"刷新后到期: {final_time}，剩余约 {final_days} 天")
                    page.screenshot(path=f"final_check_{srv_id}.png")

                except Exception as e:
                    print(f"处理 {srv_id} 时异常: {str(e)}")
                    if page:
                        page.screenshot(path=f"error_{srv_id}.png")
                    self.results.append(f"🖥 `Server:{srv_id}`\n💥 异常: {str(e)[:50]}")

            # Cookie 检查
            print("🔍 检查 Cookie 状态...")
            new_cookie_val = None
            current_cookies = context.cookies()
            for ck in current_cookies:
                if ck['name'].startswith('remember_web_'):
                    if ck['value'] != self.cookie_value:
                        new_cookie_val = ck['value']
                        break

            if new_cookie_val:
                self.results.append(f"🔄 *检测到 Cookie 更新*\n新的凭证已产生，请更新 Secret：\n`{new_cookie_val}`")

        except Exception as e:
            print(f"❌ 整体运行异常: {e}")
            if page:
                try:
                    page.screenshot(path="global_error.png")
                    print("已保存全局错误截图: global_error.png")
                except:
                    pass
            raise

        finally:
            print("🧹 清理浏览器资源...")
            if page:
                try: page.close()
                except: pass
            if context:
                try: context.close()
                except: pass
            if browser:
                try: browser.close()
                except: pass
            if playwright:
                try: playwright.stop()
                except: pass

        # 发送报告
        if self.results:
            report = "🤖 *Weirdhost 运行报告*\n\n" + "\n\n".join(self.results)
            self.send_tg_notification(report)

if __name__ == "__main__":
    bot = WeirdhostUltimate()
    bot.run()
