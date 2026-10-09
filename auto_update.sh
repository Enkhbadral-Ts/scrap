#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────
# auto_update.sh - opendata.gov.mn-аас хуулийн этгээдийн бүртгэлийг
# автоматаар татаж, SQLite индекс шинэчилнэ.
# Cron: 0 2 * * * source /root/khuuli-bot/.env && /root/khuuli-bot/data/auto_update.sh >> /root/khuuli-bot/data/update.log 2>&1
# ─────────────────────────────────────────────────────────────────────
set -euo pipefail

DATA_DIR="/root/khuuli-bot/data"
DB_FILE="$DATA_DIR/burtgel_les.db"
JSON_FILE="$DATA_DIR/LesOutputJson.json"
PATH_FILE="$DATA_DIR/last_path.txt"
HTML_FILE="/root/khuuli-bot/public/burtgel.html"
LOG_PREFIX="[$(date '+%Y-%m-%d %H:%M:%S')]"

TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-}"
TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID:-}"

send_telegram() {
    local msg="$1"
    if [ -n "$TELEGRAM_BOT_TOKEN" ] && [ -n "$TELEGRAM_CHAT_ID" ]; then
        curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
            -d chat_id="$TELEGRAM_CHAT_ID" \
            -d text="$msg" \
            -d parse_mode="HTML" > /dev/null 2>&1 || true
    fi
}

# Ямар нэг команд гэнэт унавал чимээгүй зогсохгүй, Telegram-д мэдэгдэнэ
trap 'send_telegram "❌ <b>Бүртгэл шинэчлэлт АМЖИЛТГҮЙ</b>%0Aauto_update.sh мөр ${LINENO} дээр алдаа гарлаа. update.log-ийг шалгана уу."' ERR

echo "$LOG_PREFIX === Автомат шинэчлэлт эхэллээ ==="

# 1. API-аас одоогийн файлын path-ийг авах
echo "$LOG_PREFIX Opendata.gov.mn API-д хандаж байна..."
API_RESPONSE=$(curl -s -X POST "https://opendata.gov.mn/api/v1/front/search" \
    -H "Content-Type: application/json" \
    -d '{"page":{"page":1,"page_size":1,"sort":"created_at DESC"},"org_reg_num":"5296722","query":"Хуулийн этгээдийн"}' \
    --connect-timeout 15 --max-time 30)

