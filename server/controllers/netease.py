"""
媒体信息读取器
- 窗口标题检测: 获取歌名/歌手 (网易云/Spotify/QQ音乐/浏览器等)
- SMTC (winsdk): 获取播放进度/时长/状态 (Windows 系统媒体控件)

数据合并策略:
  - 歌名/歌手 → 优先窗口标题 (更完整), SMTC 兜底
  - 播放进度/时长 → 仅 SMTC (精确), SMTC 不可用时用按键计时估算
  - 播放状态 → SMTC 优先, 窗口标题兜底
"""

import re
import asyncio
import threading
import time
from typing import Optional, Dict, Any

try:
    import win32gui
    import win32process
    import psutil
    _WIN32_OK = True
except ImportError:
    _WIN32_OK = False
    print("[MediaInfo] pywin32/psutil 未安装")

try:
    from winsdk.windows.media.control import \
        GlobalSystemMediaTransportControlsSessionManager as SMTCManager, \
        GlobalSystemMediaTransportControlsSessionPlaybackStatus as PlaybackStatus
    _SMTC_OK = True
except ImportError:
    _SMTC_OK = False
    print("[MediaInfo] winsdk 未安装，SMTC 不可用 (pip install winsdk)")


class NeteaseController:
    """窗口标题 + SMTC 双通道媒体信息读取"""

    # ---- 窗口检测配置 ----
    MEDIA_APPS = [
        'cloudmusic.exe', 'spotify.exe', 'qqmusic.exe', 'music.ui.exe',
        'wmplayer.exe', 'vlc.exe', 'potplayer.exe', 'potplayermini64.exe',
        'foobar2000.exe', 'msedge.exe', 'chrome.exe', 'firefox.exe',
    ]

    BROWSER_TITLE_PATTERNS = [
        re.compile(r'^(.+?)\s*[-—]\s*YouTube\b', re.IGNORECASE),
        re.compile(r'^(.+?)\s*[-—]\s*Bilibili', re.IGNORECASE),
        re.compile(r'^(.+)\s*[-—]\s*(?:Google\s*)?Chrome\b', re.IGNORECASE),
        re.compile(r'^(.+)\s*[-—]\s*(?:Microsoft\s*)?Edge\b', re.IGNORECASE),
        re.compile(r'^(.+?)\s*(?:[-—]\s*.*?\s*[-—])?\s*(?:Mozilla\s*)?Firefox\b', re.IGNORECASE),
    ]

    def __init__(self):
        self._cache: Dict[str, Any] = {'available': False}
        self._cache_lock = threading.Lock()
        self._running = True
        self._loop = None  # SMTC asyncio 事件循环引用

        if _WIN32_OK:
            t = threading.Thread(target=self._poll_windows, daemon=True)
            t.start()
        if _SMTC_OK:
            t2 = threading.Thread(target=self._poll_smtc, daemon=True)
            t2.start()

    # ================================================================
    #  窗口标题轮询 (歌名/歌手)
    # ================================================================

    def _poll_windows(self):
        """每 1 秒扫描窗口标题"""
        while self._running:
            try:
                info = self._scan_windows()
                with self._cache_lock:
                    # 合并: 保留 SMTC 的时长/进度, 更新窗口标题的歌名/歌手
                    old = self._cache
                    merged = {**old, **info,
                              'title': info.get('title', '') or old.get('title', ''),
                              'artist': info.get('artist', '') or old.get('artist', '')}
                    self._cache = merged
            except Exception:
                pass
            time.sleep(1)

    def _scan_windows(self) -> Dict[str, Any]:
        """扫描所有可见窗口"""
        result = {'available': False, 'title': '', 'artist': '', 'source': ''}
        media_windows = []

        def enum_callback(hwnd, _):
            if not win32gui.IsWindowVisible(hwnd):
                return True
            title = win32gui.GetWindowText(hwnd)
            if not title or len(title) < 2:
                return True
            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                proc = psutil.Process(pid)
                proc_name = proc.name().lower()
                if proc_name in self.MEDIA_APPS:
                    media_windows.append((proc_name, title))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
            return True

        win32gui.EnumWindows(enum_callback, None)
        if not media_windows:
            return result

        # 优先级排序
        priority = {n: i for i, n in enumerate([
            'cloudmusic.exe', 'spotify.exe', 'qqmusic.exe',
            'potplayer.exe', 'potplayermini64.exe', 'vlc.exe',
            'msedge.exe', 'chrome.exe', 'firefox.exe',
        ])}
        media_windows.sort(key=lambda w: priority.get(w[0], 99))
        proc_name, title = media_windows[0]

        result['available'] = True
        result['source'] = proc_name.replace('.exe', '')

        if proc_name in ('msedge.exe', 'chrome.exe', 'firefox.exe'):
            result.update(self._parse_browser_title(title))
        elif proc_name == 'cloudmusic.exe':
            result.update(self._parse_netease_title(title))
        elif proc_name == 'spotify.exe':
            result.update(self._parse_spotify_title(title))
        else:
            result.update(self._parse_generic_title(title))

        return result

    def _parse_netease_title(self, title: str) -> Dict[str, Any]:
        for sep in (' - ', ' – ', ' — '):
            parts = title.split(sep, 1)
            if len(parts) == 2:
                return {'title': parts[0].strip(), 'artist': parts[1].strip()}
        return {'title': title.strip(), 'artist': ''}

    def _parse_spotify_title(self, title: str) -> Dict[str, Any]:
        for sep in (' - ', ' – '):
            parts = title.split(sep, 1)
            if len(parts) == 2:
                return {'title': parts[1].strip(), 'artist': parts[0].strip()}
        return {'title': title.strip(), 'artist': ''}

    def _parse_browser_title(self, title: str) -> Dict[str, Any]:
        for pattern in self.BROWSER_TITLE_PATTERNS:
            m = pattern.match(title)
            if m:
                song_title = m.group(1).strip()
                if any(skip in song_title.lower() for skip in
                       ['新标签页', 'new tab', 'about:', 'chrome://', 'edge://',
                        'settings', '设置', 'google', 'bing', '百度']):
                    continue
                return {'title': song_title, 'artist': ''}
        return {'title': title.strip(), 'artist': ''}

    def _parse_generic_title(self, title: str) -> Dict[str, Any]:
        for sep in (' - ', ' – '):
            parts = title.split(sep, 1)
            if len(parts) == 2 and len(parts[0]) < 80 and len(parts[1]) < 80:
                return {'title': parts[0].strip(), 'artist': parts[1].strip()}
        return {'title': title.strip(), 'artist': ''}

    # ================================================================
    #  SMTC 轮询 (时长/进度/播放状态) — 使用 winsdk
    # ================================================================

    def _poll_smtc(self):
        """在独立线程中运行 asyncio 事件循环"""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._smtc_loop())

    async def _smtc_loop(self):
        """每 1 秒读取 SMTC 会话信息"""
        while self._running:
            try:
                manager = await SMTCManager.request_async()
                sessions = manager.get_sessions()
                if len(sessions) > 0:
                    await self._read_smtc_session(sessions[0])
                else:
                    # 没有 SMTC 会话时只清除 SMTC 数据，保留窗口标题
                    with self._cache_lock:
                        c = self._cache
                        c.pop('position', None)
                        c.pop('duration', None)
                        c.pop('smbc_playing', None)
            except Exception as e:
                pass
            await asyncio.sleep(1)

    async def _read_smtc_session(self, session):
        """读取 SMTC 会话的完整信息"""
        try:
            info = session.get_playback_info()
            status = info.playback_status  # 枚举值
            is_playing = (status == PlaybackStatus.PLAYING or
                          status == PlaybackStatus.CHANGING)

            timeline = session.get_timeline_properties()
            pos = timeline.position.total_seconds()
            dur = (timeline.end_time - timeline.start_time).total_seconds()

            props = await session.try_get_media_properties_async()
            title = props.title or ''
            artist = props.artist or ''

            source = session.source_app_user_model_id or ''

            with self._cache_lock:
                c = self._cache
                # SMTC 数据 (精确)
                c['position'] = pos
                c['duration'] = dur if dur > 0 else pos * 2  # fallback
                c['smbc_playing'] = is_playing
                c['smtc_active'] = True
                # 如果窗口标题没抓到歌名，用 SMTC 的
                if not c.get('title') and title:
                    c['title'] = title
                if not c.get('artist') and artist:
                    c['artist'] = artist
                if not c.get('source') and source:
                    c['source'] = source.split('.')[-1] if '.' in source else source
        except Exception:
            pass

    # ================================================================
    #  公共接口
    # ================================================================

    @property
    def is_available(self) -> bool:
        with self._cache_lock:
            return bool(self._cache.get('available') or self._cache.get('smtc_active'))

    def get_current_song(self) -> Dict[str, Any]:
        with self._cache_lock:
            c = dict(self._cache)

        # 只有在 SMTC 明确报告播放状态时才用, 否则由 MediaController 按键跟踪决定
        is_playing = c.get('smbc_playing')  # None 表示 SMTC 未报告

        return {
            'title': c.get('title', ''),
            'artist': c.get('artist', ''),
            'album': c.get('album', ''),
            'playing': True if is_playing else False,  # 仅 SMTC 可信
            'position': c.get('position', 0),
            'duration': c.get('duration', 0),
            'source': c.get('source', ''),
        }

    def seek_to(self, position_sec: float) -> bool:
        """通过 SMTC 跳转到指定位置 (仅支持 SMTC 的应用)"""
        if not _SMTC_OK:
            return False
        try:
            # 在后台线程的 event loop 中执行
            future = asyncio.run_coroutine_threadsafe(
                self._smtc_seek(position_sec), self._loop)
            result = future.result(timeout=3)
            return result
        except Exception:
            return False

    async def _smtc_seek(self, position_sec: float) -> bool:
        try:
            manager = await SMTCManager.request_async()
            sessions = manager.get_sessions()
            if len(sessions) == 0:
                return False
            # Windows TimeSpan 使用 100 纳秒单位 (ticks)
            ticks = int(position_sec * 10_000_000)
            await sessions[0].try_change_playback_position_async(ticks)
            return True
        except Exception:
            return False

    def get_album_cover(self) -> Optional[str]:
        return None

    def shutdown(self):
        self._running = False
