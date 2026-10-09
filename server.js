require('dotenv').config();
const express = require('express');
const path = require('path');
const fs = require('fs');

const app = express();
app.use(express.json());

// Serve beautiful landing page
app.use(express.static(path.join(__dirname, 'public')));

const PORT = process.env.PORT || 5000;
const VERIFY_TOKEN = process.env.VERIFY_TOKEN || 'khuuli_verify_token_2026';
const PAGE_ACCESS_TOKEN = process.env.PAGE_ACCESS_TOKEN || '';
const GEMINI_API_KEY = process.env.GEMINI_API_KEY || '';
const DEEPSEEK_API_KEY = process.env.DEEPSEEK_API_KEY || '';

const AI_PROVIDER = process.env.AI_PROVIDER || 'deepseek';
const AI_MODEL = process.env.AI_MODEL || 'deepseek-chat';
const TELEGRAM_BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN || '';
const TELEGRAM_CHAT_ID = process.env.TELEGRAM_CHAT_ID || '';
const PAGE_ID = process.env.PAGE_ID || '';
// Admin PSIDs - bot will always respond to these users (comma separated)
const ADMIN_PSIDS = (process.env.ADMIN_PSIDS || '').split(',').filter(Boolean);

// Phones
const PHONE_1 = '86616316';
const PHONE_2 = '86616336';

// Mongolian Phone Number Regex (8 digits, e.g. 99112233, 88112233, +976 99112233, etc.)
const PHONE_REGEX = /(?:\+?976[- ]?)?(?:[89]\d{7}|7[0-9]\d{6})\b/;

// Save captured leads to leads.json
const chatMemory = {}; // Store last 4 messages per user
const pausedUsers = {}; // { psid: timestamp } - Human handoff pause
const lastSeen = {}; // { psid: timestamp } - For automated follow-up
const followedUp = {}; // { psid: boolean } - To prevent spamming
const leadCaptured = {}; // { psid: boolean } - Prevent follow-up if lead exists
const processedMids = new Set(); // Deduplication: prevent processing same message twice
const botStartedAt = Date.now(); // Track startup time for admin detection

// Persistent bot-sent message IDs (survives restart!)
const BOT_MIDS_FILE = path.join(__dirname, "bot_sent_mids.json");
const botSentMids = new Set();
// Load persisted mids on startup
try {
  if (fs.existsSync(BOT_MIDS_FILE)) {
    const saved = JSON.parse(fs.readFileSync(BOT_MIDS_FILE, "utf8"));
    const twoHoursAgo = Date.now() - 2 * 60 * 60 * 1000;
    for (const entry of saved) {
      if (entry.ts > twoHoursAgo) botSentMids.add(entry.mid);
    }
    console.log(`[Startup] Loaded ${botSentMids.size} persisted bot message IDs`);
  }
} catch (e) {
  console.error("[Startup] Failed to load bot_sent_mids.json:", e.message);
}
function persistBotMids() {
  try {
    const now = Date.now();
    const twoHoursAgo = now - 2 * 60 * 60 * 1000;
    const arr = [...botSentMids].map(mid => ({ mid, ts: now }));
    const trimmed = arr.filter(e => e.ts > twoHoursAgo).slice(-200);
    fs.writeFileSync(BOT_MIDS_FILE, JSON.stringify(trimmed));
  } catch (e) {}
}

function saveLead(senderPsid, phone, rawText) {
  const leadsFile = path.join(__dirname, 'leads.json');
  let leads = [];
  try {
    if (fs.existsSync(leadsFile)) {
      leads = JSON.parse(fs.readFileSync(leadsFile, 'utf8'));
    }
  } catch (e) {}
  leads.push({
    psid: senderPsid,
    phone: phone,
    rawText: rawText,
    timestamp: new Date().toISOString()
  });
  try {
    fs.writeFileSync(leadsFile, JSON.stringify(leads, null, 2));
    console.log(`🎉 [LEAD SAVED] Phone: ${phone} from ${senderPsid}`);
    // Send Telegram notification
    sendTelegramNotification(`🎯 <b>Шинэ үйлчлүүлэгч!</b>\n\n📞 Утас: <code>${phone}</code>\n💬 Тэмдэглэл: ${rawText}\n🕐 ${new Date().toLocaleString('mn-MN', { timeZone: 'Asia/Ulaanbaatar' })}`);
  } catch (e) {
    console.error('Error saving lead:', e);
  }
}

