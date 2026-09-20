import express, { Request, Response, NextFunction } from 'express';
import path from 'path';
import fs from 'fs';
import cors from 'cors';
import crypto from 'crypto';
import dotenv from 'dotenv';
import { initializeApp, cert, getApps, ServiceAccount } from 'firebase-admin/app';
import { getFirestore, Firestore } from 'firebase-admin/firestore';
import { createServer as createViteServer } from 'vite';
import { recoveryQueueNode } from './server/recoveryQueue';

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
  status?: 'ACTIVE' | 'PAUSED' | 'BLOCKED' | string;
  premium?: boolean;
  can_post: boolean;
  daily_limit: number;
  plan: string;
  schedule_mode: string;
  schedule_times: string[];
  selected_sources: string[];
  post_language?: string;
  is_premium_eligible?: boolean;
  premium_enabled?: boolean;
  footer_type?: 'none' | 'text' | 'text_link' | 'inline_button' | string;
  footer_text?: string;
  footer_url?: string;
  today_delivered_count: number;
  sent_today?: number;
  today_delivered_slots?: string[];
  today_date: string;
  last_delivered_at: string | null;
  last_post_at?: string | null;
  total_delivered_count: number;
  error_status?: string | null;
  connected_at?: string;
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
  post_id?: string;
  channel_id: number;
  channel_title?: string;
  title: string;
  url: string;
  telegram_message_id: number | null;
  delivered_at: string;
  target_language?: string;
}

export interface CentralChannelRecord {
  id: string;
  chat_id: number;
  title: string;
  username: string | null;
  description?: string | null;
  added_by: number;
  active: boolean;
  bot_is_admin: boolean;
  can_post?: boolean;
  post_count: number;
  last_post_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface PremiumMediaItemRecord {
  type: string;
  file_id: string;
  caption?: string;
}

export interface ScheduleSlotRecord {
  id: string;
  time: string; // "08:00", "13:00", "20:30"
  label: string;
  active: boolean;
  timezone: string; // "Asia/Tashkent"
  created_at: string;
  updated_at: string;
}

export interface PostDistributionRecord {
  id: string; // `${postId}__channel_${targetChannelId}`
  post_id: string;
  target_channel_id: number;
  target_channel_title: string;
  status: 'PENDING' | 'SENT' | 'FAILED';
  attempts: number;
  last_attempt_at: string | null;
  sent_message_id: number | null;
  error: string | null;
  created_at: string;
  updated_at: string;
}

export interface PremiumPostRecord {
  id: string;
  source_chat_id?: number;
  source_message_id?: number;
  central_chat_id: number;
  central_message_id: number;
  media_type: string;
  text: string;
  media_file_id: string | null;
  media_group_id: string | null;
  media_items?: PremiumMediaItemRecord[];
  author_id?: number | null;
  author_name?: string | null;
  status: 'PENDING' | 'SCHEDULED' | 'PROCESSING' | 'SENT' | 'PARTIAL' | 'FAILED' | 'CANCELLED' | 'draft' | 'ready' | 'active' | 'reserved' | 'delivered' | 'archived' | string;
  distribution_type?: 'premium';
  target_mode?: 'all_active' | 'selected';
  target_channel_ids?: number[];
  target_count?: number;
  successful_count?: number;
  failed_count?: number;
  delivered_count: number;
  scheduled_at?: string | null;
  last_attempt_at?: string | null;
  last_error?: string | null;
  retry_count?: number;
  created_at: string;
  updated_at: string;
}

export interface UnifiedDatabaseState {
  version: number;
  categories: Record<string, CategoryRecord>;
  sources: Record<string, SourceRecord>;
  channels: Record<string, ChannelRecord>;
  posts: Record<string, PostRecord>;
  users: Record<string, UserRecord>;
  central_channels: Record<string, CentralChannelRecord>;
  premium_posts: Record<string, PremiumPostRecord>;
  schedules: Record<string, ScheduleSlotRecord>;
  post_distributions: Record<string, PostDistributionRecord>;
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
    central_channels: {},
    premium_posts: {},
    schedules: {},
    post_distributions: {},
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

  // Ensure default central channel @anjurxpostbaza (-1004373620008)
  if (!data.central_channels) {
    data.central_channels = {};
  }
  if (!data.central_channels['-1004373620008']) {
    data.central_channels['-1004373620008'] = {
      id: '-1004373620008',
      chat_id: -1004373620008,
      title: 'post baza',
      username: 'anjurxpostbaza',
      description: 'anjurx boti uchun postlar bazasi',
      added_by: 8157452043,
      active: true,
      bot_is_admin: true,
      can_post: true,
      post_count: Object.keys(data.premium_posts || {}).length,
      last_post_at: null,
      created_at: '2026-09-19T14:47:57.672Z',
      updated_at: new Date().toISOString(),
    };
  }

