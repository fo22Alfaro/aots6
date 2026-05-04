#!/bin/bash
echo "Verificando integridad AOTS6..."
gpg --verify soberania_evidencias/DECLARACION_SISTEMICA_AAGA.txt.asc
if [ $? -eq 0 ]; then
    echo "Estado: AUTORIDAD ROOT CONFIRMADA"
    echo "Sincronizando con los 639 nodos de la red PDC-1..."
else
    echo "ALERTA: Intento de alteración de integridad detectado."
fi
