# CookieLogin

通过百度网盘 App 扫码获取自己的网页登录 Cookie。仅使用 Python 标准库，无需安装浏览器自动化工具或第三方 Python 依赖。

## 适用系统

需要 **Python 3.10 或更新版本**，并能直接通过 HTTPS 访问 `passport.baidu.com` 和 `pan.baidu.com`。

| 电脑系统 | 启动命令 | 使用方式 |
| --- | --- | --- |
| Linux | `./start.sh` 或 `python3 qr_login.py` | 桌面电脑直接打开预览；无桌面服务器可通过 SSH 转发查看 |
| macOS | `./start.sh` 或 `python3 qr_login.py` | 在本机浏览器打开预览 |
| Windows | `py -3 qr_login.py` | 在本机浏览器打开预览，无需 WSL 或 Bash |

Linux 已完成实际运行验证；macOS 和 Windows 使用相同的跨平台标准库实现，尚未进行原生系统实测。`start.sh` 适用于提供 Bash 的环境，Windows 推荐直接使用 Python 命令。

扫码需要手机上的百度网盘 App。程序直连百度官方接口，不使用环境变量中的代理，目前不提供代理参数。

## 快速开始

获取项目：

```bash
git clone git@github.com:YangtzFan/CookieLogin.git
cd CookieLogin
```

也可从仓库页面下载 ZIP 后解压。使用 SSH 克隆需要配置 GitHub SSH 密钥。

Linux / macOS：

```bash
python3 qr_login.py
```

Windows PowerShell：

```powershell
py -3 qr_login.py
```

### 在本地电脑执行

**程序和浏览器在同一台电脑上时，无需执行 SSH 转发命令。**

1. 启动程序并保持终端运行。
2. 用这台电脑的浏览器打开终端打印的完整地址，例如 `http://127.0.0.1:8766/随机标识`，保留本次生成的随机路径。
3. 用百度网盘 App 扫描页面中央的白底二维码，并在手机上确认。
4. 登录验证成功后，Cookie 保存到项目的 `output/` 目录，程序自动退出。

二维码过期后，重新运行程序并打开新的预览地址。

### 在远程服务器上执行

在服务器启动程序后，在自己的电脑上建立 SSH 转发并保持连接：

```bash
ssh -N -L 8766:127.0.0.1:8766 用户名@服务器地址
```

随后在自己电脑的浏览器中打开程序打印的完整预览地址，扫码确认。预览服务仅监听服务器的 `127.0.0.1`，无需开放防火墙；已有的对应端口转发可继续复用。

也可以在等待扫码期间，将服务器的 `output/qrcode.png` 复制到本地打开。程序退出时会删除服务器上的二维码图片。

## Cookie 输出

手机确认后，程序会验证网盘会话，只有验证通过且取得 BDUSS 时才写入文件：

| 文件 | 内容 |
| --- | --- |
| `output/cookie.txt` | 适用于 `https://pan.baidu.com/` 的 Cookie 请求头内容 |
| `output/cookies.json` | 包含名称、值、域名、路径和有效期等信息的 Cookie 数组 |

终端会提示是否取得 STOKEN，缺少它可能影响转存功能。失败时不会覆盖已有 Cookie 文件。百度接口变化可能影响扫码登录的兼容性。

Cookie 等同于登录凭据，请勿分享或提交到 Git。Cookie 值不会显示在终端；文件在 Linux / macOS 上以 `600` 权限写入，新建输出目录使用 `700` 权限，Windows 上遵循系统 ACL。二维码和预览地址也请勿分享。

## 参数

Linux / macOS 示例：

```bash
python3 qr_login.py --port 8767 --timeout 600 --output ./my-cookies
python3 qr_login.py --help
python3 qr_login.py --version
```

Windows 将 `python3` 替换为 `py -3` 即可。

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `--port` | `8766` | 预览端口；远程使用时同步修改 SSH 转发端口 |
| `--timeout` | `300` | 最多等待扫码的秒数，二维码本身可能更早失效 |
| `--output` | 项目目录中的 `output/` | Cookie 和临时二维码的保存目录 |

网络请求另有超时，程序实际结束时间可能略晚于等待上限。

## 常见问题

- **端口被占用**：用 `--port` 指定空闲端口；远程使用时同步调整 SSH 转发。
- **预览打不开**：确认程序仍在运行，地址包含本次生成的随机路径；远程使用时确认 SSH 转发保持连接。
- **扫码超时或失败**：重新运行程序获取新二维码；如反复失败，检查到百度官方接口的 HTTPS 连接。

## 开发与打包

运行离线测试，不连接百度或读取真实 Cookie：

```bash
python3 -m unittest discover -s tests -v
```

从 Git 跟踪的源文件生成发布包：

```bash
git archive --format=tar.gz --prefix=CookieLogin/ -o ../CookieLogin-v1.0.1.tar.gz HEAD
```

默认输出、缓存和常见凭据文件已由 `.gitignore` 排除。自定义输出目录应放在仓库外，避免误提交登录数据。

## 实现来源

二维码协议参考 [CharlesPikachu/DecryptLogin 的 baidupanScanQR](https://github.com/CharlesPikachu/DecryptLogin/blob/master/DecryptLogin/modules/core/baidupan.py)。本项目使用 Python 标准库独立实现，提供二维码预览、网盘会话验证和 Cookie 本地导出。获取的是网页登录 Cookie，而非 OAuth access_token。
