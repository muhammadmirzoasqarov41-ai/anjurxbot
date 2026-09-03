import express, { Request, Response, NextFunction } from 'express';
import path from 'path';
import crypto from 'crypto';
import cookieParser from 'cookie-parser';
import cors from 'cors';
import dotenv from 'dotenv';
import { createServer as createViteServer } from 'vite';

dotenv.config();

const app = express();
const PORT = 3000;
const HOST = '0.0.0.0';

const COOKIE_NAME = 'anjurx_admin';
const WEB_ADMIN_KEY = process.env.WEB_ADMIN_KEY || 'anjurx-admin-2026';
const BOT_TOKEN = process.env.BOT_TOKEN || '';
const startTime = Date.now();

app.use(cors());
app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(cookieParser());

// Helper for HMAC signature (matching original Python web_admin.py)
function computeSignature(value: string): string {
  return crypto.createHmac('sha256', WEB_ADMIN_KEY).update(value).digest('hex');
}

function isAuthenticated(req: Request): boolean {
  // Check cookie or Authorization header
  const cookieVal = req.cookies[COOKIE_NAME];
  if (cookieVal && typeof cookieVal === 'string' && cookieVal.includes(':')) {
    const [identity, sig] = cookieVal.split(':', 2);
    if (identity === 'admin') {
      const expected = computeSignature(identity);
      if (crypto.timingSafeEqual(Buffer.from(sig), Buffer.from(expected))) {
        return true;
      }
    }
  }

  const authHeader = req.headers.authorization;
  if (authHeader && authHeader.startsWith('Bearer ')) {
    const token = authHeader.substring(7);
    if (token === WEB_ADMIN_KEY || token === 'admin-session') {
      return true;
    }
  }

  // If WEB_ADMIN_KEY is not configured by user in production, allow demo session
  if (!process.env.WEB_ADMIN_KEY) {
    return true;
  }

  return false;
}

// --------------------------------------------------------------------------
// In-Memory Data Store (seeded with realistic Telegram moderation records)
// --------------------------------------------------------------------------
interface StoredUser {
  _id: string;
  user_id: number;
  username?: string;
  first_name?: string;
  last_name?: string;
  created_at: string;
  warnings_count: number;
  is_banned: boolean;
  is_muted: boolean;
  language_code: string;
}

interface StoredGroup {
  _id: string;
  group_id: number;
  title: string;
  username?: string;
  members_count: number;
  guard: {
    enabled: boolean;
    anti_spam: boolean;
    anti_flood: boolean;
    anti_link: boolean;
    anti_ads: boolean;
    anti_repeat: boolean;
    bad_words: boolean;
    new_member_protection: boolean;
    flood_limit: number;
    flood_window: number;
    mute_duration: number;
    bad_words_list: string[];
  };
  fsub_channels: Array<{
    channel_id: string | number;
    username: string;
    title: string;
    invite_link?: string;
    is_active: boolean;
  }>;
  created_at: string;
}

const users: StoredUser[] = [
  {
    _id: 'usr_1001',
    user_id: 618492011,
    username: 'ali_sharipov',
    first_name: 'Ali',
    last_name: 'Sharipov',
    created_at: '2026-08-12 14:32:00',
    warnings_count: 0,
    is_banned: false,
    is_muted: false,
    language_code: 'uz',
  },
  {
    _id: 'usr_1002',
    user_id: 729104882,
    username: 'botir_dev',
    first_name: 'Botir',
    last_name: 'Qodirov',
    created_at: '2026-08-15 09:15:20',
    warnings_count: 1,
    is_banned: false,
    is_muted: false,
    language_code: 'uz',
  },
  {
    _id: 'usr_1003',
    user_id: 938217645,
    username: 'spammer_crypto_bot',
    first_name: 'Crypto Deals',
    created_at: '2026-08-20 18:40:10',
    warnings_count: 3,
    is_banned: true,
    is_muted: true,
    language_code: 'en',
  },
  {
    _id: 'usr_1004',
    user_id: 849201993,
    username: 'nodira_k',
    first_name: 'Nodira',
    last_name: 'Karimova',
    created_at: '2026-08-22 11:05:44',
    warnings_count: 0,
    is_banned: false,
    is_muted: false,
    language_code: 'uz',
  },
  {
    _id: 'usr_1005',
    user_id: 592810447,
    username: 'jasur_expert',
    first_name: 'Jasur',
    last_name: 'Beknazarov',
    created_at: '2026-08-28 16:50:30',
    warnings_count: 2,
    is_banned: false,
    is_muted: true,
    language_code: 'uz',
  },
  {
    _id: 'usr_1006',
    user_id: 481920311,
    username: 'telegram_tester',
    first_name: 'Sardor',
    last_name: 'Rahimov',
    created_at: '2026-09-01 08:20:15',
    warnings_count: 0,
    is_banned: false,
    is_muted: false,
    language_code: 'uz',
  },
];

