#!/bin/bash
# subir_videos.sh — fluxo completo pra subir videos novos ao acervo com seguranca.
# Uso:  ./subir_videos.sh /caminho/da/pasta/com/videos/novos

set -e

PASTA_NOVOS="$1"
PASTA_VIDEOS="/opt/acervo/videos"
DB="/data/catalog.db"

if [ -z "$PASTA_NOVOS" ]; then
  echo "ERRO: informe a pasta dos videos novos."
  echo "Uso: ./subir_videos.sh /opt/acervo/novos_para_checar"
  exit 1
fi

if [ ! -d "$PASTA_NOVOS" ]; then
  echo "ERRO: pasta nao encontrada: $PASTA_NOVOS"
  exit 1
fi

QTD=$(find "$PASTA_NOVOS" -maxdepth 1 -type f \( -iname '*.mp4' -o -iname '*.mov' -o -iname '*.avi' -o -iname '*.mkv' -o -iname '*.webm' \) | wc -l)
echo "=================================================="
echo "  SUBIR VIDEOS AO ACERVO"
echo "  Pasta: $PASTA_NOVOS"
echo "  Videos encontrados: $QTD"
echo "=================================================="
echo ""
echo ">> ETAPA 1: checando duplicatas visuais..."
echo ""

docker compose run --rm -v "$PASTA_NOVOS":/novos app python checar_duplicatas.py --videos /novos --db "$DB"

echo ""
echo "=================================================="
echo "Confira o relatorio acima."
echo "Se algum video for duplicado, saia agora (digite N),"
echo "remova ele da pasta e rode de novo."
echo "=================================================="
read -p ">> Continuar e SUBIR todos os videos da pasta? (s/N) " RESP

if [ "$RESP" != "s" ] && [ "$RESP" != "S" ]; then
  echo "Cancelado. Nenhum video foi subido."
  exit 0
fi

echo ""
echo ">> ETAPA 2: copiando videos para a pasta permanente..."
cp --update=none "$PASTA_NOVOS"/*.mp4 "$PASTA_VIDEOS"/ 2>/dev/null || true
cp --update=none "$PASTA_NOVOS"/*.mov "$PASTA_VIDEOS"/ 2>/dev/null || true
cp --update=none "$PASTA_NOVOS"/*.avi "$PASTA_VIDEOS"/ 2>/dev/null || true
cp --update=none "$PASTA_NOVOS"/*.mkv "$PASTA_VIDEOS"/ 2>/dev/null || true
cp --update=none "$PASTA_NOVOS"/*.webm "$PASTA_VIDEOS"/ 2>/dev/null || true
echo "   copiado."

echo ""
echo ">> ETAPA 3: backup do banco..."
STAMP=$(date +%Y%m%d_%H%M%S)
cp ./data/catalog.db "./data/catalog.db.backup_$STAMP"
echo "   backup: catalog.db.backup_$STAMP"

echo ""
echo ">> ETAPA 4: processando (thumbnail + impressao visual)..."
docker compose run --rm -v "$PASTA_VIDEOS":/videos app python process_videos.py --videos /videos --out /data

echo ""
echo ">> ETAPA 5: reiniciando o site..."
docker compose restart app

echo ""
echo "=================================================="
echo "  PRONTO! Videos no acervo."
echo "  Dê um refresh no site (Cmd+Shift+R) para conferir."
echo "=================================================="
