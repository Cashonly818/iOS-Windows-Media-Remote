"""
PC Media Remote - 主应用入口
Flask Web 服务器 + WebSocket + API 路由
"""

import os
import sys
import io
import json
import socket
import datetime
import secrets
import hashlib
import threading
import base64
import webbrowser

from flask import Flask, render_template, jsonify, request, send_from_directory, Response
from flask_cors import CORS
from flask_sock import Sock

# ---------- 初始化 Flask ----------
app = Flask(__name__,
            template_folder='templates',
            static_folder='static',
            static_url_path='/static')
app.secret_key = secrets.token_hex(16)
CORS(app, supports_credentials=True)

# ---------- WebSocket ----------
sock = Sock(app)

# ---------- 加载控制器 ----------
from controllers.volume import VolumeController
from controllers.media import MediaController
from controllers.system import SystemController
from controllers.potplayer import PotPlayerController
from controllers.netease import NeteaseController
from controllers.auth import AuthManager

volume_ctrl = VolumeController()
media_ctrl = MediaController()
system_ctrl = SystemController()
potplayer_ctrl = PotPlayerController()
netease_ctrl = NeteaseController()
auth_mgr = AuthManager()

# ---------- 全局变量 ----------
ws_clients = []  # 活跃的 WebSocket 客户端列表
server_start_time = datetime.datetime.now()

# ================================================================
#  HTML 页面
# ================================================================

@app.route('/')
def index():
    """主页面 - 响应式遥控器界面"""
    return render_template('index.html',
                          pc_name=system_ctrl.get_pc_name(),
                          has_pin=auth_mgr.is_pin_set())

# ================================================================
#  API 路由
# ================================================================

def _check_auth():
    """检查请求是否通过 PIN 验证"""
    if not auth_mgr.is_pin_set():
        return True
    token = request.headers.get('X-Auth-Token', '')
    return auth_mgr.verify_token(token)


@app.route('/api/ping')
def api_ping():
    """健康检查 / 服务发现"""
    return jsonify({
        "ok": True,
        "pc_name": system_ctrl.get_pc_name(),
        "version": "1.0.0",
        "server_time": datetime.datetime.now().strftime("%H:%M:%S"),
        "has_pin": auth_mgr.is_pin_set()
    })


@app.route('/api/status')
def api_status():
    """获取完整系统状态"""
    if not _check_auth():
        return jsonify({"ok": False, "error": "需要 PIN 验证"}), 401

    song_info = netease_ctrl.get_current_song()
    progress = media_ctrl.get_progress_info()
    is_playing = progress['playing']  # 仅由按键跟踪决定, 不合并其他来源

    smtc_dur = song_info.get('duration', 0)
    smtc_pos = song_info.get('position', 0)

    return jsonify({
        "ok": True,
        "pc_name": system_ctrl.get_pc_name(),
        "time": datetime.datetime.now().strftime("%H:%M"),
        "date": datetime.datetime.now().strftime("%Y年%m月%d日"),
        "volume": volume_ctrl.get_volume_percent(),
        "muted": volume_ctrl.get_mute(),
        "playing": is_playing,
        "song": {
            'title': song_info.get('title', ''),
            'artist': song_info.get('artist', ''),
            'album': song_info.get('album', ''),
            'source': song_info.get('source', ''),
            'position': smtc_pos if smtc_dur > 0 else progress['position'],
            'duration': smtc_dur if smtc_dur > 0 else progress['duration'],
            'playing': is_playing,
        },
        "smtc_available": netease_ctrl.is_available,
        "uptime": system_ctrl.get_uptime_str()
    })


@app.route('/api/auth', methods=['POST'])
def api_auth():
    """PIN 验证"""
    data = request.get_json(silent=True) or {}
    pin = data.get('pin', '')
    if auth_mgr.verify_pin(pin):
        token = auth_mgr.generate_token()
        return jsonify({"ok": True, "token": token})
    return jsonify({"ok": False, "error": "PIN 错误"}), 403


@app.route('/api/auth/status')
def api_auth_status():
    """检查是否需要 PIN"""
    return jsonify({
        "ok": True,
        "pin_required": auth_mgr.is_pin_set(),
        "pin_hint": auth_mgr.get_pin_hint()
    })