NEW_PATH=$(echo "$API_RESPONSE" | python3 -c "
import sys, json
data = json.load(sys.stdin)
items = data['result']['details']['items']
if items:
    files = items[0].get('files', [])
    if files:
        print(files[0]['path'])
" 2>/dev/null || echo "")

if [ -z "$NEW_PATH" ]; then
    echo "$LOG_PREFIX ❌ API-аас path авч чадсангүй."
    send_telegram "❌ <b>Бүртгэл шинэчлэлт АМЖИЛТГҮЙ</b>%0AAPI-аас path авч чадсангүй."
    exit 1
fi

echo "$LOG_PREFIX Шинэ path: $NEW_PATH"

# 2. Хуучин path-тай харьцуулах
OLD_PATH=""
if [ -f "$PATH_FILE" ]; then
    OLD_PATH=$(cat "$PATH_FILE")
fi

if [ "$NEW_PATH" = "$OLD_PATH" ]; then
    echo "$LOG_PREFIX ✅ Шинэчлэлт шаардлагагүй (path өөрчлөгдөөгүй)."
    exit 0
fi

# Opendata өдөр бүр огнооны хавтас солидог ч агуулга (hash) ижил байж болно.
# Hash ижил бол 7 минутын rebuild хийхгүй, зөвхөн мэдэгдэнэ.
NEW_HASH="${NEW_PATH##*/}"
OLD_HASH="${OLD_PATH##*/}"
if [ -n "$OLD_HASH" ] && [ "$NEW_HASH" = "$OLD_HASH" ]; then
    LAST_DATE="${OLD_PATH%%/*}"
    echo "$LOG_PREFIX ℹ️ Агуулга өөрчлөгдөөгүй (hash ижил: ${NEW_HASH:0:12}). Сүүлийн өөрчлөлт: $LAST_DATE"
    send_telegram "ℹ️ <b>Бүртгэл: шинэ өгөгдөл алга</b>%0AOpendata файл өөрчлөгдөөгүй (hash ижил).%0A📅 Сүүлийн өөрчлөлт: ${LAST_DATE}%0A🕐 $(date '+%Y-%m-%d %H:%M')"
    exit 0
fi

echo "$LOG_PREFIX 🔄 Шинэ хувилбар олдлоо! Татаж байна..."

# 3. JSON файл татах
DOWNLOAD_URL="https://opendata.gov.mn/api/v1/media/$NEW_PATH"
TEMP_JSON="$DATA_DIR/LesOutputJson_new.json"

if ! curl -L -o "$TEMP_JSON" --connect-timeout 30 --max-time 600 \
    --retry 3 --retry-delay 10 "$DOWNLOAD_URL"; then
    echo "$LOG_PREFIX ❌ Файл татаж чадсангүй."
    send_telegram "❌ <b>Бүртгэл шинэчлэлт АМЖИЛТГҮЙ</b>%0AФайл татахад алдаа гарлаа."
    rm -f "$TEMP_JSON"
    exit 1
fi

# Хэмжээ шалгах (дор хаяж 100MB байх ёстой)
FILE_SIZE=$(stat -c%s "$TEMP_JSON" 2>/dev/null || stat -f%z "$TEMP_JSON" 2>/dev/null || echo "0")
if [ "$FILE_SIZE" -lt 100000000 ]; then
    echo "$LOG_PREFIX ❌ Татсан файлын хэмжээ бага ($FILE_SIZE bytes). Зөв файл биш байна."
    send_telegram "❌ <b>Бүртгэл шинэчлэлт АМЖИЛТГҮЙ</b>%0AФайлын хэмжээ хэт бага: ${FILE_SIZE} bytes"
    rm -f "$TEMP_JSON"
    exit 1
fi

# 4. Хуучин файлыг солих
mv "$TEMP_JSON" "$JSON_FILE"
FILE_MB=$(python3 -c "print(round($FILE_SIZE/1048576, 1))")
echo "$LOG_PREFIX ✅ JSON файл шинэчлэгдлээ (${FILE_MB} MB)"

# 5. SQLite index rebuild (temp файлд бүтээгээд атомаар солино)
echo "$LOG_PREFIX 🔨 SQLite индекс шинэчилж байна..."
cd "$DATA_DIR"
BUILD_OUTPUT=$(python3 build_sqlite_index.py 2>&1)
echo "$BUILD_OUTPUT"

# 6. DIFF мөрийг задлах
DIFF_LINE=$(echo "$BUILD_OUTPUT" | grep "^DIFF:" || echo "")
if [ -n "$DIFF_LINE" ]; then
    DIFF_C=$(echo "$DIFF_LINE" | grep -oP '[+-]?\d+ companies' | grep -oP '[+-]?\d+' || true)
    DIFF_P=$(echo "$DIFF_LINE" | grep -oP '[+-]?\d+ people' | grep -oP '[+-]?\d+' || true)
    TG_DIFF="🆕 Шинэ: ${DIFF_C:-0} компани, ${DIFF_P:-0} хүн"
else
    TG_DIFF=""
fi

# Нийт тоог авах
# Full rebuild: "Inserted N companies and M people" / Incremental: "Incremental update: N companies, M people"
NEW_COMPANIES=$(echo "$BUILD_OUTPUT" | grep -oP '(Inserted|Incremental update:) \K[\d,]+(?= companies)' | head -1 | tr -d ',' || true)
NEW_PEOPLE=$(echo "$BUILD_OUTPUT" | grep -oP '(and |companies, )\K[\d,]+(?= people)' | head -1 | tr -d ',' || true)

# 7. burtgel.html дээрх тоог шинэчлэх
echo "$LOG_PREFIX 📝 burtgel.html хуудсыг шинэчилж байна..."
python3 -c "
import sqlite3, re

try:
    conn = sqlite3.connect('/root/khuuli-bot/data/burtgel_les.db')
    cur = conn.cursor()
    cur.execute('SELECT count(*) FROM companies')
    c_cnt = cur.fetchone()[0]
    cur.execute('SELECT count(*) FROM company_people')
    p_cnt = cur.fetchone()[0]
    conn.close()

    html_path = '/root/khuuli-bot/public/burtgel.html'
    with open(html_path, 'r', encoding='utf-8') as f:
        html = f.read()

    new_badge = f'📊 {c_cnt:,} компани · {p_cnt:,} хүний бүртгэл · Өдөр бүр шинэчлэгддэг'
    html = re.sub(r'📊\s*[\d,]+\s*компани\s*·\s*[\d,]+\s*хүний бүртгэл\s*·\s*Өдөр бүр шинэчлэгддэг', new_badge, html)

    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'Done: {new_badge}')
except Exception as e:
    print(f'Error updating HTML: {e}')
"

# 8. Зам хадгалах
echo "$NEW_PATH" > "$PATH_FILE"

# 9. PM2 restart
pm2 restart khuuli-bot --silent 2>/dev/null || true

echo "$LOG_PREFIX ✅ Бүрэн амжилттай шинэчлэгдлээ!"

# Telegram мэдэгдэл
TG_MSG="✅ <b>Бүртгэл шинэчлэгдлээ!</b>%0A🏢 Нийт: ${NEW_COMPANIES:-?} компани%0A👥 Нийт: ${NEW_PEOPLE:-?} хүн"
if [ -n "$TG_DIFF" ]; then
    TG_MSG="${TG_MSG}%0A${TG_DIFF}"
fi
TG_MSG="${TG_MSG}%0A📁 ${FILE_MB} MB%0A🕐 $(date '+%Y-%m-%d %H:%M')"

send_telegram "$TG_MSG"

echo "$LOG_PREFIX === Дууслаа ==="
