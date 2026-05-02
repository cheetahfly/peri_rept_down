@echo off
echo ========================================
echo WSL2 Ubuntu 安装脚本
echo ========================================
echo.

echo 正在安装 WSL2 和 Ubuntu...
wsl --install --distribution Ubuntu --force

echo.
echo ========================================
echo 安装完成！需要重启电脑才能继续。
echo.
echo 重启后，运行以下命令启动Ubuntu:
echo   wsl -d Ubuntu
echo.
echo 在Ubuntu中安装pdf2htmlEX:
echo   sudo apt update
echo   sudo apt install pdf2htmlEX
echo ========================================
pause