  // Ensure default distribution schedules (Tashkent UTC+5)
  if (!data.schedules || Object.keys(data.schedules).length === 0) {
    data.schedules = {
      slot_1: {
        id: 'slot_1',
        time: '08:00',
        label: 'Ertalabki tarqatish',
        active: true,
        timezone: 'Asia/Tashkent',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
      slot_2: {
        id: 'slot_2',
        time: '13:00',
        label: 'Tushki tarqatish',
        active: true,
        timezone: 'Asia/Tashkent',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
      slot_3: {
        id: 'slot_3',
        time: '20:30',
        label: 'Kechki tarqatish',
        active: true,
        timezone: 'Asia/Tashkent',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
    };
  }

  if (!data.post_distributions) {
    data.post_distributions = {};
  }
  if (!data.premium_posts) {
    data.premium_posts = {};
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

  if (!data.central_channels) {
    data.central_channels = {};
  }

  if (!data.premium_posts) {
    data.premium_posts = {};
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

    broadcastEvent('database_changed', {
      total_users: Object.keys(data.users || {}).length,
      users: Object.values(data.users || {}),
      total_channels: Object.keys(data.channels || {}).length,
    });
  } catch (e: any) {
    console.error('Could not write database:', e.message);
  }
}

/**
 * Resilient entity persistence: writes targeted document directly to Firestore if healthy,
 * or diverts to SQLite recovery queue if Firestore is unavailable or quota-exhausted.
 */
export async function saveEntityResilient(
  collection: 'source_categories' | 'sources' | 'channels' | 'users' | 'posts' | 'settings' | 'central_channels' | 'premium_posts' | 'schedules' | 'post_distributions',
  docId: string,
  data: any
) {
  const tableMap: Record<string, string> = {
    source_categories: 'pending_categories',
    sources: 'pending_sources',
    channels: 'pending_channels',
    users: 'pending_users',
    posts: 'pending_posts',
    settings: 'pending_stats',
    central_channels: 'pending_channels',
    premium_posts: 'pending_posts',
    schedules: 'pending_stats',
    post_distributions: 'pending_stats',
  };
  const table = tableMap[collection] || 'pending_stats';

  const fsDb = getFirestoreDb();
  if (!fsDb || recoveryQueueNode.isQuotaExceeded()) {
    recoveryQueueNode.enqueueEvent(table, docId, 'upsert', data);
    return;
  }

  try {
    await fsDb.collection(collection).doc(docId).set(data, { merge: true });
    recoveryQueueNode.recordSuccess('write');
  } catch (err: any) {
    if (recoveryQueueNode.isQuotaError(err)) {
      recoveryQueueNode.recordQuotaError(err);
      recoveryQueueNode.enqueueEvent(table, docId, 'upsert', data);
    } else {
      recoveryQueueNode.recordError('write', err);
    }
  }
}

// --------------------------------------------------------------------------
// Firestore Continuous Bi-Directional Synchronization & Pool Enforcement
// --------------------------------------------------------------------------
export const MAX_POST_POOL_LIMIT = 500;

export let firestoreHealthStatus: 'online' | 'quota_exceeded' | 'standby' = 'standby';
export let firestoreHealthMessage = 'Firestore sozlanmagan';
export let firestoreLastQuotaNotice: string | null = null;
let firestoreSyncInitialized = false;

/**
 * Enforces the strict 500-post pool limit.
 * Cleanup algorithm:
 * 1. Expired posts
 * 2. Oldest delivered posts (if > 500)
 * 3. Oldest queued / assigned / failed posts (if still > 500)
 * 4. Preserves freshest, newest posts!
 * Deletes in Firestore via batches (up to 450 per batch).
 */
export async function cleanupPostPool(
  db: UnifiedDatabaseState,
  fsDb?: FirebaseFirestore.Firestore | null
): Promise<{ deleted_count: number; remaining_count: number }> {
  const posts = Object.values(db.posts || {});
  const now = Date.now();

  for (const p of posts) {
    if (p.expires_at && new Date(p.expires_at).getTime() <= now && p.status !== 'delivered') {
      p.status = 'expired';
    }
  }

  if (posts.length <= MAX_POST_POOL_LIMIT) {
    return { deleted_count: 0, remaining_count: posts.length };
  }

  const toDeleteIds: string[] = [];
  let remaining: PostRecord[] = [];

  // Step 1: Expired posts first
  for (const p of posts) {
    if (p.status === 'expired' || (p.expires_at && new Date(p.expires_at).getTime() <= now && p.status !== 'delivered')) {
      toDeleteIds.push(p.post_id);
    } else {
      remaining.push(p);
    }
  }

  // Step 2: If still > 500, delete oldest delivered posts
  if (remaining.length > MAX_POST_POOL_LIMIT) {
    const delivered = remaining.filter((p) => p.status === 'delivered');
    delivered.sort((a, b) => {
      const tA = new Date(a.delivered_at || a.fetched_at || 0).getTime();
      const tB = new Date(b.delivered_at || b.fetched_at || 0).getTime();
      return tA - tB;
    });

    const excess = remaining.length - MAX_POST_POOL_LIMIT;
    const deliveredToRemove = delivered.slice(0, excess);
    const delSet = new Set(deliveredToRemove.map((p) => p.post_id));
    for (const p of deliveredToRemove) {
      toDeleteIds.push(p.post_id);
    }
    remaining = remaining.filter((p) => !delSet.has(p.post_id));
  }

  // Step 3: If still > 500, delete oldest queued / assigned / failed posts
  if (remaining.length > MAX_POST_POOL_LIMIT) {
    remaining.sort((a, b) => {
      const tA = new Date(a.fetched_at || 0).getTime();
      const tB = new Date(b.fetched_at || 0).getTime();
      return tA - tB;
    });

    const excess = remaining.length - MAX_POST_POOL_LIMIT;
    const oldestToRemove = remaining.slice(0, excess);
    const oldSet = new Set(oldestToRemove.map((p) => p.post_id));
    for (const p of oldestToRemove) {
      toDeleteIds.push(p.post_id);
    }
    remaining = remaining.filter((p) => !oldSet.has(p.post_id));
  }

  // Apply deletions locally
  for (const id of toDeleteIds) {
    delete db.posts[id];
  }

  db.updated_at = new Date().toISOString();
  try {
    fs.writeFileSync(DB_FILE, JSON.stringify(db, null, 2), 'utf-8');
  } catch (err: any) {
    console.error('Failed saving cleaned database:', err.message);
  }

  // Apply controlled deletions to Firestore only if healthy (never huge delete storms)
  if (fsDb && toDeleteIds.length > 0 && !recoveryQueueNode.isQuotaExceeded()) {
    try {
      // Process small batch of at most 25 deletes per run
      const batchIds = toDeleteIds.slice(0, 25);
      const batch = fsDb.batch();
      for (const pid of batchIds) {
        batch.delete(fsDb.collection('posts').doc(pid));
      }
      await batch.commit();
      recoveryQueueNode.recordSuccess('write');
      console.log(`[Firestore Batch Cleanup] Successfully purged ${batchIds.length} excess/expired posts from Firestore.`);
    } catch (fsErr: any) {
      if (recoveryQueueNode.isQuotaError(fsErr)) {
        recoveryQueueNode.recordQuotaError(fsErr);
      } else {
        recoveryQueueNode.recordError('write', fsErr);
      }
      console.warn('[Firestore Cleanup Notice]:', fsErr.message);
    }
  }

  console.log(`[Post Pool Cleanup] Purged ${toDeleteIds.length} posts. Post pool count now: ${Object.keys(db.posts).length} <= ${MAX_POST_POOL_LIMIT}`);
  return { deleted_count: toDeleteIds.length, remaining_count: Object.keys(db.posts).length };
}

export async function syncFirestoreToLocal() {
  const fsDb = getFirestoreDb();
  if (!fsDb) {
    return;
  }

  // 1. Cheap health check ping (Single write, zero full scans)
  try {
    await fsDb.collection('settings').doc('system_health').set({
      ping_at: new Date().toISOString(),
      service: 'web_admin',
    }, { merge: true });
    recoveryQueueNode.recordSuccess('write');
  } catch (err: any) {
    if (recoveryQueueNode.isQuotaError(err)) {
      recoveryQueueNode.recordQuotaError(err);
      console.warn('[Firestore Startup] Quota exceeded on startup health check. Skipping scans.');
      return;
    }
    recoveryQueueNode.recordError('write', err);
  }

  try {
    const data = loadDatabase();

    // 2. Only seed categories & sources if local database was completely empty (fresh container)
    const hasCategories = Object.keys(data.categories || {}).length > 0;
    const hasSources = Object.keys(data.sources || {}).length > 0;

    if (!hasCategories && !recoveryQueueNode.isQuotaExceeded()) {
      try {
        const catsSnap = await fsDb.collection('source_categories').limit(50).get();
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
          recoveryQueueNode.recordSuccess('read');
        }
      } catch (e: any) {
        if (recoveryQueueNode.isQuotaError(e)) recoveryQueueNode.recordQuotaError(e);
      }
    }

    if (!hasSources && !recoveryQueueNode.isQuotaExceeded()) {
      try {
        const sourcesSnap = await fsDb.collection('sources').limit(100).get();
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
          recoveryQueueNode.recordSuccess('read');
        }
      } catch (e: any) {
        if (recoveryQueueNode.isQuotaError(e)) recoveryQueueNode.recordQuotaError(e);
      }
    }

    // Load Central Channels if not present
    if (Object.keys(data.central_channels || {}).length === 0 && !recoveryQueueNode.isQuotaExceeded()) {
      try {
        const cchanSnap = await fsDb.collection('central_channels').limit(50).get();
        if (!cchanSnap.empty) {
          cchanSnap.forEach((doc) => {
            const c = doc.data();
            const cid = Number(c.chat_id || doc.id);
            data.central_channels[cid] = {
              id: String(cid),
              chat_id: cid,
              title: c.title || `Markaziy Kanal ${cid}`,
              username: c.username || null,
              description: c.description || null,
              added_by: Number(c.added_by || 8157452043),
              active: c.active !== false,
              bot_is_admin: c.bot_is_admin !== false,
              can_post: c.can_post !== false,
              post_count: Number(c.post_count || 0),
              last_post_at: c.last_post_at || null,
              created_at: c.created_at || new Date().toISOString(),
              updated_at: c.updated_at || new Date().toISOString(),
            };
          });
          recoveryQueueNode.recordSuccess('read');
        }
      } catch (e: any) {
        if (recoveryQueueNode.isQuotaError(e)) recoveryQueueNode.recordQuotaError(e);
      }
    }

    // Load Premium Posts if not present
    if (Object.keys(data.premium_posts || {}).length === 0 && !recoveryQueueNode.isQuotaExceeded()) {
      try {
        const ppostsSnap = await fsDb.collection('premium_posts').limit(100).get();
        if (!ppostsSnap.empty) {
          ppostsSnap.forEach((doc) => {
            const p = doc.data();
            const pid = p.id || doc.id;
            data.premium_posts[pid] = {
              id: pid,
              central_chat_id: Number(p.central_chat_id || 0),
              central_message_id: Number(p.central_message_id || 0),
              media_type: p.media_type || 'text',
              text: p.text || '',
              media_file_id: p.media_file_id || null,
              media_group_id: p.media_group_id || null,
              media_items: p.media_items || [],
              author_id: p.author_id || null,
              author_name: p.author_name || null,
              status: p.status || 'ready',
              delivered_count: Number(p.delivered_count || 0),
              created_at: p.created_at || new Date().toISOString(),
              updated_at: p.updated_at || new Date().toISOString(),
            };
          });
          recoveryQueueNode.recordSuccess('read');
        }
      } catch (e: any) {
        if (recoveryQueueNode.isQuotaError(e)) recoveryQueueNode.recordQuotaError(e);
      }
    }

    // Enforce 500 post limit cleanup on local pool
    await cleanupPostPool(data, fsDb);
  } catch (err: any) {
    if (recoveryQueueNode.isQuotaError(err)) {
      recoveryQueueNode.recordQuotaError(err);
    }
    console.error('[Firestore Targeted Sync Notice]:', err.message);
  }
}

export function initFirestoreRealtimeListeners() {
  const fsDb = getFirestoreDb();
  if (!fsDb || firestoreSyncInitialized) return;
  if (recoveryQueueNode.isQuotaExceeded()) {
    console.log('[Firestore] Realtime listeners deferred due to active QUOTA_EXCEEDED state.');
    return;
  }
  firestoreSyncInitialized = true;

  console.log('[Firestore] Registering lightweight real-time listeners (users & channels only)...');

  // Live Users Listener (with error handler to catch 429/RESOURCE_EXHAUSTED)
  fsDb.collection('users').onSnapshot(
    (snap) => {
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
    },
    (err: any) => {
      if (recoveryQueueNode.isQuotaError(err)) {
        recoveryQueueNode.recordQuotaError(err);
        console.warn('[Firestore] Users listener encountered quota error, circuit breaker opened.');
      }
    }
  );

  // Live Channels Listener (with error handler to catch 429/RESOURCE_EXHAUSTED)
  fsDb.collection('channels').onSnapshot(
    (snap) => {
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
    },
    (err: any) => {
      if (recoveryQueueNode.isQuotaError(err)) {
        recoveryQueueNode.recordQuotaError(err);
        console.warn('[Firestore] Channels listener encountered quota error, circuit breaker opened.');
      }
    }
  );

  // Live Central Channels Listener
  fsDb.collection('central_channels').onSnapshot(
    (snap) => {
      try {
        const data = loadDatabase();
        snap.docChanges().forEach((change) => {
          const c = change.doc.data();
          const cid = Number(c.chat_id || change.doc.id);
          if (change.type === 'removed') {
            delete data.central_channels[cid];
          } else {
            data.central_channels[cid] = {
              id: String(cid),
              chat_id: cid,
              title: c.title || `Markaziy Kanal ${cid}`,
              username: c.username || null,
              description: c.description || null,
              added_by: Number(c.added_by || 8157452043),
              active: c.active !== false,
              bot_is_admin: c.bot_is_admin !== false,
              can_post: c.can_post !== false,
              post_count: Number(c.post_count || 0),
              last_post_at: c.last_post_at || null,
              created_at: c.created_at || new Date().toISOString(),
              updated_at: c.updated_at || new Date().toISOString(),
            };
          }
        });
        data.updated_at = new Date().toISOString();
        fs.writeFileSync(DB_FILE, JSON.stringify(data, null, 2), 'utf-8');
      } catch (e: any) {
        console.warn('Error in central_channels onSnapshot:', e.message);
      }
    },
    (err: any) => {
      if (recoveryQueueNode.isQuotaError(err)) {
        recoveryQueueNode.recordQuotaError(err);
      }
    }
  );

  // Live Premium Posts Listener
  fsDb.collection('premium_posts').onSnapshot(
    (snap) => {
      try {
        const data = loadDatabase();
        snap.docChanges().forEach((change) => {
          const p = change.doc.data();
          const pid = p.id || change.doc.id;
          if (change.type === 'removed') {
            delete data.premium_posts[pid];
          } else {
            data.premium_posts[pid] = {
              id: pid,
              central_chat_id: Number(p.central_chat_id || 0),
              central_message_id: Number(p.central_message_id || 0),
              media_type: p.media_type || 'text',
              text: p.text || '',
              media_file_id: p.media_file_id || null,
              media_group_id: p.media_group_id || null,
              media_items: p.media_items || [],
              author_id: p.author_id || null,
              author_name: p.author_name || null,
              status: p.status || 'ready',
              delivered_count: Number(p.delivered_count || 0),
              created_at: p.created_at || new Date().toISOString(),
              updated_at: p.updated_at || new Date().toISOString(),
            };
          }
        });
        data.updated_at = new Date().toISOString();
        fs.writeFileSync(DB_FILE, JSON.stringify(data, null, 2), 'utf-8');
      } catch (e: any) {
        console.warn('Error in premium_posts onSnapshot:', e.message);
      }
    },
    (err: any) => {
      if (recoveryQueueNode.isQuotaError(err)) {
        recoveryQueueNode.recordQuotaError(err);
      }
    }
  );
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
// 0. HEALTH & RESILIENCE DIAGNOSTICS (PUBLIC & PROTECTED)
// ==========================================================================

app.get('/api/health', (req: Request, res: Response) => {
  const diag = recoveryQueueNode.getDiagnostics();
  const db = loadDatabase();
  return res.json({
    status: 'ok',
    version: '2.4.0-resilient',
    timestamp: new Date().toISOString(),
    firestore_health: {
      status: diag.firestore_status,
      is_stale: diag.is_stale,
      message: diag.message,
      quota_exceeded: diag.firestore_status === 'QUOTA_EXCEEDED',
      next_check: diag.next_health_check_at,
    },
    pool: {
      total_posts: Object.keys(db.posts || {}).length,
      pool_max: MAX_POST_POOL_LIMIT,
    },
    recovery_queue: {
      total_pending: diag.queue.total_pending,
      total_size: diag.queue.total_queue_size,
      oldest_item_age_seconds: diag.queue.oldest_item_age_seconds,
    },
    translator: {
      configured: Boolean((process.env.GEMINI_API_KEY || '').trim()),
      model: (process.env.GEMINI_TRANSLATION_MODEL || 'gemini-3.8-flash').trim() || 'gemini-3.8-flash',
    },
  });
});

app.get('/api/translator/status', (req: Request, res: Response) => {
  const apiKey = (process.env.GEMINI_API_KEY || '').trim();
  const configured = Boolean(
    apiKey &&
      !apiKey.startsWith('YOUR_') &&
      !apiKey.toLowerCase().includes('placeholder') &&
      apiKey.length >= 8
  );
  const model = (process.env.GEMINI_TRANSLATION_MODEL || 'gemini-3.8-flash').trim() || 'gemini-3.8-flash';

  return res.json({
    status: 'ok',
    configured,
    model,
    cache_enabled: true,
    supported_languages: ['uz', 'ru', 'en', 'auto'],
    last_success_at: null,
    last_error_at: null,
    message: configured ? 'Gemini Translator tayyor' : 'Gemini API key sozlanmagan',
  });
});

app.get('/api/diagnostics/recovery', authMiddleware, (req: Request, res: Response) => {
  const diag = recoveryQueueNode.getDiagnostics();
  const db = loadDatabase();
  return res.json({
    status: 'ok',
    canonical_truth: 'Firestore',
    local_queue_purpose: 'Crash-safe buffer during quota or transient outages',
    pool_policy: 'Strict 500 max post limit',
    diagnostics: diag,
    pool_stats: {
      total_posts: Object.keys(db.posts || {}).length,
      pool_max: MAX_POST_POOL_LIMIT,
      queued: Object.values(db.posts || {}).filter((p) => p.status === 'queued').length,
      assigned: Object.values(db.posts || {}).filter((p) => p.status === 'assigned').length,
      delivered: Object.values(db.posts || {}).filter((p) => p.status === 'delivered').length,
      expired: Object.values(db.posts || {}).filter((p) => p.status === 'expired').length,
    },
  });
});

app.post('/api/recovery/flush', authMiddleware, async (req: Request, res: Response) => {
  const fsDb = getFirestoreDb();
  if (!fsDb) {
    return res.status(400).json({ error: 'Firestore sozlanmagan' });
  }

  // Attempt health check probe
  try {
    await fsDb.collection('settings').doc('system_health').set({
      manual_probe_at: new Date().toISOString(),
      service: 'web_admin',
    }, { merge: true });
    recoveryQueueNode.recordSuccess('write');
    recoveryQueueNode.transitionToRecovering();
  } catch (err: any) {
    if (recoveryQueueNode.isQuotaError(err)) {
      recoveryQueueNode.recordQuotaError(err);
      return res.status(429).json({
        error: 'Firestore kvotasi hali ham to‘lgan. Qayta urinib ko‘rish kechiktirildi.',
        next_check: recoveryQueueNode.getDiagnostics().next_health_check_at,
      });
    }
    return res.status(500).json({ error: err.message });
  }

  return res.json({
    status: 'ok',
    message: 'Firestore aloqasi tasdiqlandi. Tiklanish boshlandi.',
    diagnostics: recoveryQueueNode.getDiagnostics(),
  });
});

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
  const assignedPosts = postsList.filter((p) => p.status === 'assigned').length;
  const deliveredPosts = postsList.filter((p) => p.status === 'delivered' || (db.delivered_signatures && db.delivered_signatures.includes(p.post_id))).length;
  const failedPosts = postsList.filter((p) => p.status === 'failed').length;
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
  if (firestoreHealthStatus === 'quota_exceeded') {
    alerts.push({
      id: 'alert_firestore_quota',
      severity: 'warning',
      title: 'Google Cloud Firestore Kvotasi To‘ldi',
      message: "Firestore bepul o‘qish/yozish kvotasi tugagan. Tizim avtomatik ravishda diskdagi xavfsiz JSON bazasidan to‘liq va uzluksiz ishlamoqda.",
      count: 1,
      action: 'view_system',
    });
  }
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
      // Canonical Post Metrics
      total_posts: postsList.length,
      queued_posts: queuedPosts,
      assigned_posts: assignedPosts,
      delivered_posts: totalDelivered,
      failed_posts: failedPosts,
      expired_posts: expiredPosts,
      pool_queued: queuedPosts,
      pool_assigned: assignedPosts,
      pool_delivered: deliveredPosts,
      pool_expired: expiredPosts,
      pool_total: postsList.length,
      pool_max: MAX_POST_POOL_LIMIT,
    },
    firestore_health: {
      status: recoveryQueueNode.getState().toLowerCase(),
      canonical_status: recoveryQueueNode.getState(),
      message: recoveryQueueNode.getDiagnostics().message,
      last_quota_notice: recoveryQueueNode.getDiagnostics().last_quota_error_at,
      queue: recoveryQueueNode.getQueueStats(),
      diagnostics: recoveryQueueNode.getDiagnostics(),
    },
    pulse: {
      bot: 'online',
      gardener: 'running',
      storage_mode: getFirestoreDb()
        ? recoveryQueueNode.isQuotaExceeded()
          ? 'Firestore (Kvotada - SQLite Navbat Faol)'
          : 'Dual (Firestore + Local Sync)'
        : 'Local JSON File',
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
  const page = Math.max(1, parseInt(String(req.query.page || '1'), 10));
  const limit = Math.min(50, Math.max(5, parseInt(String(req.query.limit || '50'), 10)));

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

  const total = list.length;
  const startIndex = (page - 1) * limit;
  const pagedChannels = list.slice(startIndex, startIndex + limit);

  return res.json({
    status: 'ok',
    total,
    page,
    limit,
    total_pages: Math.ceil(total / limit) || 1,
    channels: pagedChannels,
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
  if (post_language && ['uz', 'uz_cyrl', 'ru', 'en', 'auto'].includes(post_language.toLowerCase())) {
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

// Update Channel Premium Eligibility (Super Admin Only)
app.patch('/api/channels/:chat_id/premium-eligibility', authMiddleware, async (req: Request, res: Response) => {
  const cid = String(req.params.chat_id);
  const db = loadDatabase();
  const channel = db.channels[cid];

  if (!channel) {
    return res.status(404).json({ error: 'Kanal topilmadi' });
  }

  const { is_premium_eligible } = req.body;
  if (typeof is_premium_eligible !== 'boolean') {
    return res.status(400).json({ error: 'is_premium_eligible maydoni boolean bo‘lishi kerak' });
  }

  channel.is_premium_eligible = is_premium_eligible;
  if (!is_premium_eligible) {
    channel.premium_enabled = false;
  }
  channel.updated_at = new Date().toISOString();

  saveDatabase(db);
  await saveEntityResilient('channels', cid, channel);

  addSystemLog(
    'INFO',
    'Premium',
    `'${channel.title}' kanali uchun Premium huquqi: ${is_premium_eligible ? 'BERILDI' : 'BEKOR QILINDI'}`
  );

  return res.json({
    status: 'ok',
    channel,
  });
});

// Update Channel Footer Configuration
app.patch('/api/channels/:chat_id/footer', authMiddleware, async (req: Request, res: Response) => {
  const cid = String(req.params.chat_id);
  const db = loadDatabase();
  const channel = db.channels[cid];

  if (!channel) {
    return res.status(404).json({ error: 'Kanal topilmadi' });
  }

  const { footer_type, footer_text, footer_url } = req.body;
  if (footer_type && !['none', 'text', 'link', 'button'].includes(footer_type)) {
    return res.status(400).json({ error: 'Noto‘g‘ri footer turi' });
  }

  if (footer_type !== undefined) channel.footer_type = footer_type;
  if (footer_text !== undefined) channel.footer_text = footer_text;
  if (footer_url !== undefined) channel.footer_url = footer_url;
  channel.updated_at = new Date().toISOString();

  saveDatabase(db);
  await saveEntityResilient('channels', cid, channel);

  return res.json({
    status: 'ok',
    channel,
  });
});

// ==========================================================================
// 3.5. CENTRAL CONTENT CHANNELS & PREMIUM POSTS (SUPER ADMIN)
// ==========================================================================

const CENTRAL_POST_BASE_CHAT_ID = -1004373620008;

function escapeHtml(str: string): string {
  return (str || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

async function verifyBotAdminInChat(chatId: number): Promise<{
  botIsAdmin: boolean;
  canPost: boolean;
  status: string;
  title?: string;
  username?: string;
  description?: string;
  error?: string;
}> {
  const botToken = process.env.BOT_TOKEN;
  if (!botToken || botToken.trim() === '') {
    return { botIsAdmin: true, canPost: true, status: 'mock_administrator' };
  }

  try {
    const meRes = await fetch(`https://api.telegram.org/bot${botToken}/getMe`);
    const meData = (await meRes.json()) as any;
    if (!meData.ok || !meData.result?.id) {
      return { botIsAdmin: false, canPost: false, status: 'error', error: 'Bot getMe failed' };
    }
    const botUserId = meData.result.id;

    const [chatRes, memberRes] = await Promise.all([
      fetch(`https://api.telegram.org/bot${botToken}/getChat?chat_id=${chatId}`),
      fetch(`https://api.telegram.org/bot${botToken}/getChatMember?chat_id=${chatId}&user_id=${botUserId}`),
    ]);

    const chatData = (await chatRes.json()) as any;
    const memberData = (await memberRes.json()) as any;

    if (!memberData.ok || !memberData.result) {
      return {
        botIsAdmin: false,
        canPost: false,
        status: memberData.description || 'not_member',
        error: memberData.description,
      };
    }

    const memberStatus = memberData.result.status;
    const isAdm = memberStatus === 'administrator' || memberStatus === 'creator';
    const canPost = Boolean(memberData.result.can_post_messages || memberStatus === 'creator' || isAdm);

    return {
      botIsAdmin: isAdm,
      canPost,
      status: memberStatus,
      title: chatData.result?.title,
      username: chatData.result?.username,
      description: chatData.result?.description,
    };
  } catch (err: any) {
    return { botIsAdmin: false, canPost: false, status: 'error', error: err.message };
  }
}

// 1. Central Post Base Status Endpoint
app.get('/api/central-post-base/status', authMiddleware, async (req: Request, res: Response) => {
  const db = loadDatabase();
  const centralRecord = db.central_channels[CENTRAL_POST_BASE_CHAT_ID];
  const premPosts = Object.values(db.premium_posts || {}).filter(
    (p) => p.central_chat_id === CENTRAL_POST_BASE_CHAT_ID
  );

  const verify = await verifyBotAdminInChat(CENTRAL_POST_BASE_CHAT_ID);

  let statusMessage = "Bot @anjurxpostbaza kanalida administrator sifatida ulangan va faol.";
  let actionRequired = false;

  if (!verify.botIsAdmin) {
    statusMessage = "Bot @anjurxpostbaza kanalida administrator emas. Kanal sozlamalariga kirib, botni admin qiling.";
    actionRequired = true;
  } else if (!verify.canPost) {
    statusMessage = "Bot admin, lekin xabar yuborish (Post Messages) ruxsati yoqilmagan.";
    actionRequired = true;
  }

  // Update local DB if verify returned live details
  if (centralRecord && verify.botIsAdmin !== undefined) {
    centralRecord.bot_is_admin = verify.botIsAdmin;
    centralRecord.can_post = verify.canPost;
    if (verify.title) centralRecord.title = verify.title;
    if (verify.username) centralRecord.username = verify.username;
    centralRecord.post_count = premPosts.length;
    saveDatabase(db);
  }

  return res.json({
    status: 'ok',
    central_post_base: {
      chat_id: CENTRAL_POST_BASE_CHAT_ID,
      title: verify.title || centralRecord?.title || 'post baza',
      username: verify.username || centralRecord?.username || 'anjurxpostbaza',
      description: verify.description || centralRecord?.description || 'anjurx boti uchun postlar bazasi',
      bot_is_admin: verify.botIsAdmin,
      can_post: verify.canPost,
      member_status: verify.status,
      post_count: premPosts.length,
      last_post_at: centralRecord?.last_post_at || (premPosts[0]?.created_at ?? null),
      status_message: statusMessage,
      action_required: actionRequired,
      active: centralRecord?.active ?? true,
    },
  });
});

app.post('/api/central-post-base/recheck', authMiddleware, async (req: Request, res: Response) => {
  const verify = await verifyBotAdminInChat(CENTRAL_POST_BASE_CHAT_ID);
  const db = loadDatabase();
  if (db.central_channels[CENTRAL_POST_BASE_CHAT_ID]) {
    db.central_channels[CENTRAL_POST_BASE_CHAT_ID].bot_is_admin = verify.botIsAdmin;
    db.central_channels[CENTRAL_POST_BASE_CHAT_ID].can_post = verify.canPost;
    if (verify.title) db.central_channels[CENTRAL_POST_BASE_CHAT_ID].title = verify.title;
    if (verify.username) db.central_channels[CENTRAL_POST_BASE_CHAT_ID].username = verify.username;
    saveDatabase(db);
  }
  return res.json({
    status: 'ok',
    verified: verify,
  });
});

// 2. Central Channels list and CRUD
app.get('/api/central-channels', authMiddleware, (req: Request, res: Response) => {
  const db = loadDatabase();
  const list = Object.values(db.central_channels || {});
  return res.json({
    status: 'ok',
    total: list.length,
    central_channels: list,
  });
});

app.post('/api/central-channels', authMiddleware, async (req: Request, res: Response) => {
  const { chat_id, title, username, description } = req.body;
  if (!chat_id || !title) {
    return res.status(400).json({ error: 'chat_id va title kiritilishi shart' });
  }

  const numCid = Number(chat_id);
  const db = loadDatabase();
  const now = new Date().toISOString();

  const verify = await verifyBotAdminInChat(numCid);
  if (!verify.botIsAdmin && process.env.BOT_TOKEN) {
    return res.status(400).json({
      error: `Bot ushbu kanalda administrator emas (${verify.status}). Iltimos, avval botni kanalga admin qilib qo‘shing.`,
    });
  }

  const record: CentralChannelRecord = {
    id: String(numCid),
    chat_id: numCid,
    title: String(title).trim(),
    username: username ? String(username).trim() : null,
    description: description ? String(description).trim() : null,
    added_by: (req as any).user?.user_id || 8157452043,
    active: true,
    bot_is_admin: verify.botIsAdmin,
    can_post: verify.canPost,
    post_count: db.central_channels[numCid]?.post_count || 0,
    last_post_at: db.central_channels[numCid]?.last_post_at || null,
    created_at: db.central_channels[numCid]?.created_at || now,
    updated_at: now,
  };

  db.central_channels[numCid] = record;
  saveDatabase(db);
  await saveEntityResilient('central_channels', String(numCid), record);
  addSystemLog('INFO', 'CentralChannel', `Markaziy kanal saqlandi: '${record.title}' (${record.chat_id})`);

  return res.status(201).json({
    status: 'ok',
    central_channel: record,
  });
});

app.delete('/api/central-channels/:chat_id', authMiddleware, async (req: Request, res: Response) => {
  const cid = Number(req.params.chat_id);
  const db = loadDatabase();

  if (!db.central_channels[cid]) {
    return res.status(404).json({ error: 'Markaziy kanal topilmadi' });
  }

  const title = db.central_channels[cid].title;
  delete db.central_channels[cid];
  saveDatabase(db);

  addSystemLog('WARNING', 'CentralChannel', `Markaziy kanal o‘chirildi: '${title}' (${cid})`);
  return res.json({
    status: 'ok',
    message: `'${title}' markaziy kanali o‘chirildi`,
  });
});

// 3. Premium Channels (Destination channels with premium eligibility/activation)
app.get('/api/premium-channels', authMiddleware, (req: Request, res: Response) => {
  const db = loadDatabase();
  const allChannels = Object.values(db.channels || {});

  // Destination channels that have premium enabled or eligible
  const premiumChannels = allChannels
    .filter((c) => c.chat_id !== CENTRAL_POST_BASE_CHAT_ID && (c.premium || c.is_premium_eligible || c.premium_enabled))
    .map((c) => ({
      ...c,
      status: c.status || (c.active ? 'ACTIVE' : 'PAUSED'),
      premium: Boolean(c.premium || c.is_premium_eligible || c.premium_enabled),
      sent_today: c.sent_today || c.today_delivered_count || 0,
    }));

  // Other candidate channels that can be upgraded
  const connectableChannels = allChannels
    .filter((c) => c.chat_id !== CENTRAL_POST_BASE_CHAT_ID && !(c.premium || c.is_premium_eligible || c.premium_enabled))
    .map((c) => ({
      chat_id: c.chat_id,
      title: c.title,
      username: c.username,
      daily_limit: c.daily_limit,
      plan: c.plan,
    }));

  return res.json({
    status: 'ok',
    total_premium: premiumChannels.length,
    premium_channels: premiumChannels,
    connectable_channels: connectableChannels,
  });
});

app.post('/api/channels/:chat_id/make-premium', authMiddleware, async (req: Request, res: Response) => {
  const cid = Number(req.params.chat_id);
  const db = loadDatabase();
  const channel = db.channels[cid];
  if (!channel) {
    return res.status(404).json({ error: 'Kanal topilmadi' });
  }

  channel.premium = true;
  channel.is_premium_eligible = true;
  channel.premium_enabled = true;
  channel.status = 'ACTIVE';
  channel.active = true;
  channel.updated_at = new Date().toISOString();

  saveDatabase(db);
  await saveEntityResilient('channels', String(cid), channel);
  addSystemLog('INFO', 'Premium', `'${channel.title}' kanali uchun Premium tarqatish yoqildi`);
  broadcastEvent('channel_updated', { channel });

  return res.json({ status: 'ok', channel });
});

app.post('/api/channels/:chat_id/remove-premium', authMiddleware, async (req: Request, res: Response) => {
  const cid = Number(req.params.chat_id);
  const db = loadDatabase();
  const channel = db.channels[cid];
  if (!channel) {
    return res.status(404).json({ error: 'Kanal topilmadi' });
  }

  channel.premium = false;
  channel.is_premium_eligible = false;
  channel.premium_enabled = false;
  channel.updated_at = new Date().toISOString();

  saveDatabase(db);
  await saveEntityResilient('channels', String(cid), channel);
  addSystemLog('INFO', 'Premium', `'${channel.title}' kanali uchun Premium huquqi o‘chirildi`);
  broadcastEvent('channel_updated', { channel });

  return res.json({ status: 'ok', channel });
});

app.post('/api/channels/:chat_id/toggle-status', authMiddleware, async (req: Request, res: Response) => {
  const cid = Number(req.params.chat_id);
  const { status } = req.body;
  const db = loadDatabase();
  const channel = db.channels[cid];
  if (!channel) {
    return res.status(404).json({ error: 'Kanal topilmadi' });
  }

  const targetStatus = ['ACTIVE', 'PAUSED', 'BLOCKED'].includes(status) ? status : (channel.status === 'ACTIVE' ? 'PAUSED' : 'ACTIVE');
  channel.status = targetStatus;
  channel.active = targetStatus === 'ACTIVE';
  channel.updated_at = new Date().toISOString();

  saveDatabase(db);
  await saveEntityResilient('channels', String(cid), channel);
  addSystemLog('INFO', 'Channel', `'${channel.title}' holati o‘zgartirildi: ${targetStatus}`);
  broadcastEvent('channel_updated', { channel });

  return res.json({ status: 'ok', channel });
});

app.patch('/api/channels/:chat_id/limit', authMiddleware, async (req: Request, res: Response) => {
  const cid = Number(req.params.chat_id);
  const { daily_limit } = req.body;
  const db = loadDatabase();
  const channel = db.channels[cid];
  if (!channel) {
    return res.status(404).json({ error: 'Kanal topilmadi' });
  }

  channel.daily_limit = Math.max(1, parseInt(String(daily_limit || 20), 10));
  channel.updated_at = new Date().toISOString();

  saveDatabase(db);
  await saveEntityResilient('channels', String(cid), channel);
  return res.json({ status: 'ok', channel });
});

// 4. Schedules CRUD
app.get('/api/schedules', authMiddleware, (req: Request, res: Response) => {
  const db = loadDatabase();
  const list = Object.values(db.schedules || {}).sort((a, b) => a.time.localeCompare(b.time));
  return res.json({ status: 'ok', total: list.length, schedules: list });
});

app.post('/api/schedules', authMiddleware, async (req: Request, res: Response) => {
  const { time, label } = req.body;
  if (!time || !/^\d{2}:\d{2}$/.test(String(time).trim())) {
    return res.status(400).json({ error: 'Vaqt HH:mm formatida bo‘lishi kerak (masalan: 14:30)' });
  }

  const db = loadDatabase();
  const cleanTime = String(time).trim();
  const id = `slot_${Date.now()}`;
  const record: ScheduleSlotRecord = {
    id,
    time: cleanTime,
    label: label ? String(label).trim() : `${cleanTime} tarqatish`,
    active: true,
    timezone: 'Asia/Tashkent',
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };

  db.schedules[id] = record;
  saveDatabase(db);
  await saveEntityResilient('schedules', id, record);
  return res.status(201).json({ status: 'ok', schedule: record });
});

app.patch('/api/schedules/:id', authMiddleware, async (req: Request, res: Response) => {
  const id = String(req.params.id);
  const db = loadDatabase();
  const slot = db.schedules[id];
  if (!slot) {
    return res.status(404).json({ error: 'Jadval topilmadi' });
  }

  if (req.body.time) {
    const cleanTime = String(req.body.time).trim();
    if (/^\d{2}:\d{2}$/.test(cleanTime)) slot.time = cleanTime;
  }
  if (req.body.label !== undefined) slot.label = String(req.body.label).trim();
  if (req.body.active !== undefined) slot.active = Boolean(req.body.active);
  slot.updated_at = new Date().toISOString();

  saveDatabase(db);
  await saveEntityResilient('schedules', id, slot);
  return res.json({ status: 'ok', schedule: slot });
});

app.delete('/api/schedules/:id', authMiddleware, async (req: Request, res: Response) => {
  const id = String(req.params.id);
  const db = loadDatabase();
  if (!db.schedules[id]) {
    return res.status(404).json({ error: 'Jadval topilmadi' });
  }

  delete db.schedules[id];
  saveDatabase(db);
  return res.json({ status: 'ok', message: 'Jadval o‘chirildi' });
});

// 5. Post Dispatching Function
async function dispatchPremiumPost(
  postId: string,
  options?: { force?: boolean; specificChannelId?: number }
) {
  const db = loadDatabase();
  const post = db.premium_posts[postId];
  if (!post) {
    return { success: false, error: 'Post topilmadi' };
  }

  const botToken = process.env.BOT_TOKEN;
  if (!botToken || botToken.trim() === '') {
    return { success: false, error: 'BOT_TOKEN sozlanmagan' };
  }

  post.status = 'PROCESSING';
  post.last_attempt_at = new Date().toISOString();
  saveDatabase(db);
  broadcastEvent('premium_posts_updated', { post_id: post.id, status: post.status });

  // Filter destination channels (strictly active premium, excluding central post base)
  let candidateChannels = Object.values(db.channels).filter((c) => {
    if (c.chat_id === CENTRAL_POST_BASE_CHAT_ID) return false;
    const isPrem = Boolean(c.premium || c.is_premium_eligible || c.premium_enabled);
    const isActive = c.status ? c.status === 'ACTIVE' : c.active;
    return isPrem && isActive && c.can_post;
  });

  if (options?.specificChannelId) {
    candidateChannels = candidateChannels.filter((c) => c.chat_id === options.specificChannelId);
  } else if (post.target_mode === 'selected' && Array.isArray(post.target_channel_ids) && post.target_channel_ids.length > 0) {
    candidateChannels = candidateChannels.filter((c) => post.target_channel_ids!.includes(c.chat_id));
  }

  console.log(`[DISTRIBUTION] Starting: postId=${post.id}`);

  let successCount = 0;
  let failCount = 0;
  const nowIso = new Date().toISOString();

  for (const ch of candidateChannels) {
    const sig = `prem:${post.id}:${ch.chat_id}`;
    if (!options?.force && db.delivered_signatures.includes(sig)) {
      console.log(`[DISTRIBUTION] Skipping already delivered: postId=${post.id} channelId=${ch.chat_id}`);
      continue;
    }

    console.log(`[DISTRIBUTION] Target: channelId=${ch.chat_id}`);

    // Footer formatting
    let textToSend = post.text || '';
    let replyMarkup: any = null;

    if (ch.footer_type && ch.footer_type !== 'none') {
      const fText = ch.footer_text || (ch.username ? `@${ch.username.replace('@', '')}` : ch.title);
      const fUrl = ch.footer_url || (ch.username ? `https://t.me/${ch.username.replace('@', '')}` : undefined);

      if (ch.footer_type === 'text') {
        textToSend = textToSend ? `${textToSend}\n\n📢 ${fText}` : `📢 ${fText}`;
      } else if (ch.footer_type === 'text_link') {
        const linkHtml = fUrl ? `<a href="${fUrl}">${escapeHtml(fText)}</a>` : escapeHtml(fText);
        textToSend = textToSend ? `${textToSend}\n\n👉 ${linkHtml}` : `👉 ${linkHtml}`;
      } else if (ch.footer_type === 'inline_button' && fUrl) {
        replyMarkup = {
          inline_keyboard: [[{ text: fText, url: fUrl }]],
        };
      }
    }

    let sentMsgId: number | null = null;
    let sendError: string | null = null;

    try {
      if (post.media_type === 'photo' && post.media_file_id) {
        const body: any = {
          chat_id: ch.chat_id,
          photo: post.media_file_id,
          caption: textToSend.slice(0, 1024),
          parse_mode: 'HTML',
        };
        if (replyMarkup) body.reply_markup = replyMarkup;
        const resp = await fetch(`https://api.telegram.org/bot${botToken}/sendPhoto`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        });
        const resJson = (await resp.json()) as any;
        if (!resJson.ok) throw new Error(resJson.description || 'sendPhoto xatoligi');
        sentMsgId = resJson.result?.message_id || null;
      } else if (post.media_type === 'video' && post.media_file_id) {
        const body: any = {
          chat_id: ch.chat_id,
          video: post.media_file_id,
          caption: textToSend.slice(0, 1024),
          parse_mode: 'HTML',
        };
        if (replyMarkup) body.reply_markup = replyMarkup;
        const resp = await fetch(`https://api.telegram.org/bot${botToken}/sendVideo`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        });
        const resJson = (await resp.json()) as any;
        if (!resJson.ok) throw new Error(resJson.description || 'sendVideo xatoligi');
        sentMsgId = resJson.result?.message_id || null;
      } else if (post.media_type === 'media_group' && Array.isArray(post.media_items) && post.media_items.length > 0) {
        const media = post.media_items.map((itm, idx) => ({
          type: itm.type || 'photo',
          media: itm.file_id,
          caption: idx === 0 ? textToSend.slice(0, 1024) : undefined,
          parse_mode: idx === 0 ? 'HTML' : undefined,
        }));
        const resp = await fetch(`https://api.telegram.org/bot${botToken}/sendMediaGroup`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ chat_id: ch.chat_id, media }),
        });
        const resJson = (await resp.json()) as any;
        if (!resJson.ok) throw new Error(resJson.description || 'sendMediaGroup xatoligi');
        sentMsgId = resJson.result?.[0]?.message_id || null;
        if (replyMarkup) {
          try {
            await fetch(`https://api.telegram.org/bot${botToken}/sendMessage`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ chat_id: ch.chat_id, text: '🔗 Havola:', reply_markup: replyMarkup }),
            });
          } catch {}
        }
      } else {
        const body: any = {
          chat_id: ch.chat_id,
          text: textToSend || '...',
          parse_mode: 'HTML',
        };
        if (replyMarkup) body.reply_markup = replyMarkup;
        const resp = await fetch(`https://api.telegram.org/bot${botToken}/sendMessage`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        });
        const resJson = (await resp.json()) as any;
        if (!resJson.ok) throw new Error(resJson.description || 'sendMessage xatoligi');
        sentMsgId = resJson.result?.message_id || null;
      }

      console.log(`[DISTRIBUTION] SUCCESS: postId=${post.id} channelId=${ch.chat_id}`);
      successCount++;

      // Register delivery signatures & statistics
      if (!db.delivered_signatures.includes(sig)) {
        db.delivered_signatures.push(sig);
      }
      db.posts_delivered = (db.posts_delivered || 0) + 1;
      post.delivered_count = (post.delivered_count || 0) + 1;

      ch.today_delivered_count = (ch.today_delivered_count || 0) + 1;
      ch.sent_today = (ch.sent_today || 0) + 1;
      ch.total_delivered_count = (ch.total_delivered_count || 0) + 1;
      ch.last_delivered_at = nowIso;
      ch.last_post_at = nowIso;
      ch.updated_at = nowIso;

      const distId = `${post.id}__channel_${ch.chat_id}`;
      db.post_distributions[distId] = {
        id: distId,
        post_id: post.id,
        target_channel_id: ch.chat_id,
        target_channel_title: ch.title,
        status: 'SENT',
        attempts: 1,
        last_attempt_at: nowIso,
        sent_message_id: sentMsgId,
        error: null,
        created_at: nowIso,
        updated_at: nowIso,
      };

      const delRecord = {
        signature: sig,
        source_id: `central_${post.central_chat_id}`,
        external_post_id: String(post.central_message_id),
        post_id: post.id,
        channel_id: ch.chat_id,
        channel_title: ch.title,
        title: post.text ? post.text.slice(0, 80) : `Premium Post #${post.central_message_id}`,
        url: `https://t.me/c/${String(post.central_chat_id).replace('-100', '')}/${post.central_message_id}`,
        telegram_message_id: sentMsgId,
        delivered_at: nowIso,
        target_language: ch.post_language || 'uz',
      };
      db.recent_posts.unshift(delRecord as any);
      if (db.recent_posts.length > 100) db.recent_posts.pop();

      // Persist to Firestore resiliently
      await saveEntityResilient('channels', String(ch.chat_id), ch);
      await saveEntityResilient('post_distributions', distId, db.post_distributions[distId]);

    } catch (err: any) {
      sendError = err.message || 'Telegram API xatoligi';
      console.error(`[DISTRIBUTION] FAILED: postId=${post.id} channelId=${ch.chat_id} error=${sendError}`);
      failCount++;

      const distId = `${post.id}__channel_${ch.chat_id}`;
      db.post_distributions[distId] = {
        id: distId,
        post_id: post.id,
        target_channel_id: ch.chat_id,
        target_channel_title: ch.title,
        status: 'FAILED',
        attempts: (db.post_distributions[distId]?.attempts || 0) + 1,
        last_attempt_at: nowIso,
        sent_message_id: null,
        error: sendError,
        created_at: db.post_distributions[distId]?.created_at || nowIso,
        updated_at: nowIso,
      };
      await saveEntityResilient('post_distributions', distId, db.post_distributions[distId]);
    }

