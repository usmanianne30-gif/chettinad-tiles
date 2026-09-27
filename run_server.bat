@echo off
title Chettinad Tiles – Game Server
echo =========================================
echo  Chettinad Tiles  –  Local Game Server
echo =========================================
echo.
echo Starting WebSocket server on port 8765...
echo Share your IP address with players to connect:
echo  ws://YOUR-IP-HERE:8765
echo.
echo Press Ctrl+C to stop the server.
echo.
python server.py
pause
