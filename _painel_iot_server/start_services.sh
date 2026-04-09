#!/bin/bash

# Script para iniciar o servidor Painel IoT e a bridge Arduino

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "📊 Iniciando Painel IoT (MaeDagua)..."
echo "  → Servidor: http://127.0.0.1:8000"
echo "  → Arduino: /dev/ttyUSB0 @ 115200 baud"
echo ""

cd "$SCRIPT_DIR"

# Iniciar FastAPI em background
echo "[1/2] Iniciando FastAPI (main.py)..."
python3 main.py > server.log 2>&1 &
SERVER_PID=$!
echo "      PID: $SERVER_PID"

sleep 2

# Iniciar bridge em background
echo "[2/2] Iniciando Bridge Arduino (bridge_arduino.py)..."
python3 bridge_arduino.py > bridge.log 2>&1 &
BRIDGE_PID=$!
echo "      PID: $BRIDGE_PID"

echo ""
echo "✅ Serviços iniciados com sucesso!"
echo ""
echo "📝 Logs:"
echo "   - Servidor: tail -f server.log"
echo "   - Bridge:   tail -f bridge.log"
echo ""
echo "🌐 Abra o navegador em: http://127.0.0.1:8000"
echo ""
echo "Para parar todos os serviços:"
echo "   kill $SERVER_PID $BRIDGE_PID"
echo ""
