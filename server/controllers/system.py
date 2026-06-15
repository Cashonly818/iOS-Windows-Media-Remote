"""
系统控制器
实现锁屏、息屏、关机、重启等系统级操作
"""

import os
import socket
import subprocess
import datetime

try:
    import psutil
    _PSUTIL_OK = True
except ImportError:
    _PSUTIL_OK = False
    print("[System] psutil 未安装，CPU/内存信息不可用。运行: pip install psutil")


class SystemController:
    """Windows 系统控制器"""

    def __init__(self):
        self._start_time = datetime.datetime.now()

    def get_pc_name(self) -> str:
        """获取电脑名称"""
        return socket.gethostname()

    def get_lan_ip(self) -> str:
        """获取局域网 IP"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return '127.0.0.1'

    def get_uptime_str(self) -> str:
        """获取运行时间字符串"""
        delta = datetime.datetime.now() - self._start_time
        hours, remainder = divmod(int(delta.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours > 0:
            return f"{hours}小时{minutes}分钟"
        elif minutes > 0:
            return f"{minutes}分钟{seconds}秒"
        return f"{seconds}秒"

    def lock_screen(self) -> bool:
        """锁定屏幕"""
        try:
            subprocess.Popen(
                'rundll32.exe user32.dll,LockWorkStation',
                shell=True
            )
            return True
        except Exception as e:
            print(f"[System] 锁屏失败: {e}")
            return False

    def sleep(self) -> bool:
        """使电脑进入睡眠模式"""
        try:
            subprocess.Popen(
                'rundll32.exe powrprof.dll,SetSuspendState 0,1,0',
                shell=True
            )
            return True
        except Exception as e:
            print(f"[System] 睡眠失败: {e}")
            return False

    def shutdown(self) -> bool:
        """关机 (60秒后执行)"""
        try:
            subprocess.Popen('shutdown /s /t 60 /c "PC Media Remote 远程关机"', shell=True)
            return True
        except Exception as e:
            print(f"[System] 关机失败: {e}")
            return False

    def restart(self) -> bool:
        """重启 (60秒后执行)"""
        try:
            subprocess.Popen('shutdown /r /t 60 /c "PC Media Remote 远程重启"', shell=True)
            return True
        except Exception as e:
            print(f"[System] 重启失败: {e}")
            return False

    def cancel_shutdown(self) -> bool:
        """取消计划中的关机/重启"""
        try:
            subprocess.Popen('shutdown /a', shell=True)
            return True
        except Exception as e:
            print(f"[System] 取消关机失败: {e}")
            return False

    def get_cpu_usage(self) -> float:
        """获取 CPU 使用率"""
        if not _PSUTIL_OK:
            return -1.0
        return psutil.cpu_percent(interval=0.1)

    def get_memory_usage(self) -> float:
        """获取内存使用率"""
        if not _PSUTIL_OK:
            return -1.0
        return psutil.virtual_memory().percent
