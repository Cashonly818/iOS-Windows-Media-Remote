"""
PotPlayer 控制器
通过查找 PotPlayer 窗口并发送键盘快捷键实现控制

PotPlayer 默认快捷键:
  Space      - 播放/暂停
  ←/→        - 后退/前进 5 秒
  ↑/↓        - 音量 +/- (不推荐用，用系统音量替代)
  Enter      - 全屏
  Alt+Enter  - 全屏 (备选)
  C          - 加速播放 (+0.1x)
  X          - 减速播放 (-0.1x)
  Z          - 重置倍速
  F5         - 打开设置
  F7         - 播放列表
"""

import time
import subprocess
import win32gui
import win32con
import win32api
import win32process
import psutil
from typing import Optional


class PotPlayerController:
    """PotPlayer 窗口控制器"""

    # PotPlayer 的窗口类名 (多种可能)
    POTPLAYER_WINDOW_CLASSES = [
        'PotPlayer',
        'PotPlayer64',
        'TVideoWindow',
        'TSetupForm',
    ]

    def __init__(self):
        self._hwnd: Optional[int] = None
        self._last_search_time = 0

    def _find_potplayer_window(self) -> Optional[int]:
        """查找 PotPlayer 的主播放窗口句柄"""
        # 缓存窗口句柄，每 2 秒重新查找一次
        now = time.time()
        if self._hwnd and (now - self._last_search_time) < 2:
            # 验证缓存的窗口是否还存在
            if win32gui.IsWindow(self._hwnd):
                return self._hwnd

        self._last_search_time = now
        found_hwnd = None

        # 方法1: 按窗口类名查找
        def enum_callback(hwnd, _):
            nonlocal found_hwnd
            class_name = win32gui.GetClassName(hwnd)
            window_text = win32gui.GetWindowText(hwnd)

            # 检查类名匹配
            if any(cls in class_name for cls in self.POTPLAYER_WINDOW_CLASSES):
                found_hwnd = hwnd
                return False  # 停止枚举

            # 检查窗口标题包含 "PotPlayer"
            if 'PotPlayer' in window_text or 'potplayer' in window_text.lower():
                found_hwnd = hwnd
                return False

            return True

        try:
            win32gui.EnumWindows(enum_callback, None)
        except Exception:
            pass

        # 方法2: 按进程名查找窗口
        if not found_hwnd:
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    if proc.info['name'] and 'potplayer' in proc.info['name'].lower():
                        pid = proc.info['pid']

                        def enum_proc_windows(hwnd, _):
                            nonlocal found_hwnd
                            _, process_id = win32process.GetWindowThreadProcessId(hwnd)
                            if process_id == pid and win32gui.IsWindowVisible(hwnd):
                                found_hwnd = hwnd
                                return False
                            return True

                        win32gui.EnumWindows(enum_proc_windows, None)
                        if found_hwnd:
                            break
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

        self._hwnd = found_hwnd
        if found_hwnd:
            print(f"[PotPlayer] 找到窗口: {win32gui.GetWindowText(found_hwnd)} (hwnd={found_hwnd})")
        return found_hwnd

    def _is_potplayer_running(self) -> bool:
        """检查 PotPlayer 是否在运行"""
        return self._find_potplayer_window() is not None

    def _send_key(self, vk_code: int, modifiers: list = None) -> bool:
        """向 PotPlayer 窗口发送键盘消息"""
        hwnd = self._find_potplayer_window()
        if not hwnd:
            print("[PotPlayer] 未找到 PotPlayer 窗口")
            return False

        try:
            # 确保窗口可以接收键盘输入 (非最小化)
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                time.sleep(0.1)

            # 将窗口置于前台以获得键盘焦点
            win32gui.SetForegroundWindow(hwnd)
            time.sleep(0.05)

            # 发送按键修饰符 (Ctrl, Alt, Shift)
            if modifiers:
                for mod in modifiers:
                    win32api.keybd_event(mod, 0, 0, 0)

            # 按下按键
            win32api.keybd_event(vk_code, 0, 0, 0)
            time.sleep(0.03)
            # 释放按键
            win32api.keybd_event(vk_code, 0, win32con.KEYEVENTF_KEYUP, 0)

            # 释放修饰符
            if modifiers:
                for mod in reversed(modifiers):
                    win32api.keybd_event(mod, 0, win32con.KEYEVENTF_KEYUP, 0)

            return True
        except Exception as e:
            print(f"[PotPlayer] 发送按键失败: {e}")
            return False

    def fullscreen(self) -> bool:
        """全屏切换 — Alt+Enter"""
        try:
            import pyautogui
            pyautogui.hotkey('alt', 'enter')
            return True
        except Exception as e:
            print(f"[PotPlayer] 全屏失败: {e}")
            return False

    def _activate_window(self):
        """激活 PotPlayer 窗口 (确保按键发送到正确窗口)"""
        hwnd = self._find_potplayer_window()
        if hwnd:
            try:
                if win32gui.IsIconic(hwnd):
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(hwnd)
                time.sleep(0.08)
            except Exception:
                pass

    def seek_forward(self, seconds: int = 10) -> bool:
        """快进 — 发送右方向键 (PotPlayer 默认每次 5 秒)"""
        presses = max(1, seconds // 5)
        self._activate_window()
        try:
            import pyautogui
            for _ in range(presses):
                pyautogui.press('right')
                time.sleep(0.03)
            return True
        except Exception as e:
            print(f"[PotPlayer] 快进失败: {e}")
            return False

    def seek_backward(self, seconds: int = 10) -> bool:
        """后退 — 发送左方向键"""
        presses = max(1, seconds // 5)
        self._activate_window()
        try:
            import pyautogui
            for _ in range(presses):
                pyautogui.press('left')
                time.sleep(0.03)
            return True
        except Exception as e:
            print(f"[PotPlayer] 后退失败: {e}")
            return False

    def fullscreen(self) -> bool:
        """全屏切换 — Alt+Enter"""
        self._activate_window()
        try:
            import pyautogui
            pyautogui.hotkey('alt', 'enter')
            return True
        except Exception as e:
            print(f"[PotPlayer] 全屏失败: {e}")
            return False

    def set_speed(self, speed: float) -> bool:
        """PotPlayer 倍速: Z=1x, C=+0.1x, X=-0.1x"""
        self._activate_window()
        try:
            import pyautogui
            pyautogui.press('z')
            time.sleep(0.08)
            if speed >= 1.0:
                steps = int(round((speed - 1.0) / 0.1))
                for _ in range(steps):
                    pyautogui.press('c')
                    time.sleep(0.03)
            else:
                steps = int(round((1.0 - speed) / 0.1))
                for _ in range(steps):
                    pyautogui.press('x')
                    time.sleep(0.03)
            return True
        except Exception as e:
            print(f"[PotPlayer] 倍速失败: {e}")
            return False

    def seek_to(self, position_sec: float) -> bool:
        """PotPlayer 精确跳转: Ctrl+G → HH:MM:SS → Enter"""
        self._activate_window()
        try:
            import pyautogui
            pyautogui.hotkey('ctrl', 'g')
            time.sleep(0.2)
            hours = int(position_sec // 3600)
            mins = int((position_sec % 3600) // 60)
            secs = int(position_sec % 60)
            time_str = f"{hours:02d}{mins:02d}{secs:02d}"
            pyautogui.write(time_str, interval=0.02)
            time.sleep(0.1)
            pyautogui.press('enter')
            return True
        except Exception as e:
            print(f"[PotPlayer] 跳转失败: {e}")
            return False

    def play_pause(self) -> bool:
        """播放/暂停 — Space 键"""
        self._activate_window()
        try:
            import pyautogui
            pyautogui.press('space')
            return True
        except Exception as e:
            print(f"[PotPlayer] 播放/暂停失败: {e}")
            return False

    @property
    def is_running(self) -> bool:
        return self._is_potplayer_running()
