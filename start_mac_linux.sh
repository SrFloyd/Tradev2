#!/bin/sh
printf 'API Key Binance (somente leitura; não será salva em arquivo): '
read BINANCE_API_KEY
printf 'API Secret Binance (não será salva em arquivo): '
stty -echo
read BINANCE_API_SECRET
stty echo
printf '\n'
export BINANCE_API_KEY BINANCE_API_SECRET
exec python3 "$(dirname "$0")/server.py"
