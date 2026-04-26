#!/data/data/com.termux/files/usr/bin/bash

LOG="./logs/core.log"

echo "=== AOTS⁶ START ===" >> $LOG

# 1. Runtime
BOOT=$(echo $BOOTCLASSPATH)
echo "[BOOT] $BOOT" >> $LOG

# 2. Procesos
PS=$(ps -A)
echo "$PS" > ./data/processes.txt

# 3. Servicios (si viene de Shizuku)
SERVICE_COUNT=$(service list | wc -l)
echo "[SERVICES] $SERVICE_COUNT" >> $LOG

# 4. APEX
APEX=$(ls /apex)
echo "$APEX" > ./data/apex.txt

# 5. Señales clave
if echo "$PS" | grep -q "com.whatsapp"; then
    echo "[EVENT] WhatsApp activo" >> $LOG
fi

if echo "$PS" | grep -q "com.android.systemui"; then
    echo "[EVENT] SystemUI activo" >> $LOG
fi

echo "=== AOTS⁶ END ===" >> $LOG
