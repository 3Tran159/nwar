Set sh = CreateObject("WScript.Shell")
Set fs = CreateObject("Scripting.FileSystemObject")
base = fs.GetParentFolderName(WScript.ScriptFullName)
py = "C:\Users\ThinkPad\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\pythonw.exe"
sh.Run Chr(34) & py & Chr(34) & " " & Chr(34) & base & "\server.py" & Chr(34) & " --open", 0, False
