import sys, re

with open('/root/khuuli-bot/server.js', 'r', encoding='utf-8') as f:
    content = f.read()

log_visit_code = """
// --- VISIT LOGGER ---
function logVisit(req, pageName) {
  try {
    const ip = req.headers['x-forwarded-for'] || req.socket.remoteAddress || 'Unknown';
    const ua = req.headers['user-agent'] || 'Unknown';
    let device = 'Desktop';
    if (/mobile/i.test(ua)) device = 'Mobile';
    let os = 'Unknown OS';
    if (/windows/i.test(ua)) os = 'Windows';
    else if (/mac/i.test(ua)) os = 'MacOS';
    else if (/linux/i.test(ua)) os = 'Linux';
    else if (/android/i.test(ua)) os = 'Android';
    else if (/ios|iphone|ipad/i.test(ua)) os = 'iOS';
    
    const time = new Date().toLocaleString('mn-MN', { timeZone: 'Asia/Ulaanbaatar' });
    const query = req.query.q ? `\n🔍 Хайлт: <code>${req.query.q}</code>` : '';
    const msg = `👁️ <b>Хандалт (${pageName})</b>\n\n🕒 Цаг: ${time}\n🌐 IP: <code>${ip}</code>\n📱 Төхөөрөмж: ${device} (${os})${query}`;
    sendTelegramNotification(msg);
  } catch(e) {
    console.error('Visit log error:', e);
  }
}
// -------------------
"""

# Insert after sendTelegramNotification definition ends
match = re.search(r'async function sendTelegramNotification.*?}(?=\n)', content, re.DOTALL)
if match and "logVisit" not in content:
    insert_pos = match.end()
    content = content[:insert_pos] + "\n" + log_visit_code + content[insert_pos:]
elif "logVisit" in content:
    print("logVisit already exists.")

# Now patch app.get('/burtgel'
burtgel_route = """app.get("/burtgel", (req, res) => {
  logVisit(req, 'Бүртгэл');
  res.sendFile(path.join(__dirname, "public", "burtgel.html"));
});"""
content = re.sub(r'app\.get\(\"/burtgel\",\s*\(req,\s*res\)\s*=>\s*\{.*?\n\}\);', burtgel_route, content, flags=re.DOTALL)

# Now patch app.get('/gazar'
gazar_route = """app.get("/gazar", (req, res) => {
  logVisit(req, 'Газар');
  res.sendFile(path.join(__dirname, "public", "gazar.html"));
});"""
content = re.sub(r'app\.get\(\"/gazar\",\s*\(req,\s*res\)\s*=>\s*\{.*?\n\}\);', gazar_route, content, flags=re.DOTALL)

with open('/root/khuuli-bot/server.js', 'w', encoding='utf-8') as f:
    f.write(content)

print("SUCCESS")
