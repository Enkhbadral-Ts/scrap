import sys

with open('/root/khuuli-bot/data/auto_update_gazar.sh', 'r', encoding='utf-8') as f:
    content = f.read()

telegram_snippet = """
TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-8856014072:AAFDYY9VhjeUDxf0MkdHdc2Q0qn2VF-CGFA}"
TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID:-2110849919}"

send_telegram() {
    local msg="$1"
    if [ -n "$TELEGRAM_BOT_TOKEN" ] && [ -n "$TELEGRAM_CHAT_ID" ]; then
        curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
            -d chat_id="$TELEGRAM_CHAT_ID" \
            -d text="$msg" \
            -d parse_mode="HTML" > /dev/null 2>&1 || true
    fi
}
"""

if "send_telegram" not in content:
    # Insert after set -euo pipefail
    content = content.replace("set -euo pipefail", "set -euo pipefail\n" + telegram_snippet)
    
    # Insert notification at the end
    end_msg = """send_telegram "✅ <b>Газрын дата шинэчлэгдлээ!</b>%0A🗺️ Нэгж талбар: ${PARCEL_COUNT}%0A📁 Хэмжээ: ${DB_SIZE}%0A🕐 Огноо: $(date '+%Y-%m-%d %H:%M')"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 🏁 Шинэчлэл дууслаа" >> "$LOG_FILE\""""
    content = content.replace('echo "[$(date \'+%Y-%m-%d %H:%M:%S\')] 🏁 Шинэчлэл дууслаа" >> "$LOG_FILE"', end_msg)

    with open('/root/khuuli-bot/data/auto_update_gazar.sh', 'w', encoding='utf-8') as f:
        f.write(content)
    print("SUCCESS: Added Telegram to gazar update script")
else:
    print("Telegram already in gazar update script")