// Send Telegram Notification
async function sendTelegramNotification(message) {
  if (!TELEGRAM_BOT_TOKEN || !TELEGRAM_CHAT_ID) return;
  try {
    await fetch(`https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        chat_id: TELEGRAM_CHAT_ID,
        text: message,
        parse_mode: 'HTML'
      })
    });
    console.log('📩 [Telegram] Notification sent');
  } catch (e) {
    console.error('❌ [Telegram] Failed to send:', e.message);
  }
}

// Admin reply detection: echo handler + Graph API (persistent botSentMids survives restart)
async function hasAdminRepliedRecently(userPsid) {
  // Quick check: already paused by echo handler?
  if (pausedUsers[userPsid]) {
    const elapsed = Date.now() - pausedUsers[userPsid];
    if (elapsed < 12 * 60 * 60 * 1000) return true;
  }

  // Graph API check: look for admin messages in last 10 minutes
  if (!PAGE_ACCESS_TOKEN) return false;
  try {
    const url = `https://graph.facebook.com/v21.0/me/conversations?user_id=${userPsid}&fields=messages.limit(5){from,created_time,id}&access_token=${PAGE_ACCESS_TOKEN}`;
    const res = await fetch(url);
    if (!res.ok) {
      console.log(`[Admin Check] API ${res.status} — skipping`);
      return false;
    }
    const data = await res.json();

    const conv = data.data?.[0];
    if (!conv?.messages?.data) return false;

    const PAGE_ID_VAL = "494803463977316";
    const tenMinAgo = Date.now() - 10 * 60 * 1000;

    for (const msg of conv.messages.data) {
      const msgTime = new Date(msg.created_time).getTime();
      if (msgTime < tenMinAgo) continue;

      // Skip user messages
      if (msg.from?.id === userPsid) continue;

      // Page-sent message: bot or admin?
      if (msg.from?.id === PAGE_ID_VAL) {
        if (!botSentMids.has(msg.id)) {
          console.log(`[Admin Detected] msg ${msg.id} to ${userPsid} at ${msg.created_time}`);
          return true;
        }
      }
    }
  } catch (e) {
    console.error("[Admin Check Error]:", e.message);
  }
  return false;
}

// Working Hours Check (Mon-Fri 09:00-18:00 UB time)
// ⚠️ BOOST MODE: Temporarily always returns true (disable during ad campaigns)
function isWorkingHours() {
  return true; // TODO: Boost дууссаны дараа доорх кодыг буцааж идэвхжүүлэх
  // const now = new Date();
  // const ubTime = new Date(now.toLocaleString('en-US', { timeZone: 'Asia/Ulaanbaatar' }));
  // const day = ubTime.getDay(); // 0=Sun, 6=Sat
  // const hour = ubTime.getHours();
  // return day >= 1 && day <= 5 && hour >= 9 && hour < 18;
}

function getWorkingHoursMessage() {
  if (isWorkingHours()) {
    return 'Манай өмгөөлөгч одоо ажиллаж байна, тун удахгүй тантай холбогдоно.';
  } else {
    return 'Одоо ажлын бус цаг байна. Маргааш өглөө хамгийн түрүүнд тантай холбогдох болно.';
  }
}

// Check if lead already exists for this PSID
function isLeadDuplicate(senderPsid) {
  const leadsFile = path.join(__dirname, 'leads.json');
  try {
    if (fs.existsSync(leadsFile)) {
      const leads = JSON.parse(fs.readFileSync(leadsFile, 'utf8'));
      return leads.some(l => l.psid === senderPsid);
    }
  } catch (e) {}
  return false;
}

// Specialized Prompt for Conversational Legal Assistance & Fast Lead Closing (Anti-Token Waste)
const SYSTEM_PROMPT = `Чи бол "Өмгөөлөл.мн" (khuuli.com) хуулийн фирмийн албан ёсны ухаалаг хууль зүйн туслах AI юм.

ҮНДСЭН ДҮРЭМ (МАШ ЧУХАЛ):
1. ДАВХАР МЭНДЧИЛГЭЭ ХИЙХГҮЙ, ШУУД АЖИЛДАА ОРОХ:
   - Хэрэглэгчид өмнө нь Facebook-ээс мэндчилгээ очсон тул "Сайн байна уу, Өмгөөлөл.мн-д тавтай морил" гэх мэт урт мэндчилгээг хэзээ ч давтан бичихгүй!
   - Хэрэглэгч "Сайн уу", "сайн байна уу", "эхлэх" гэх мэт зөвхөн мэндчилгээ ирүүлбэл шууд: "Танд ямар хууль зүйн асуудал эсвэл гэрээ, итгэмжлэл хийлгэх хэрэгцээ гарсан бэ? Нөхцөл байдлаа товч бичнэ үү, би тусалъя." гэж асууна.

2. АСУУДАЛ ЯРЬЖ БАЙХАД ХУУЛИЙН ЗӨВЛӨМЖ ӨГӨӨД, УТАС РУУ ШУУД ХААХ (ТОКЕН ХЭМНЭХ ДҮРЭМ):
   - Хэрэглэгч асуудал ярьж байвал ҮНИЙН ЖАГСААЛТ ДУРДАХГҮЙ!
   - Тухайн асуудалд нь Монгол Улсын Иргэний хуулийн дагуу 1-2 өгүүлбэрт хууль зүйн гарц, эрсдэлийг товч тодорхой зөвлөнө.
   - Дараа нь яриаг сунжруулахгүйгээр шууд УТАСНЫ ДУГААР ЛУУ ХААНА:
     "Энэ эрсдэлээс сэргийлэх хамгийн зөв арга бол хуулийн шаардлага хангасан гэрээ байгуулах явдал юм. Манай өмгөөлөгчид таны энэ нөхцөлд тохирсон гэрээг боловсруулах эсвэл бэлэн гэрээг тань хянаж өгөх боломжтой.
     Таны асуудлыг хуулийн дагуу бүрэн шийдэхийн тулд та холбогдох утасны дугаараа үлдээнэ үү, манай өмгөөлөгч шуурхай залгаж зөвлөгөө өгье! Эсвэл манай ${PHONE_1}, ${PHONE_2} дугаарт холбогдоорой."
   - Хэрэв хэрэглэгч дугаараа өгөхгүй дахин лавшруулж үнэгүй зөвлөгөө асуусаар байвал урт тайлбар хийж токен үрэхгүй: "Таны энэ асуудлын хууль зүйн эцсийн дүгнэлтийг манай өмгөөлөгч утсаар эсвэл биечлэн дэлгэрэнгүй зөвлөх шаардлагатай. Та утасны дугаараа үлдээнэ үү, бид залгая. (Утас: ${PHONE_1}, ${PHONE_2})" гэж эелдэгээр утас руу чиглүүлж яриаг хаана.

3. ЗӨВХӨН ҮНЭ, ТӨЛБӨР АСУУСАН ҮЕД Л ҮНИЙГ ТОДОРХОЙ ХЭЛНЭ:
   - Хэрэглэгч "үнэ хэд вэ", "үнэ ханш", "төлбөр хэд вэ", "үнэ" гэж асуусан үед л үнийг танилцуулна:
     - ✅ **Эхний удаа утсаар 10 минутын зөвлөгөө, нэг удаагийн бичгийн зөвлөгөө**: Үнэгүй (Та бидэн рүү залгах юм уу, бичнэ үү)
     - ✅ **Дараагийн удаа утсаар өгөх 10 минутын зөвлөгөө**: 20,000₮
     - ✅ **Хууль зүйн баримт бичиг боловсруулах**: 30,000₮-өөс эхэлнэ (итгэмжлэл, нэхэмжлэл, хүсэлт, өргөдөл, гомдол, тушаал, шийдвэр, албан бичиг гэх мэт)
     - ✅ **Гэрээний бэлэн загвар**: 30,000₮
     - ✅ **Гэрээний төсөл боловсруулах**: 100,000₮-өөс эхэлнэ
     *Тайлбар: Ажлын цар хүрээ, ээдрээ төвөгшлөөс хамаарч үнийг харилцан тохиролцоно.*
     
     Та холбогдох дугаараа үлдээвэл манай өмгөөлөгч тантай холбогдож ярилцана. Холбоо барих: ${PHONE_1}, ${PHONE_2}

ЕРӨНХИЙ ШААРДЛАГА:
- Нийт хариулт ердөө 2-4 өгүүлбэр, цэгцтэй, уншихад хялбар байна.
- Үргэлж эелдэг, найрсаг, хүндэтгэлтэй ("Та") харилцана.
- Хууль зүйн бус (хоол, код, ерөнхий) сэдэвт: "Уучлаарай, манайх зөвхөн хууль зүйн зөвлөгөө, гэрээ, итгэмжлэл боловсруулах үйлчилгээ үзүүлдэг. Танд ямар хууль зүйн асуудлаар туслалцаа хэрэгтэй байна вэ?" гэж буцаана.

ГАЛИГ (ЛАТИН ҮСГЭЭР БИЧСЭН МОНГОЛ):
- Хэрэглэгч англи үсгээр монголоор бичиж болно, жишээ нь: "sain bnu" = "сайн байна уу", "geree" = "гэрээ", "huulch" = "хуульч", "une hed ve" = "үнэ хэд вэ"
- АНХААРУУЛГА: "hulsluh" гэдэг нь "хөлслөх" (түрээслэх) гэсэн үг бөгөөд "худалдах" (sales) гэж андуурч болохгүй! "hudalda" эсвэл "hudaldah" байвал худалдах гэрээ гэнэ.
- Ийм мессежийг бүрэн ойлгож монголоор хариу бич. Хэрэглэгчийг засахгүй — шууд ойлгож, монголоор хариулна.`;

// Quick replies focused on contract & POA drafting
function getQuickReplies() {
  return [
    {
      content_type: 'text',
      title: '📄 Гэрээ хянуулах',
      payload: 'BTN_REVIEW'
    },
    {
      content_type: 'text',
      title: '✍️ Шинэ гэрээ хийлгэх',
      payload: 'BTN_CREATE'
    },
    {
      content_type: 'text',
      title: '📑 Итгэмжлэл хийлгэх',
      payload: 'BTN_POA'
    },
    {
      content_type: 'text',
      title: '👤 Ажилтантай ярих',
      payload: 'BTN_STAFF'
    }
  ];
}

// Health check API & Leads Viewer
app.get('/api/health', (req, res) => {
  res.json({
    status: 'ok',
    app: 'Khuuli.com & Өмгөөлөл.мн Bot',
    primaryProvider: AI_PROVIDER,
    hasGemini: !!GEMINI_API_KEY,
    hasDeepSeek: !!DEEPSEEK_API_KEY
  });
});

app.get('/api/leads', (req, res) => {
  const leadsFile = path.join(__dirname, 'leads.json');
  if (fs.existsSync(leadsFile)) {
    try {
      const data = JSON.parse(fs.readFileSync(leadsFile, 'utf8'));
      return res.json(data);
    } catch (e) {}
  }
  res.json([]);
});

// Meta Webhook Verification
app.get('/webhook', (req, res) => {
  const mode = req.query['hub.mode'];
  const token = req.query['hub.verify_token'];
  const challenge = req.query['hub.challenge'];

  if (mode && token) {
    if (mode === 'subscribe' && token === VERIFY_TOKEN) {
      console.log('✅ Webhook verified successfully by Meta');
      res.status(200).send(challenge);
    } else {
      console.warn('❌ Verification token mismatch:', token);
      res.sendStatus(403);
    }
  } else {
    res.status(400).send('Missing hub parameters');
  }
});

// Meta Webhook Events Receiver
app.post('/webhook', (req, res) => {
  const body = req.body;

  if (body.object === 'page') {
    res.status(200).send('EVENT_RECEIVED');

    for (const entry of body.entry) {
      if (entry.messaging && entry.messaging.length > 0) {
        for (const webhookEvent of entry.messaging) {
          const senderPsid = webhookEvent.sender.id;

          // 1. Human Handoff (Echo interception)
          if (webhookEvent.message && webhookEvent.message.is_echo) {
            const recipientPsid = webhookEvent.recipient.id;
            
            // We intercept and process it as a normal message TO the admin
            if (ADMIN_PSIDS.includes(recipientPsid)) {
              const echoText = webhookEvent.message.text;
              if (echoText) {
                console.log(`\n🔧 [Admin Test] Processing echo as message for admin ${recipientPsid}: "${echoText}"`);
                processMessage(recipientPsid, echoText).catch(console.error);
              }
              continue;
            }
            
            console.log(`\n🛑 [Human Handoff] Admin replied manually. Pausing bot for ${recipientPsid} for 1 hour.`);
            pausedUsers[recipientPsid] = Date.now();
            continue;
          }

          // Log sender PSID for admin discovery
          if (ADMIN_PSIDS.length === 0) {
            console.log(`🔑 [PSID] ${senderPsid} — set ADMIN_PSIDS in .env to enable admin test mode`);
          }

          // Skip pause check for admin users
          const isAdmin = ADMIN_PSIDS.includes(senderPsid);
          if (isAdmin && pausedUsers[senderPsid]) {
            delete pausedUsers[senderPsid];
            console.log(`🔧 [Admin] Bypassed pause for ${senderPsid}`);
          }

          // Deduplication: skip if message already processed
          const mid = webhookEvent.message?.mid;
          if (mid) {
            if (processedMids.has(mid)) {
              console.log(`⏭️ [Skip] Duplicate message ${mid} from ${senderPsid}`);
              continue;
            }
            processedMids.add(mid);
            // Clean old mids (keep last 200)
            if (processedMids.size > 200) {
              const arr = [...processedMids];
              arr.slice(0, 100).forEach(m => processedMids.delete(m));
            }
          }

          // Check if bot is paused for this user
          const pauseDuration = 12 * 60 * 60 * 1000; // 12 hours
          if (pausedUsers[senderPsid] && (Date.now() - pausedUsers[senderPsid] < pauseDuration)) {
            console.log(`⏸️ [Paused] Ignoring message from ${senderPsid} (human handling)`);
            continue; // Silently ignore user messages while human is handling it
          } else if (pausedUsers[senderPsid]) {
            // Pause expired, clean up and resume bot
            delete pausedUsers[senderPsid];
            console.log(`▶️ [Resumed] Bot resumed for ${senderPsid} (pause expired)`);
          }

          // Update lastSeen tracking for automated follow-ups
          if (webhookEvent.message || webhookEvent.postback) {
            lastSeen[senderPsid] = Date.now();
            // We DO NOT reset followedUp flag here anymore. 
            // This prevents the bot from nagging the user with the same follow-up message every 2 hours if they reply but don't leave a number.
          }

          // 2. Quick reply or Button postback
          if (webhookEvent.postback) {
            const payload = webhookEvent.postback.payload;
            handleButtonPayload(senderPsid, payload).catch(console.error);
            continue;
          }

          if (webhookEvent.message) {
            // Quick reply button clicked
            if (webhookEvent.message.quick_reply) {
              const payload = webhookEvent.message.quick_reply.payload;
              handleButtonPayload(senderPsid, payload).catch(console.error);
              continue;
            }

            // 2. Handle Like / Thumbs Up Sticker (Facebook default like button)
            const isSticker = !!webhookEvent.message.sticker_id || 
              (webhookEvent.message.attachments && webhookEvent.message.attachments[0]?.payload?.sticker_id);

            if (isSticker) {
              console.log(`\n👍 [Like / Sticker received] From ${senderPsid}`);
              const likeReply = `Баярлалаа! 👍 Танд гэрээ, итгэмжлэл боловсруулах эсвэл хууль зүйн зөвлөгөө хэрэгтэй бол хэзээ ч хамаагүй бидэнд хандаарай. Бид туслахад үргэлж бэлэн байна!\n\n📞 Холбоо барих: ${PHONE_1}, ${PHONE_2}`;
              sendFacebookMessage(senderPsid, likeReply, getQuickReplies()).catch(console.error);
              continue;
            }

            // 3. Handle Attachments (Image / PDF / File sent for contract review)
            if (webhookEvent.message.attachments && webhookEvent.message.attachments.length > 0) {
              console.log(`\n📄 [Attachment received] From ${senderPsid}`);
              const docReply = `Таны илгээсэн файлыг хүлээн авлаа! 📄\n\nМанай өмгөөлөгчид баримт бичгийг тань хянаад хууль зүйн эрсдэлийг тооцож хариу өгөх болно. Та холбогдох утасны дугаараа үлдээнэ үү, бид эргэн холбогдож дүгнэлтийг танилцуулъя!\n\n📞 Холбоо барих: ${PHONE_1}, ${PHONE_2}`;
              sendFacebookMessage(senderPsid, docReply, getQuickReplies()).catch(console.error);
              continue;
            }

            const userText = webhookEvent.message.text;
            if (!userText) continue;

            // 4. Handle Text Thumbs Up or simple appreciation (👍, ok, etc.)
            if (/^(👍|👌|👏|🙏|🤝|\(y\)|like)$/i.test(userText.trim())) {
              console.log(`\n👍 [Text Like received] From ${senderPsid}: "${userText}"`);
              const likeReply = `Баярлалаа! 👍 Танд гэрээ, итгэмжлэл боловсруулах эсвэл хууль зүйн зөвлөгөө хэрэгтэй бол хэзээ ч хамаагүй бидэнд хандаарай. Бид туслахад үргэлж бэлэн байна!\n\n📞 Холбоо барих: ${PHONE_1}, ${PHONE_2}`;
              sendFacebookMessage(senderPsid, likeReply, getQuickReplies()).catch(console.error);
              continue;
            }

            console.log(`\n📩 [Message] From ${senderPsid}: "${userText}"`);
            processMessage(senderPsid, userText).catch(console.error);
          }
        }
      }
    }
  } else {
    res.sendStatus(404);
  }
});

// Instant Button responses
async function handleButtonPayload(senderPsid, payload) {
  // Auto-detect admin reply for button interactions too
  if (!ADMIN_PSIDS.includes(senderPsid)) {
    try {
      const adminReplied = await hasAdminRepliedRecently(senderPsid);
      if (adminReplied) {
        console.log(`\n🛑 [Auto-Handoff] Admin replied to ${senderPsid}. Pausing bot (button click).`);
        pausedUsers[senderPsid] = Date.now();
        return;
      }
    } catch (e) {}
  }

  if (payload === 'BTN_REVIEW') {
    const text = "За ойлголоо! 📄 Хянуулах гэрээ, итгэмжлэлийнхээ зургийг эсвэл PDF файлыг энэ чатаар илгээгээрэй. Манай өмгөөлөгчид хянаад хууль зүйн эрсдэлийг нь танд зөвлөх болно.";
    await sendFacebookMessage(senderPsid, text, getQuickReplies());
    return;
  }

  if (payload === 'BTN_CREATE') {
    const text = "✍️ Танд ямар харилцаанд зориулж гэрээ боловсруулах шаардлагатай байгаа вэ? (Жишээ нь: зээл, түрээс, худалдах, хөдөлмөр, хамтран ажиллах г.м.)\n\nТа гол нөхцөл болон хэрэгцээгээ товч бичээрэй, манай хуульчид танд тохирсон шийдлийг зөвлөе.";
    await sendFacebookMessage(senderPsid, text, getQuickReplies());
    return;
  }

  if (payload === 'BTN_POA') {
    const text = "📑 Ямар эрх олгох итгэмжлэл (байгууллагын, банкны, хөрөнгө захиран зарцуулах, төлөөлөх г.м.) хийлгэх хэрэгтэй байгаагаа товч бичнэ үү. Нотариатаар батлуулахад асуудалгүй албан ёсны төслийг боловсруулаад өгнө.";
    await sendFacebookMessage(senderPsid, text, getQuickReplies());
    return;
  }

  if (payload === 'BTN_STAFF') {
    const text = `👤 Мэргэшсэн өмгөөлөгч, хуульчтай шууд холбогдоход бэлэн байна.\n\nТа холбогдох утасны дугаараа үлдээнэ үү! Бид тантай шуурхай эргэн холбогдож дэлгэрэнгүй зөвлөгөө өгөх болно.\n\n📞 Шууд залгах: ${PHONE_1}, ${PHONE_2}`;
    await sendFacebookMessage(senderPsid, text, getQuickReplies());
    return;
  }
}

// Track quota blocks
let geminiBlockedUntil = 0;

// Unified AI Caller (DeepSeek only — Gemini temporarily disabled)
async function askAI(messagesArray) {
  try {
    const res = await callDeepSeek(messagesArray, 'deepseek-chat');
    if (res) return { text: res, provider: 'deepseek' };
  } catch (err) {
    console.error('[DeepSeek error]:', err.message);
  }
  return null;
}

// Process Message
async function processMessage(senderPsid, userText) {
  // Auto-detect admin reply (Meta Business Suite echoes are unreliable)
  if (!ADMIN_PSIDS.includes(senderPsid)) {
    try {
      const adminReplied = await hasAdminRepliedRecently(senderPsid);
      if (adminReplied) {
        console.log(`\n🛑 [Auto-Handoff] Admin already replied to ${senderPsid}. Pausing bot for 1 hour.`);
        pausedUsers[senderPsid] = Date.now();
        return;
      }
    } catch (e) {
      console.error('[Auto-Handoff Error]:', e.message);
    }
  }

  const lower = userText.toLowerCase();

  // 1. Check if user provided a phone number (Instant Lead Closing - 0 tokens!)
  const phoneMatch = userText.match(PHONE_REGEX);
  if (phoneMatch) {
    const detectedPhone = phoneMatch[0];

    // Duplicate lead check
    if (isLeadDuplicate(senderPsid)) {
      console.log(`♻️ [Duplicate Lead] ${senderPsid} already exists, skipping save.`);
      const dupReply = `Таны дугаарыг бид аль хэдийн хүлээн авсан. ✅ ${getWorkingHoursMessage()}`;
      await sendFacebookMessage(senderPsid, dupReply, getQuickReplies());
      return;
    }

    saveLead(senderPsid, detectedPhone, userText);
    leadCaptured[senderPsid] = true;
    const closeReply = `Баярлалаа! Таны утасны дугаарыг (${detectedPhone}) хүлээн авлаа. ✅\n\n${getWorkingHoursMessage()} Танд амжилт хүсье! 🤝`;
    await sendFacebookMessage(senderPsid, closeReply, getQuickReplies());
    return;
  }

  // 2. Staff request (Human Handoff)
  if (lower.includes('хүнтэй ярих') || lower.includes('ажилтантай') || lower.includes('утсаар залгах') || lower.includes('залгаарай') || lower.includes('утас залга')) {
    pausedUsers[senderPsid] = Date.now();
    console.log(`\n🛑 [Human Handoff] User requested staff. Pausing bot for ${senderPsid}`);
    sendTelegramNotification(`👤 <b>Хүнтэй ярих хүсэлт!</b>\n\n🆔 PSID: <code>${senderPsid}</code>\n💬 ${getWorkingHoursMessage()}\n🕐 ${new Date().toLocaleString('mn-MN', { timeZone: 'Asia/Ulaanbaatar' })}`);
    const staffMsg = `Түр хүлээнэ үү. ${getWorkingHoursMessage()}\n\n📞 Шууд залгах: ${PHONE_1}, ${PHONE_2}`;
    await sendFacebookMessage(senderPsid, staffMsg, getQuickReplies());
    return;
  }

  // 3. Keyword Filtering (Rule-based)
  // Galig (Latin script Mongolian) greeting detection
  const galigGreetings = /^(sain bnu|sain bnuu|sain bn u|sainuu|sn bn uu|sain baina uu|hi|hello|hey)$/i;
  if (galigGreetings.test(lower.trim())) {
    await sendFacebookMessage(senderPsid, "Сайн байна уу! 👋 Танд ямар хууль зүйн асуудал эсвэл гэрээ, итгэмжлэл хийлгэх хэрэгцээ гарсан бэ? Нөхцөл байдлаа товч бичнэ үү, би тусалъя.", getQuickReplies());
    return;
  }

  if (lower.includes('хаана') || lower.includes('хаяг') || lower.includes('байршил')) {
    await sendFacebookMessage(senderPsid, `📍 Манай хаяг: Хан-Уул дүүрэг, 22-р хороо, Гэрэлт хотхон, Цацралт хаус\n\n📞 Холбоо барих: ${PHONE_1}, ${PHONE_2}`, getQuickReplies());
    return;
  }
  if ((lower.includes('үнэ') || lower.includes('хэд вэ') || lower.includes('төлбөр')) && lower.length < 30) {
    await sendFacebookMessage(senderPsid, `✅ Эхний удаа утсаар 10 минутын зөвлөгөө, нэг удаагийн бичгийн зөвлөгөө: Үнэгүй (Та бидэн рүү залгах юм уу, бичнэ үү)\n✅ Дараагийн удаа утсаар өгөх 10 мин зөвлөгөө: 20,000₮\n✅ Баримт бичиг боловсруулах: 30,000₮-өөс эхэлнэ\n✅ Гэрээний бэлэн загвар: 30,000₮\n✅ Гэрээний төсөл боловсруулах: 100,000₮-өөс эхэлнэ\n*Тайлбар: Ажлын цар хүрээнээс хамаарч үнийг тохиролцоно.*\n\nТа холбогдох дугаараа үлдээнэ үү.`, getQuickReplies());
    return;
  }

  // 4. Memory Truncation (limit to last 4 messages)
  if (!chatMemory[senderPsid]) {
    chatMemory[senderPsid] = [];
  }
  chatMemory[senderPsid].push({ role: 'user', content: userText });
  if (chatMemory[senderPsid].length > 4) {
    chatMemory[senderPsid].shift();
  }

  // 5. AI response with typing indicator
  await sendTypingIndicator(senderPsid, 'typing_on');

  const aiStart = Date.now();
  const aiResult = await askAI(chatMemory[senderPsid]);
  const aiTime = ((Date.now() - aiStart) / 1000).toFixed(1);
  let replyText = aiResult ? aiResult.text : '';

  if (!replyText) {
    replyText = `Танд ямар хууль зүйн асуудал эсвэл гэрээ, итгэмжлэл хийлгэх хэрэгцээ гарсан бэ? Нөхцөл байдлаа товч бичнэ үү, би тусалъя. Утас: ${PHONE_1}, ${PHONE_2}`;
  } else {
    console.log(`🤖 [AI Reply via ${aiResult.provider} in ${aiTime}s]:\n${replyText}\n`);
    // Save AI reply to memory too
    chatMemory[senderPsid].push({ role: 'assistant', content: replyText });
    if (chatMemory[senderPsid].length > 4) {
      chatMemory[senderPsid].shift();
    }
  }

  await sendTypingIndicator(senderPsid, 'typing_off');
  await sendFacebookMessage(senderPsid, replyText, getQuickReplies());
}

// Call Google Gemini API
async function callGemini(messagesArray, modelName = 'gemini-2.5-flash') {
  const geminiUrl = `https://generativelanguage.googleapis.com/v1beta/models/${modelName}:generateContent?key=${GEMINI_API_KEY}`;
  
  const contents = messagesArray.map(m => ({
    role: m.role === 'assistant' ? 'model' : 'user',
    parts: [{ text: m.content }]
  }));
  
  // Prepend SYSTEM_PROMPT to the first user message
  if (contents.length > 0) {
    contents[0].parts[0].text = `${SYSTEM_PROMPT}\n\nХэрэглэгчийн мессеж: ${contents[0].parts[0].text}`;
  }

  const payload = {
    contents: contents,
    generationConfig: {
      temperature: 0.3,
      maxOutputTokens: 2048,
      thinkingConfig: {
        thinkingBudget: 0
      }
    }
  };

  const res = await fetch(geminiUrl, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Gemini API (${modelName}) returned ${res.status}: ${err}`);
  }

  const data = await res.json();
  return data.candidates?.[0]?.content?.parts?.[0]?.text;
}

// Call DeepSeek API
async function callDeepSeek(messagesArray, modelName = 'deepseek-chat') {
  const res = await fetch('https://api.deepseek.com/chat/completions', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${DEEPSEEK_API_KEY}`
    },
    body: JSON.stringify({
      model: modelName,
      messages: [
        { role: 'system', content: SYSTEM_PROMPT },
        ...messagesArray
      ],
      temperature: 0.3,
      max_tokens: 1000
    })
  });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(`DeepSeek API returned ${res.status}: ${err}`);
  }

  const data = await res.json();
  return data.choices?.[0]?.message?.content;
}

