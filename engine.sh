#!/data/data/com.termux/files/usr/bin/bash

while true; do
    bash core.sh

    # Regla 1: demasiados procesos
    COUNT=$(ps -A | wc -l)
    if [ "$COUNT" -gt 300 ]; then
        echo "[AOTS⁶] Sobrecarga detectada ($COUNT procesos)" >> ./logs/alerts.log
    fi

    # Regla 2: cambios en APEX
    NEW=$(ls /apex | md5sum)
    OLD=$(cat ./data/apex.hash 2>/dev/null)

    if [ "$NEW" != "$OLD" ]; then
        echo "[AOTS⁶] Cambio en módulos APEX" >> ./logs/alerts.log
        echo "$NEW" > ./data/apex.hash
    fi

    sleep 10
done
