@echo off
chcp 65001 > nul
echo.
echo ============================================
echo   RADIO SC NEWS — Iniciando servidor...
echo ============================================
echo.

:: Verificar ambiente virtual
if not exist venv\Scripts\activate.bat (
    echo [ERRO] Ambiente virtual não encontrado.
    echo Execute primeiro: instalar.bat
    pause
    exit /b 1
)

call venv\Scripts\activate.bat

:: Verificar se Flask está instalado
python -c "import flask" >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERRO] Dependências não instaladas.
    echo Execute primeiro: instalar.bat
    pause
    exit /b 1
)

echo [OK] Iniciando Rádio SC News...
echo.
echo Acesse no navegador: http://localhost:5000
echo Painel admin:        http://localhost:5000/admin
echo Senha admin:         julia181014
echo.
echo Pressione Ctrl+C para parar o servidor.
echo.

python app.py
pause
