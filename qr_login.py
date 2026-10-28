#!/usr/bin/env python3
"""Browserless Baidu QR login. Protocol reference: CharlesPikachu/DecryptLogin.

Independent implementation using only Python's standard library. No account
information is sent anywhere except official Baidu HTTPS endpoints.
"""
import argparse
import base64
import contextlib
import http.cookiejar
import json
from pathlib import Path
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import tempfile
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def private_write(path, content):
    """Atomically write a credential file with owner-only permissions on POSIX."""
    fd, temporary = tempfile.mkstemp(prefix='.cookie-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            handle.write(content)
        os.replace(temporary, path)
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temporary)


def run(args):
    output = args.output.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    jar = http.cookiejar.CookieJar()
    # Ignore stale environment proxies. SOCKS is deliberately not needed here.
    client = urllib.request.build_opener(urllib.request.ProxyHandler({}),
                                        urllib.request.HTTPCookieProcessor(jar))
    client.addheaders = [('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')]

    def get(url, params=None, timeout=35):
        if params:
            url += '?' + urllib.parse.urlencode(params)
        with client.open(url, timeout=timeout) as response:
            return response.read(), response.headers.get('Content-Type', '')

    def get_json(url, params=None, timeout=35):
        body, _ = get(url, params, timeout)
        return json.loads(body)

    data = get_json('https://passport.baidu.com/v2/api/getqrcode', {'lp': 'pc'})
    if data.get('errno') != 0 or not data.get('sign'):
        raise RuntimeError(f"二维码接口失败，errno={data.get('errno')}")
    sign = data['sign']
    image, content_type = get('https://passport.baidu.com/v2/api/qrcode',
                              {'sign': sign, 'lp': 'pc'})
    if not (image.startswith(b'\x89PNG') or image.startswith(b'\xff\xd8') or image.startswith(b'GIF8')):
        raise RuntimeError('二维码接口没有返回支持的图片格式。')
    image_path = output / 'qrcode.png'
    # Image may be JPEG; browser/image viewers detect its actual format.
    fd, temporary = tempfile.mkstemp(prefix='.qr-', dir=output)
    fd_path = Path(temporary)
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(image)
        os.replace(fd_path, image_path)
    finally:
        with contextlib.suppress(FileNotFoundError):
            fd_path.unlink()
    token = '/' + secrets.token_urlsafe(24)
    image_type = ('image/png' if image.startswith(b'\x89PNG') else
                  'image/jpeg' if image.startswith(b'\xff\xd8') else 'image/gif')
    image_data = base64.b64encode(image).decode('ascii')
    preview_html = ('''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<title>百度网盘扫码登录 · CookieLogin</title>
<style>
:root { color-scheme: only light; background: #fff; color: #17202a; }
* { box-sizing: border-box; }
body { margin: 0; min-height: 100vh; min-height: 100dvh; padding: 24px;
       display: grid; place-items: center; background: #fff;
       font-family: system-ui, sans-serif; }
main { width: 100%; max-width: 480px; text-align: center; }
h1 { margin: 0 0 12px; font-size: 24px; }
p { margin: 12px 0; line-height: 1.6; color: #4b5563; }
.qr { display: inline-block; max-width: 100%; padding: 24px;
      background: #fff; border: 1px solid #e5e7eb; border-radius: 12px; }
img { display: block; width: 288px; max-width: 100%; height: auto;
      background: #fff; image-rendering: pixelated; }
</style>
</head>
<body><main>
<h1>百度网盘扫码登录</h1>
<p>请用百度网盘 App 扫码，并在手机上确认登录。</p>
<div class="qr"><img alt="百度网盘登录二维码" src="data:''' + image_type +
                    ';base64,' + image_data + '''"></div>
<p>二维码过期后，请重新运行程序获取新二维码。</p>
</main></body></html>''').encode('utf-8')

    class Preview(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            if self.path != token:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(preview_html)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.end_headers()
            self.wfile.write(preview_html)

    try:
        server = ThreadingHTTPServer(('127.0.0.1', args.port), Preview)
    except OSError as error:
        image_path.unlink(missing_ok=True)
        raise RuntimeError(f'无法监听预览端口 {args.port}，请使用 --port 指定空闲端口。') from error
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f'扫码预览地址：http://127.0.0.1:{server.server_port}{token}', flush=True)
    print(f'二维码图片：{image_path}', flush=True)
    print('请用百度网盘 App 扫码并在手机上确认。二维码过期后重新运行。', flush=True)
    try:
        deadline = time.monotonic() + args.timeout
        ticket = None
        previous = None
        while time.monotonic() < deadline:
            now = int(time.time() * 1000)
            try:
                poll = get_json('https://passport.baidu.com/channel/unicast', {
                    'channel_id': sign, 'tpl': 'netdisk', 'apiver': 'v3', 'tt': now, '_': now,
                }, timeout=min(35, max(1, deadline - time.monotonic())))
            except (TimeoutError, urllib.error.URLError):
                time.sleep(1)
                continue
            channel = poll.get('channel_v') or {}
            if isinstance(channel, str):
                channel = json.loads(channel)
            status = channel.get('status')
            if poll.get('errno') == 0 and status == 0 and channel.get('v'):
                ticket = channel['v']
                break
            if status != previous:
                print('等待手机扫码或确认…', flush=True)
                previous = status
            time.sleep(1)
        if not ticket:
            raise RuntimeError('等待扫码超时或二维码已失效，请重新启动。')
        print('已收到手机确认，正在建立并验证网盘会话…', flush=True)
        get('https://passport.baidu.com/v3/login/main/qrbdusslogin', {
            'v': int(time.time() * 1000), 'bduss': ticket,
            'loginVersion': 'v4', 'qrcode': 1, 'tpl': 'netdisk', 'apiver': 'v3',
            'tt': int(time.time() * 1000),
        })
        get('https://pan.baidu.com/disk/main')
        quota = get_json('https://pan.baidu.com/api/quota', {'checkexpire': 1, 'checkfree': 1})
        if quota.get('errno') != 0 or not isinstance(quota.get('total'), (int, float)):
            raise RuntimeError(f"扫码后网盘验证失败（errno={quota.get('errno')}），未导出 Cookie。")
        request = urllib.request.Request('https://pan.baidu.com/')
        jar.add_cookie_header(request)
        header = request.get_header('Cookie') or ''
        cookies = [c for c in jar if c.domain.lstrip('.') == 'baidu.com' or
                   c.domain.lstrip('.').endswith('.baidu.com')]
        names = {c.name for c in cookies}
        if 'BDUSS' not in names:
            raise RuntimeError('验证后没有获得 BDUSS，未导出 Cookie。')
        serialized = [{'name': c.name, 'value': c.value, 'domain': c.domain,
                       'path': c.path, 'expires': c.expires if c.expires is not None else -1,
                       'secure': c.secure, 'httpOnly': c.has_nonstandard_attr('HttpOnly')}
                      for c in cookies]
        private_write(output / 'cookie.txt', header + '\n')
        private_write(output / 'cookies.json', json.dumps(serialized, ensure_ascii=False, indent=2) + '\n')
        print(f'网盘登录验证成功，Cookie 已保存至：{output}', flush=True)
        print('已取得 BDUSS；' + ('已取得 STOKEN。' if 'STOKEN' in names else '未取得 STOKEN，部分转存功能可能不可用。'), flush=True)
    finally:
        server.shutdown()
        server.server_close()
        with contextlib.suppress(FileNotFoundError):
            image_path.unlink()


def main():
    parser = argparse.ArgumentParser(description='无需浏览器的百度网盘扫码登录（仅 Python 标准库）')
    parser.add_argument('--version', action='version', version='CookieLogin 1.0.1')
    parser.add_argument('--port', type=int, default=8766)
    parser.add_argument('--timeout', type=int, default=300)
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parent / 'output')
    args = parser.parse_args()
    if args.timeout <= 0 or not 0 <= args.port <= 65535:
        parser.error('timeout 必须为正数，port 必须在 0 到 65535 之间')
    try:
        run(args)
    except KeyboardInterrupt:
        print('\n已取消。')
        return 130
    except Exception as error:
        # Network exceptions can include a login ticket in the request URL.
        if isinstance(error, (urllib.error.URLError, urllib.error.HTTPError)):
            print('网络请求失败。请检查官方接口连接后重试。', flush=True)
        elif isinstance(error, RuntimeError):
            print(f'运行失败：{error}', flush=True)
        else:
            print(f'运行失败（{type(error).__name__}），未输出包含凭据的响应。', flush=True)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
