@echo off
chcp 65001 > nul
echo.
echo ============================================
echo   RADIO SC NEWS — Instalação
echo ============================================
echo.

:: Verificar se Python está instalado
python --version >nul 2>&1
if %errorlevel% == 0 goto python_ok

echo [!] Python não encontrado. Instalando via winget...
winget install --id Python.Python.3.12 --source winget --accept-package-agreements --accept-source-agreements
if %errorlevel% neq 0 (
    echo.
    echo [ERRO] Falha ao instalar Python automaticamente.
    echo Por favor, instale manualmente em: https://www.python.org/downloads/
    echo Marque a opcao "Add Python to PATH" durante a instalação.
    pause
    exit /b 1
)
echo.
echo [OK] Python instalado! Reiniciando script com novo PATH...
:: Atualizar PATH para esta sessão
for /f "tokens=*" %%a in ('where python 2^>nul') do set PYTHON_PATH=%%a
if "%PYTHON_PATH%"=="" (
    echo Feche este terminal, abra um novo e execute instalar.bat novamente.
    pause
    exit /b 0
)

:python_ok
echo [OK] Python encontrado:
python --version
echo.

:: Criar ambiente virtual
if not exist venv (
    echo [*] Criando ambiente virtual...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo [ERRO] Falha ao criar ambiente virtual.
        pause
        exit /b 1
    )
    echo [OK] Ambiente virtual criado.
) else (
    echo [OK] Ambiente virtual já existe.
)

echo.
echo [*] Instalando dependências...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip --quiet
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERRO] Falha ao instalar dependências.
    pause
    exit /b 1
)

echo.
echo ============================================
echo   Instalação concluída com sucesso!
echo.
echo   Para iniciar o servidor, execute:
echo   iniciar.bat
echo ============================================
echo.
pause
