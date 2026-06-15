# 🎵 iOS-Windows Media Remote

**iPhone 浏览器控制 Windows 电脑媒体播放** — 无需安装 App，扫码即用。

> iOS Safari 打开 → 遥控 Windows 上的 Spotify / 网易云 / QQ音乐 / PotPlayer / YouTube / VLC …

<p align="center">
  <img src="https://img.shields.io/badge/platform-Windows%2010%2F11-blue" alt="Platform">
  <img src="https://img.shields.io/badge/python-3.12+-green" alt="Python">
  <img src="https://img.shields.io/badge/ios-15+-lightgrey" alt="iOS">
  <img src="https://img.shields.io/badge/license-MIT-yellow" alt="License">
</p>

---

## ✨ 功能

### 媒体控制
- **播放 / 暂停 / 上一首 / 下一首** — 系统多媒体键，兼容所有播放器
- **进度条拖动跳转** — 支持 SMTC（Spotify、Chrome YouTube）精确跳转，PotPlayer Ctrl+G 跳转
- **快进 / 后退 10 秒** — 方向键 + SMTC 双通道
- **音量控制** — 系统音量滑块 + 静音
- **全屏切换** — Alt+Enter 通用快捷键

### 歌曲信息
- 自动读取 **歌名 / 歌手**（窗口标题检测）
- 支持 **SMTC 真实时长**（Spotify、Chrome、Edge、UWP 应用）
- 播放进度实时同步（WebSocket + 按键计时双保险）

### PotPlayer 专属
- 全屏 / 快进 / 后退 / 倍速播放（0.5x ~ 2x）
- 进度条拖动 → 自动打开定位对话框精确定位

### 系统控制
- 🔒 锁屏 / 😴 息屏 / ⏻ 关机 / 🔄 重启

### 连接方式
- 📷 **二维码扫码** — 启动时自动打开浏览器显示二维码，手机相机扫即连
- 🔍 **局域网扫描** — 覆盖 10 个常见网段
- ✍️ **手动输入 IP**

### 安全 & 体验
- 🔐 PIN 码验证（可选）
- 📱 **PWA 支持** — 添加到 iPhone 桌面，像原生 App 一样使用
- 🌙 iOS 风格深色毛玻璃 UI
- 📱 iPad 横屏双栏适配

---

## 🚀 快速开始

### 方式一：双击运行（推荐）

下载 [PC_Media_Remote.exe](https://github.com/Cashonly818/iOS-Windows-Media-Remote/releases) → 双击 → 浏览器弹出二维码 → 手机扫码

### 方式二：Python 源码运行

```bash
# 环境: Python 3.12+, Windows 10/11
git clone https://github.com/Cashonly818/iOS-Windows-Media-Remote.git
cd PC-Media-Remote/server
pip install -r requirements.txt
python app.py
```

启动后终端打印：
```
======================================================
     PC Media Remote  v1.0.0
======================================================
  电脑名称: MyPC
  本地地址: http://192.168.1.100:8080
======================================================
  浏览器已打开二维码页面，手机扫描即可连接
======================================================
```

### iPhone 连接

1. 相机扫描二维码 → Safari 自动打开
2. **自动进入遥控界面**（无需手动操作）
3. 建议：分享 → 添加到主屏幕 → 下次从桌面图标一键打开

---

## 📁 项目结构

```
PC-Media-Remote/
├── server/
│   ├── app.py                    # Flask 主程序 (REST + WebSocket)
│   ├── controllers/
│   │   ├── volume.py             # 系统音量 (pycaw)
│   │   ├── media.py              # 媒体键 + 进度跟踪 (pyautogui)
│   │   ├── system.py             # 锁屏/关机/重启
│   │   ├── potplayer.py          # PotPlayer 专属控制
│   │   ├── netease.py            # 歌曲信息 (窗口标题 + SMTC)
│   │   └── auth.py               # PIN 认证
│   ├── templates/
│   │   ├── index.html            # 遥控器页面
│   │   └── welcome.html          # 二维码欢迎页
│   ├── static/
│   │   ├── css/style.css         # iOS 风格样式
│   │   ├── js/app.js             # 前端逻辑
│   │   ├── manifest.json         # PWA
│   │   ├── sw.js                 # Service Worker
│   │   └── icons/                # App 图标
│   ├── requirements.txt
│   ├── start_server.bat          # 一键启动
│   └── auto_start.vbs            # 开机自启
├── build_exe.py                  # PyInstaller 打包脚本
└── README.md
```

---

## 📡 API

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/ping` | 服务发现 |
| `GET` | `/api/status` | 完整状态 (音量/播放/歌曲/进度) |
| `POST` | `/api/playpause` | 播放/暂停 |
| `POST` | `/api/next` | 下一首 |
| `POST` | `/api/previous` | 上一首 |
| `POST` | `/api/volume` | 设置音量 `{level:60}` |
| `POST` | `/api/seek` | 跳转 `{position:120}` |
| `POST` | `/api/seek/forward` | 快进 10 秒 |
| `POST` | `/api/seek/backward` | 后退 10 秒 |
| `POST` | `/api/fullscreen` | 全屏切换 |
| `POST` | `/api/speed` | 倍速 `{speed:1.5}` |
| `POST` | `/api/lock` | 锁屏 |
| `POST` | `/api/shutdown` | 关机 `{confirm:true}` |
| `POST` | `/api/restart` | 重启 `{confirm:true}` |
| `WS` | `/ws` | WebSocket 实时状态推送 |

---

## 🔧 打包为 EXE

```bash
pip install pyinstaller
python build_exe.py
# 输出: dist/PC_Media_Remote.exe (~37MB, 无需 Python)
```

### 开机自启

将 `PC_Media_Remote.exe` 快捷方式放入：
```
Win+R → shell:startup → 粘贴快捷方式
```

---

## ⚠️ 说明

- **仅限个人局域网使用**，请勿暴露到公网
- 网易云音乐 Win32 版不支持 SMTC（无时长数据），UWP 版完整支持
- Spotify / Chrome / Edge / YouTube 完整支持 SMTC（时长 + 精确跳转）
- PotPlayer 使用 Ctrl+G 对话框实现精确定位
- 关机/重启有 60 秒延迟，可在电脑上 `shutdown /a` 取消

---

## 🛠 技术栈

| 层 | 技术 |
|----|------|
| 服务端 | Python 3.12 / Flask / flask-sock |
| 音量 | pycaw (Windows Core Audio) |
| 媒体键 | pyautogui |
| 歌曲信息 | pywin32 (窗口标题) + winsdk (SMTC) |
| 前端 | Vanilla HTML/CSS/JS |
| 实时通信 | WebSocket |
| PWA | Service Worker + Manifest |
| 打包 | PyInstaller → 单文件 EXE |

---

## 📄 License

MIT — 仅供个人使用
