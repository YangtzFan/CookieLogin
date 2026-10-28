# CookieLogin

通过百度网盘 App 扫码获取自己的网页登录 Cookie，适用于 SSH 服务器。无需 Chromium、Playwright、pip 或管理员权限，仅使用 Python 标准库。

已在 Linux + Windows SSH 场景完成一次真实登录：获取二维码、手机确认、网盘容量接口验证成功，并导出 BDUSS 和 STOKEN。百度接口变化可能影响兼容性；每次运行都会验证登录结果。

## 快速开始

需要 Python 3.10 或更新版本。

```bash
git clone git@github.com:YangtzFan/CookieLogin.git
cd CookieLogin
./start.sh
```

也可以直接执行，适用于 Linux、macOS 和 Windows：

```bash
python3 qr_login.py
```

Windows 可使用 `py -3 qr_login.py`。程序直连百度官方 HTTPS 接口，不使用环境变量中的代理，目前不提供代理参数。

## 通过 SSH 查看二维码

在你自己的电脑上建立端口转发，并保持连接：

```bash
ssh -N -L 8766:127.0.0.1:8766 用户名@服务器地址
```

如果使用 SSH 别名，例如 `open3`：

```bash
ssh -N -L 8766:127.0.0.1:8766 open3
```

在服务器运行 `./start.sh` 后，复制终端打印的完整地址，例如 `http://127.0.0.1:8766/随机标识`，在自己电脑的浏览器打开。必须保留随机路径。用百度网盘 App 扫码，并在手机上确认。

预览仅监听服务器的 `127.0.0.1`，无需开放防火墙。二维码过期后重新运行；每次运行会生成新的地址。已有端口转发可继续复用。

### 不使用端口转发

程序等待扫码时，也可以在 Windows 本地 PowerShell 下载并打开二维码图片。请替换服务器别名和项目绝对路径：

```powershell
scp open3:/path/to/CookieLogin/output/qrcode.png "$env:TEMP\baidu-qrcode.png"
Invoke-Item "$env:TEMP\baidu-qrcode.png"
```

二维码文件在程序退出后自动从服务器删除，本地副本可自行删除。

## Cookie 输出

只有手机确认、网盘容量接口验证通过，并取得 BDUSS 后，才生成或替换以下文件：

| 文件 | 内容 |
| --- | --- |
| `output/cookie.txt` | 适用于 `https://pan.baidu.com/` 的 Cookie 请求头内容 |
| `output/cookies.json` | 百度域 Cookie 数组，含名称、值、域名、路径、有效期等字段 |

终端会单独提示是否取得 STOKEN，缺少 STOKEN 可能影响转存功能。Cookie 值不会显示在终端。失败时已有的 Cookie 文件保持原样，可能属于以前的登录。

输出文件在 POSIX 系统上以 `600` 权限原子写入，新建输出目录使用 `700` 权限。Windows 文件访问权限遵循系统 ACL。Cookie 等同于登录凭据，请仅在可信的本地程序中使用，不要提交至 Git 或发送给他人。二维码和带随机标识的预览地址也请勿分享。

`cookies.json` 可供支持此结构的工具使用，或导入 Playwright 的 `context.add_cookies()`。`cookie.txt` 可用于需要 Cookie 请求头的本地客户端。

## 参数

```bash
./start.sh --port 8767 --timeout 600 --output ./my-cookies
./start.sh --help
./start.sh --version
```

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `--port` | `8766` | 本地二维码预览端口；使用其他端口时同步修改 SSH 转发 |
| `--timeout` | `300` | 二维码获取成功后最多等待扫码的秒数；二维码自身可能更早失效 |
| `--output` | 项目目录中的 `output/` | Cookie 和临时二维码输出目录 |

网络请求另有超时，程序实际结束时间可能略晚于等待上限。程序退出后关闭预览服务；已建立的 SSH 转发可手动关闭。

## 常见问题

- **`Address already in use` 或无法监听端口**：用 `--port` 指定空闲端口，并调整 SSH 转发。
- **浏览器打不开预览**：确认服务器程序正在等待扫码、SSH 转发保持连接，且地址包含本次运行生成的完整随机路径。
- **`remote port forwarding failed for listen port 1081`**：这是 SSH 配置中其他远程转发的警告，是否影响 SSH 会话取决于配置；本项目使用的本地预览端口默认是 8766。
- **扫码超时或接口不兼容**：重新运行生成二维码。如果重复失败，请检查到 `passport.baidu.com` 和 `pan.baidu.com` 的 HTTPS 连接。项目不会绕过百度要求的验证。

## 开发与打包

测试不会连接百度，也不会读取真实 Cookie：

```bash
python3 -m unittest discover -s tests -v
```

从 Git 跟踪的源文件生成发布包，避免打入本地登录数据：

```bash
git archive --format=tar.gz --prefix=CookieLogin/ -o ../CookieLogin-v1.0.0.tar.gz HEAD
```

仓库仅包含程序、启动脚本、文档和测试。默认输出、虚拟环境、缓存及常见凭据文件都由 `.gitignore` 排除；自定义输出目录也应保持在 Git 仓库外。

## 实现来源

二维码请求和轮询协议参考 [CharlesPikachu/DecryptLogin 的 baidupanScanQR](https://github.com/CharlesPikachu/DecryptLogin/blob/master/DecryptLogin/modules/core/baidupan.py)。本项目使用 Python 标准库独立实现，并增加 SSH 图片预览、网盘会话验证、私有文件导出和退出清理。它获取网页登录 Cookie，不是 OAuth access_token，也不依赖第三方登录中转服务。
