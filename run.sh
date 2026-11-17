#!/bin/bash
# Navega para o diretório onde o script está localizado
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$DIR"

# Detecta se existe ambiente virtual (venv ou .venv) na pasta
if [ -f "$DIR/venv/bin/python3" ]; then
    PYTHON_EXEC="$DIR/venv/bin/python3"
elif [ -f "$DIR/venv/bin/python" ]; then
    PYTHON_EXEC="$DIR/venv/bin/python"
elif [ -f "$DIR/.venv/bin/python3" ]; then
    PYTHON_EXEC="$DIR/.venv/bin/python3"
elif [ -f "$DIR/.venv/bin/python" ]; then
    PYTHON_EXEC="$DIR/.venv/bin/python"
else
    PYTHON_EXEC="$(command -v python3 || command -v python)"
fi

echo "==================================================" >> monitor.log
echo "Execucao em: $(date '+%Y-%m-%d %H:%M:%S')" >> monitor.log
"$PYTHON_EXEC" main.py >> monitor.log 2>&1