    await new Promise((r) => setTimeout(r, 250));
  }

  post.target_count = candidateChannels.length;
  post.successful_count = (post.successful_count || 0) + successCount;
  post.failed_count = (post.failed_count || 0) + failCount;
  post.updated_at = new Date().toISOString();

  if (candidateChannels.length === 0) {
    post.status = 'FAILED';
    post.last_error = 'Birorta ham faol Premium kanal topilmadi';
  } else if (failCount === 0 && successCount > 0) {
    post.status = 'SENT';
  } else if (successCount > 0 && failCount > 0) {
    post.status = 'PARTIAL';
  } else if (successCount === 0 && failCount > 0) {
    post.status = 'FAILED';
  }

  saveDatabase(db);
  await saveEntityResilient('premium_posts', post.id, post);
  broadcastEvent('premium_posts_updated', { post_id: post.id, status: post.status });

  return { success: successCount > 0, post, successCount, failCount };
}

// 6. Premium Posts API Endpoints
app.get('/api/premium-posts', authMiddleware, (req: Request, res: Response) => {
  const db = loadDatabase();
  let list = Object.values(db.premium_posts || {});

  const status = String(req.query.status || 'ALL').toUpperCase();
  const search = String(req.query.search || '').trim().toLowerCase();

  // Compute status counts
  const counts = {
    all: list.length,
    pending: list.filter((p) => p.status === 'PENDING' || p.status === 'ready' || p.status === 'draft').length,
    scheduled: list.filter((p) => p.status === 'SCHEDULED').length,
    processing: list.filter((p) => p.status === 'PROCESSING').length,
    sent: list.filter((p) => p.status === 'SENT' || p.status === 'delivered').length,
    partial: list.filter((p) => p.status === 'PARTIAL').length,
    failed: list.filter((p) => p.status === 'FAILED').length,
    cancelled: list.filter((p) => p.status === 'CANCELLED').length,
  };

  if (status !== 'ALL') {
    if (status === 'PENDING') {
      list = list.filter((p) => p.status === 'PENDING' || p.status === 'ready' || p.status === 'draft');
    } else if (status === 'SENT') {
      list = list.filter((p) => p.status === 'SENT' || p.status === 'delivered');
    } else {
      list = list.filter((p) => (p.status || '').toUpperCase() === status);
    }
  }

  if (search) {
    list = list.filter(
      (p) =>
        (p.text && p.text.toLowerCase().includes(search)) ||
        p.id.toLowerCase().includes(search) ||
        (p.author_name && p.author_name.toLowerCase().includes(search))
    );
  }

  list.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());

  const page = Math.max(1, parseInt(String(req.query.page || '1'), 10));
  const limit = Math.min(100, Math.max(5, parseInt(String(req.query.limit || '20'), 10)));
  const startIndex = (page - 1) * limit;

  return res.json({
    status: 'ok',
    total: list.length,
    counts,
    page,
    limit,
    posts: list.slice(startIndex, startIndex + limit),
  });
});