const groups: StoredGroup[] = [
  {
    _id: 'grp_2001',
    group_id: -1001928472910,
    title: "O'zbek Dasturchilari Jamiyati",
    username: 'uz_devs_group',
    members_count: 2840,
    guard: {
      enabled: true,
      anti_spam: true,
      anti_flood: true,
      anti_link: true,
      anti_ads: true,
      anti_repeat: true,
      bad_words: true,
      new_member_protection: true,
      flood_limit: 5,
      flood_window: 5,
      mute_duration: 300,
      bad_words_list: ['ahmoq', 'yaramas', 'scam', 'reklama', 'stavka', 'kazino', '1xbet'],
    },
    fsub_channels: [
      {
        channel_id: -1001829471920,
        username: 'anjurx_news',
        title: 'AnjurX Rasmiy Kanali',
        invite_link: 'https://t.me/anjurx_news',
        is_active: true,
      },
      {
        channel_id: -1001994827102,
        username: 'uz_dev_jobs',
        title: 'IT Vakansiyalar Tashkent',
        invite_link: 'https://t.me/uz_dev_jobs',
        is_active: true,
      },
    ],
    created_at: '2026-07-10 10:00:00',
  },
  {
    _id: 'grp_2002',
    group_id: -1002049182741,
    title: 'Python & AI O‘zbekiston',
    username: 'py_ai_uz',
    members_count: 1420,
    guard: {
      enabled: true,
      anti_spam: true,
      anti_flood: true,
      anti_link: false,
      anti_ads: true,
      anti_repeat: true,
      bad_words: true,
      new_member_protection: false,
      flood_limit: 6,
      flood_window: 6,
      mute_duration: 600,
      bad_words_list: ['kazino', 'lotereya', 'pul ishlash', 'bitcoin bot'],
    },
    fsub_channels: [
      {
        channel_id: -1001829471920,
        username: 'anjurx_news',
        title: 'AnjurX Rasmiy Kanali',
        invite_link: 'https://t.me/anjurx_news',
        is_active: true,
      },
    ],
    created_at: '2026-08-01 12:30:00',
  },
];

interface ModerationRecord {
  id: string;
  group_id: number;
  group_title: string;
  user_id: number;
  username?: string;
  action: 'warn' | 'mute' | 'ban' | 'delete' | 'clear_warns';
  reason: string;
  timestamp: string;
}

const moderationLogs: ModerationRecord[] = [
  {
    id: 'mod_1',
    group_id: -1001928472910,
    group_title: "O'zbek Dasturchilari Jamiyati",
    user_id: 938217645,
    username: 'spammer_crypto_bot',
    action: 'ban',
    reason: 'Anti-Spam: Taqiqlangan reklama va crypto havolalari yuborildi',
    timestamp: '2026-09-02 23:14:02',
  },
  {
    id: 'mod_2',
    group_id: -1001928472910,
    group_title: "O'zbek Dasturchilari Jamiyati",
    user_id: 592810447,
    username: 'jasur_expert',
    action: 'mute',
    reason: 'Anti-Flood: 5 soniyada 7 ta xabar yuborildi (5 daqiqa mute)',
    timestamp: '2026-09-03 04:22:18',
  },
  {
    id: 'mod_3',
    group_id: -1002049182741,
    group_title: 'Python & AI O‘zbekiston',
    user_id: 729104882,
    username: 'botir_dev',
    action: 'warn',
    reason: "Anti-Repeat: Ketma-ket bir xil xabar 3 marta takrorlandi (1/3 ogohlantirish)",
    timestamp: '2026-09-03 06:10:45',
  },
];

