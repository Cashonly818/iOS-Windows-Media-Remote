"""
音量控制器 - 基于 pycaw
实现系统音量的读取、设置、增减、静音切换
"""

try:
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    from comtypes import CLSCTX_ALL
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False
    print("[Volume] pycaw 未安装，音量控制不可用。运行: pip install pycaw")


class VolumeController:
    """Windows 系统音量控制器"""

    def __init__(self):
        self._interface = None
        if _AVAILABLE:
            try:
                devices = AudioUtilities.GetSpeakers()
                interface = devices.Activate(
                    IAudioEndpointVolume._iid_, CLSCTX_ALL, None
                )
                self._interface = interface.QueryInterface(IAudioEndpointVolume)
            except Exception as e:
                print(f"[Volume] 初始化失败: {e}")

    @property
    def available(self) -> bool:
        """音量控制是否可用"""
        return self._interface is not None

    def get_volume_percent(self) -> int:
        """获取当前音量百分比 (0-100)"""
        if not self._interface:
            return 0
        return int(round(self._interface.GetMasterVolumeLevelScalar() * 100))

    def get_mute(self) -> bool:
        """获取静音状态"""
        if not self._interface:
            return False
        # pycaw GetMute() 返回 int (0 或 1), 转为 bool
        return bool(self._interface.GetMute())

    def set_volume(self, percent: int) -> int:
        """设置音量到指定百分比 (0-100)，返回实际音量"""
        if not self._interface:
            return 0
        percent = max(0, min(100, int(percent)))
        self._interface.SetMasterVolumeLevelScalar(percent / 100.0, None)
        return self.get_volume_percent()

    def volume_up(self, step: int = 5) -> int:
        """音量增加"""
        if not self._interface:
            return 0
        current = self.get_volume_percent()
        return self.set_volume(current + step)

    def volume_down(self, step: int = 5) -> int:
        """音量减少"""
        if not self._interface:
            return 0
        current = self.get_volume_percent()
        return self.set_volume(current - step)

    def toggle_mute(self) -> bool:
        """切换静音状态，返回新的静音状态"""
        if not self._interface:
            return False
        current = bool(self._interface.GetMute())
        self._interface.SetMute(not current, None)
        return not current
