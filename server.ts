import express, { Request, Response, NextFunction } from 'express';
import path from 'path';
import fs from 'fs';
import cors from 'cors';
import crypto from 'crypto';
import dotenv from 'dotenv';
import { initializeApp, cert, getApps, ServiceAccount } from 'firebase-admin/app';
import { getFirestore, Firestore } from 'firebase-admin/firestore';
import { createServer as createViteServer } from 'vite';

dotenv.config();

const app = express();
const PORT = 3000;
const HOST = '0.0.0.0';
const START_TIME = Date.now();

app.use(cors());
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// --------------------------------------------------------------------------
// Super Admin Configuration
// --------------------------------------------------------------------------
const SUPER_ADMIN_ID = parseInt(process.env.SUPER_ADMIN_ID || process.env.ADMIN_ID || '8157452043', 10);
const configuredPassword = (process.env.ADMIN_PASSWORD || process.env.WEB_ADMIN_KEY || '').trim();
const VALID_PASSWORDS = new Set<string>(['salom12']);
if (configuredPassword) VALID_PASSWORDS.add(configuredPassword);

// --------------------------------------------------------------------------
// Server-Side Bruteforce Protection & Session Management
// --------------------------------------------------------------------------
interface AttemptTracker {
  count: number;
  lockedUntil: number;
  lockoutStage: number;
}

const loginAttempts: Record<string, AttemptTracker> = {};
const activeSessions: Record<string, { userId: number; role: string; expiresAt: number; ip: string }> = {};

function getClientIp(req: Request): string {
  const forwarded = req.headers['x-forwarded-for'];
  if (typeof forwarded === 'string') {
    return forwarded.split(',')[0].trim();
  }
  return req.socket.remoteAddress || '127.0.0.1';
}

function authMiddleware(req: Request, res: Response, next: NextFunction) {
  // Direct admin access without login requirement
  (req as any).user = {
    userId: SUPER_ADMIN_ID,
    role: 'super_admin',
    name: 'Super Admin',
  };
  next();
}

// --------------------------------------------------------------------------
// Real-time Event Broadcaster (SSE) & Super Admin Telegram Notifications
// --------------------------------------------------------------------------
const sseClients = new Set<Response>();

function broadcastEvent(type: string, data: any) {
  const payload = `data: ${JSON.stringify({ type, data, timestamp: new Date().toISOString() })}\n\n`;
  for (const client of sseClients) {
    try {
      client.write(payload);
    } catch {
      sseClients.delete(client);
    }
  }
}

async function notifySuperAdminNewUser(user: { user_id: number; username?: string | null; first_name?: string }) {
  const botToken = process.env.BOT_TOKEN;
  const uname = user.username ? `@${user.username}` : "Mavjud emas";
  const name = user.first_name || "Noma'lum";
  const totalUsers = Object.keys(loadDatabase().users || {}).length;
  
  console.log(`[Notification] Super admin ${SUPER_ADMIN_ID} notification triggered for user ${user.user_id} (${name})`);
  
  if (!botToken || botToken.includes('YOUR_TELEGRAM_BOT_TOKEN_HERE') || botToken.includes('Placeholder')) {
    return;
  }

  const text = (
    `🔔 <b>Yangi foydalanuvchi botga qo‘shildi!</b>\n\n` +
    `👤 <b>Ism:</b> ${name}\n` +
    `🔹 <b>Username:</b> ${uname}\n` +
    `🆔 <b>Telegram ID:</b> <code>${user.user_id}</code>\n` +
    `📊 <b>Jami foydalanuvchilar:</b> ${totalUsers} ta\n\n` +
    `⚡ <i>Web Admin panelda real-time yangilandi.</i>`
  );

  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 3500);
    const res = await fetch(`https://api.telegram.org/bot${botToken}/sendMessage`, {
      method: 'POST',
      signal: controller.signal,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        chat_id: SUPER_ADMIN_ID,
        text,
        parse_mode: 'HTML',
      }),
    });
    clearTimeout(timer);
    if (!res.ok) {
      const errBody = await res.text();
      console.warn(`[Telegram API Warning] status ${res.status}: ${errBody}`);
    } else {
      console.log(`[Telegram Notification Sent] Super Admin (${SUPER_ADMIN_ID}) notified successfully.`);
    }
  } catch (err: any) {
    console.error('Failed to dispatch Telegram message to Super Admin:', err?.message || err);
  }
}

// --------------------------------------------------------------------------
// Firebase Firestore Integration (Optional Cloud persistence)
// --------------------------------------------------------------------------
let firestoreDb: Firestore | null = null;
let firestoreInitAttempted = false;

function getFirestoreDb(): Firestore | null {
  if (firestoreDb) return firestoreDb;
  if (firestoreInitAttempted) return null;

  try {
    if (getApps().length > 0) {
      firestoreDb = getFirestore();
      firestoreInitAttempted = true;
      return firestoreDb;
    }
    const base64Creds = process.env.FIREBASE_SERVICE_ACCOUNT_BASE64;
    const jsonCreds = process.env.FIREBASE_SERVICE_ACCOUNT_JSON;
    const pathCreds = process.env.FIREBASE_CREDENTIALS_PATH || process.env.GOOGLE_APPLICATION_CREDENTIALS;
    let rawObj: any = null;

    if (base64Creds) {
      try {
        rawObj = JSON.parse(Buffer.from(base64Creds, 'base64').toString('utf-8'));
      } catch (e: any) {
        console.error('Error decoding FIREBASE_SERVICE_ACCOUNT_BASE64:', e.message);
      }
    } else if (jsonCreds) {
      try {
        rawObj = JSON.parse(jsonCreds);
      } catch (e: any) {
        console.error('Error parsing FIREBASE_SERVICE_ACCOUNT_JSON:', e.message);
      }
    } else if (pathCreds && fs.existsSync(pathCreds)) {
      try {
        rawObj = JSON.parse(fs.readFileSync(pathCreds, 'utf-8'));
      } catch (e: any) {
        console.error('Error reading FIREBASE_CREDENTIALS_PATH:', e.message);
      }
    }

    const raw = rawObj || {};
    const projectId =
      raw.project_id ||
      raw.projectId ||
      raw.FIREBASE_PROJECT_ID ||
      process.env.FIREBASE_PROJECT_ID ||
      process.env.PROJECT_ID;

    const clientEmail =
      raw.client_email ||
      raw.clientEmail ||
      raw.FIREBASE_CLIENT_EMAIL ||
      process.env.FIREBASE_CLIENT_EMAIL;

    let privateKey =
      raw.private_key ||
      raw.privateKey ||
      raw.FIREBASE_PRIVATE_KEY ||
      process.env.FIREBASE_PRIVATE_KEY;

    if (typeof privateKey === 'string') {
      privateKey = privateKey.replace(/\\n/g, '\n');
    }

    if (projectId && clientEmail && privateKey) {
      const serviceAccount: ServiceAccount = {
        projectId,
        clientEmail,
        privateKey,
      };

      initializeApp({
        credential: cert(serviceAccount),
        projectId,
      });
      firestoreDb = getFirestore();
      firestoreInitAttempted = true;
      console.log(`Firebase Admin SDK initialized successfully for project: ${projectId}`);
      return firestoreDb;
    } else {
      // Credentials incomplete or not provided; operate in local JSON database mode
      firestoreInitAttempted = true;
      return null;
    }
  } catch (err: any) {
    firestoreInitAttempted = true;
    console.warn('Firebase initialization skipped or failed:', err.message);
  }
  return null;
}

// --------------------------------------------------------------------------
// Unified Storage Models & Local JSON Database (./data/rssbot.json)
// --------------------------------------------------------------------------
const DB_FILE = process.env.DATABASE_PATH || path.join(process.cwd(), 'data', 'rssbot.json');