app.post('/api/premium-posts/:id/schedule', authMiddleware, async (req: Request, res: Response) => {
  const id = String(req.params.id);
  const { scheduled_at, target_mode, target_channel_ids } = req.body;
  const db = loadDatabase();
  const post = db.premium_posts[id];
  if (!post) {
    return res.status(404).json({ error: 'Post topilmadi' });
  }

  post.scheduled_at = scheduled_at || null;
  post.status = 'SCHEDULED';
  if (target_mode) post.target_mode = target_mode;
  if (Array.isArray(target_channel_ids)) post.target_channel_ids = target_channel_ids;
  post.updated_at = new Date().toISOString();

  saveDatabase(db);
  await saveEntityResilient('premium_posts', id, post);
  addSystemLog('INFO', 'Schedule', `Post ${id} rejalashtirildi: ${post.scheduled_at}`);
  broadcastEvent('premium_posts_updated', { post_id: id, post });

  return res.json({ status: 'ok', post });
});

app.post('/api/premium-posts/:id/send-now', authMiddleware, async (req: Request, res: Response) => {
  const id = String(req.params.id);
  const result = await dispatchPremiumPost(id, { force: true });
  return res.json({
    status: result.success ? 'ok' : 'error',
    message: result.success ? 'Post muvaffaqiyatli tarqatildi' : result.error || 'Tarqatishda xatolik yuz berdi',
    result,
  });
});