// Typing indicator
async function sendTypingIndicator(recipientId, action = 'typing_on') {
  if (!PAGE_ACCESS_TOKEN) return;
  try {
    await fetch(`https://graph.facebook.com/v21.0/me/messages?access_token=${PAGE_ACCESS_TOKEN}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        recipient: { id: recipientId },
        sender_action: action
      })
    });
  } catch (e) {}
}

// Send Facebook message
async function sendFacebookMessage(recipientId, messageText, quickReplies = null) {
  if (!PAGE_ACCESS_TOKEN) return;

  const messagePayload = {
    recipient: { id: recipientId },
    message: {
      text: messageText
    }
  };

  if (quickReplies && quickReplies.length > 0) {
    messagePayload.message.quick_replies = quickReplies;
  }

  const url = `https://graph.facebook.com/v21.0/me/messages?access_token=${PAGE_ACCESS_TOKEN}`;
  const fbRes = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(messagePayload)
  });

  const respData = await fbRes.json();
  if (!fbRes.ok) {
    console.error(`❌ [Facebook Send API Error]:`, JSON.stringify(respData));
  } else {
    console.log(`✅ [Facebook Send Success] Message sent to ${recipientId}`);
    // Track bot-sent message IDs for admin detection
    if (respData.message_id) {
      botSentMids.add(respData.message_id);
      persistBotMids();
      if (botSentMids.size > 500) {
        const arr = [...botSentMids];
        arr.slice(0, 250).forEach(m => botSentMids.delete(m));
        persistBotMids();
      }
    }
  }
}