# ---------- 媒体控制 ----------

@app.route('/api/seek', methods=['POST'])
def api_seek():
    """跳转到指定位置"""
    if not _check_auth():
        return jsonify({"ok": False, "error": "需要验证"}), 401
    data = request.get_json(silent=True) or {}
    position = data.get('position', 0)
    try:
        position = float(position)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "无效的位置"}), 400

    # 根据播放源选择跳转方式
    if potplayer_ctrl.is_running:
        # PotPlayer 专用: Ctrl+G 精确定位
        potplayer_ctrl.seek_to(position)
    else:
        # SMTC (Spotify/浏览器等) 或降级方案
        if not netease_ctrl.seek_to(position):
            media_ctrl.seek_approximate(position)
    _broadcast_status()
    return jsonify({"ok": True, "position": position})


@app.route('/api/playpause', methods=['POST'])
def api_playpause():
    if not _check_auth():
        return jsonify({"ok": False, "error": "需要验证"}), 401
    success = media_ctrl.play_pause()
    _broadcast_status()
    return jsonify({"ok": success})


@app.route('/api/next', methods=['POST'])
def api_next():
    if not _check_auth():
        return jsonify({"ok": False, "error": "需要验证"}), 401
    success = media_ctrl.next_track()
    return jsonify({"ok": success})


@app.route('/api/previous', methods=['POST'])
def api_previous():
    if not _check_auth():
        return jsonify({"ok": False, "error": "需要验证"}), 401
    success = media_ctrl.previous_track()
    return jsonify({"ok": success})


# ---------- 音量控制 ----------

@app.route('/api/volumeup', methods=['POST'])
def api_volume_up():
    if not _check_auth():
        return jsonify({"ok": False, "error": "需要验证"}), 401
    new_vol = volume_ctrl.volume_up()
    _broadcast_status()
    return jsonify({"ok": True, "volume": new_vol})


@app.route('/api/volumedown', methods=['POST'])
def api_volume_down():
    if not _check_auth():
        return jsonify({"ok": False, "error": "需要验证"}), 401
    new_vol = volume_ctrl.volume_down()
    _broadcast_status()
    return jsonify({"ok": True, "volume": new_vol})


@app.route('/api/volume', methods=['POST'])
def api_volume_set():
    """设置音量到指定值"""
    if not _check_auth():
        return jsonify({"ok": False, "error": "需要验证"}), 401
    data = request.get_json(silent=True) or {}
    level = data.get('level', 50)
    new_vol = volume_ctrl.set_volume(level)
    _broadcast_status()
    return jsonify({"ok": True, "volume": new_vol})


@app.route('/api/mute', methods=['POST'])
def api_mute():
    if not _check_auth():
        return jsonify({"ok": False, "error": "需要验证"}), 401
    muted = volume_ctrl.toggle_mute()
    _broadcast_status()
    return jsonify({"ok": True, "muted": muted})


# ---------- 系统控制 ----------

@app.route('/api/lock', methods=['POST'])
def api_lock():
    if not _check_auth():
        return jsonify({"ok": False, "error": "需要验证"}), 401
    success = system_ctrl.lock_screen()
    return jsonify({"ok": success})


@app.route('/api/sleep', methods=['POST'])
def api_sleep():
    if not _check_auth():
        return jsonify({"ok": False, "error": "需要验证"}), 401
    success = system_ctrl.sleep()
    return jsonify({"ok": success})


@app.route('/api/shutdown', methods=['POST'])
def api_shutdown():
    if not _check_auth():
        return jsonify({"ok": False, "error": "需要验证"}), 401
    # 关机前需要二次确认
    data = request.get_json(silent=True) or {}
    if not data.get('confirm'):
        return jsonify({"ok": False, "error": "需要 confirm 参数确认关机"}), 400
    success = system_ctrl.shutdown()
    return jsonify({"ok": success})


@app.route('/api/restart', methods=['POST'])
def api_restart():
    if not _check_auth():
        return jsonify({"ok": False, "error": "需要验证"}), 401
    data = request.get_json(silent=True) or {}
    if not data.get('confirm'):
        return jsonify({"ok": False, "error": "需要 confirm 参数确认重启"}), 400
    success = system_ctrl.restart()
    return jsonify({"ok": success})