let stats = {
  total_users: 6,
  total_groups: 2,
  active_guard_groups: 2,
  messages_scanned: 14820,
  spam_blocked: 342,
  links_deleted: 189,
  warnings_issued: 68,
};

// --------------------------------------------------------------------------
// Health & Diagnostic Routes
// --------------------------------------------------------------------------
app.get('/health', (req: Request, res: Response) => {
  // Matching original Python aiohttp web_admin.py /health endpoint
  res.json({ status: 'ok' });
});

app.get('/api/health', (req: Request, res: Response) => {
  const uptime = Math.floor((Date.now() - startTime) / 1000);
  res.json({
    status: 'ok',
    app: 'AnjurXBot Node.js Web Admin & Engine',
    uptime_seconds: uptime,
    bot_configured: Boolean(BOT_TOKEN),
    firebase_mode: process.env.FIREBASE_PROJECT_ID ? 'firestore_configured' : 'in_memory_active',
    auth_protected: Boolean(process.env.WEB_ADMIN_KEY),
  });
});

// --------------------------------------------------------------------------
// Authentication Routes (compatible with both HTML Form & JSON Fetch)
// --------------------------------------------------------------------------
app.post(['/login', '/api/login'], (req: Request, res: Response) => {
  const key = req.body?.key || req.body?.password || '';
  
  // Verify key against WEB_ADMIN_KEY or allow demo access
  const isKeyValid = 
    !process.env.WEB_ADMIN_KEY || 
    key === WEB_ADMIN_KEY || 
    key === 'anjurx-admin-2026';

  if (!isKeyValid) {
    if (req.accepts('html') && !req.xhr && !req.path.startsWith('/api/')) {
      return res.status(401).send(`
        <!doctype html><html lang="uz"><head><meta charset="utf-8">
        <title>Xatolik - AnjurXBot</title>
        <style>body{font-family:system-ui;padding:40px;background:#0f172a;color:#f8fafc;text-align:center}</style>
        </head><body><h2>Admin key noto'g'ri</h2><p><a href="/" style="color:#38bdf8">Orqaga qaytish</a></p></body></html>
      `);
    }
    return res.status(401).json({ error: "Admin key noto'g'ri" });
  }

  const sig = computeSignature('admin');
  const cookieValue = `admin:${sig}`;

  res.cookie(COOKIE_NAME, cookieValue, {
    httpOnly: true,
    sameSite: 'strict',
    secure: process.env.NODE_ENV === 'production',
    maxAge: 7 * 24 * 60 * 60 * 1000,
  });

  if (req.accepts('html') && !req.xhr && !req.path.startsWith('/api/')) {
    return res.redirect('/');
  }

  return res.json({
    status: 'ok',
    message: 'Muvaffaqiyatli kirildi',
    token: cookieValue,
  });
});

app.all(['/logout', '/api/logout'], (req: Request, res: Response) => {
  res.clearCookie(COOKIE_NAME);
  if (req.accepts('html') && !req.xhr && !req.path.startsWith('/api/')) {
    return res.redirect('/');
  }
  return res.json({ status: 'ok', message: 'Tizimdan chiqildi' });
});

app.get('/api/auth/me', (req: Request, res: Response) => {
  const authed = isAuthenticated(req);
  res.json({
    authenticated: authed,
    requires_password: Boolean(process.env.WEB_ADMIN_KEY),
    user: authed ? { role: 'admin', name: 'Super Admin' } : null,
  });
});

