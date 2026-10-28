"""Offline tests using synthetic responses; never open real accounts or secrets."""
import contextlib
import http.cookiejar
import io
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import qr_login


class FakeResponse:
    def __init__(self, body, content_type='application/json'):
        self.body = body
        self.headers = {'Content-Type': content_type}

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass


class FakeClient:
    def __init__(self, jar, quota_ok=True):
        self.jar = jar
        self.quota_ok = quota_ok

    def open(self, url, timeout):
        if '/getqrcode?' in url:
            data = {'errno': 0, 'sign': 'synthetic-sign'}
        elif '/qrcode?' in url:
            return FakeResponse(b'\x89PNG\r\n\x1a\nsynthetic', 'image/png')
        elif '/unicast?' in url:
            data = {'errno': 0, 'channel_v': json.dumps({'status': 0, 'v': 'synthetic-ticket'})}
        elif '/qrbdusslogin?' in url:
            for name in ('BDUSS', 'STOKEN'):
                self.jar.set_cookie(http.cookiejar.Cookie(
                    0, name, 'synthetic-only', None, False, '.baidu.com', True,
                    True, '/', True, True, None, True, None, None, {}, False))
            data = {}
        elif '/disk/main' in url:
            data = {}
        elif '/api/quota?' in url:
            data = {'errno': 0, 'total': 1024} if self.quota_ok else {'errno': -6}
        else:
            raise AssertionError('Unexpected request')
        return FakeResponse(json.dumps(data).encode())


class FakeServer:
    def __init__(self, *_):
        self.server_port = 8766
        self.closed = False

    def serve_forever(self):
        pass

    def shutdown(self):
        pass

    def server_close(self):
        self.closed = True


class LoginTests(unittest.TestCase):
    def invoke(self, directory, quota_ok=True):
        def build(*handlers):
            jar = handlers[1].cookiejar
            return FakeClient(jar, quota_ok)
        args = SimpleNamespace(output=Path(directory), port=8766, timeout=300)
        with patch.object(qr_login.urllib.request, 'build_opener', side_effect=build), \
             patch.object(qr_login, 'ThreadingHTTPServer', FakeServer), \
             contextlib.redirect_stdout(io.StringIO()) as messages:
            qr_login.run(args)
        return messages.getvalue()

    def test_success_exports_credentials_and_removes_qr(self):
        with tempfile.TemporaryDirectory() as directory:
            text = self.invoke(directory)
            output = Path(directory)
            self.assertIn('网盘登录验证成功', text)
            self.assertNotIn('synthetic-only', text)
            self.assertNotIn('synthetic-ticket', text)
            self.assertIn('BDUSS=synthetic-only', (output / 'cookie.txt').read_text())
            cookies = json.loads((output / 'cookies.json').read_text())
            self.assertEqual({c['name'] for c in cookies}, {'BDUSS', 'STOKEN'})
            self.assertFalse((output / 'qrcode.png').exists())
            if os.name == 'posix':
                self.assertEqual((output / 'cookie.txt').stat().st_mode & 0o777, 0o600)

    def test_failed_verification_preserves_previous_cookie(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'cookie.txt'
            path.write_text('previous-synthetic-cookie')
            with self.assertRaisesRegex(RuntimeError, '验证失败'):
                self.invoke(directory, quota_ok=False)
            self.assertEqual(path.read_text(), 'previous-synthetic-cookie')
            self.assertFalse((Path(directory) / 'cookies.json').exists())
            self.assertFalse((Path(directory) / 'qrcode.png').exists())

    def test_timeout_removes_qr_and_does_not_export(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(qr_login.time, 'monotonic', side_effect=[0, 301]):
                with self.assertRaisesRegex(RuntimeError, '超时'):
                    self.invoke(directory)
            self.assertFalse((Path(directory) / 'cookie.txt').exists())
            self.assertFalse((Path(directory) / 'qrcode.png').exists())

    def test_private_write_replaces_symlink_without_touching_target(self):
        if os.name != 'posix':
            self.skipTest('POSIX symlink and mode behavior')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / 'target'
            target.write_text('untouched')
            output = root / 'cookie.txt'
            output.symlink_to(target)
            qr_login.private_write(output, 'replacement')
            self.assertFalse(output.is_symlink())
            self.assertEqual(target.read_text(), 'untouched')
            self.assertEqual(output.read_text(), 'replacement')
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)


if __name__ == '__main__':
    unittest.main()