# ---------- 通用播放控制 (SMTC + 键盘 + PotPlayer) ----------

def _smtc_seek_relative(delta_sec: float) -> bool:
    """通过 SMTC 相对跳转 (优先方案)"""
    try:
        pos = netease_ctrl.get_current_song().get('position', 0)
        dur = netease_ctrl.get_current_song().get('duration', 0)
        if dur > 0:
            target = max(0, min(dur, pos + delta_sec))
            return netease_ctrl.seek_to(target)
    except Exception:
        pass
    return False

def _send_key_combo(*keys):
    """发送组合键 (pyautogui)"""
    try:
        import pyautogui
        pyautogui.hotkey(*keys)
        return True
    except Exception:
        return False


@app.route('/api/fullscreen', methods=['POST'])
def api_fullscreen():
    """全屏切换"""
    if not _check_auth():
        return jsonify({"ok": False, "error": "需要验证"}), 401
    if potplayer_ctrl.is_running:
        potplayer_ctrl.fullscreen()
    else:
        _send_key_combo('alt', 'enter')
    return jsonify({"ok": True})


@app.route('/api/seek/forward', methods=['POST'])
def api_seek_forward():
    """快进 10 秒"""
    if not _check_auth():
        return jsonify({"ok": False, "error": "需要验证"}), 401
    if potplayer_ctrl.is_running:
        potplayer_ctrl.seek_forward(10)
    else:
        for _ in range(3):
            _send_key_combo('right')
        _smtc_seek_relative(10)
    _broadcast_status()
    return jsonify({"ok": True})


@app.route('/api/seek/backward', methods=['POST'])
def api_seek_backward():
    """后退 10 秒"""
    if not _check_auth():
        return jsonify({"ok": False, "error": "需要验证"}), 401
    if potplayer_ctrl.is_running:
        potplayer_ctrl.seek_backward(10)
    else:
        for _ in range(3):
            _send_key_combo('left')
        _smtc_seek_relative(-10)
    _broadcast_status()
    return jsonify({"ok": True})


@app.route('/api/speed', methods=['POST'])
def api_speed():
    """设置倍速 — PotPlayer"""
    if not _check_auth():
        return jsonify({"ok": False, "error": "需要验证"}), 401
    data = request.get_json(silent=True) or {}
    speed = data.get('speed', 1.0)
    ok = potplayer_ctrl.set_speed(speed)
    return jsonify({"ok": ok})


# ---------- 网易云音乐 ----------

@app.route('/api/netease/song')
def api_netease_song():
    """获取当前播放的歌曲信息"""
    if not _check_auth():
        return jsonify({"ok": False, "error": "需要验证"}), 401
    song = netease_ctrl.get_current_song()
    return jsonify({"ok": True, "song": song})


@app.route('/api/netease/cover')
def api_netease_cover():
    """获取专辑封面图片 (base64)"""
    if not _check_auth():
        return jsonify({"ok": False, "error": "需要验证"}), 401
    cover = netease_ctrl.get_album_cover()
    return jsonify({"ok": True, "cover": cover})


# ================================================================
#  WebSocket - 实时状态推送
# ================================================================

@sock.route('/ws')
def websocket_handler(ws):
    """WebSocket 连接处理"""
    ws_clients.append(ws)
    print(f"[WS] 客户端连接 (当前 {len(ws_clients)} 个)")
    try:
        while True:
            # 等待客户端消息 (心跳或请求)
            message = ws.receive()
            if message is None:
                break
            msg = json.loads(message) if isinstance(message, str) else {}
            if msg.get('action') == 'get_status':
                # 客户端请求状态
                status_data = _build_status_data()
                ws.send(json.dumps(status_data, ensure_ascii=False))
            elif msg.get('action') == 'ping':
                ws.send(json.dumps({"type": "pong"}))
    except Exception as e:
        print(f"[WS] 连接异常: {e}")
    finally:
        if ws in ws_clients:
            ws_clients.remove(ws)
        print(f"[WS] 客户端断开 (当前 {len(ws_clients)} 个)")


