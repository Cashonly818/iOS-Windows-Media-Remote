"""
PC Media Remote - PyInstaller 打包脚本
将 Python 服务器打包为单个 .exe 文件，双击即用

使用方法:
  1. pip install pyinstaller
  2. python build_exe.py
  3. dist/PC_Media_Remote.exe
"""

import os, sys, shutil, subprocess

APP_NAME = "PC_Media_Remote"
SERVER_DIR = os.path.join(os.path.dirname(__file__), 'server')
DIST_DIR = os.path.join(os.path.dirname(__file__), 'dist')

def clean():
    for d in ['build', 'dist']:
        p = os.path.join(os.path.dirname(__file__), d)
        if os.path.exists(p): shutil.rmtree(p)
    for f in os.listdir(os.path.dirname(__file__)):
        if f.endswith('.spec'):
            os.remove(os.path.join(os.path.dirname(__file__), f))

def build():
    os.makedirs(DIST_DIR, exist_ok=True)

    # 隐藏导入列表
    hidden = [
        'controllers', 'controllers.volume', 'controllers.media',
        'controllers.system', 'controllers.potplayer', 'controllers.netease',
        'controllers.auth',
        'flask_sock', 'flask_cors',
        'pycaw', 'comtypes', 'comtypes.stream',
        'pyautogui', 'psutil', 'pywin32', 'win32gui', 'win32con',
        'win32api', 'win32process', 'win32com',
        'winsdk', 'qrcode', 'PIL',
    ]

    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--onefile',
        '--noconsole',
        f'--name={APP_NAME}',
        '--clean', '--noconfirm',
        '--add-data', f'{os.path.join(SERVER_DIR, "templates")};templates',
        '--add-data', f'{os.path.join(SERVER_DIR, "static")};static',
        '--distpath', DIST_DIR,
        '--workpath', os.path.join(os.path.dirname(__file__), 'build'),
    ]
    for h in hidden:
        cmd.extend(['--hidden-import', h])
    cmd.extend([
        '--exclude-module', 'matplotlib',
        '--exclude-module', 'numpy',
        '--exclude-module', 'pandas',
        '--exclude-module', 'cv2',
        '--exclude-module', 'tkinter',
        os.path.join(SERVER_DIR, 'app.py'),
    ])

    print(f"[Build] Packaging {APP_NAME}...")
    print(f"[Build] This may take 3-5 minutes...")
    subprocess.run(cmd, cwd=SERVER_DIR)

    exe = os.path.join(DIST_DIR, f'{APP_NAME}.exe')
    if os.path.exists(exe):
        size_mb = os.path.getsize(exe) / (1024*1024)
        print(f"\n[Build] Done: {exe} ({size_mb:.1f} MB)")
        print(f"[Build] Double-click to run, no Python needed.")
    else:
        print("[Build] Failed - exe not found")

if __name__ == '__main__':
    if '--clean' in sys.argv:
        clean()
    else:
        build()
