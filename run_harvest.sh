#!/usr/bin/env bash
# run_harvest.sh - Mac унтахаас сэргийлж (caffeinate), egazar датаг аюулгүй татах
# Ашиглах: ./run_harvest.sh [ub|commercial|sync]

TARGET=${1:-ub}
WORKERS=${2:-15}
RATE_LIMIT=${3:-15}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================================="
echo "☕ CAFFEINE ИДЭВХЖИЖ БАЙНА: Таны Mac унтахгүй (No Sleep)"
echo "   Горим: $TARGET | Workers: $WORKERS | Rate Limit: $RATE_LIMIT req/s"
echo "   Зогсоох: Ctrl + C (Автоматаар Mac хэвийн горимд шилжинэ)"
echo "=========================================================="

if [ "$TARGET" = "commercial" ]; then
    CMD="python3 egazar_collector.py fetch-details --target ub --commercial-only --rate-limit $RATE_LIMIT --workers $WORKERS"
elif [ "$TARGET" = "sync" ]; then
    CMD="python3 egazar_collector.py sync-daily --days 3 --rate-limit $RATE_LIMIT --workers $WORKERS"
else
    CMD="python3 egazar_collector.py fetch-details --target ub --rate-limit $RATE_LIMIT --workers $WORKERS"
fi

# caffeinate тушаал:
# -d: Дэлгэц унтрахаас сэргийлэх
# -i: Систем idle унтахаас сэргийлэх
# -m: Диск амрахаас сэргийлэх
# -s: Цахилгаанд залгаатай үед унтахаас сэргийлэх
# -u: Хэрэглэгч идэвхтэй байна гэж тооцох
exec /usr/bin/caffeinate -dimsu $CMD