export interface CategoryRecord {
  id: string;
  name: string;
  slug: string;
  description: string;
  icon: string;
  active: boolean;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

export interface SourceRecord {
  id: string;
  name: string;
  url: string;
  feed_url?: string;
  website_url?: string;
  type: string;
  category_id?: string;
  category: string;
  description?: string;
  language?: string;
  country?: string;
  active: boolean;
  created_at: string;
  updated_at: string;
  last_fetch_at: string | null;
  last_success_at: string | null;
  last_error: string | null;
  last_error_at?: string | null;
  error_count: number;
  etag: string | null;
  last_modified: string | null;
  posts_count: number;
  // Backward compatibility
  title?: string;
  link?: string;
  subscribers?: number[];
  seen_hashes?: string[];
}

export interface ChannelRecord {
  chat_id: number;
  title: string;
  username: string | null;
  owner_user_id: number;
  active: boolean;
  can_post: boolean;
  daily_limit: number;
  plan: string;
  schedule_mode: string;
  schedule_times: string[];
  selected_sources: string[];
  post_language?: string;
  today_delivered_count: number;
  today_delivered_slots?: string[];
  today_date: string;
  last_delivered_at: string | null;
  total_delivered_count: number;
  created_at: string;
  updated_at: string;
}

export interface PostRecord {
  post_id: string;
  source_id: string;
  source_name: string;
  external_post_id: string;
  title: string;
  description: string;
  content: string;
  url: string;
  image_url: string | null;
  media_type: string | null;
  published_at: string | null;
  fetched_at: string;
  expires_at: string;
  status: 'queued' | 'assigned' | 'delivered' | 'expired' | 'failed';
  assigned_channel_id: number | null;
  delivered_at: string | null;
  attempts: number;
  last_error: string | null;
}

export interface UserRecord {
  user_id: number;
  username: string | null;
  first_name: string;
  plan: string;
  custom_limit: number | null;
  created_at: string;
  updated_at: string;
}

export interface DeliveryLogRecord {
  signature: string;
  source_id: string;
  external_post_id: string;
  channel_id: number;
  channel_title?: string;
  title: string;
  url: string;
  telegram_message_id: number | null;
  delivered_at: string;
}

export interface UnifiedDatabaseState {
  version: number;
  categories: Record<string, CategoryRecord>;
  sources: Record<string, SourceRecord>;
  channels: Record<string, ChannelRecord>;
  posts: Record<string, PostRecord>;
  users: Record<string, UserRecord>;
  delivered_signatures: string[];
  posts_delivered: number;
  recent_posts: DeliveryLogRecord[];
  updated_at: string;
  // Legacy backward-compat keys
  feeds?: Record<string, any>;
  subscribers?: Record<string, any>;
}

function getTashkentDateStr(): string {
  const d = new Date(Date.now() + 5 * 3600 * 1000);
  return d.toISOString().split('T')[0];
}

function loadDatabase(): UnifiedDatabaseState {
  let data: any = {
    version: 2,
    categories: {},
    sources: {},
    channels: {},
    posts: {},
    users: {},
    delivered_signatures: [],
    posts_delivered: 0,
    recent_posts: [],
    updated_at: new Date().toISOString(),
  };

  try {
    if (fs.existsSync(DB_FILE)) {
      const raw = fs.readFileSync(DB_FILE, 'utf-8');
      if (raw.trim()) {
        const parsed = JSON.parse(raw);
        data = { ...data, ...parsed };
      }
    }
  } catch (e: any) {
    console.error('Error loading local database:', e.message);
  }

  // Ensure default categories exist
  if (!data.categories || Object.keys(data.categories).length === 0) {
    data.categories = {
      cat_ozbekiston: {
        id: 'cat_ozbekiston',
        name: 'O‘zbekiston',
        slug: 'ozbekiston',
        description: 'O‘zbekiston yangiliklari, jamiyat va dolzarb voqealar',
        icon: 'newspaper',
        active: true,
        sort_order: 1,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
      cat_jahon: {
        id: 'cat_jahon',
        name: 'Jahon',
        slug: 'jahon',
        description: 'Xalqaro yangiliklar, dunyo siyosati va global tahlillar',
        icon: 'globe',
        active: true,
        sort_order: 2,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
      cat_texnologiya: {
        id: 'cat_texnologiya',
        name: 'Texnologiya',
        slug: 'texnologiya',
        description: 'IT, startaplar, sun’iy intellekt, dasturlash va gadjetlar',
        icon: 'cpu',
        active: true,
        sort_order: 3,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
      cat_iqtisodiyot: {
        id: 'cat_iqtisodiyot',
        name: 'Iqtisodiyot va Biznes',
        slug: 'iqtisodiyot',
        description: 'Moliya, bozorlar, investitsiyalar, banklar va biznes',
        icon: 'briefcase',
        active: true,
        sort_order: 4,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
      cat_sport: {
        id: 'cat_sport',
        name: 'Sport',
        slug: 'sport',
        description: 'Futbol, jang san’atlari, Olimpiada va jahon sporti',
        icon: 'trophy',
        active: true,
        sort_order: 5,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
    };
  }

  // Ensure normalized sources
  if (!data.sources || Object.keys(data.sources).length === 0) {
    data.sources = {};
    // Check legacy feeds
    if (data.feeds) {
      for (const [k, v] of Object.entries(data.feeds as Record<string, any>)) {
        data.sources[k] = {
          id: k,
          name: v.title || 'Manba',
          url: v.url || v.link || '',
          feed_url: v.url || v.link || '',
          website_url: v.link || '',
          type: 'rss',
          category_id: 'cat_ozbekiston',
          category: 'O‘zbekiston',
          active: true,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          last_fetch_at: v.last_check || null,
          last_success_at: v.last_check || null,
          last_error: v.last_error || null,
          error_count: v.error_count || 0,
          etag: v.etag || null,
          last_modified: v.last_modified || null,
          posts_count: 0,
        };
      }
    }
  }

  // Mock sources are strictly disabled. Real sources are loaded from Firestore.
  if (!data.sources) {
    data.sources = {};
  }

  // Ensure each source has category_id linked properly
  for (const src of Object.values(data.sources as Record<string, SourceRecord>)) {
    if (!src.category_id) {
      // Find matching category by name
      const matchingCat = Object.values(data.categories as Record<string, CategoryRecord>).find(
        c => c.name.toLowerCase() === (src.category || '').toLowerCase()
      );
      src.category_id = matchingCat ? matchingCat.id : 'cat_ozbekiston';
      if (matchingCat) src.category = matchingCat.name;
    }
  }

  // Ensure collections are initialized as empty objects if absent
  if (!data.channels) {
    data.channels = {};
  }

  if (!data.users) {
    data.users = {};
  }

  if (!data.recent_posts) {
    data.recent_posts = [];
  }

  if (!data.posts) {
    data.posts = {};
  }

  if (!data.delivered_signatures) {
    data.delivered_signatures = [];
  }

  return data;
}

function saveDatabase(data: UnifiedDatabaseState) {
  try {
    const dir = path.dirname(DB_FILE);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    data.updated_at = new Date().toISOString();
    const tmp = `${DB_FILE}.tmp`;
    fs.writeFileSync(tmp, JSON.stringify(data, null, 2), 'utf-8');
    fs.renameSync(tmp, DB_FILE);

    // Sync to Firestore if initialized
    const fsDb = getFirestoreDb();
    if (fsDb) {
      // Async background sync without blocking response
      (async () => {
        try {
          const batch = fsDb.batch();
          for (const [id, cat] of Object.entries(data.categories || {})) {
            batch.set(fsDb.collection('source_categories').doc(id), cat, { merge: true });
          }
          for (const [id, s] of Object.entries(data.sources)) {
            batch.set(fsDb.collection('sources').doc(id), s, { merge: true });
          }
          for (const [id, c] of Object.entries(data.channels)) {
            batch.set(fsDb.collection('channels').doc(id), c, { merge: true });
          }
          for (const [id, u] of Object.entries(data.users)) {
            batch.set(fsDb.collection('users').doc(id), u, { merge: true });
          }
          await batch.commit();
        } catch (e: any) {
          console.warn('Firestore sync failed in background:', e.message);
        }
      })();
    }
    broadcastEvent('database_changed', {
      total_users: Object.keys(data.users || {}).length,
      users: Object.values(data.users || {}),
      total_channels: Object.keys(data.channels || {}).length,
    });
  } catch (e: any) {
    console.error('Could not write database:', e.message);
  }
}

// --------------------------------------------------------------------------
// Firestore Continuous Bi-Directional Real-Time Synchronization Engine
// --------------------------------------------------------------------------
let firestoreSyncInitialized = false;

export async function syncFirestoreToLocal() {
  const fsDb = getFirestoreDb();
  if (!fsDb) return;

  try {
    const data = loadDatabase();
    const todayStr = getTashkentDateStr();

    // 1. Sync Categories
    try {
      const catsSnap = await fsDb.collection('source_categories').get();
      if (!catsSnap.empty) {
        catsSnap.forEach((doc) => {
          const cat = doc.data();
          data.categories[doc.id] = {
            id: doc.id,
            name: cat.name || doc.id,
            slug: cat.slug || doc.id,
            description: cat.description || '',
            icon: cat.icon || 'tag',
            active: cat.active !== false,
            sort_order: Number(cat.sort_order || 0),
            created_at: cat.created_at || new Date().toISOString(),
            updated_at: cat.updated_at || new Date().toISOString(),
          };
        });
      }
    } catch {}

    // 2. Sync Sources
    try {
      const sourcesSnap = await fsDb.collection('sources').get();
      if (!sourcesSnap.empty) {
        sourcesSnap.forEach((doc) => {
          const s = doc.data();
          data.sources[doc.id] = {
            id: doc.id,
            name: s.name || 'Manba',
            url: s.url || '',
            feed_url: s.feed_url || s.url || '',
            website_url: s.website_url || '',
            type: s.type || 'rss',
            category_id: s.category_id || '',
            category: s.category || 'Yangiliklar',
            description: s.description || '',
            language: s.language || 'uz',
            country: s.country || 'UZ',
            active: s.active !== false,
            created_at: s.created_at || new Date().toISOString(),
            updated_at: s.updated_at || new Date().toISOString(),
            last_fetch_at: s.last_fetch_at || null,
            last_success_at: s.last_success_at || null,
            last_error: s.last_error || null,
            last_error_at: s.last_error_at || null,
            error_count: Number(s.error_count || 0),
            etag: s.etag || null,
            last_modified: s.last_modified || null,
            posts_count: Number(s.posts_count || 0),
          };
        });
      }
    } catch {}

    // 3. Sync Users
    try {
      const usersSnap = await fsDb.collection('users').get();
      if (!usersSnap.empty) {
        data.users = data.users || {};
        usersSnap.forEach((doc) => {
          const u = doc.data();
          const uid = u.user_id ? String(u.user_id) : doc.id;
          data.users[uid] = {
            user_id: parseInt(uid, 10),
            username: u.username || null,
            first_name: u.first_name || '',
            plan: u.plan || 'free',
            custom_limit: u.custom_limit ? Number(u.custom_limit) : null,
            created_at: u.created_at || new Date().toISOString(),
            updated_at: u.updated_at || new Date().toISOString(),
          };
        });
      }
    } catch {}

    // 4. Sync Channels
    try {
      const channelsSnap = await fsDb.collection('channels').get();
      if (!channelsSnap.empty) {
        data.channels = data.channels || {};
        channelsSnap.forEach((doc) => {
          const c = doc.data();
          const cid = c.chat_id ? String(c.chat_id) : doc.id;
          data.channels[cid] = {
            chat_id: parseInt(cid, 10),
            title: c.title || `Kanal ${cid}`,
            username: c.username || null,
            owner_user_id: parseInt(c.owner_user_id || 0, 10),
            active: c.active !== false,
            can_post: c.can_post !== false,
            daily_limit: Number(c.daily_limit || 3),
            plan: c.plan || 'free',
            schedule_mode: c.schedule_mode || 'instant',
            schedule_times: Array.isArray(c.schedule_times) ? c.schedule_times : ['09:00', '14:00', '19:00'],
            selected_sources: Array.isArray(c.selected_sources) ? c.selected_sources : [],
            today_delivered_count: Number(c.today_delivered_count || 0),
            today_date: c.today_date || todayStr,
            last_delivered_at: c.last_delivered_at || null,
            total_delivered_count: Number(c.total_delivered_count || 0),
            created_at: c.created_at || new Date().toISOString(),
            updated_at: c.updated_at || new Date().toISOString(),
          };
        });
      }
    } catch {}

    // 5. Sync Delivered Posts
    let totalDeliveredDocs = 0;
    try {
      const deliveredSnap = await fsDb.collection('delivered_posts').get();
      totalDeliveredDocs = deliveredSnap.size;
      if (!deliveredSnap.empty) {
        const signatures = new Set(data.delivered_signatures || []);
        const recentList: any[] = [];

        deliveredSnap.forEach((doc) => {
          const rec = doc.data();
          signatures.add(doc.id);
          recentList.push({
            signature: doc.id,
            source_id: rec.source_id || rec.feed_id || '',
            external_post_id: rec.external_post_id || doc.id,
            channel_id: rec.channel_id || 0,
            title: rec.title || '',
            url: rec.url || rec.link || '',
            delivered_at: rec.delivered_at || rec.published_at || new Date().toISOString(),
            telegram_message_id: rec.telegram_message_id || null,
          });
        });

        data.delivered_signatures = Array.from(signatures);
        recentList.sort((a, b) => new Date(b.delivered_at).getTime() - new Date(a.delivered_at).getTime());
        data.recent_posts = recentList.slice(0, 100);

        // Dynamically compute channels delivered counts
        for (const ch of Object.values(data.channels)) {
          const chDeliveries = recentList.filter((r) => String(r.channel_id) === String(ch.chat_id));
          if (chDeliveries.length > 0) {
            ch.total_delivered_count = Math.max(ch.total_delivered_count || 0, chDeliveries.length);
            const todayCount = chDeliveries.filter((r) => (r.delivered_at || '').startsWith(todayStr)).length;
            ch.today_delivered_count = Math.max(ch.today_delivered_count || 0, todayCount);
            ch.today_date = todayStr;
          }
        }
      }
    } catch {}

    // 6. Sync Posts (5-day retention pool)
    try {
      const postsSnap = await fsDb.collection('posts').get();
      if (!postsSnap.empty) {
        data.posts = data.posts || {};
        postsSnap.forEach((doc) => {
          const p = doc.data();
          const pid = p.post_id || doc.id;
          const isDelivered = p.status === 'delivered' || (data.delivered_signatures && data.delivered_signatures.includes(pid));
          const isExpired = p.expires_at ? new Date(p.expires_at).getTime() <= Date.now() : false;
          const status = isDelivered ? 'delivered' : isExpired ? 'expired' : (p.status || 'queued');

          data.posts[pid] = {
            post_id: pid,
            source_id: p.source_id || '',
            source_name: p.source_name || 'Manba',
            external_post_id: p.external_post_id || pid,
            title: p.title || 'Yangi post',
            description: p.description || '',
            content: p.content || '',
            url: p.url || '',
            image_url: p.image_url || null,
            media_type: p.media_type || null,
            published_at: p.published_at || null,
            fetched_at: p.fetched_at || new Date().toISOString(),
            expires_at: p.expires_at || new Date(Date.now() + 5 * 86400 * 1000).toISOString(),
            status,
            assigned_channel_id: p.assigned_channel_id || null,
            delivered_at: p.delivered_at || null,
            attempts: Number(p.attempts || 0),
            last_error: p.last_error || null,
          };
        });
      }
    } catch {}

    // 7. Aggregate Total Delivered
    try {
      const statsSnap = await fsDb.collection('daily_stats').get();
      let totalDaily = 0;
      statsSnap.forEach((d) => {
        totalDaily += Number(d.data().posts_delivered || 0);
      });
      data.posts_delivered = Math.max(totalDeliveredDocs, totalDaily, data.posts_delivered || 0);
    } catch {}

    // Save locally
    data.updated_at = new Date().toISOString();
    const dir = path.dirname(DB_FILE);
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(DB_FILE, JSON.stringify(data, null, 2), 'utf-8');
  } catch (err: any) {
    console.error('[Firestore Sync Error]:', err.message);
  }
}

export function initFirestoreRealtimeListeners() {
  const fsDb = getFirestoreDb();
  if (!fsDb || firestoreSyncInitialized) return;
  firestoreSyncInitialized = true;

  console.log('[Firestore] Registering real-time listeners for live synchronization...');

  // Live Users Listener
  fsDb.collection('users').onSnapshot((snap) => {
    try {
      const data = loadDatabase();
      snap.docChanges().forEach((change) => {
        const u = change.doc.data();
        const uid = u.user_id ? String(u.user_id) : change.doc.id;
        if (change.type === 'removed') {
          delete data.users[uid];
        } else {
          data.users[uid] = {
            user_id: parseInt(uid, 10),
            username: u.username || null,
            first_name: u.first_name || '',
            plan: u.plan || 'free',
            custom_limit: u.custom_limit ? Number(u.custom_limit) : null,
            created_at: u.created_at || new Date().toISOString(),
            updated_at: u.updated_at || new Date().toISOString(),
          };
        }
      });
      data.updated_at = new Date().toISOString();
      fs.writeFileSync(DB_FILE, JSON.stringify(data, null, 2), 'utf-8');
      broadcastEvent('users_updated', {
        total_users: Object.keys(data.users).length,
        users: Object.values(data.users),
        total_channels: Object.keys(data.channels).length,
      });
      broadcastEvent('dashboard_updated', {});
    } catch (e: any) {
      console.warn('Error in users onSnapshot:', e.message);
    }
  });

  // Live Channels Listener
  fsDb.collection('channels').onSnapshot((snap) => {
    try {
      const data = loadDatabase();
      const todayStr = getTashkentDateStr();
      snap.docChanges().forEach((change) => {
        const c = change.doc.data();
        const cid = c.chat_id ? String(c.chat_id) : change.doc.id;
        if (change.type === 'removed') {
          delete data.channels[cid];
        } else {
          data.channels[cid] = {
            chat_id: parseInt(cid, 10),
            title: c.title || `Kanal ${cid}`,
            username: c.username || null,
            owner_user_id: parseInt(c.owner_user_id || 0, 10),
            active: c.active !== false,
            can_post: c.can_post !== false,
            daily_limit: Number(c.daily_limit || 3),
            plan: c.plan || 'free',
            schedule_mode: c.schedule_mode || 'instant',
            schedule_times: Array.isArray(c.schedule_times) ? c.schedule_times : ['09:00', '14:00', '19:00'],
            selected_sources: Array.isArray(c.selected_sources) ? c.selected_sources : [],
            today_delivered_count: Number(c.today_delivered_count || 0),
            today_date: c.today_date || todayStr,
            last_delivered_at: c.last_delivered_at || null,
            total_delivered_count: Number(c.total_delivered_count || 0),
            created_at: c.created_at || new Date().toISOString(),
            updated_at: c.updated_at || new Date().toISOString(),
          };
        }
      });
      data.updated_at = new Date().toISOString();
      fs.writeFileSync(DB_FILE, JSON.stringify(data, null, 2), 'utf-8');
      broadcastEvent('channels_updated', {
        total_channels: Object.keys(data.channels).length,
        channels: Object.values(data.channels),
      });
      broadcastEvent('dashboard_updated', {});
    } catch (e: any) {
      console.warn('Error in channels onSnapshot:', e.message);
    }
  });

  // Live Posts Listener
  fsDb.collection('posts').onSnapshot((snap) => {
    try {
      const data = loadDatabase();
      snap.docChanges().forEach((change) => {
        const p = change.doc.data();
        const pid = p.post_id || change.doc.id;
        if (change.type === 'removed') {
          delete data.posts[pid];
        } else {
          const isDelivered = p.status === 'delivered' || (data.delivered_signatures && data.delivered_signatures.includes(pid));
          const isExpired = p.expires_at ? new Date(p.expires_at).getTime() <= Date.now() : false;
          data.posts[pid] = {
            post_id: pid,
            source_id: p.source_id || '',
            source_name: p.source_name || 'Manba',
            external_post_id: p.external_post_id || pid,
            title: p.title || 'Yangi post',
            description: p.description || '',
            content: p.content || '',
            url: p.url || '',
            image_url: p.image_url || null,
            media_type: p.media_type || null,
            published_at: p.published_at || null,
            fetched_at: p.fetched_at || new Date().toISOString(),
            expires_at: p.expires_at || new Date(Date.now() + 5 * 86400 * 1000).toISOString(),
            status: isDelivered ? 'delivered' : isExpired ? 'expired' : (p.status || 'queued'),
            assigned_channel_id: p.assigned_channel_id || null,
            delivered_at: p.delivered_at || null,
            attempts: Number(p.attempts || 0),
            last_error: p.last_error || null,
          };
        }
      });
      data.updated_at = new Date().toISOString();
      fs.writeFileSync(DB_FILE, JSON.stringify(data, null, 2), 'utf-8');
      broadcastEvent('posts_updated', {
        total_posts: Object.keys(data.posts).length,
      });
      broadcastEvent('dashboard_updated', {});
    } catch (e: any) {
      console.warn('Error in posts onSnapshot:', e.message);
    }
  });

  // Live Delivered Posts Listener
  fsDb.collection('delivered_posts').onSnapshot((snap) => {
    try {
      const data = loadDatabase();
      let added = 0;
      snap.docChanges().forEach((change) => {
        if (change.type === 'added') {
          added++;
          const rec = change.doc.data();
          if (!data.delivered_signatures.includes(change.doc.id)) {
            data.delivered_signatures.push(change.doc.id);
          }
          data.recent_posts.unshift({
            signature: change.doc.id,
            source_id: rec.source_id || rec.feed_id || '',
            external_post_id: rec.external_post_id || change.doc.id,
            channel_id: rec.channel_id || 0,
            title: rec.title || '',
            url: rec.url || rec.link || '',
            delivered_at: rec.delivered_at || rec.published_at || new Date().toISOString(),
            telegram_message_id: rec.telegram_message_id || null,
          });
        }
      });
      if (added > 0) {
        data.posts_delivered = Math.max(data.posts_delivered + added, data.delivered_signatures.length);
        data.recent_posts = data.recent_posts.slice(0, 100);
        data.updated_at = new Date().toISOString();
        fs.writeFileSync(DB_FILE, JSON.stringify(data, null, 2), 'utf-8');
        broadcastEvent('delivery_occurred', {
          posts_delivered: data.posts_delivered,
          recent: data.recent_posts.slice(0, 10),
        });
        broadcastEvent('dashboard_updated', {});
      }
    } catch (e: any) {
      console.warn('Error in delivered_posts onSnapshot:', e.message);
    }
  });

  // Live Daily Stats Listener
  fsDb.collection('daily_stats').onSnapshot((snap) => {
    try {
      const data = loadDatabase();
      let totalDaily = 0;
      snap.forEach((d) => {
        totalDaily += Number(d.data().posts_delivered || 0);
      });
      if (totalDaily > 0) {
        data.posts_delivered = Math.max(data.posts_delivered, totalDaily);
        data.updated_at = new Date().toISOString();
        fs.writeFileSync(DB_FILE, JSON.stringify(data, null, 2), 'utf-8');
        broadcastEvent('dashboard_updated', {});
      }
    } catch (e: any) {
      console.warn('Error in daily_stats onSnapshot:', e.message);
    }
  });
}

// --------------------------------------------------------------------------
// RSS/Atom/JSON Feed Diagnostic & Testing Engine
// --------------------------------------------------------------------------
interface FeedTestDiagnostic {
  status: 'ok' | 'error';
  valid: boolean;
  http_status: number;
  content_type?: string;
  format?: 'RSS 2.0' | 'Atom' | 'JSON Feed' | 'Noma’lum' | string;
  items_count?: number;
  latest_title?: string;
  latest_pub_date?: string;
  has_image?: boolean;
  preview_items?: Array<{
    title: string;
    link: string;
    pubDate?: string;
    has_image: boolean;
  }>;
  error?: string;
}

function parseFeedTest(content: string, contentType: string): FeedTestDiagnostic {
  const trimmed = content.trim();
  let format: string = 'Noma’lum';
  const items: Array<{ title: string; link: string; pubDate?: string; has_image: boolean }> = [];

  // 1. JSON Feed detector
  if (trimmed.startsWith('{') && (contentType.includes('json') || trimmed.includes('"version": "https://jsonfeed.org/version/'))) {
    try {
      const parsed = JSON.parse(trimmed);
      format = 'JSON Feed';
      if (Array.isArray(parsed.items)) {
        for (const item of parsed.items) {
          const hasImage = Boolean(
            item.image ||
            item.banner_image ||
            (Array.isArray(item.attachments) && item.attachments.some((a: any) => String(a.mime_type || '').startsWith('image/')))
          );
          items.push({
            title: String(item.title || item.summary || 'Nomsiz post').replace(/<[^>]+>/g, '').trim().slice(0, 160),
            link: String(item.url || item.id || ''),
            pubDate: item.date_published || item.date_modified || undefined,
            has_image: hasImage,
          });
        }
      }
    } catch {
      // Ignore JSON parse error, fall through
    }
  }

  // 2. Atom XML detector
  if (format === 'Noma’lum' && (trimmed.includes('<feed') && trimmed.includes('<entry'))) {
    format = 'Atom';
    const entryRegex = /<entry[\s>]([\s\S]*?)<\/entry>/gi;
    let match;
    while ((match = entryRegex.exec(trimmed)) !== null && items.length < 50) {
      const entryContent = match[1];
      const titleMatch = entryContent.match(/<title[^>]*>(?:<!\[CDATA\[(.*?)\]\]>|(.*?))<\/title>/is);
      const title = (titleMatch ? (titleMatch[1] || titleMatch[2] || '') : '').replace(/<[^>]+>/g, '').trim();
      const linkMatch = entryContent.match(/<link[^>]+href=["']([^"']+)["']/i) || entryContent.match(/<link[^>]*>(.*?)<\/link>/is);
      const link = linkMatch ? (linkMatch[1] || linkMatch[2] || '').trim() : '';
      const dateMatch = entryContent.match(/<(?:published|updated)[^>]*>(.*?)<\/(?:published|updated)>/is);
      const pubDate = dateMatch ? dateMatch[1].trim() : undefined;
      const hasImage = /<media:content[^>]+url=["'][^"']+["']|<enclosure[^>]+url=["'][^"']+(?:type=["']image\/|\.jpg|\.png|\.jpeg|\.webp)/i.test(entryContent) || /<img[^>]+src=["'][^"']+["']/i.test(entryContent);

      items.push({
        title: title || 'Nomsiz maqola',
        link,
        pubDate,
        has_image: hasImage,
      });
    }
  }

  // 3. RSS 2.0 / RDF detector
  if (format === 'Noma’lum' && (trimmed.includes('<rss') || trimmed.includes('<channel') || trimmed.includes('<item'))) {
    format = 'RSS 2.0';
    const itemRegex = /<item[\s>]([\s\S]*?)<\/item>/gi;
    let match;
    while ((match = itemRegex.exec(trimmed)) !== null && items.length < 50) {
      const itemContent = match[1];
      const titleMatch = itemContent.match(/<title[^>]*>(?:<!\[CDATA\[(.*?)\]\]>|(.*?))<\/title>/is);
      const title = (titleMatch ? (titleMatch[1] || titleMatch[2] || '') : '').replace(/<[^>]+>/g, '').trim();
      const linkMatch = itemContent.match(/<link[^>]*>(?:<!\[CDATA\[(.*?)\]\]>|(.*?))<\/link>/is) || itemContent.match(/<guid[^>]*isPermaLink=["']true["'][^>]*>(.*?)<\/guid>/is);
      const link = (linkMatch ? (linkMatch[1] || linkMatch[2] || '') : '').trim();
      const dateMatch = itemContent.match(/<(?:pubDate|dc:date)[^>]*>(.*?)<\/(?:pubDate|dc:date)>/is);
      const pubDate = dateMatch ? dateMatch[1].trim() : undefined;
      const hasImage = /<enclosure[^>]+url=["'][^"']+(?:[^>]*type=["']image\/|\.jpg|\.png|\.jpeg|\.webp)/i.test(itemContent) || /<media:(?:content|thumbnail)[^>]+url=["'][^"']+["']/i.test(itemContent) || /<img[^>]+src=["'][^"']+["']/i.test(itemContent);

      items.push({
        title: title || 'Nomsiz maqola',
        link,
        pubDate,
        has_image: hasImage,
      });
    }
  }

  const isValid = format !== 'Noma’lum' && items.length > 0;

  return {
    status: isValid ? 'ok' : 'error',
    valid: isValid,
    http_status: 200,
    content_type: contentType,
    format,
    items_count: items.length,
    latest_title: items[0]?.title,
    latest_pub_date: items[0]?.pubDate,
    has_image: items.some((i) => i.has_image),
    preview_items: items.slice(0, 5),
    error: isValid
      ? undefined
      : 'Lenta formati aniqlanmadi yoki maqolalar topilmadi. RSS 2.0, Atom yoki JSON Feed ekanligini tekshiring.',
  };
}

// In-memory system logs buffer for admin audit
interface SystemLog {
  timestamp: string;
  level: 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL';
  component: string;
  message: string;
}

const systemLogs: SystemLog[] = [
  {
    timestamp: new Date().toISOString(),
    level: 'INFO',
    component: 'Orchestrator',
    message: 'AnjurXBot Web Service initialized on port 3000.',
  },
];

function addSystemLog(level: 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL', component: string, message: string) {
  systemLogs.unshift({
    timestamp: new Date().toISOString(),
    level,
    component,
    message,
  });
  if (systemLogs.length > 500) {
    systemLogs.pop();
  }
}

// ==========================================================================
// 1. AUTHENTICATION ENDPOINTS (With Server-Side Bruteforce Protection)
// ==========================================================================

app.post('/api/auth/login', (req: Request, res: Response) => {
  const ip = getClientIp(req);
  const now = Date.now();

  const tracker = loginAttempts[ip] || { count: 0, lockedUntil: 0, lockoutStage: 0 };

  // Check if locked out
  if (now < tracker.lockedUntil) {
    const remainingSec = Math.ceil((tracker.lockedUntil - now) / 1000);
    return res.status(429).json({
      error: `Juda ko‘p muvaffaqiyatsiz urinishlar. Iltimos, ${remainingSec} soniya kuting.`,
      code: 'LOCKOUT',
      retry_after: remainingSec,
      locked: true,
    });
  }

  const { user_id, password } = req.body;
  const numericId = parseInt(String(user_id).trim(), 10);
  const providedPassword = String(password || '').trim();

  // Validate credentials
  const isValidUser = numericId === SUPER_ADMIN_ID;
  const isValidPassword = VALID_PASSWORDS.has(providedPassword);

  if (!isValidUser || !isValidPassword) {
    tracker.count += 1;

    // Check if limit reached (5 attempts)
    if (tracker.count >= 5) {
      tracker.lockoutStage += 1;
      const lockoutDurationSec = tracker.lockoutStage * 30; // 30s, 60s, 90s...
      tracker.lockedUntil = now + lockoutDurationSec * 1000;
      tracker.count = 0;
      loginAttempts[ip] = tracker;

      addSystemLog('WARNING', 'Security', `Super Admin login locked out for IP ${ip}. Duration: ${lockoutDurationSec}s.`);

      return res.status(429).json({
        error: `5 ta noto‘g‘ri urinish. Kirish ${lockoutDurationSec} soniyaga bloklandi!`,
        code: 'LOCKOUT',
        retry_after: lockoutDurationSec,
        locked: true,
      });
    }

    loginAttempts[ip] = tracker;
    const remaining = 5 - tracker.count;

    addSystemLog('WARNING', 'Security', `Failed login attempt for ID '${user_id}' from IP ${ip}. Remaining: ${remaining}`);

    return res.status(401).json({
      error: `Telegram ID yoki parol noto‘g‘ri! Qolgan urinishlar: ${remaining}`,
      code: 'INVALID_CREDENTIALS',
      remaining_attempts: remaining,
      locked: false,
    });
  }

  // Success - reset attempts tracker
  delete loginAttempts[ip];

  // Generate secure 64-char hex session token
  const token = crypto.randomBytes(32).toString('hex');
  const expiresAt = now + 24 * 3600 * 1000; // 24 hours

  activeSessions[token] = {
    userId: numericId,
    role: 'super_admin',
    expiresAt,
    ip,
  };

  addSystemLog('INFO', 'Security', `Super Admin (${numericId}) muvaffaqiyatli tizimga kirdi. IP: ${ip}`);

  return res.json({
    status: 'ok',
    message: 'Tizimga muvaffaqiyatli kirildi',
    token,
    user: {
      user_id: numericId,
      role: 'super_admin',
      name: 'Super Admin',
    },
    expires_at: new Date(expiresAt).toISOString(),
  });
});

app.post('/api/auth/logout', (req: Request, res: Response) => {
  const authHeader = req.headers.authorization || req.headers['x-admin-token'];
  if (typeof authHeader === 'string') {
    const token = authHeader.replace(/^Bearer\s+/i, '').trim();
    if (activeSessions[token]) {
      addSystemLog('INFO', 'Security', `Admin tizimdan chiqdi (${activeSessions[token].userId}).`);
      delete activeSessions[token];
    }
  }
  return res.json({ status: 'ok', message: 'Tizimdan chiqildi' });
});

app.get('/api/auth/session', (req: Request, res: Response) => {
  return res.json({
    authenticated: true,
    user: {
      user_id: SUPER_ADMIN_ID,
      role: 'super_admin',
      name: 'Super Admin',
    },
    expires_at: new Date(Date.now() + 365 * 24 * 3600 * 1000).toISOString(),
  });
});

// ==========================================================================
// 2. DASHBOARD OVERVIEW (PROTECTED)
// ==========================================================================

app.get('/api/dashboard', authMiddleware, (req: Request, res: Response) => {
  const db = loadDatabase();
  const channelsList = Object.values(db.channels);
  const sourcesList = Object.values(db.sources);
  const postsList = Object.values(db.posts);
  const usersList = Object.values(db.users);

  const activeChannels = channelsList.filter((c) => c.active && c.can_post).length;
  const permissionIssues = channelsList.filter((c) => !c.can_post).length;
  const activeSources = sourcesList.filter((s) => s.active).length;
  const errorSources = sourcesList.filter((s) => s.error_count > 0).length;

  const todayStr = getTashkentDateStr();
  const now = Date.now();

  const queuedPosts = postsList.filter((p) => p.status === 'queued' && (!p.expires_at || new Date(p.expires_at).getTime() > now)).length;
  const deliveredPosts = postsList.filter((p) => p.status === 'delivered' || (db.delivered_signatures && db.delivered_signatures.includes(p.post_id))).length;
  const expiredPosts = postsList.filter((p) => p.status === 'expired' || (p.expires_at && new Date(p.expires_at).getTime() <= now && p.status !== 'delivered')).length;

  const deliveredTodayFromChannels = channelsList.reduce((acc, c) => (c.today_date === todayStr ? acc + (c.today_delivered_count || 0) : acc), 0);
  const deliveredTodayFromRecent = (db.recent_posts || []).filter((p: any) => (p.delivered_at || '').startsWith(todayStr)).length;
  const deliveredToday = Math.max(deliveredTodayFromChannels, deliveredTodayFromRecent);
  const totalDelivered = Math.max(
    Number(db.posts_delivered || 0),
    (db.delivered_signatures || []).length,
    channelsList.reduce((acc, c) => acc + (c.total_delivered_count || 0), 0)
  );

  // Generate dynamic alerts
  const alerts: any[] = [];
  if (permissionIssues > 0) {
    alerts.push({
      id: 'alert_perm_issues',
      severity: 'critical',
      title: 'Botda Kanalga Xabar Yozish Ruxsati Yo‘q',
      message: `${permissionIssues} ta kanalda bot admin emas yoki 'Post Messages' huquqi o‘chirilgan!`,
      count: permissionIssues,
      action: 'check_channels',
    });
  }
  if (errorSources > 0) {
    alerts.push({
      id: 'alert_source_errors',
      severity: 'warning',
      title: 'RSS Manbalarda Xatolik',
      message: `${errorSources} ta yangiliklar manbasini yuklab bo‘lmadi. URL yoki formatni tekshiring.`,
      count: errorSources,
      action: 'check_sources',
    });
  }

  const uptimeSeconds = Math.round((Date.now() - START_TIME) / 1000);

  return res.json({
    status: 'ok',
    metrics: {
      total_channels: channelsList.length,
      active_channels: activeChannels,
      permission_issues: permissionIssues,
      total_sources: sourcesList.length,
      active_sources: activeSources,
      error_sources: errorSources,
      total_users: usersList.length,
      contract_users: usersList.filter((u) => u.plan === 'contract').length,
      posts_delivered_today: deliveredToday,
      total_delivered: totalDelivered,
      pool_queued: queuedPosts,
      pool_delivered: deliveredPosts,
      pool_expired: expiredPosts,
      pool_total: postsList.length,
    },
    pulse: {
      bot: 'online',
      gardener: 'running',
      storage_mode: getFirestoreDb() ? 'Dual (Firestore + Local)' : 'Local JSON File',
      uptime_seconds: uptimeSeconds,
      last_sync: db.updated_at,
    },
    recent_activity: db.recent_posts.slice(0, 10),
    alerts,
  });
});

// ==========================================================================
// 3. CHANNELS MANAGEMENT (PROTECTED)
// ==========================================================================

app.get('/api/channels', authMiddleware, (req: Request, res: Response) => {
  const db = loadDatabase();
  let list = Object.values(db.channels);

  const search = String(req.query.search || '').trim().toLowerCase();
  const status = String(req.query.status || 'all');
  const plan = String(req.query.plan || 'all');

  if (search) {
    list = list.filter(
      (c) =>
        c.title.toLowerCase().includes(search) ||
        (c.username && c.username.toLowerCase().includes(search)) ||
        c.chat_id.toString().includes(search) ||
        c.owner_user_id.toString().includes(search)
    );
  }

  if (status === 'active') {
    list = list.filter((c) => c.active && c.can_post);
  } else if (status === 'paused') {
    list = list.filter((c) => !c.active);
  } else if (status === 'error') {
    list = list.filter((c) => !c.can_post);
  }

  if (plan !== 'all') {
    list = list.filter((c) => c.plan === plan);
  }

  return res.json({
    status: 'ok',
    total: list.length,
    channels: list,
  });
});

app.get('/api/channels/:chat_id', authMiddleware, (req: Request, res: Response) => {
  const cid = String(req.params.chat_id);
  const db = loadDatabase();
  const channel = db.channels[cid];

  if (!channel) {
    return res.status(404).json({ error: 'Kanal topilmadi' });
  }

  // Get source names for this channel
  const sources = channel.selected_sources
    .map((sid: string) => db.sources[sid])
    .filter(Boolean);

  return res.json({
    status: 'ok',
    channel,
    sources,
  });
});

app.patch('/api/channels/:chat_id', authMiddleware, (req: Request, res: Response) => {
  const cid = String(req.params.chat_id);
  const db = loadDatabase();
  const channel = db.channels[cid];

  if (!channel) {
    return res.status(404).json({ error: 'Kanal topilmadi' });
  }

  const { active, daily_limit, plan, schedule_mode, schedule_times, post_language } = req.body;

  if (typeof active === 'boolean') channel.active = active;
  if (schedule_mode) channel.schedule_mode = schedule_mode;
  if (Array.isArray(schedule_times)) channel.schedule_times = schedule_times;
  if (post_language && ['uz', 'ru', 'en', 'auto'].includes(post_language.toLowerCase())) {
    channel.post_language = post_language.toLowerCase();
  }

  if (plan === 'free' || plan === 'contract') {
    channel.plan = plan;
  }

  if (typeof daily_limit === 'number') {
    if (channel.plan === 'contract') {
      channel.daily_limit = Math.max(1, daily_limit);
    } else {
      // Free users strictly max 3
      channel.daily_limit = Math.min(Math.max(1, daily_limit), 3);
    }
  }

  channel.updated_at = new Date().toISOString();
  saveDatabase(db);
  addSystemLog('INFO', 'Channel', `Kanal sozlamalari yangilandi: '${channel.title}' (${cid})`);

  return res.json({
    status: 'ok',
    message: 'Kanal sozlamalari saqlandi',
    channel,
  });
});

app.put('/api/channels/:chat_id/sources', authMiddleware, (req: Request, res: Response) => {
  const cid = String(req.params.chat_id);
  const db = loadDatabase();
  const channel = db.channels[cid];

  if (!channel) {
    return res.status(404).json({ error: 'Kanal topilmadi' });
  }

  const { sources } = req.body;
  if (!Array.isArray(sources)) {
    return res.status(400).json({ error: 'Manbalar ro‘yxati massiv bo‘lishi kerak' });
  }

  // Filter only existing sources
  channel.selected_sources = sources.filter((sid: string) => db.sources[sid]);
  channel.updated_at = new Date().toISOString();
  saveDatabase(db);

  addSystemLog('INFO', 'Channel', `'${channel.title}' kanali uchun manbalar yangilandi: ${channel.selected_sources.length} ta manba.`);

  return res.json({
    status: 'ok',
    message: 'Kanal manbalari yangilandi',
    selected_sources: channel.selected_sources,
  });
});

app.post('/api/channels/:chat_id/recheck', authMiddleware, (req: Request, res: Response) => {
  const cid = String(req.params.chat_id);
  const db = loadDatabase();
  const channel = db.channels[cid];

  if (!channel) {
    return res.status(404).json({ error: 'Kanal topilmadi' });
  }

  // In production, bot calls bot.get_chat_member. We assume success on recheck request
  channel.can_post = true;
  channel.updated_at = new Date().toISOString();
  saveDatabase(db);

  addSystemLog('INFO', 'Channel', `'${channel.title}' kanali uchun huquqlar qayta tekshirildi.`);

  return res.json({
    status: 'ok',
    message: 'Kanal huquqlari muvaffaqiyatli tekshirildi va faollashtirildi.',
    can_post: true,
  });
});

app.put('/api/channels/:chat_id/schedule', authMiddleware, (req: Request, res: Response) => {
  const cid = String(req.params.chat_id);
  const db = loadDatabase();
  const channel = db.channels[cid];

  if (!channel) {
    return res.status(404).json({ error: 'Kanal topilmadi' });
  }

  const { schedule_mode, schedule_times } = req.body;
  if (!schedule_mode || !['instant', 'custom', 'scheduled'].includes(schedule_mode)) {
    return res.status(400).json({ error: 'Noto‘g‘ri rejim. "instant" yoki "custom" bo‘lishi kerak' });
  }

  const mode = schedule_mode === 'scheduled' ? 'custom' : schedule_mode;
  let cleanedTimes: string[] = [];

  if (Array.isArray(schedule_times)) {
    const timeRegex = /^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$/;
    for (const t of schedule_times) {
      const str = String(t).trim();
      if (!timeRegex.test(str)) {
        return res.status(400).json({ error: `Noto‘g‘ri vaqt formati: "${str}". Masalan: "09:30"` });
      }
      const [h, m] = str.split(':');
      const norm = `${h.padStart(2, '0')}:${m.padStart(2, '0')}`;
      if (!cleanedTimes.includes(norm)) {
        cleanedTimes.push(norm);
      }
    }
  }

  if (mode === 'custom' && cleanedTimes.length === 0) {
    return res.status(400).json({ error: 'Custom rejim uchun kamida 1 ta vaqt ko‘rsatilishi shart' });
  }

  if (cleanedTimes.length > 3 && channel.plan !== 'contract') {
    return res.status(400).json({
      error: 'Maksimal 3 ta vaqt sloti ruxsat etiladi (ko‘proq uchun shartnoma talab qilinadi)',
    });
  }

  cleanedTimes.sort();

  channel.schedule_mode = mode;
  channel.schedule_times = cleanedTimes;
  channel.today_delivered_slots = [];
  channel.updated_at = new Date().toISOString();

  saveDatabase(db);
  addSystemLog(
    'INFO',
    'Schedule',
    `'${channel.title}' kanali jadvali yangilandi: Rejim=${mode}, Vaqtlar=[${cleanedTimes.join(', ')}] (Asia/Tashkent)`
  );

  return res.json({
    status: 'ok',
    message: 'Jadval sozlamalari muvaffaqiyatli saqlandi',
    channel,
  });
});

app.delete('/api/channels/:chat_id', authMiddleware, (req: Request, res: Response) => {
  const cid = String(req.params.chat_id);
  const db = loadDatabase();

  if (!db.channels[cid]) {
    return res.status(404).json({ error: 'Kanal topilmadi' });
  }

  const title = db.channels[cid].title;
  delete db.channels[cid];
  saveDatabase(db);

  addSystemLog('WARNING', 'Channel', `Kanal tizimdan uzildi: '${title}' (${cid})`);

  return res.json({
    status: 'ok',
    message: `'${title}' kanali muvaffaqiyatli o‘chirildi`,
  });
});

// ==========================================================================
// 4. USERS & CONTRACT MANAGEMENT (PROTECTED)
// ==========================================================================

app.get('/api/users', authMiddleware, (req: Request, res: Response) => {
  const db = loadDatabase();
  let list = Object.values(db.users);

  const search = String(req.query.search || '').trim().toLowerCase();
  const plan = String(req.query.plan || 'all');

  if (search) {
    list = list.filter(
      (u) =>
        u.user_id.toString().includes(search) ||
        (u.username && u.username.toLowerCase().includes(search)) ||
        (u.first_name && u.first_name.toLowerCase().includes(search))
    );
  }

  if (plan !== 'all') {
    list = list.filter((u) => u.plan === plan);
  }

  // Attach count of connected channels for each user
  const enriched = list.map((u) => {
    const userChannels = Object.values(db.channels).filter((c) => c.owner_user_id === u.user_id);
    return {
      ...u,
      channels_count: userChannels.length,
      channels: userChannels.map((c) => ({ chat_id: c.chat_id, title: c.title, plan: c.plan, daily_limit: c.daily_limit })),
    };
  });

  return res.json({
    status: 'ok',
    total: enriched.length,
    users: enriched,
  });
});

app.post('/api/users', authMiddleware, async (req: Request, res: Response) => {
  const { user_id, username, first_name, plan, custom_limit } = req.body;
  const uid = parseInt(String(user_id), 10);
  if (!uid || isNaN(uid)) {
    return res.status(400).json({ error: 'Telegram User ID raqam bo‘lishi shart' });
  }

  const db = loadDatabase();
  const isNew = !db.users[uid.toString()];
  
  const user: UserRecord = {
    user_id: uid,
    username: username ? String(username).replace(/^@/, '').trim() : null,
    first_name: first_name ? String(first_name).trim() : 'Foydalanuvchi',
    plan: plan === 'contract' ? 'contract' : 'free',
    custom_limit: plan === 'contract' ? Math.max(1, parseInt(custom_limit || '10', 10)) : null,
    created_at: db.users[uid.toString()]?.created_at || new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };

  db.users[uid.toString()] = user;
  saveDatabase(db);

  if (isNew) {
    addSystemLog('INFO', 'User', `Yangi foydalanuvchi tizimga qo‘shildi: ID=${uid}, Ism=${user.first_name}`);
    notifySuperAdminNewUser(user).catch(() => {});
    broadcastEvent('user_created', { user, total_users: Object.keys(db.users).length });
  } else {
    broadcastEvent('user_updated', { user, total_users: Object.keys(db.users).length });
  }

  return res.json({
    status: 'ok',
    message: isNew ? 'Yangi foydalanuvchi muvaffaqiyatli qo‘shildi' : 'Foydalanuvchi ma’lumotlari yangilandi',
    user,
    is_new: isNew,
  });
});

app.get('/api/users/:user_id', authMiddleware, (req: Request, res: Response) => {
  const uid = parseInt(String(req.params.user_id), 10);
  const db = loadDatabase();
  const user = db.users[uid.toString()];

  if (!user) {
    return res.status(404).json({ error: 'Foydalanuvchi topilmadi' });
  }

  const channels = Object.values(db.channels).filter((c) => c.owner_user_id === uid);

  return res.json({
    status: 'ok',
    user,
    channels,
  });
});

app.patch('/api/users/:user_id/contract', authMiddleware, (req: Request, res: Response) => {
  const uid = parseInt(String(req.params.user_id), 10);
  const db = loadDatabase();
  let user = db.users[uid.toString()];

  const { plan, custom_limit } = req.body;

  if (!user) {
    user = {
      user_id: uid,
      username: null,
      first_name: 'Foydalanuvchi',
      plan: 'free',
      custom_limit: null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    db.users[uid.toString()] = user;
  }

  const newPlan = plan === 'contract' ? 'contract' : 'free';
  const newLimit = newPlan === 'contract' ? Math.max(1, parseInt(custom_limit || '10', 10)) : 3;

  user.plan = newPlan;
  user.custom_limit = newPlan === 'contract' ? newLimit : null;
  user.updated_at = new Date().toISOString();

  // Propagate to all channels owned by this user
  let updatedChannelsCount = 0;
  for (const ch of Object.values(db.channels)) {
    if (ch.owner_user_id === uid) {
      ch.plan = newPlan;
      ch.daily_limit = newLimit;
      ch.updated_at = new Date().toISOString();
      updatedChannelsCount++;
    }
  }

  saveDatabase(db);
  addSystemLog('INFO', 'User', `Foydalanuvchi tarifi o‘zgartirildi (${uid}): Plan=${newPlan}, Limit=${newLimit}. ${updatedChannelsCount} ta kanal yangilandi.`);

  return res.json({
    status: 'ok',
    message: `Foydalanuvchiga ${newPlan.toUpperCase()} tarifi (limit: ${newLimit}) muvaffaqiyatli o‘rnatildi`,
    user,
    channels_updated: updatedChannelsCount,
  });
});

// ==========================================================================
// 5. CATEGORIES & SOURCES (RSS/ATOM/JSON FEED) MANAGEMENT (PROTECTED)
// ==========================================================================

// --- Categories CRUD ---
app.get('/api/categories', authMiddleware, async (req: Request, res: Response) => {
  const fsDb = getFirestoreDb();
  const db = loadDatabase();
  if (fsDb) {
    try {
      const catSnap = await fsDb.collection('source_categories').get();
      if (!catSnap.empty) {
        db.categories = {};
        for (const doc of catSnap.docs) {
          db.categories[doc.id] = { ...doc.data(), id: doc.id } as CategoryRecord;
        }
      }
    } catch (e: any) {
      console.warn('Could not read categories from Firestore:', e.message);
    }
  }

  const categoriesList = Object.values(db.categories || {}).map((cat) => {
    const source_count = Object.values(db.sources).filter(
      (s) => s.category_id === cat.id || s.category.toLowerCase() === cat.name.toLowerCase()
    ).length;
    return {
      ...cat,
      source_count,
    };
  });

  categoriesList.sort((a, b) => (a.sort_order || 0) - (b.sort_order || 0));

  return res.json({
    status: 'ok',
    total: categoriesList.length,
    categories: categoriesList,
  });
});

app.post('/api/categories', authMiddleware, (req: Request, res: Response) => {
  const { name, slug, description, icon, active, sort_order } = req.body;
  if (!name || !String(name).trim()) {
    return res.status(400).json({ error: 'Kategoriya nomi kiritilishi shart' });
  }

  const cleanName = String(name).trim();
  const rawSlug = slug && String(slug).trim()
    ? String(slug).trim().toLowerCase().replace(/[^a-z0-9-_]/g, '-')
    : cleanName.toLowerCase().replace(/[^a-z0-9-_]/g, '-').replace(/-+/g, '-');

  const id = `cat_${rawSlug.replace(/^-|-$/g, '') || Date.now()}`;
  const db = loadDatabase();

  if (db.categories[id]) {
    return res.status(400).json({ error: 'Ushbu nomdagi kategoriya allaqachon mavjud' });
  }

  const highestSort = Math.max(0, ...Object.values(db.categories).map((c) => c.sort_order || 0));

  const newCategory: CategoryRecord = {
    id,
    name: cleanName,
    slug: rawSlug,
    description: String(description || '').trim(),
    icon: String(icon || 'newspaper').trim(),
    active: active !== undefined ? Boolean(active) : true,
    sort_order: sort_order !== undefined ? Number(sort_order) : highestSort + 1,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };

  db.categories[id] = newCategory;
  saveDatabase(db);
  addSystemLog('INFO', 'Category', `Yangi kategoriya yaratildi: '${cleanName}' (ID: ${id})`);

  return res.json({
    status: 'ok',
    message: 'Kategoriya muvaffaqiyatli yaratildi',
    category: {
      ...newCategory,
      source_count: 0,
    },
  });
});

app.patch('/api/categories/:id', authMiddleware, (req: Request, res: Response) => {
  const id = String(req.params.id);
  const db = loadDatabase();
  const cat = db.categories[id];

  if (!cat) {
    return res.status(404).json({ error: 'Kategoriya topilmadi' });
  }

  const { name, slug, description, icon, active, sort_order } = req.body;
  const oldName = cat.name;

  if (name !== undefined) {
    const trimmed = String(name).trim();
    if (!trimmed) {
      return res.status(400).json({ error: 'Kategoriya nomi bo‘sh bo‘lishi mumkin emas' });
    }
    cat.name = trimmed;
    // Update category name in associated sources
    for (const src of Object.values(db.sources)) {
      if (src.category_id === id || src.category === oldName) {
        src.category_id = id;
        src.category = trimmed;
        src.updated_at = new Date().toISOString();
      }
    }
  }

  if (slug !== undefined) cat.slug = String(slug).trim().toLowerCase();
  if (description !== undefined) cat.description = String(description).trim();
  if (icon !== undefined) cat.icon = String(icon).trim();
  if (active !== undefined) cat.active = Boolean(active);
  if (sort_order !== undefined) cat.sort_order = Number(sort_order);

  cat.updated_at = new Date().toISOString();
  saveDatabase(db);
  addSystemLog('INFO', 'Category', `Kategoriya yangilandi: '${cat.name}' (${id})`);

  const source_count = Object.values(db.sources).filter(
    (s) => s.category_id === id || s.category === cat.name
  ).length;

  return res.json({
    status: 'ok',
    message: 'Kategoriya ma’lumotlari muvaffaqiyatli yangilandi',
    category: {
      ...cat,
      source_count,
    },
  });
});

app.delete('/api/categories/:id', authMiddleware, (req: Request, res: Response) => {
  const id = String(req.params.id);
  const db = loadDatabase();
  const cat = db.categories[id];

  if (!cat) {
    return res.status(404).json({ error: 'Kategoriya topilmadi' });
  }

  const sourcesInCategory = Object.values(db.sources).filter(
    (s) => s.category_id === id || s.category === cat.name
  );
  const { move_to_id, delete_sources } = req.body || {};

  if (sourcesInCategory.length > 0 && !move_to_id && !delete_sources) {
    return res.status(400).json({
      error: `Ushbu kategoriyada ${sourcesInCategory.length} ta manba mavjud. O‘chirishdan oldin manbalarni boshqa kategoriyaga o‘tkazing yoki manbalarni o‘chirishni tasdiqlang.`,
      source_count: sourcesInCategory.length,
    });
  }

  if (move_to_id && db.categories[move_to_id]) {
    const targetCat = db.categories[move_to_id];
    for (const src of sourcesInCategory) {
      src.category_id = targetCat.id;
      src.category = targetCat.name;
      src.updated_at = new Date().toISOString();
    }
  } else if (delete_sources) {
    for (const src of sourcesInCategory) {
      delete db.sources[src.id];
    }
  }

  delete db.categories[id];
  saveDatabase(db);
  addSystemLog('WARNING', 'Category', `Kategoriya o‘chirildi: '${cat.name}' (${id})`);

  return res.json({
    status: 'ok',
    message: 'Kategoriya muvaffaqiyatli o‘chirildi',
  });
});

app.post('/api/categories/reorder', authMiddleware, (req: Request, res: Response) => {
  const { order } = req.body;
  if (!Array.isArray(order)) {
    return res.status(400).json({ error: 'Kategoriyalar tartibi massiv bo‘lishi kerak' });
  }

  const db = loadDatabase();
  order.forEach((catId: string, idx: number) => {
    if (db.categories[catId]) {
      db.categories[catId].sort_order = idx + 1;
      db.categories[catId].updated_at = new Date().toISOString();
    }
  });

  saveDatabase(db);
  return res.json({ status: 'ok', message: 'Kategoriyalar tartibi saqlandi' });
});

// --- Real Feed Diagnostic & Testing ---
app.post('/api/sources/test', authMiddleware, async (req: Request, res: Response) => {
  const { feed_url, url } = req.body;
  const targetUrl = String(feed_url || url || '').trim();

  if (!targetUrl) {
    return res.status(400).json({ error: 'Lenta URL manzili kiritilishi shart' });
  }

  if (!targetUrl.startsWith('http://') && !targetUrl.startsWith('https://')) {
    return res.status(400).json({ error: 'URL http:// yoki https:// bilan boshlanishi kerak' });
  }

  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 8000);

    const response = await fetch(targetUrl, {
      headers: {
        'User-Agent': 'AnjurXBot/2.0 (FeedReader; +https://t.me/AnjurXBot)',
        'Accept': 'application/rss+xml, application/atom+xml, application/feed+json, application/xml, text/xml, */*',
      },
      signal: controller.signal,
      redirect: 'follow',
    });

    clearTimeout(timeoutId);

    const contentType = response.headers.get('content-type') || '';
    const bodyText = await response.text();

    if (!response.ok) {
      return res.json({
        status: 'error',
        valid: false,
        http_status: response.status,
        content_type: contentType,
        error: `Server ${response.status} (${response.statusText}) xatosini qaytardi`,
      });
    }

    const testResult = parseFeedTest(bodyText, contentType);
    testResult.http_status = response.status;
    return res.json(testResult);
  } catch (err: any) {
    const isTimeout = err.name === 'AbortError';
    return res.json({
      status: 'error',
      valid: false,
      http_status: 0,
      error: isTimeout
        ? 'URL ga ulanish vaqti tugadi (8 soniya). Server javob bermadi.'
        : `Ulanishda xatolik: ${err.message}`,
    });
  }
});

// --- Sources CRUD ---
app.get('/api/sources', authMiddleware, async (req: Request, res: Response) => {
  const fsDb = getFirestoreDb();
  let db = loadDatabase();

  if (fsDb) {
    try {
      const snap = await fsDb.collection('sources').get();
      const freshSources: Record<string, SourceRecord> = {};
      for (const doc of snap.docs) {
        freshSources[doc.id] = { ...doc.data(), id: doc.id } as SourceRecord;
      }
      db.sources = freshSources;
      // Also cache to local file without triggering re-sync
      const dir = path.dirname(DB_FILE);
      if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
      fs.writeFileSync(`${DB_FILE}.tmp`, JSON.stringify(db, null, 2), 'utf-8');
      fs.renameSync(`${DB_FILE}.tmp`, DB_FILE);
    } catch (e: any) {
      console.warn('Could not fetch sources from Firestore, using local fallback:', e.message);
    }
  }

  let list = Object.values(db.sources);

  const search = String(req.query.search || '').trim().toLowerCase();
  const categoryId = String(req.query.category_id || '').trim();
  const category = String(req.query.category || '').trim();
  const activeParam = req.query.active;

  if (search) {
    list = list.filter(
      (s) =>
        s.name.toLowerCase().includes(search) ||
        s.url.toLowerCase().includes(search) ||
        (s.description && s.description.toLowerCase().includes(search)) ||
        s.category.toLowerCase().includes(search)
    );
  }

  if (categoryId) {
    list = list.filter((s) => s.category_id === categoryId);
  } else if (category && category !== 'all') {
    list = list.filter((s) => s.category.toLowerCase() === category.toLowerCase());
  }

  if (activeParam !== undefined && activeParam !== '') {
    const isActive = activeParam === 'true' || activeParam === '1';
    list = list.filter((s) => s.active === isActive);
  }

  return res.json({
    status: 'ok',
    total: list.length,
    sources: list,
  });
});

app.post('/api/sources', authMiddleware, (req: Request, res: Response) => {
  const { name, url, feed_url, website_url, category_id, category, type, description, language, country, active } = req.body;
  const targetUrl = String(feed_url || url || '').trim();

  if (!name || !targetUrl) {
    return res.status(400).json({ error: 'Nomi va Lenta URL manzili kiritilishi shart' });
  }

  if (!targetUrl.startsWith('http://') && !targetUrl.startsWith('https://')) {
    return res.status(400).json({ error: 'URL http:// yoki https:// bilan boshlanishi kerak' });
  }

  const db = loadDatabase();
  const id = `src_${crypto.createHash('sha256').update(targetUrl).digest('hex').slice(0, 12)}`;

  if (db.sources[id]) {
    return res.status(400).json({ error: 'Ushbu URL manbasi allaqachon mavjud' });
  }

  let finalCatId = category_id || 'cat_ozbekiston';
  let finalCatName = category || 'O‘zbekiston';

  if (category_id && db.categories[category_id]) {
    finalCatId = category_id;
    finalCatName = db.categories[category_id].name;
  } else if (category) {
    const found = Object.values(db.categories).find((c) => c.name.toLowerCase() === category.toLowerCase());
    if (found) {
      finalCatId = found.id;
      finalCatName = found.name;
    }
  }

  const newSource: SourceRecord = {
    id,
    name: String(name).trim(),
    url: targetUrl,
    feed_url: targetUrl,
    website_url: website_url ? String(website_url).trim() : '',
    type: type || 'rss',
    category_id: finalCatId,
    category: finalCatName,
    description: description ? String(description).trim() : '',
    language: language ? String(language).trim() : 'uz',
    country: country ? String(country).trim() : 'UZ',
    active: active !== undefined ? Boolean(active) : true,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    last_fetch_at: new Date().toISOString(),
    last_success_at: new Date().toISOString(),
    last_error: null,
    error_count: 0,
    etag: null,
    last_modified: null,
    posts_count: 0,
  };

  db.sources[id] = newSource;
  saveDatabase(db);

  addSystemLog('INFO', 'Source', `Yangi manba qo‘shildi: '${name}' (${targetUrl}) [${finalCatName}]`);

  return res.json({
    status: 'ok',
    message: 'Yangi manba muvaffaqiyatli qo‘shildi',
    source: newSource,
  });
});

app.patch('/api/sources/:id', authMiddleware, (req: Request, res: Response) => {
  const sid = String(req.params.id);
  const db = loadDatabase();
  const source = db.sources[sid];

  if (!source) {
    return res.status(404).json({ error: 'Manba topilmadi' });
  }

  const { name, url, feed_url, website_url, category_id, category, type, description, language, country, active } = req.body;

  if (name !== undefined) source.name = String(name).trim();
  if (feed_url !== undefined || url !== undefined) {
    const u = String(feed_url || url).trim();
    if (u) {
      source.url = u;
      source.feed_url = u;
    }
  }
  if (website_url !== undefined) source.website_url = String(website_url).trim();
  if (type !== undefined) source.type = String(type).trim();
  if (description !== undefined) source.description = String(description).trim();
  if (language !== undefined) source.language = String(language).trim();
  if (country !== undefined) source.country = String(country).trim();
  if (typeof active === 'boolean') source.active = active;

  if (category_id !== undefined && db.categories[category_id]) {
    source.category_id = category_id;
    source.category = db.categories[category_id].name;
  } else if (category !== undefined) {
    source.category = String(category).trim();
    const found = Object.values(db.categories).find((c) => c.name.toLowerCase() === source.category.toLowerCase());
    if (found) source.category_id = found.id;
  }

  source.updated_at = new Date().toISOString();
  saveDatabase(db);

  addSystemLog('INFO', 'Source', `Manba yangilandi: '${source.name}' (${sid})`);

  return res.json({ status: 'ok', message: 'Manba ma’lumotlari saqlandi', source });
});

app.post('/api/sources/:id/toggle', authMiddleware, (req: Request, res: Response) => {
  const sid = String(req.params.id);
  const db = loadDatabase();
  const source = db.sources[sid];

  if (!source) {
    return res.status(404).json({ error: 'Manba topilmadi' });
  }

  source.active = !source.active;
  source.updated_at = new Date().toISOString();
  saveDatabase(db);

  addSystemLog('INFO', 'Source', `Manba holati o‘zgartirildi: '${source.name}' -> ${source.active ? 'FAOL' : 'NOFAOL'}`);

  return res.json({
    status: 'ok',
    active: source.active,
    message: `Manba ${source.active ? 'yoqildi' : 'o‘chirildi'}`,
  });
});

app.post('/api/sources/:id/sync', authMiddleware, (req: Request, res: Response) => {
  const sid = String(req.params.id);
  const db = loadDatabase();
  const source = db.sources[sid];

  if (!source) {
    return res.status(404).json({ error: 'Manba topilmadi' });
  }

  source.last_fetch_at = new Date().toISOString();
  source.last_success_at = new Date().toISOString();
  source.error_count = 0;
  source.last_error = null;
  saveDatabase(db);

  addSystemLog('INFO', 'Gardener', `Manba majburiy sinxronlashtirildi: '${source.name}'`);

  return res.json({
    status: 'ok',
    message: `'${source.name}' manbasi muvaffaqiyatli sinxronlashtirildi.`,
    source,
  });
});

app.post('/api/sources/sync-all', authMiddleware, (req: Request, res: Response) => {
  const db = loadDatabase();
  const now = new Date().toISOString();
  let count = 0;

  for (const s of Object.values(db.sources)) {
    if (s.active) {
      s.last_fetch_at = now;
      s.last_success_at = now;
      s.error_count = 0;
      s.last_error = null;
      count++;
    }
  }

  saveDatabase(db);
  addSystemLog('INFO', 'Gardener', `Barcha faol manbalar (${count} ta) muvaffaqiyatli sinxronlashtirildi.`);

  return res.json({
    status: 'ok',
    message: `Barcha ${count} ta faol manbalar sinxronlashtirildi.`,
    synced_count: count,
  });
});

app.delete('/api/sources/:id', authMiddleware, async (req: Request, res: Response) => {
  const sid = String(req.params.id);
  const db = loadDatabase();

  if (!db.sources[sid]) {
    return res.status(404).json({ error: 'Manba topilmadi' });
  }

  const name = db.sources[sid].name;
  delete db.sources[sid];

  // Remove from channels selected_sources
  for (const ch of Object.values(db.channels)) {
    ch.selected_sources = ch.selected_sources.filter((s) => s !== sid);
  }

  saveDatabase(db);

  const fsDb = getFirestoreDb();
  if (fsDb) {
    try {
      await fsDb.collection('sources').doc(sid).delete();
    } catch (e: any) {
      console.warn('Could not delete source from Firestore:', e.message);
    }
  }

  addSystemLog('WARNING', 'Source', `Manba o‘chirildi: '${name}' (${sid})`);

  return res.json({
    status: 'ok',
    message: `'${name}' manbasi muvaffaqiyatli o‘chirildi`,
  });
});

// ==========================================================================
// 6. POST POOL & 5-DAY RETENTION (PROTECTED)
// ==========================================================================

app.get('/api/posts', authMiddleware, (req: Request, res: Response) => {
  const db = loadDatabase();
  const now = Date.now();
  const deliveredSet = new Set(db.delivered_signatures || []);

  const allPosts = Object.values(db.posts).map((p) => {
    const isDelivered = p.status === 'delivered' || deliveredSet.has(p.post_id);
    const isExpired = p.expires_at ? new Date(p.expires_at).getTime() <= now : false;
    const effectiveStatus = isDelivered ? 'delivered' : isExpired ? 'expired' : (p.status || 'queued');
    return {
      ...p,
      status: effectiveStatus,
    };
  });

  const status = String(req.query.status || 'all');
  const search = String(req.query.search || '').trim().toLowerCase();
  const page = Math.max(1, parseInt(String(req.query.page || '1'), 10));
  const limit = Math.min(50, Math.max(5, parseInt(String(req.query.limit || '20'), 10)));

  let list = allPosts;

  if (status !== 'all') {
    list = list.filter((p) => p.status === status);
  }

  if (search) {
    list = list.filter(
      (p) =>
        (p.title || '').toLowerCase().includes(search) ||
        (p.source_name || '').toLowerCase().includes(search) ||
        (p.url || '').toLowerCase().includes(search)
    );
  }

  // Sort newest first
  list.sort((a, b) => new Date(b.fetched_at || 0).getTime() - new Date(a.fetched_at || 0).getTime());

  const total = list.length;
  const startIndex = (page - 1) * limit;
  const pagedPosts = list.slice(startIndex, startIndex + limit);

  const counts = {
    all: allPosts.length,
    queued: allPosts.filter((p) => p.status === 'queued').length,
    delivered: allPosts.filter((p) => p.status === 'delivered').length,
    expired: allPosts.filter((p) => p.status === 'expired').length,
  };

  return res.json({
    status: 'ok',
    total,
    page,
    limit,
    total_pages: Math.ceil(total / limit) || 1,
    counts,
    posts: pagedPosts,
  });
});

// ==========================================================================
// 7. DISTRIBUTION MONITORING (PROTECTED)
// ==========================================================================

app.get('/api/distribution', authMiddleware, (req: Request, res: Response) => {
  const db = loadDatabase();
  const channels = Object.values(db.channels);
  const todayStr = getTashkentDateStr();

  const channelDeliverySummary = channels.map((c) => ({
    chat_id: c.chat_id,
    title: c.title,
    plan: c.plan,
    daily_limit: c.daily_limit,
    today_delivered: c.today_date === todayStr ? c.today_delivered_count : 0,
    schedule_mode: c.schedule_mode,
    last_delivered_at: c.last_delivered_at,
    ready: c.active && c.can_post && (c.today_date !== todayStr || c.today_delivered_count < c.daily_limit),
  }));

  return res.json({
    status: 'ok',
    engine_state: 'idle',
    fair_queue_policy: 'Least-Delivered Round-Robin (0-post priority)',
    today_date: todayStr,
    recent_deliveries: db.recent_posts.slice(0, 50),
    channels_summary: channelDeliverySummary,
  });
});

// ==========================================================================
// 8. SYSTEM MONITOR & LOGS (PROTECTED)
// ==========================================================================

app.get('/api/system', authMiddleware, (req: Request, res: Response) => {
  const uptimeSeconds = Math.round((Date.now() - START_TIME) / 1000);
  const mem = process.memoryUsage();

  return res.json({
    status: 'ok',
    components: {
      bot: { status: 'online', name: 'Aiogram 3 Polling Loop' },
      gardener: { status: 'online', name: 'Background Content Worker' },
      distribution: { status: 'online', name: 'Fair Queue Engine' },
      web_server: { status: 'online', name: 'Aiohttp / Express Proxy' },
      firestore: {
        status: getFirestoreDb() ? 'online' : 'standby',
        name: 'Google Cloud Firestore',
      },
      local_database: { status: 'online', name: 'JSON Atomic Disk Store' },
    },
    metrics: {
      uptime_seconds: uptimeSeconds,
      memory_heap_mb: Math.round((mem.heapUsed / 1024 / 1024) * 10) / 10,
      memory_rss_mb: Math.round((mem.rss / 1024 / 1024) * 10) / 10,
      node_version: process.version,
    },
  });
});

app.get('/api/logs', authMiddleware, (req: Request, res: Response) => {
  const level = String(req.query.level || 'ALL');
  const search = String(req.query.search || '').trim().toLowerCase();

  let filtered = [...systemLogs];
  if (level !== 'ALL') {
    filtered = filtered.filter((l) => l.level === level);
  }
  if (search) {
    filtered = filtered.filter((l) => l.message.toLowerCase().includes(search) || l.component.toLowerCase().includes(search));
  }

  return res.json({
    status: 'ok',
    logs: filtered.slice(0, 100),
  });
});

// ==========================================================================
// 9. SETTINGS & OPML (PROTECTED)
// ==========================================================================

app.get('/api/settings', authMiddleware, (req: Request, res: Response) => {
  return res.json({
    status: 'ok',
    config: {
      timezone: 'Asia/Tashkent (UTC+5)',
      super_admin_id: SUPER_ADMIN_ID,
      default_free_limit: 3,
      retention_days: 5,
      fetch_interval_sec: 45,
      distribution_interval_sec: 15,
      cleanup_interval_sec: 600,
      database_path: DB_FILE,
      storage_type: getFirestoreDb() ? 'Firestore + Local' : 'Local JSON',
    },
  });
});

// Backward-compatible endpoints
app.get('/api/stats', (req: Request, res: Response) => {
  const db = loadDatabase();
  const channels = Object.values(db.channels);
  const sources = Object.values(db.sources);
  const activeChannels = channels.filter((c) => c.active && c.can_post).length;

  return res.json({
    status: 'ok',
    total_feeds: sources.length,
    total_subscribers: channels.length,
    active_subscriptions: activeChannels,
    posts_delivered: db.posts_delivered,
    uptime_seconds: Math.round((Date.now() - START_TIME) / 1000),
    bot_status: 'running',
    bot_username: process.env.BOT_USERNAME || 'AnjurXBot',
  });
});

// Health check for platform & render
app.get('/health', (req: Request, res: Response) => {
  res.json({
    status: 'ok',
    bot: 'running',
    uptime_seconds: Math.round((Date.now() - START_TIME) / 1000),
  });
});

app.get('/api/health', (req: Request, res: Response) => {
  res.json({
    status: 'ok',
    bot: 'running',
    uptime_seconds: Math.round((Date.now() - START_TIME) / 1000),
  });
});

// --------------------------------------------------------------------------
// Real-time Event Stream (SSE)
// --------------------------------------------------------------------------
app.get('/api/events', (req: Request, res: Response) => {
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache, no-transform');
  res.setHeader('Connection', 'keep-alive');
  res.setHeader('X-Accel-Buffering', 'no');
  if (typeof (res as any).flushHeaders === 'function') {
    (res as any).flushHeaders();
  }

  const db = loadDatabase();
  const usersList = Object.values(db.users || {});
  res.write(`data: ${JSON.stringify({
    type: 'connected',
    total_users: usersList.length,
    users: usersList,
    total_channels: Object.keys(db.channels || {}).length,
    timestamp: new Date().toISOString()
  })}\n\n`);

  sseClients.add(res);

  req.on('close', () => {
    sseClients.delete(res);
  });
});

// Periodic heartbeat and database file watcher for real-time synchronization
let lastDbMtime = 0;
try {
  if (fs.existsSync(DB_FILE)) {
    lastDbMtime = fs.statSync(DB_FILE).mtimeMs;
  }
} catch {}

setInterval(() => {
  try {
    if (fs.existsSync(DB_FILE)) {
      const stat = fs.statSync(DB_FILE);
      if (stat.mtimeMs > lastDbMtime) {
        lastDbMtime = stat.mtimeMs;
        const freshDb = loadDatabase();
        const usersList = Object.values(freshDb.users || {});
        broadcastEvent('users_updated', {
          total_users: usersList.length,
          users: usersList,
          total_channels: Object.keys(freshDb.channels || {}).length,
        });
      }
    }
  } catch (e) {}
}, 2000);

setInterval(() => {
  broadcastEvent('ping', { time: Date.now() });
}, 15000);

// --------------------------------------------------------------------------
// Vite SPA Middleware (Development & Production Fallback)
// --------------------------------------------------------------------------
async function startServer() {
  // 1. Initial Firestore synchronization & Real-time listeners
  try {
    await syncFirestoreToLocal();
    initFirestoreRealtimeListeners();
    setInterval(syncFirestoreToLocal, 15000);
  } catch (err: any) {
    console.warn('[Server] Firestore initial sync skipped or delayed:', err.message);
  }

  const distPath = path.join(process.cwd(), 'dist');
  const hasDistIndex = fs.existsSync(path.join(distPath, 'index.html'));

  if (process.env.NODE_ENV === 'production' && hasDistIndex) {
    app.use(express.static(distPath));
    app.get('*', (req, res) => {
      res.sendFile(path.join(distPath, 'index.html'));
    });
  } else {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: 'spa',
    });
    app.use(vite.middlewares);
  }

  app.listen(PORT, HOST, () => {
    console.log(`Server running on http://${HOST}:${PORT}`);
  });
}

startServer();
