#!/bin/bash
# Tesseract OCR 安装脚本
# 用于自动下载并安装 Tesseract OCR 及中文语言包

set -e

echo "=== Tesseract OCR 安装脚本 ==="
echo ""

# 检查操作系统
if [[ "$OSTYPE" == "msys"* ]] || [[ "$OSTYPE" == "win32"* ]]; then
    echo "检测到 Windows 系统"
    OS="windows"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo "检测到 Linux 系统"
    OS="linux"
else
    echo "不支持的操作系统: $OSTYPE"
    exit 1
fi

install_windows() {
    echo ""
    echo "=== Windows 安装 ==="
    
    # 下载地址 (UB Mannheim 构建)
    TESSERACT_URL="https://github.com/UB-Mannheim/tesseract/releases/download/v5.4.1.20250107/tesseract-5.4.1-oem-x64-setup.exe"
    INSTALLER_PATH="/tmp/tesseract-setup.exe"
    
    echo "正在下载 Tesseract OCR 安装包..."
    echo "下载地址: $TESSERACT_URL"
    
    if command -v curl &> /dev/null; then
        curl -L -o "$INSTALLER_PATH" "$TESSERACT_URL"
    elif command -v wget &> /dev/null; then
        wget -O "$INSTALLER_PATH" "$TESSERACT_URL"
    else
        echo "错误: 需要 curl 或 wget"
        exit 1
    fi
    
    echo "下载完成: $INSTALLER_PATH"
    echo ""
    echo "请手动运行安装程序完成安装:"
    echo "1. 双击 $INSTALLER_PATH"
    echo "2. 选择 'Full' 安装模式"
    echo "3. 安装中文语言包 (chi_sim)"
    echo "4. 完成安装后，将以下路径添加到系统 PATH:"
    echo "   C:\\Program Files\\Tesseract-OCR"
    echo ""
    echo "或者直接运行以下命令静默安装:"
    echo "$INSTALLER_PATH /S"
}

install_linux() {
    echo ""
    echo "=== Linux 安装 ==="
    
    if command -v tesseract &> /dev/null; then
        echo "Tesseract 已安装: $(tesseract --version)"
    else
        echo "正在安装 Tesseract..."
        sudo apt-get update
        sudo apt-get install -y tesseract-ocr tesseract-ocr-chi-sim
    fi
    
    echo ""
    echo "验证安装:"
    tesseract --version
    tesseract --list-langs | grep chi
}

# 主流程
if [[ "$OS" == "windows" ]]; then
    install_windows
elif [[ "$OS" == "linux" ]]; then
    install_linux
fi

echo ""
echo "=== 安装后验证 ==="
echo "运行以下命令验证:"
echo "  python -c \"import pytesseract; print(pytesseract.get_tesseract_version())\""
echo ""
echo "=== 完成 ==="
