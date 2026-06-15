' ============================================================
' PC Media Remote - 开机自启动脚本 (隐藏窗口运行)
' 用法: 将此文件的快捷方式放入 Windows 启动文件夹
'   Win+R → shell:startup → 粘贴快捷方式
' ============================================================

Set objShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")

' 获取脚本所在目录
scriptDir = objFSO.GetParentFolderName(WScript.ScriptFullName)

' 启动 Python 服务器 (隐藏窗口)
objShell.Run "pythonw.exe """ & scriptDir & "\app.py""", 0, False

' pythonw.exe 启动无控制台窗口
' 如果 pythonw.exe 不可用，改用 python.exe 并最小化窗口:
' objShell.Run "python.exe """ & scriptDir & "\app.py""", 2, False
