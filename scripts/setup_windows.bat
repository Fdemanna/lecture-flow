@echo off
echo ===================================
echo Instalando dependencias de Windows
echo ===================================
python -m venv venv_win
call venv_win\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements-win.txt
echo Finalizado. Ya puedes usar Iniciar_Windows.vbs
pause