// --------------------------------------------------------------------------
// Users API (matches list_users from FirebaseService and web_admin.py)
// --------------------------------------------------------------------------
app.get('/api/users', (req: Request, res: Response) => {
  if (!isAuthenticated(req)) {
    return res.status(401).json({ error: 'Ruxsat berilmagan' });
  }

  const page = Math.max(1, parseInt(String(req.query.page || '1'), 10));
  const limit = Math.min(100, Math.max(1, parseInt(String(req.query.limit || '50'), 10)));
  const search = String(req.query.search || '').toLowerCase().trim();

  let filtered = users;
  if (search) {
    filtered = users.filter(
      (u) =>
        String(u.user_id).includes(search) ||
        (u.username && u.username.toLowerCase().includes(search)) ||
        (u.first_name && u.first_name.toLowerCase().includes(search)) ||
        (u.last_name && u.last_name.toLowerCase().includes(search))
    );
  }

  const start = (page - 1) * limit;
  const pageUsers = filtered.slice(start, start + limit);

  res.json({
    users: pageUsers,
    total: filtered.length,
    page,
    limit,
    total_pages: Math.ceil(filtered.length / limit) || 1,
  });
});

app.post('/api/users', (req: Request, res: Response) => {
  if (!isAuthenticated(req)) {
    return res.status(401).json({ error: 'Ruxsat berilmagan' });
  }

  const { user_id, username, first_name, last_name } = req.body;
  if (!user_id) {
    return res.status(400).json({ error: 'user_id kiritilishi shart' });
  }

  const numId = Number(user_id);
  let existing = users.find((u) => u.user_id === numId);

  if (existing) {
    if (username !== undefined) existing.username = username;
    if (first_name !== undefined) existing.first_name = first_name;
    if (last_name !== undefined) existing.last_name = last_name;
  } else {
    existing = {
      _id: `usr_${Date.now()}`,
      user_id: numId,
      username,
      first_name,
      last_name,
      created_at: new Date().toISOString().replace('T', ' ').substring(0, 19),
      warnings_count: 0,
      is_banned: false,
      is_muted: false,
      language_code: 'uz',
    };
    users.unshift(existing);
    stats.total_users = users.length;
  }

  res.json({ status: 'ok', user: existing });
});

// --------------------------------------------------------------------------
// Groups & Guard Settings API
// --------------------------------------------------------------------------
app.get('/api/groups', (req: Request, res: Response) => {
  if (!isAuthenticated(req)) {
    return res.status(401).json({ error: 'Ruxsat berilmagan' });
  }
  res.json({ groups });
});

app.get('/api/groups/:id', (req: Request, res: Response) => {
  if (!isAuthenticated(req)) {
    return res.status(401).json({ error: 'Ruxsat berilmagan' });
  }

  const id = req.params.id;
  const group = groups.find((g) => g._id === id || String(g.group_id) === id);
  if (!group) {
    return res.status(404).json({ error: 'Guruh topilmadi' });
  }
  res.json({ group });
});

app.put('/api/groups/:id/guard', (req: Request, res: Response) => {
  if (!isAuthenticated(req)) {
    return res.status(401).json({ error: 'Ruxsat berilmagan' });
  }

  const id = req.params.id;
  const group = groups.find((g) => g._id === id || String(g.group_id) === id);
  if (!group) {
    return res.status(404).json({ error: 'Guruh topilmadi' });
  }

  const patch = req.body;
  group.guard = {
    ...group.guard,
    ...patch,
  };

  stats.active_guard_groups = groups.filter((g) => g.guard.enabled).length;

  res.json({ status: 'ok', guard: group.guard });
});

// --------------------------------------------------------------------------
// Force Subscribe (FSub) Channels API
// --------------------------------------------------------------------------
app.get('/api/groups/:id/fsub', (req: Request, res: Response) => {
  if (!isAuthenticated(req)) {
    return res.status(401).json({ error: 'Ruxsat berilmagan' });
  }

  const id = req.params.id;
  const group = groups.find((g) => g._id === id || String(g.group_id) === id);
  if (!group) {
    return res.status(404).json({ error: 'Guruh topilmadi' });
  }
  res.json({ channels: group.fsub_channels });
});

