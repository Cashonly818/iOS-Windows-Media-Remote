"""
媒体控制器 - 基于 pyautogui
发送系统级多媒体按键 (播放/暂停/上一首/下一首)
兼容 Spotify、网易云音乐、QQ音乐、浏览器等所有媒体应用

同时估算播放进度 (由于无法从系统直接读取，通过按键时间推算)
"""

import time
import threading

try:
    import pyautogui
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False
    print("[Media] pyautogui 未安装，媒体键控制不可用。运行: pip install pyautogui")


class MediaController:
    """系统媒体键控制器 + 进度估算"""

    def __init__(self):
        self._playing = False
        self._lock = threading.Lock()

        # 进度估算
        self._play_start_time = 0.0     # 最近一次播放的开始时间戳
        self._accumulated_position = 0.0  # 已播放累计秒数 (暂停时更新)
        self._track_duration = 0.0       # 当前曲目总时长 (未知时 = 0)
        self._progress_lock = threading.Lock()

        if _AVAILABLE:
            pyautogui.FAILSAFE = False

    def _press_key(self, key: str):
        """安全地按下媒体键"""
        if not _AVAILABLE:
            print(f"[Media] pyautogui 不可用，无法发送按键: {key}")
            return False
        with self._lock:
            try:
                pyautogui.press(key)
                time.sleep(0.05)
                return True
            except Exception as e:
                print(f"[Media] 按键失败 '{key}': {e}")
                return False

    def play_pause(self) -> bool:
        """播放/暂停 — 无条件切换内部状态 (按键发送结果不影响 UI 状态)"""
        self._press_key('playpause')
        with self._progress_lock:
            if self._playing:
                self._accumulated_position += time.time() - self._play_start_time
            else:
                self._play_start_time = time.time()
            self._playing = not self._playing
        return True

    def next_track(self) -> bool:
        """下一首"""
        self._press_key('nexttrack')
        with self._progress_lock:
            self._accumulated_position = 0.0
            self._play_start_time = time.time()
            self._playing = True
        return True

    def previous_track(self) -> bool:
        """上一首"""
        self._press_key('prevtrack')
        with self._progress_lock:
            self._accumulated_position = 0.0
            self._play_start_time = time.time()
            self._playing = True
        return True

    def stop(self) -> bool:
        """停止播放"""
        self._press_key('stop')
        with self._progress_lock:
            self._accumulated_position = 0.0
            self._playing = False
        return True

    def is_playing(self) -> bool:
        """获取播放状态"""
        return self._playing

    def get_position(self) -> float:
        """获取估算的当前播放位置 (秒)"""
        with self._progress_lock:
            if self._playing:
                return self._accumulated_position + (time.time() - self._play_start_time)
            return self._accumulated_position

    def get_duration(self) -> float:
        """获取曲目总时长 (未知时返回估算值)"""
        pos = self.get_position()
        if self._track_duration > 0:
            return self._track_duration
        # 估算: 普通歌曲 3-4 分钟，如果播放进度超过 4 分钟则动态扩展
        if pos <= 0:
            return 0
        return max(240, int(pos * 1.5))

    def seek_approximate(self, target_sec: float) -> bool:
        """
        降级 seek: 由于 pyautogui 不支持快进/快退多媒体键，
        无法在非 SMTC 应用中精确跳转。仅更新内部进度位置。
        """
        with self._progress_lock:
            self._accumulated_position = target_sec
            self._play_start_time = time.time()
        return True

    def get_progress_info(self) -> dict:
        """获取完整的进度信息"""
        return {
            'playing': self._playing,
            'position': self.get_position(),
            'duration': self.get_duration(),
        }