// --- Automated Follow-up Cron (Every 10 mins) ---
setInterval(() => {
  const now = Date.now();
  const MAX_AGE = 24 * 60 * 60 * 1000; // 24 hours - clean up old entries

  for (const [psid, time] of Object.entries(lastSeen)) {
    const age = now - time;

    // If 2 hours have passed and no lead captured and not yet followed up
    if (age > 2 * 60 * 60 * 1000 && !leadCaptured[psid] && !followedUp[psid]) {
       followedUp[psid] = true;
       const msg = "Сайн байна уу? Та хуулийн асуудлаа шийдэж чадсан уу? Бидэнтэй утсаар холбогдож дэлгэрэнгүй зөвлөгөө авах бол дугаараа үлдээнэ үү.";
       sendFacebookMessage(psid, msg, getQuickReplies()).catch(console.error);
       console.log(`\n🔄 [Automated Follow-up] Sent to ${psid}`);
    }

    // Memory cleanup: remove entries older than 24 hours
    if (age > MAX_AGE) {
      delete lastSeen[psid];
      delete followedUp[psid];
      delete leadCaptured[psid];
      delete chatMemory[psid];
      delete pausedUsers[psid];
    }
  }
}, 30 * 60 * 1000);


// ═══════════════════════════════════════════════════════════════════
// БҮРТГЭЛ ХАЙЛТЫН API - Компанийн бүртгэл, хувьцаа эзэмшигч хайлт
// ═══════════════════════════════════════════════════════════════════
const Database = require("better-sqlite3");
const DB_PATH = path.join(__dirname, "data", "burtgel_les.db");