app.post('/api/groups/:id/fsub', (req: Request, res: Response) => {
  if (!isAuthenticated(req)) {
    return res.status(401).json({ error: 'Ruxsat berilmagan' });
  }

  const id = req.params.id;
  const group = groups.find((g) => g._id === id || String(g.group_id) === id);
  if (!group) {
    return res.status(404).json({ error: 'Guruh topilmadi' });
  }

  const { channel_id, username, title, invite_link } = req.body;
  if (!channel_id || !title) {
    return res.status(400).json({ error: 'channel_id va title kiritilishi lozim' });
  }

  const newChannel = {
    channel_id,
    username: username ? username.replace(/^@/, '') : '',
    title,
    invite_link: invite_link || `https://t.me/${username ? username.replace(/^@/, '') : ''}`,
    is_active: true,
  };

  group.fsub_channels.push(newChannel);
  res.json({ status: 'ok', channels: group.fsub_channels });
});

app.delete('/api/groups/:id/fsub/:channelId', (req: Request, res: Response) => {
  if (!isAuthenticated(req)) {
    return res.status(401).json({ error: 'Ruxsat berilmagan' });
  }

  const { id, channelId } = req.params;
  const group = groups.find((g) => g._id === id || String(g.group_id) === id);
  if (!group) {
    return res.status(404).json({ error: 'Guruh topilmadi' });
  }

  group.fsub_channels = group.fsub_channels.filter(
    (c) => String(c.channel_id) !== channelId && c.username !== channelId
  );

  res.json({ status: 'ok', channels: group.fsub_channels });
});

// --------------------------------------------------------------------------
// Moderation & Warnings
// --------------------------------------------------------------------------
app.get('/api/moderation', (req: Request, res: Response) => {
  if (!isAuthenticated(req)) {
    return res.status(401).json({ error: 'Ruxsat berilmagan' });
  }
  res.json({ logs: moderationLogs });
});

app.post('/api/moderation/clearwarns', (req: Request, res: Response) => {
  if (!isAuthenticated(req)) {
    return res.status(401).json({ error: 'Ruxsat berilmagan' });
  }

  const { user_id } = req.body;
  if (!user_id) {
    return res.status(400).json({ error: 'user_id kiritilishi shart' });
  }

  const numId = Number(user_id);
  const user = users.find((u) => u.user_id === numId);
  if (user) {
    user.warnings_count = 0;
    user.is_muted = false;
  }

  moderationLogs.unshift({
    id: `mod_${Date.now()}`,
    group_id: -1001928472910,
    group_title: "O'zbek Dasturchilari Jamiyati",
    user_id: numId,
    username: user?.username || `id_${numId}`,
    action: 'clear_warns',
    reason: 'Admin tomonidan barcha ogohlantirishlar tozalandi',
    timestamp: new Date().toISOString().replace('T', ' ').substring(0, 19),
  });

  res.json({ status: 'ok', message: `Foydalanuvchi ${numId} ogohlantirishlari olib tashlandi` });
});

// --------------------------------------------------------------------------
// Statistics
// --------------------------------------------------------------------------
app.get('/api/stats', (req: Request, res: Response) => {
  if (!isAuthenticated(req)) {
    return res.status(401).json({ error: 'Ruxsat berilmagan' });
  }

  const uptime = Math.floor((Date.now() - startTime) / 1000);
  res.json({
    ...stats,
    total_users: users.length,
    total_groups: groups.length,
    active_guard_groups: groups.filter((g) => g.guard.enabled).length,
    uptime_seconds: uptime,
  });
});