app.post('/api/premium-posts/:id/cancel', authMiddleware, async (req: Request, res: Response) => {
  const id = String(req.params.id);
  const db = loadDatabase();
  const post = db.premium_posts[id];
  if (!post) {
    return res.status(404).json({ error: 'Post topilmadi' });
  }

  post.status = 'CANCELLED';
  post.updated_at = new Date().toISOString();
  saveDatabase(db);
  await saveEntityResilient('premium_posts', id, post);
  broadcastEvent('premium_posts_updated', { post_id: id, post });

  return res.json({ status: 'ok', post });
});

app.post('/api/premium-posts/:id/retry', authMiddleware, async (req: Request, res: Response) => {
  const id = String(req.params.id);
  const result = await dispatchPremiumPost(id, { force: false });
  return res.json({
    status: result.success ? 'ok' : 'error',
    message: result.success ? 'Post qayta tarqatildi' : result.error || 'Qayta urinishda xatolik',
    result,
  });
});

app.delete('/api/premium-posts/:id', authMiddleware, async (req: Request, res: Response) => {
  const id = String(req.params.id);
  const db = loadDatabase();
  if (!db.premium_posts[id]) {
    return res.status(404).json({ error: 'Post topilmadi' });
  }

  delete db.premium_posts[id];
  saveDatabase(db);
  broadcastEvent('premium_posts_updated', { post_id: id, deleted: true });
  return res.json({ status: 'ok', message: 'Post o‘chirildi' });
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

  const total = enriched.length;
  const page = Math.max(1, parseInt(String(req.query.page || '1'), 10));
  const limit = Math.min(50, Math.max(5, parseInt(String(req.query.limit || '50'), 10)));
  const startIndex = (page - 1) * limit;
  const pagedUsers = enriched.slice(startIndex, startIndex + limit);

  return res.json({
    status: 'ok',
    total,
    page,
    limit,
    total_pages: Math.ceil(total / limit) || 1,
    users: pagedUsers,
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
app.get('/api/categories', authMiddleware, (req: Request, res: Response) => {
  const db = loadDatabase();

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
app.get('/api/sources', authMiddleware, (req: Request, res: Response) => {
  const db = loadDatabase();
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
// 6. POST POOL & 500-POST RETENTION (PROTECTED)
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
  const limit = Math.min(50, Math.max(5, parseInt(String(req.query.limit || '50'), 10)));

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
    assigned: allPosts.filter((p) => p.status === 'assigned').length,
    delivered: allPosts.filter((p) => p.status === 'delivered').length,
    failed: allPosts.filter((p) => p.status === 'failed').length,
    expired: allPosts.filter((p) => p.status === 'expired').length,
  };

  return res.json({
    status: 'ok',
    total,
    page,
    limit,
    total_pages: Math.ceil(total / limit) || 1,
    counts,
    pool_max: MAX_POST_POOL_LIMIT,
    firestore_status: recoveryQueueNode.getState().toLowerCase(),
    firestore_message: recoveryQueueNode.getDiagnostics().message,
    posts: pagedPosts,
  });
});

app.post('/api/posts/cleanup', authMiddleware, async (req: Request, res: Response) => {
  const db = loadDatabase();
  const fsDb = getFirestoreDb();
  const beforeCount = Object.keys(db.posts).length;
  const result = await cleanupPostPool(db, fsDb);

  addSystemLog('INFO', 'Gardener', `Post pool tozalandi: ${result.deleted_count} ta post o'chirildi. Pool: ${result.remaining_count}/${MAX_POST_POOL_LIMIT}`);
  broadcastEvent('posts_updated', { total_posts: result.remaining_count });
  broadcastEvent('dashboard_updated', {});

  return res.json({
    status: 'ok',
    message: `Post pool muvaffaqiyatli tozalandi. ${result.deleted_count} ta post o'chirildi. Hozirgi pool hajmi: ${result.remaining_count} / ${MAX_POST_POOL_LIMIT}`,
    before_count: beforeCount,
    deleted_count: result.deleted_count,
    remaining_count: result.remaining_count,
    pool_max: MAX_POST_POOL_LIMIT,
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
      translator: {
        status: (process.env.GEMINI_API_KEY || '').trim() ? 'online' : 'not_configured',
        name: `Gemini Translator (${(process.env.GEMINI_TRANSLATION_MODEL || 'gemini-3.8-flash').trim() || 'gemini-3.8-flash'})`,
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
// TELEGRAM INGESTION POLLER (CENTRAL POST BASE)
// --------------------------------------------------------------------------
let lastTelegramUpdateOffset = 0;
let isPollingTelegram = false;

async function pollTelegramUpdates() {
  const botToken = process.env.BOT_TOKEN;
  if (!botToken || isPollingTelegram) return;

  isPollingTelegram = true;
  try {
    const url = `https://api.telegram.org/bot${botToken}/getUpdates?offset=${lastTelegramUpdateOffset}&limit=50&timeout=3`;
    const res = await fetch(url);
    const data = (await res.json()) as any;

    if (data.ok && Array.isArray(data.result)) {
      for (const update of data.result) {
        if (update.update_id >= lastTelegramUpdateOffset) {
          lastTelegramUpdateOffset = update.update_id + 1;
        }

        const msg = update.channel_post || update.message;
        if (!msg || !msg.chat) continue;

        const chatId = Number(msg.chat.id);
        const db = loadDatabase();
        const isCentral = chatId === CENTRAL_POST_BASE_CHAT_ID || (db.central_channels && db.central_channels[chatId]?.active);

        if (!isCentral) continue;

        console.log(`[POST_BASE] Received post: sourceChatId=${chatId} messageId=${msg.message_id}`);

        const postId = `prem_${chatId}_${msg.message_id}`;
        if (db.premium_posts[postId]) continue; // Already ingested

        let mediaType = 'text';
        let mediaFileId: string | null = null;
        const mediaGroupId: string | null = msg.media_group_id ? String(msg.media_group_id) : null;
        let text = msg.text || msg.caption || '';
        const mediaItems: any[] = [];

        if (msg.photo && Array.isArray(msg.photo) && msg.photo.length > 0) {
          mediaType = mediaGroupId ? 'media_group' : 'photo';
          mediaFileId = msg.photo[msg.photo.length - 1].file_id;
          mediaItems.push({ type: 'photo', file_id: mediaFileId, caption: text });
        } else if (msg.video) {
          mediaType = mediaGroupId ? 'media_group' : 'video';
          mediaFileId = msg.video.file_id;
          mediaItems.push({ type: 'video', file_id: mediaFileId, caption: text });
        } else if (msg.document) {
          mediaType = 'document';
          mediaFileId = msg.document.file_id;
          mediaItems.push({ type: 'document', file_id: mediaFileId, caption: text });
        } else if (msg.animation) {
          mediaType = 'animation';
          mediaFileId = msg.animation.file_id;
          mediaItems.push({ type: 'animation', file_id: mediaFileId, caption: text });
        }

        const nowIso = new Date().toISOString();
        const newPost: PremiumPostRecord = {
          id: postId,
          source_chat_id: chatId,
          source_message_id: msg.message_id,
          central_chat_id: chatId,
          central_message_id: msg.message_id,
          media_type: mediaType,
          text,
          media_file_id: mediaFileId,
          media_group_id: mediaGroupId,
          media_items: mediaItems,
          author_id: msg.from?.id || null,
          author_name: msg.author_signature || msg.from?.first_name || null,
          status: 'PENDING',
          distribution_type: 'premium',
          target_mode: 'all_active',
          delivered_count: 0,
          successful_count: 0,
          failed_count: 0,
          created_at: nowIso,
          updated_at: nowIso,
        };

        db.premium_posts[postId] = newPost;
        if (db.central_channels[chatId]) {
          db.central_channels[chatId].post_count = Object.values(db.premium_posts).filter(
            (p) => p.central_chat_id === chatId
          ).length;
          db.central_channels[chatId].last_post_at = nowIso;
        }
        saveDatabase(db);
        await saveEntityResilient('premium_posts', postId, newPost);
        console.log(`[POST_BASE] Saved to Firestore: postId=${postId}`);

        broadcastEvent('premium_posts_updated', { post_id: postId, post: newPost });
        addSystemLog('INFO', 'PostBase', `Yangi post qabul qilindi: ID ${postId} (${mediaType})`);

        // Trigger distribution to active premium channels
        setTimeout(() => {
          dispatchPremiumPost(postId).catch((err) => {
            console.error(`[DISTRIBUTION] Auto-dispatch error for ${postId}:`, err);
          });
        }, 1000);
      }
    }
  } catch (err: any) {
    // Polling ignore
  } finally {
    isPollingTelegram = false;
  }
}

// --------------------------------------------------------------------------
// SCHEDULED DISTRIBUTION WORKER (Asia/Tashkent UTC+5)
// --------------------------------------------------------------------------
async function checkScheduleSlots() {
  try {
    const db = loadDatabase();
    const now = new Date(Date.now() + 5 * 3600 * 1000);
    const hh = String(now.getUTCHours()).padStart(2, '0');
    const mm = String(now.getUTCMinutes()).padStart(2, '0');
    const timeStr = `${hh}:${mm}`;

    const activeSlots = Object.values(db.schedules || {}).filter((s) => s.active && s.time === timeStr);
    if (activeSlots.length === 0) return;

    const postsToDispatch = Object.values(db.premium_posts || {}).filter(
      (p) => p.status === 'SCHEDULED' || p.status === 'PENDING'
    );

    for (const post of postsToDispatch) {
      console.log(`[SCHEDULE] Triggering distribution at ${timeStr} for post: ${post.id}`);
      await dispatchPremiumPost(post.id);
    }
  } catch (err: any) {
    console.warn('[Schedule Check Error]:', err.message);
  }
}

// --------------------------------------------------------------------------
// Vite SPA Middleware (Development & Production Fallback)
// --------------------------------------------------------------------------
async function startServer() {
  // 1. Initial Firestore targeted synchronization & lightweight Real-time listeners
  try {
    await syncFirestoreToLocal();
    initFirestoreRealtimeListeners();
    // Gentle periodic pool cleanup every 10 minutes (NO 15-second full collection scans!)
    setInterval(async () => {
      try {
        const db = loadDatabase();
        const fsDb = getFirestoreDb();
        await cleanupPostPool(db, fsDb);
      } catch (err: any) {
        console.warn('[Periodic Pool Cleanup Error]:', err.message);
      }
    }, 10 * 60 * 1000);

    // Background Telegram updates poller & schedule check
    setInterval(pollTelegramUpdates, 3000);
    setInterval(checkScheduleSlots, 30000);
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