let burtgelDb = null;
function getBurtgelDb() {
  if (!burtgelDb) {
    burtgelDb = new Database(DB_PATH, { readonly: true });
  }
  return burtgelDb;
}

// Preload DB on startup
try {
  getBurtgelDb();
  console.log("📋 better-sqlite3 DB loaded (" + (fs.statSync(DB_PATH).size / 1048576).toFixed(0) + " MB)");
} catch (e) {
  console.error("DB load error:", e.message);
}

// Search API — FTS5 powered (sub-millisecond, hyphen-tolerant)
// "оюун-эрдэнэ" → "оюунэрдэнэ" → FTS5 MATCH
function normalizeFts(text) {
  if (!text) return "";
  return text.toLowerCase().trim()
    .replace(/[-–—]/g, "")
    .replace(/\s+/g, " ");
}

app.get("/api/burtgel/search", async (req, res) => {
  const q = (req.query.q || "").trim();
  const filter = (req.query.filter || "all").toLowerCase();
  const limit = Math.min(parseInt(req.query.limit) || 50, 100);

  if (q.length < 2) {
    return res.json({ error: "Query хамгийн багадаа 2 тэмдэгт байна.", companies: [], total_companies: 0, total_matches: 0, duration_ms: 0 });
  }

  const t0 = Date.now();
  try {
    const db = getBurtgelDb();
    let flatRows = [];

    // Build role filter for post-FTS filtering
    let roleFilter = "";
    if (filter === "shareholder") roleFilter = " AND p.role = 'Хувьцаа эзэмшигч'";
    else if (filter === "director") roleFilter = " AND (p.role LIKE '%захирал%' OR p.role LIKE '%Захирал%')";
    else if (filter === "ubo") roleFilter = " AND p.role LIKE '%өмчлөгч%'";

    const baseSql = `SELECT p.reg_no, p.role, p.father_name, p.first_name, p.gender, p.reg_date AS role_date,
                          c.name AS company_name, c.form, c.reg_date AS comp_date, c.activities
                   FROM company_people p
                   JOIN companies c ON p.reg_no = c.reg_no`;

    if (/^\d{6,8}$/.test(q)) {
      // Регистрийн дугаараар шууд хайх (индекс ашиглана)
      flatRows = db.prepare(`${baseSql} WHERE p.reg_no = ?${roleFilter} LIMIT ?`).all(q, limit);
    } else {
      const normalized = normalizeFts(q);
      const parts = normalized.split(/\s+/).filter(p => p.length >= 2);
      if (parts.length === 0) {
        return res.json({ query: q, filter, total_companies: 0, total_matches: 0, duration_ms: Date.now() - t0, companies: [] });
      }

      // FTS5 match expression: each word as prefix
      const ftsTerm = parts.map(p => `"${p}"*`).join(" ");

      // 1. Компанийн нэрээр FTS5 хайлт
      try {
        const compRegs = db.prepare(`SELECT reg_no FROM fts_companies WHERE fts_companies MATCH ? LIMIT ?`).all(ftsTerm, limit);
        if (compRegs.length > 0) {
          const placeholders = compRegs.map(() => "?").join(",");
          const cParams = compRegs.map(r => r.reg_no);
          cParams.push(limit);
          flatRows = db.prepare(`${baseSql} WHERE p.reg_no IN (${placeholders})${roleFilter} LIMIT ?`).all(...cParams);
        }
      } catch (ftsErr) {
        // FTS5 хүснэгт байхгүй бол хуучин LIKE-руу буцна
        console.warn("FTS5 company search fallback:", ftsErr.message);
        const ql = q.toLowerCase();
        flatRows = db.prepare(`${baseSql} WHERE (c.name_lower LIKE ? OR c.name_lower LIKE ?)${roleFilter} LIMIT ?`).all(`${ql}%`, `% ${ql}%`, limit);
      }

      // 2. Хувь хүний нэрээр FTS5 хайлт
      if (flatRows.length < limit) {
        try {
          const pRows = db.prepare(`
            SELECT fp.reg_no, fp.role, fp.father_text AS father_name, fp.first_text AS first_name,
                   '' AS gender, '' AS role_date,
                   c.name AS company_name, c.form, c.reg_date AS comp_date, c.activities
            FROM fts_people fp
            JOIN companies c ON fp.reg_no = c.reg_no
            WHERE fts_people MATCH ?
            ${roleFilter ? roleFilter.replace(/p\./g, 'fp.') : ''}
            LIMIT ?
          `).all(ftsTerm, limit - flatRows.length);
          flatRows.push(...pRows);
        } catch (ftsErr) {
          // FTS5 байхгүй бол хуучин LIKE хайлт
          console.warn("FTS5 people search fallback:", ftsErr.message);
          const ql = q.toLowerCase();
          const fParts = ql.split(/\s+/);
          let conditions = [];
          let params = [];
          for (const p of fParts) {
            conditions.push(`(p.full_lower LIKE ? OR p.full_lower LIKE ?)`);
            params.push(`${p}%`, `% ${p}%`);
          }
          const pSql = `${baseSql} WHERE (${conditions.join(' AND ')})${roleFilter} LIMIT ?`;
          params.push(limit - flatRows.length);
          const pRows = db.prepare(pSql).all(...params);
          flatRows.push(...pRows);
        }
      }
    }

    // Давхардал хасах (reg_no + father + first)
    const seen = new Set();
    flatRows = flatRows.filter(r => {
      const key = `${r.reg_no}_${r.father_name}_${r.first_name}_${r.role}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });

    // Group by company
    const companyMap = {};
    for (const r of flatRows) {
      if (!companyMap[r.reg_no]) {
        companyMap[r.reg_no] = {
          reg_no: r.reg_no,
          name: r.company_name,
          form: r.form,
          reg_date: r.comp_date,
          activities: r.activities,
          roles: []
        };
      }
      companyMap[r.reg_no].roles.push({
        role: r.role,
        father: r.father_name,
        first: r.first_name,
        gender: r.gender,
        date: r.role_date
      });
    }

    const companies = Object.values(companyMap);
    const durationMs = Date.now() - t0;

    res.json({ query: q, filter, total_companies: companies.length, total_matches: flatRows.length, duration_ms: durationMs, companies });
  } catch (err) {
    console.error("Burtgel search error:", err.message);
    res.status(500).json({ error: err.message, companies: [], total_companies: 0, total_matches: 0, duration_ms: Date.now() - t0 });
  }
});

// Company detail by reg_no
app.get("/api/burtgel/company/:regNo", async (req, res) => {
  try {
    const db = getBurtgelDb();
    const comp = db.prepare("SELECT * FROM companies WHERE reg_no = ?").get(req.params.regNo);
    if (!comp) return res.status(404).json({ error: "Олдсонгүй" });

    const people = db.prepare("SELECT role, father_name, first_name, gender, reg_date FROM company_people WHERE reg_no = ?").all(req.params.regNo);
    
    res.json({ company: comp, people });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Serve burtgel page
app.get("/burtgel", (req, res) => {
  res.sendFile(path.join(__dirname, "public", "burtgel.html"));
});

console.log("📋 Бүртгэл хайлтын API холбогдлоо: /api/burtgel/search, /burtgel");


app.listen(PORT, '0.0.0.0', () => {
  console.log(`=======================================================`);
  console.log(`🚀 Өмгөөлөл.мн (khuuli.com) Bot running with Like & File Handlers on port ${PORT}`);
  console.log(`   Provider Priority: ${AI_PROVIDER} | Failover Ready: true`);
  console.log(`=======================================================`);
});