def _broadcast_status():
    """向所有 WebSocket 客户端广播当前状态"""
    if not ws_clients:
        return
    data = json.dumps(_build_status_data(), ensure_ascii=False)
    dead = []
    for ws in ws_clients:
        try:
            ws.send(data)
        except Exception:
            dead.append(ws)
    for ws in dead:
        ws_clients.remove(ws)


def _build_status_data():
    """构建状态数据字典"""
    song_info = netease_ctrl.get_current_song()
    progress = media_ctrl.get_progress_info()
    is_playing = progress['playing']
    smtc_dur = song_info.get('duration', 0)
    smtc_pos = song_info.get('position', 0)

    return {
        "type": "status",
        "pc_name": system_ctrl.get_pc_name(),
        "time": datetime.datetime.now().strftime("%H:%M"),
        "date": datetime.datetime.now().strftime("%Y年%m月%d日"),
        "volume": volume_ctrl.get_volume_percent(),
        "muted": volume_ctrl.get_mute(),
        "playing": is_playing,
        "song": {
            'title': song_info.get('title', ''),
            'artist': song_info.get('artist', ''),
            'album': song_info.get('album', ''),
            'source': song_info.get('source', ''),
            'position': smtc_pos if smtc_dur > 0 else progress['position'],
            'duration': smtc_dur if smtc_dur > 0 else progress['duration'],
            'playing': is_playing,
        },
        "smtc_available": netease_ctrl.is_available,
    }


# ================================================================
#  PWA 支持
# ================================================================

@app.route('/manifest.json')
def manifest():
    """PWA 清单文件"""
    return send_from_directory('static', 'manifest.json')


@app.route('/sw.js')
def service_worker():
    """Service Worker"""
    return send_from_directory('static', 'sw.js', mimetype='application/javascript')


# ================================================================
#  二维码 — 手机扫码直接连接 (替代不可靠的 HTTP 扫描)
# ================================================================

# 全局缓存二维码 (启动时生成)
_qrcode_base64 = None
_qrcode_url = None


def _generate_qrcode():
    """生成服务器 URL 的二维码图片"""
    global _qrcode_base64, _qrcode_url
    local_ip = system_ctrl.get_lan_ip()
    _qrcode_url = f"http://{local_ip}:8080"
    try:
        import qrcode
        qr = qrcode.QRCode(box_size=10, border=2)
        qr.add_data(_qrcode_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color='black', back_color='white')
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        _qrcode_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')
    except ImportError:
        print("[QRCode] qrcode 库未安装，跳过二维码生成。pip install qrcode[pil]")


@app.route('/welcome')
def welcome():
    """欢迎页 — 展示二维码供手机扫描"""
    return render_template('welcome.html', url=_qrcode_url)


@app.route('/api/qrcode')
def api_qrcode():
    """获取二维码图片和 URL"""
    return jsonify({
        "ok": True,
        "url": _qrcode_url,
        "qrcode_base64": _qrcode_base64,
    })


@app.route('/qrcode.png')
def qrcode_image():
    """直接返回二维码 PNG 图片"""
    if _qrcode_base64:
        img_data = base64.b64decode(_qrcode_base64)
        return Response(img_data, mimetype='image/png')
    return Response('QR code not available', status=404)


# ================================================================
#  启动入口
# ================================================================

def print_banner():
    """打印启动横幅"""
    local_ip = system_ctrl.get_lan_ip()
    border = "=" * 54
    print(f"""
{border}
     PC Media Remote  v1.0.0
{border}
  电脑名称: {system_ctrl.get_pc_name()}
  本地地址: http://{local_ip}:8080
  本机地址: http://127.0.0.1:8080
  PIN 验证: {'已启用' if auth_mgr.is_pin_set() else '未设置'}
{border}
  iPhone 扫码连接:
  打开页面后点击二维码图标即可扫码
  或在 Safari 直接输入上方地址
{border}""")


def main():
    """主启动函数"""
    _generate_qrcode()
    print_banner()

    # 自动在电脑浏览器打开二维码页面 (用手机扫屏幕即可连接)
    def _open_browser():
        import time
        time.sleep(1)  # 等服务器就绪
        webbrowser.open(f'http://127.0.0.1:8080/welcome')
    threading.Thread(target=_open_browser, daemon=True).start()

    print("[Server] 服务器启动中...")
    app.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False)


if __name__ == '__main__':
    main()