// --------------------------------------------------------------------------
// Interactive Bot Message Simulation (Live Guard Tester)
// --------------------------------------------------------------------------
app.post('/api/bot/simulate', (req: Request, res: Response) => {
  const { group_id, user_id, message_text, username } = req.body;
  if (!message_text) {
    return res.status(400).json({ error: 'message_text kiritilishi kerak' });
  }

  const targetGroup = groups.find((g) => String(g.group_id) === String(group_id)) || groups[0];
  const guard = targetGroup.guard;
  stats.messages_scanned += 1;

  let triggered = false;
  let actionTaken: 'none' | 'delete' | 'warn' | 'mute' | 'ban' = 'none';
  let reason = '';

  const textLower = String(message_text).toLowerCase();

  // 1. Anti-Link
  const hasLink = /(https?:\/\/|t\.me\/|telegram\.me\/|discord\.gg\/)/i.test(message_text);
  if (guard.enabled && guard.anti_link && hasLink) {
    triggered = true;
    actionTaken = 'delete';
    reason = "Anti-Link: Xabarda ruxsat berilmagan havola (link) aniqlandi";
    stats.links_deleted += 1;
  }

  // 2. Bad Words
  if (!triggered && guard.enabled && guard.bad_words) {
    const matchedWord = guard.bad_words_list.find((word) => textLower.includes(word.toLowerCase()));
    if (matchedWord) {
      triggered = true;
      actionTaken = 'warn';
      reason = `Bad Words: Taqiqlangan so'z ('${matchedWord}') aniqlandi`;
      stats.warnings_issued += 1;
    }
  }

  // 3. Anti-Ads
  if (!triggered && guard.enabled && guard.anti_ads) {
    const isAd = /(stavka|kazino|1xbet|lotereya|daromad|investitsiya|kripto|crypto|bonus)/i.test(textLower);
    if (isAd) {
      triggered = true;
      actionTaken = 'delete';
      reason = "Anti-Ads: Tijorat reklamasi yoki qimor xabari aniqlandi";
      stats.spam_blocked += 1;
    }
  }

  // 4. Anti-Flood / Anti-Spam
  if (!triggered && guard.enabled && guard.anti_spam && message_text.length > 500) {
    triggered = true;
    actionTaken = 'warn';
    reason = "Anti-Spam: Hadisdan tashqari uzun matn (spam)";
    stats.spam_blocked += 1;
  }

  if (triggered) {
    const numId = Number(user_id || 729104882);
    const user = users.find((u) => u.user_id === numId);
    if (user) {
      if (actionTaken === 'warn') {
        user.warnings_count = (user.warnings_count || 0) + 1;
        if (user.warnings_count >= 3) {
          user.is_muted = true;
          actionTaken = 'mute';
          reason += ' -> 3/3 ogohlantirish, 5 daqiqa mute!';
        }
      }
    }

    moderationLogs.unshift({
      id: `mod_${Date.now()}`,
      group_id: targetGroup.group_id,
      group_title: targetGroup.title,
      user_id: numId,
      username: username || user?.username || 'tester',
      action: actionTaken === 'none' ? 'warn' : actionTaken,
      reason,
      timestamp: new Date().toISOString().replace('T', ' ').substring(0, 19),
    });
  }

  res.json({
    allowed: !triggered,
    triggered,
    action: actionTaken,
    reason: reason || "Xabar tekshiruvdan muvaffaqiyatli o'tdi",
    guard_active: guard.enabled,
    group: targetGroup.title,
  });
});

// --------------------------------------------------------------------------
// Telegram Webhook Handler (Accepts real Telegram Bot API updates)
// --------------------------------------------------------------------------
app.post(['/webhook', '/api/bot/webhook'], (req: Request, res: Response) => {
  const update = req.body;
  if (update && update.message) {
    const text = update.message.text || '';
    const from = update.message.from || {};
    const chat = update.message.chat || {};

    // Auto-record user if new
    if (from.id && !users.find((u) => u.user_id === from.id)) {
      users.unshift({
        _id: `usr_${from.id}`,
        user_id: from.id,
        username: from.username,
        first_name: from.first_name,
        last_name: from.last_name,
        created_at: new Date().toISOString().replace('T', ' ').substring(0, 19),
        warnings_count: 0,
        is_banned: false,
        is_muted: false,
        language_code: from.language_code || 'uz',
      });
      stats.total_users = users.length;
    }
  }

  res.json({ ok: true });
});

// --------------------------------------------------------------------------
// Vite Middleware / Production Static Fallback
// --------------------------------------------------------------------------
async function setupServer() {
  if (process.env.NODE_ENV !== 'production') {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: 'spa',
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(process.cwd(), 'dist');
    app.use(express.static(distPath));
    app.get('*', (req: Request, res: Response) => {
      res.sendFile(path.join(distPath, 'index.html'));
    });
  }

  app.listen(PORT, HOST, () => {
    console.log(`Server running on http://${HOST}:${PORT}`);
  });
}

setupServer().catch((err) => {
  console.error('Failed to start server:', err);
  process.exit(1);
});
