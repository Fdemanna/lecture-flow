Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' Obtener la ruta absoluta de la carpeta donde se encuentra este archivo .vbs
strCarpeta = fso.GetParentFolderName(WScript.ScriptFullName)

' Forzar que el directorio de trabajo sea la raíz del proyecto
WshShell.CurrentDirectory = strCarpeta

' Determinar si el lanzador se encuentra en scripts\ o en la raíz
rutaBat = ""
If fso.FileExists(strCarpeta & "\scripts\lanzador_win.bat") Then
    rutaBat = strCarpeta & "\scripts\lanzador_win.bat"
ElseIf fso.FileExists(strCarpeta & "\lanzador_win.bat") Then
    rutaBat = strCarpeta & "\lanzador_win.bat"
End If

If rutaBat = "" Then
    MsgBox "No se encontro 'lanzador_win.bat' en: " & vbCrLf & strCarpeta, 16, "LectureFlow - Error"
Else
    WshShell.Run "cmd /c """ & rutaBat & """", 0, False
End If

Set fso = Nothing
Set WshShell = Nothing