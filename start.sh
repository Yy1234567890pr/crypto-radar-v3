#!/bin/bash
# 链上监控雷达 v3 启动脚本

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

# 检查Python版本
PYTHON=""
if command -v python3.12 &> /dev/null; then
    PYTHON="python3.12"
elif command -v python3.11 &> /dev/null; then
    PYTHON="python3.11"
elif command -v python3 &> /dev/null; then
    PYTHON="python3"
else
    echo "❌ 未找到Python，请先安装Python 3.10+"
    exit 1
fi

# 检查依赖
echo "🔄 检查依赖..."
$PYTHON -c "import aiohttp" 2>/dev/null || {
    echo "📦 安装aiohttp..."
    $PYTHON -m pip install aiohttp --user -q
}

echo ""
echo "🚀 链上监控雷达 v3"
echo "="50
echo ""
echo "选择运行模式:"
echo "  1) 测试模式 - 运行一次扫描"
echo "  2) 生产模式 - 持续监控"
echo "  3) 配置推送"
echo ""

read -p "请选择 [1-3]: " choice

case $choice in
    1)
        echo ""
        echo "🧪 启动测试模式..."
        $PYTHON radar_v3.py
        ;;
    2)
        echo ""
        echo "🐄 启动生产模式 (按Ctrl+C停止)..."
        # 修改脚本为持续模式
        sed -i 's/# asyncio.run(radar.run_forever())/asyncio.run(radar.run_forever())/' radar_v3.py
        sed -i 's/result = asyncio.run(test_once())/# result = asyncio.run(test_once())/' radar_v3.py
        $PYTHON radar_v3.py
        # 恢复测试模式
        sed -i 's/asyncio.run(radar.run_forever())/# asyncio.run(radar.run_forever())/' radar_v3.py
        sed -i 's/# result = asyncio.run(test_once())/result = asyncio.run(test_once())/' radar_v3.py
        ;;
    3)
        echo ""
        echo "🔐 配置推送设置"
        echo ""
        read -p "Telegram Bot Token (回车保留当前): " tg_token
        read -p "Telegram Chat ID: " tg_chat
        read -p "微信Webhook URL (可选): " wx_hook
        
        [ -n "$tg_token" ] && echo "export TG_TOKEN='$tg_token'" >> ~/.bashrc
        [ -n "$tg_chat" ] && echo "export TG_CHAT_ID='$tg_chat'" >> ~/.bashrc
        [ -n "$wx_hook" ] && echo "export WX_WEBHOOK='$wx_hook'" >> ~/.bashrc
        
        echo ""
        echo "✅ 配置已保存，请重新登录或执行: source ~/.bashrc"
        ;;
    *)
        echo "无效选择"
        exit 1
        ;;
esac
