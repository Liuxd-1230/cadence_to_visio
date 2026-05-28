@echo off
chcp 65001 >nul
setlocal

echo.
echo ========================================
echo  Cadence to Visio - 打包工具
echo ========================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.8+
    pause
    exit /b 1
)

echo [1/3] 安装依赖...
pip install -r requirements.txt -q
if errorlevel 1 (
    echo [错误] 依赖安装失败
    pause
    exit /b 1
)

echo [2/3] 打包中（约 1-2 分钟）...
pyinstaller --noconfirm --onefile --windowed --name "CadenceToVisio" --add-data "circuit.vss;." --add-data "cadence_to_visio_core.py;." --add-data "cadence_to_visio_v2.py;." --hidden-import openpyxl --hidden-import win32com --hidden-import win32com.client --hidden-import pythoncom gui_app.py

if errorlevel 1 (
    echo [错误] 打包失败
    pause
    exit /b 1
)

echo.
echo [3/3] 打包完成！
echo ========================================
echo  输出文件: dist\CadenceToVisio.exe
echo ========================================
echo.
echo 使用方法:
echo   1. 将 CadenceToVisio.exe 复制到工作目录
echo   2. 确保同目录有 inst_info.txt, netlist.txt, wires.xlsx
echo   3. 双击运行 CadenceToVisio.exe
echo.
echo 注意: 目标机器需要安装 Microsoft Visio
echo.
pause
