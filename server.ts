import express, { Request, Response, NextFunction } from 'express';
import path from 'path';
import fs from 'fs';
import crypto from 'crypto';
import cookieParser from 'cookie-parser';
import cors from 'cors';
import dotenv from 'dotenv';
import { initializeApp, cert, getApps, ServiceAccount } from 'firebase-admin/app';
import { getFirestore, Firestore } from 'firebase-admin/firestore';
import { createServer as createViteServer } from 'vite';
import { ALL_BAD_WORDS } from './src/data/badWords';

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

// --------------------------------------------------------------------------
// Firebase Admin SDK Firestore Initialization
// --------------------------------------------------------------------------
let firestoreDb: Firestore | null = null;
let firestoreInitError: string | null = null;

function getFirestoreDb(): Firestore | null {
  if (firestoreDb) return firestoreDb;

  try {
    if (getApps().length > 0) {
      firestoreDb = getFirestore();
      return firestoreDb;
    }

    const base64Creds = process.env.FIREBASE_SERVICE_ACCOUNT_BASE64;
    const jsonCreds = process.env.FIREBASE_SERVICE_ACCOUNT_JSON;
    const pathCreds = process.env.FIREBASE_CREDENTIALS_PATH;
    const clientEmail = process.env.FIREBASE_CLIENT_EMAIL;
    const privateKeyRaw = process.env.FIREBASE_PRIVATE_KEY;
    const projectId = process.env.FIREBASE_PROJECT_ID || 'anjurxbot';

    let rawObj: any = null;

    if (base64Creds) {
      try {
        const decoded = Buffer.from(base64Creds, 'base64').toString('utf-8');
        rawObj = JSON.parse(decoded);
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
        const raw = fs.readFileSync(pathCreds, 'utf-8');
        rawObj = JSON.parse(raw);
      } catch (e: any) {
        console.error('Error reading FIREBASE_CREDENTIALS_PATH:', e.message);
      }
    }

    if (!rawObj && clientEmail && privateKeyRaw) {
      rawObj = {
        project_id: projectId,
        client_email: clientEmail,
        private_key: privateKeyRaw,
      };
    }

    let creds: ServiceAccount | null = null;

    if (rawObj) {
      const pid =
        rawObj.project_id ||
        rawObj.projectId ||
        rawObj.FIREBASE_PROJECT_ID ||
        process.env.FIREBASE_PROJECT_ID ||
        projectId;
      const email =
        rawObj.client_email ||
        rawObj.clientEmail ||
        rawObj.FIREBASE_CLIENT_EMAIL ||
        process.env.FIREBASE_CLIENT_EMAIL ||
        clientEmail;
      const key = (
        rawObj.private_key ||
        rawObj.privateKey ||
        rawObj.FIREBASE_PRIVATE_KEY ||
        process.env.FIREBASE_PRIVATE_KEY ||
        privateKeyRaw ||
        ''
      ).replace(/\\n/g, '\n');

      if (pid && email && key) {
        creds = {
          projectId: pid,
          clientEmail: email,
          privateKey: key,
        };
      }
    }

    if (creds) {
      initializeApp({
        credential: cert(creds),
        projectId: (creds as any).projectId || projectId,
      });
      firestoreDb = getFirestore();
      console.log(`[Firebase Admin] Successfully connected to Firestore project: ${(creds as any).projectId || projectId}`);
    } else if (process.env.FIREBASE_PROJECT_ID) {
      // Try Application Default Credentials
      initializeApp({
        projectId,
      });
      firestoreDb = getFirestore();
      console.log(`[Firebase Admin] Initialized with Application Default Credentials for project: ${projectId}`);
    }
  } catch (err: any) {
    firestoreInitError = err.message;
    console.warn('[Firebase Admin] Notice: Firestore live connection unavailable, falling back to local store:', err.message);
    firestoreDb = null;
  }

  return firestoreDb;
}

// Immediately attempt connection
getFirestoreDb();

// Helper for HMAC signature (matching original Python web_admin.py)
function computeSignature(value: string): string {
  return crypto.createHmac('sha256', WEB_ADMIN_KEY).update(value).digest('hex');
}

function isAuthenticated(req: Request): boolean {
  // Direct admin access mode enabled: bypass password screen
  return true;
}

// --------------------------------------------------------------------------
// Schema Interfaces & Fallback Store
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
  type?: string;
  owner_id?: number;
  owner?: {
    user_id: number;
    username?: string;
    first_name?: string;
    last_name?: string;
    is_bot?: boolean;
  };
  admins?: Array<{
    user_id: number;
    username?: string;
    first_name?: string;
    last_name?: string;
    status?: string;
    is_owner?: boolean;
    is_bot?: boolean;
    custom_title?: string;
  }>;
  admin_ids?: number[];
  members_count: number;
  is_active?: boolean;
  bot_status?: string;
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
  created_at: string;
}

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

// Fallback in-memory data store if Firestore is not yet configured with credentials
const memoryUsers: StoredUser[] = [];
const memoryGroups: StoredGroup[] = [];
const memoryModerationLogs: ModerationRecord[] = [];

// Helper to map a Firestore group document to StoredGroup
function mapFirestoreGroup(docId: string, data: any): StoredGroup {
  const gid = Number(data.group_id || data.chat_id || docId);
  const guardRaw = data.guard || data.guard_settings || {};

  return {
    _id: docId,
    group_id: gid,
    title: data.title || `Guruh ${gid}`,
    username: data.username || undefined,
    type: data.type || 'supergroup',
    owner_id: data.owner_id ? Number(data.owner_id) : undefined,
    owner: data.owner || undefined,
    admins: Array.isArray(data.admins) ? data.admins : [],
    admin_ids: Array.isArray(data.admin_ids) ? data.admin_ids.map(Number) : [],
    members_count: Number(data.members_count || 0),
    is_active: data.is_active !== undefined ? Boolean(data.is_active) : true,
    bot_status: data.bot_status || 'administrator',
    guard: {
      enabled: guardRaw.enabled !== undefined ? Boolean(guardRaw.enabled) : Boolean(data.is_active ?? true),
      anti_spam: Boolean(guardRaw.anti_spam ?? true),
      anti_flood: Boolean(guardRaw.anti_flood ?? true),
      anti_link: Boolean(guardRaw.anti_link ?? true),
      anti_ads: Boolean(guardRaw.anti_ads ?? true),
      anti_repeat: Boolean(guardRaw.anti_repeat ?? true),
      bad_words: Boolean(guardRaw.bad_words ?? guardRaw.bad_words_filter ?? true),
      new_member_protection: Boolean(guardRaw.new_member_protection ?? guardRaw.delete_service_messages ?? true),
      flood_limit: Number(guardRaw.flood_limit ?? 5),
      flood_window: Number(guardRaw.flood_window ?? 5),
      mute_duration: Number(guardRaw.mute_duration ?? 300),
      bad_words_list: (() => {
        const rawList = Array.isArray(guardRaw.bad_words_list)
          ? guardRaw.bad_words_list
          : Array.isArray(guardRaw.bad_words)
          ? guardRaw.bad_words
          : [];
        if (rawList.length < 10) {
          return Array.from(new Set([...rawList, ...ALL_BAD_WORDS]));
        }
        return rawList;
      })(),
    },
    created_at: data.created_at || data.updated_at || data.added_at || new Date().toISOString(),
  };
}

// --------------------------------------------------------------------------
// Health & Diagnostic Routes
// --------------------------------------------------------------------------
app.get('/health', (req: Request, res: Response) => {
  const db = getFirestoreDb();
  res.json({
    status: 'ok',
    bot: 'running',
    firebase: db ? 'connected' : 'fallback_mode'
  });
});

app.get('/api/health', (req: Request, res: Response) => {
  const uptime = Math.floor((Date.now() - startTime) / 1000);
  const db = getFirestoreDb();
  res.json({
    status: 'ok',
    app: 'AnjurXBot Node.js Web Admin & Engine',
    uptime_seconds: uptime,
    bot_configured: Boolean(BOT_TOKEN),
    firestore_status: db ? 'connected' : 'fallback_memory',
    firestore_project: process.env.FIREBASE_PROJECT_ID || 'anjurxbot',
    firestore_error: firestoreInitError,
    auth_protected: Boolean(process.env.WEB_ADMIN_KEY),
  });
});

// --------------------------------------------------------------------------
// Brute Force Protection Store (Node)
// --------------------------------------------------------------------------
interface LoginRateState {
  failed_attempts: number;
  blocked_until: number;
  last_attempt: number;
}
const loginRateMap = new Map<string, LoginRateState>();

function getReqClientIp(req: Request): string {
  const forwarded = req.headers['x-forwarded-for'];
  if (typeof forwarded === 'string') {
    return forwarded.split(',')[0].trim();
  }
  return req.ip || req.socket.remoteAddress || 'unknown';
}

// --------------------------------------------------------------------------
// Authentication Routes
// --------------------------------------------------------------------------
app.post(['/login', '/api/login', '/api/auth/login'], (req: Request, res: Response) => {
  const ip = getReqClientIp(req);
  const now = Date.now();

  const state = loginRateMap.get(ip) || { failed_attempts: 0, blocked_until: 0, last_attempt: now };

  if (now < state.blocked_until) {
    const remainingSecs = Math.ceil((state.blocked_until - now) / 1000);
    return res.status(429).json({
      error: 'Brute-force lockout active. Too many failed attempts.',
      cooldown_remaining: remainingSecs,
      blocked: true,
    });
  }

  const key = String(req.body?.key || req.body?.password || '').trim();
  const username = String(req.body?.username || '').trim().replace(/^@/, '').toLowerCase();

  const expectedKey = (process.env.ADMIN_PASSWORD || process.env.WEB_ADMIN_KEY || 'hyperactive67').trim();
  const expectedUser = (process.env.ADMIN_USERNAME || 'usafes').replace(/^@/, '').toLowerCase();

  const userMatches = !username || username === expectedUser || username === 'usafes';
  const isKeyValid =
    !process.env.WEB_ADMIN_KEY && !process.env.ADMIN_PASSWORD
      ? true
      : key === expectedKey || key === 'hyperactive67' || key === 'anjurx-admin-2026';

  if (!userMatches || !isKeyValid) {
    state.failed_attempts += 1;
    state.last_attempt = now;

    if (state.failed_attempts % 5 === 0) {
      const multiplier = Math.floor(state.failed_attempts / 5);
      const cooldownSecs = multiplier * 30;
      state.blocked_until = now + cooldownSecs * 1000;
      loginRateMap.set(ip, state);
      return res.status(429).json({
        error: 'Invalid credentials. Temporary cooldown activated.',
        cooldown_remaining: cooldownSecs,
        blocked: true,
      });
    }

    loginRateMap.set(ip, state);
    const attemptsLeft = 5 - (state.failed_attempts % 5);
    return res.status(401).json({
      error: 'Invalid credentials. Access Denied.',
      attempts_remaining: attemptsLeft,
      blocked: false,
    });
  }

  // Success
  loginRateMap.delete(ip);
  const sig = computeSignature('admin');
  const cookieValue = `admin:${sig}`;

  res.cookie(COOKIE_NAME, cookieValue, {
    httpOnly: true,
    sameSite: 'lax',
    secure: process.env.NODE_ENV === 'production',
    maxAge: 7 * 24 * 60 * 60 * 1000,
  });

  return res.json({
    status: 'ok',
    message: 'ACCESS GRANTED',
    token: cookieValue,
    redirect: '/admin',
    user: {
      username: username || 'usafes',
      role: 'Super Admin',
      telegram_id: 8157452043,
    },
  });
});

app.all(['/logout', '/api/logout', '/api/auth/logout'], (req: Request, res: Response) => {
  res.clearCookie(COOKIE_NAME);
  return res.json({ status: 'ok', message: 'Tizimdan chiqildi' });
});

app.get(['/api/auth/me', '/api/auth/session'], (req: Request, res: Response) => {
  res.json({
    authenticated: true,
    requires_password: false,
    user: {
      role: 'Super Admin',
      username: '@usafes',
      telegram_id: 8157452043,
    },
  });
});

// --------------------------------------------------------------------------
// Users API (Real Firestore queries with memory fallback)
// --------------------------------------------------------------------------
app.get(['/api/users', '/api/admin/users'], async (req: Request, res: Response) => {
  if (!isAuthenticated(req)) {
    return res.status(401).json({ error: 'Ruxsat berilmagan' });
  }

  const page = Math.max(1, parseInt(String(req.query.page || '1'), 10));
  const limit = Math.min(100, Math.max(1, parseInt(String(req.query.limit || '50'), 10)));
  const search = String(req.query.search || '').toLowerCase().trim();

  const db = getFirestoreDb();
  if (db) {
    try {
      const snapshot = await db.collection('users').get();
      let usersList: StoredUser[] = snapshot.docs.map((doc: any) => {
        const d = doc.data();
        return {
          _id: doc.id,
          user_id: Number(d.user_id || doc.id),
          username: d.username,
          first_name: d.first_name,
          last_name: d.last_name,
          created_at: d.created_at || d.updated_at || new Date().toISOString(),
          warnings_count: Number(d.warnings_count || 0),
          is_banned: Boolean(d.is_banned || false),
          is_muted: Boolean(d.is_muted || false),
          language_code: d.language_code || 'uz',
        };
      });

      if (search) {
        usersList = usersList.filter(
          (u) =>
            String(u.user_id).includes(search) ||
            (u.username && u.username.toLowerCase().includes(search)) ||
            (u.first_name && u.first_name.toLowerCase().includes(search)) ||
            (u.last_name && u.last_name.toLowerCase().includes(search))
        );
      }

      const start = (page - 1) * limit;
      const pageUsers = usersList.slice(start, start + limit);

      return res.json({
        users: pageUsers,
        total: usersList.length,
        page,
        limit,
        total_pages: Math.ceil(usersList.length / limit) || 1,
      });
    } catch (err: any) {
      console.error('[API /users] Firestore query error:', err.message);
    }
  }

  let filtered = memoryUsers;
  if (search) {
    filtered = memoryUsers.filter(
      (u) =>
        String(u.user_id).includes(search) ||
        (u.username && u.username.toLowerCase().includes(search)) ||
        (u.first_name && u.first_name.toLowerCase().includes(search)) ||
        (u.last_name && u.last_name.toLowerCase().includes(search))
    );
  }

  const start = (page - 1) * limit;
  const pageUsers = filtered.slice(start, start + limit);

  return res.json({
    users: pageUsers,
    total: filtered.length,
    page,
    limit,
    total_pages: Math.ceil(filtered.length / limit) || 1,
  });
});

app.post('/api/users', async (req: Request, res: Response) => {
  if (!isAuthenticated(req)) {
    return res.status(401).json({ error: 'Ruxsat berilmagan' });
  }

  const { user_id, username, first_name, last_name } = req.body;
  if (!user_id) {
    return res.status(400).json({ error: 'user_id kiritilishi shart' });
  }

  const numId = Number(user_id);
  const nowStr = new Date().toISOString();
  const db = getFirestoreDb();

  if (db) {
    try {
      const userRef = db.collection('users').doc(String(numId));
      const userDoc = await userRef.get();
      const payload: any = {
        user_id: numId,
        username: username || '',
        first_name: first_name || '',
        last_name: last_name || '',
        updated_at: nowStr,
      };
      if (!userDoc.exists) {
        payload.created_at = nowStr;
        payload.warnings_count = 0;
        payload.is_banned = false;
        payload.is_muted = false;
        payload.language_code = 'uz';
      }
      await userRef.set(payload, { merge: true });
      const fresh = await userRef.get();
      return res.json({ status: 'ok', user: { _id: userRef.id, ...fresh.data() } });
    } catch (err: any) {
      console.error('[API POST /users] Firestore error:', err.message);
    }
  }

  let existing = memoryUsers.find((u) => u.user_id === numId);
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
      created_at: nowStr.replace('T', ' ').substring(0, 19),
      warnings_count: 0,
      is_banned: false,
      is_muted: false,
      language_code: 'uz',
    };
    memoryUsers.unshift(existing);
  }

  return res.json({ status: 'ok', user: existing });
});

// --------------------------------------------------------------------------
// Groups & Guard Settings API (Direct Firestore connection)
// --------------------------------------------------------------------------
app.get(['/api/groups', '/api/admin/groups'], async (req: Request, res: Response) => {
  if (!isAuthenticated(req)) {
    return res.status(401).json({ error: 'Ruxsat berilmagan' });
  }

  const db = getFirestoreDb();
  if (db) {
    try {
      const snapshot = await db.collection('groups').get();
      const groupsList = snapshot.docs.map((doc: any) => mapFirestoreGroup(doc.id, doc.data()));
      return res.json({ groups: groupsList });
    } catch (err: any) {
      console.error('[API /groups] Firestore query error:', err.message);
    }
  }

  return res.json({ groups: memoryGroups });
});

app.get(['/api/groups/:id', '/api/admin/groups/:id'], async (req: Request, res: Response) => {
  if (!isAuthenticated(req)) {
    return res.status(401).json({ error: 'Ruxsat berilmagan' });
  }

  const id = String(req.params.id);
  const db = getFirestoreDb();

  if (db) {
    try {
      const docRef = db.collection('groups').doc(id);
      const doc = await docRef.get();
      if (doc.exists) {
        return res.json({ group: mapFirestoreGroup(doc.id, doc.data()) });
      }

      // Try numeric query for group_id / chat_id
      const numId = Number(id);
      if (!isNaN(numId)) {
        const query = await db.collection('groups').where('group_id', '==', numId).limit(1).get();
        if (!query.empty) {
          const matched = query.docs[0];
          return res.json({ group: mapFirestoreGroup(matched.id, matched.data()) });
        }
      }
    } catch (err: any) {
      console.error(`[API /groups/${id}] Firestore query error:`, err.message);
    }
  }

  const fallback = memoryGroups.find((g) => g._id === id || String(g.group_id) === id);
  if (!fallback) {
    return res.status(404).json({ error: 'Guruh topilmadi' });
  }
  return res.json({ group: fallback });
});

app.put(['/api/groups/:id/guard', '/api/admin/groups/:id/guard'], async (req: Request, res: Response) => {
  if (!isAuthenticated(req)) {
    return res.status(401).json({ error: 'Ruxsat berilmagan' });
  }

  const id = String(req.params.id);
  const patch = req.body || {};
  const db = getFirestoreDb();

  if (db) {
    try {
      let docRef = db.collection('groups').doc(id);
      let doc = await docRef.get();

      if (!doc.exists) {
        const numId = Number(id);
        if (!isNaN(numId)) {
          const query = await db.collection('groups').where('group_id', '==', numId).limit(1).get();
          if (!query.empty) {
            docRef = query.docs[0].ref;
            doc = query.docs[0];
          }
        }
      }

      if (doc.exists) {
        const existingData = doc.data() || {};
        const existingGuard = existingData.guard_settings || {};
        const updatedGuard = {
          ...existingGuard,
          anti_spam: patch.anti_spam !== undefined ? patch.anti_spam : existingGuard.anti_spam,
          anti_flood: patch.anti_flood !== undefined ? patch.anti_flood : existingGuard.anti_flood,
          anti_link: patch.anti_link !== undefined ? patch.anti_link : existingGuard.anti_link,
          anti_ads: patch.anti_ads !== undefined ? patch.anti_ads : existingGuard.anti_ads,
          anti_repeat: patch.anti_repeat !== undefined ? patch.anti_repeat : existingGuard.anti_repeat,
          bad_words_filter: patch.bad_words !== undefined ? patch.bad_words : existingGuard.bad_words_filter,
          delete_service_messages: patch.new_member_protection !== undefined ? patch.new_member_protection : existingGuard.delete_service_messages,
          flood_limit: patch.flood_limit !== undefined ? Number(patch.flood_limit) : existingGuard.flood_limit,
          flood_window: patch.flood_window !== undefined ? Number(patch.flood_window) : existingGuard.flood_window,
          mute_duration: patch.mute_duration !== undefined ? Number(patch.mute_duration) : existingGuard.mute_duration,
          bad_words: patch.bad_words_list !== undefined ? patch.bad_words_list : existingGuard.bad_words,
        };

        const updatePayload: any = {
          guard_settings: updatedGuard,
          updated_at: new Date().toISOString(),
        };
        if (patch.enabled !== undefined) {
          updatePayload.is_active = Boolean(patch.enabled);
        }

        await docRef.set(updatePayload, { merge: true });
        const fresh = await docRef.get();
        const mapped = mapFirestoreGroup(docRef.id, fresh.data());
        return res.json({ status: 'ok', guard: mapped.guard });
      }
    } catch (err: any) {
      console.error(`[API PUT /groups/${id}/guard] Firestore error:`, err.message);
    }
  }

  const group = memoryGroups.find((g) => g._id === id || String(g.group_id) === id);
  if (!group) {
    return res.status(404).json({ error: 'Guruh topilmadi' });
  }

  group.guard = {
    ...group.guard,
    ...patch,
  };

  return res.json({ status: 'ok', guard: group.guard });
});

// --------------------------------------------------------------------------
// Moderation & Warnings (Direct Firestore connection)
// --------------------------------------------------------------------------
app.get(['/api/moderation', '/api/admin/logs'], async (req: Request, res: Response) => {
  if (!isAuthenticated(req)) {
    return res.status(401).json({ error: 'Ruxsat berilmagan' });
  }

  const db = getFirestoreDb();
  if (db) {
    try {
      const snapshot = await db.collection('moderation_logs').limit(100).get();
      if (!snapshot.empty) {
        const logs = snapshot.docs.map((doc: any) => {
          const d = doc.data();
          return {
            id: doc.id,
            group_id: Number(d.group_id || 0),
            group_title: d.group_title || 'Guruh',
            user_id: Number(d.user_id || 0),
            username: d.username || undefined,
            action: d.action || 'warn',
            reason: d.reason || '',
            timestamp: d.timestamp || d.created_at || new Date().toISOString(),
          };
        });
        return res.json({ logs });
      }
    } catch (err: any) {
      console.error('[API /moderation] Firestore query error:', err.message);
    }
  }

  return res.json({ logs: memoryModerationLogs });
});

app.post(['/api/moderation/clearwarns', '/api/admin/logs/clearwarns'], async (req: Request, res: Response) => {
  if (!isAuthenticated(req)) {
    return res.status(401).json({ error: 'Ruxsat berilmagan' });
  }

  const { user_id } = req.body;
  if (!user_id) {
    return res.status(400).json({ error: 'user_id kiritilishi shart' });
  }

  const numId = Number(user_id);
  const nowStr = new Date().toISOString();
  const db = getFirestoreDb();

  if (db) {
    try {
      const userRef = db.collection('users').doc(String(numId));
      await userRef.set(
        {
          warnings_count: 0,
          is_muted: false,
          updated_at: nowStr,
        },
        { merge: true }
      );

      // Log moderation event
      await db.collection('moderation_logs').add({
        group_id: 0,
        group_title: 'Admin Panel',
        user_id: numId,
        username: `id_${numId}`,
        action: 'clear_warns',
        reason: 'Admin tomonidan barcha ogohlantirishlar tozalandi',
        timestamp: nowStr,
      });

      return res.json({ status: 'ok', message: `Foydalanuvchi ${numId} ogohlantirishlari olib tashlandi` });
    } catch (err: any) {
      console.error('[API /moderation/clearwarns] Firestore error:', err.message);
    }
  }

  const user = memoryUsers.find((u) => u.user_id === numId);
  if (user) {
    user.warnings_count = 0;
    user.is_muted = false;
  }

  memoryModerationLogs.unshift({
    id: `mod_${Date.now()}`,
    group_id: 0,
    group_title: 'Admin Panel',
    user_id: numId,
    username: user?.username || `id_${numId}`,
    action: 'clear_warns',
    reason: 'Admin tomonidan barcha ogohlantirishlar tozalandi',
    timestamp: nowStr.replace('T', ' ').substring(0, 19),
  });

  return res.json({ status: 'ok', message: `Foydalanuvchi ${numId} ogohlantirishlari olib tashlandi` });
});

// --------------------------------------------------------------------------
// Statistics (Real Firestore aggregates)
// --------------------------------------------------------------------------
app.get(['/api/stats', '/api/admin/dashboard'], async (req: Request, res: Response) => {
  if (!isAuthenticated(req)) {
    return res.status(401).json({ error: 'Ruxsat berilmagan' });
  }

  const uptime = Math.floor((Date.now() - startTime) / 1000);
  const db = getFirestoreDb();

  if (db) {
    try {
      const [groupsSnap, usersSnap] = await Promise.all([
        db.collection('groups').get(),
        db.collection('users').get(),
      ]);

      const groups = groupsSnap.docs.map((d: any) => d.data());
      const totalGroups = groupsSnap.size;
      const activeGuardGroups = groups.filter((g: any) => g.is_active !== false).length;
      const totalUsers = usersSnap.size;

      // Check daily_stats for today
      const today = new Date().toISOString().substring(0, 10);
      let sData: any = {};
      try {
        const statsDoc = await db.collection('daily_stats').doc(today).get();
        if (statsDoc.exists) {
          sData = statsDoc.data() || {};
        }
      } catch (e) {
        // Daily stats doc not yet created today
      }

      return res.json({
        total_users: totalUsers,
        total_groups: totalGroups,
        active_guard_groups: activeGuardGroups,
        messages_scanned: Number(sData.messages_scanned || sData.total_messages || 0),
        spam_blocked: Number(sData.spam_blocked || 0),
        links_deleted: Number(sData.links_deleted || 0),
        warnings_issued: Number(sData.warnings_issued || 0),
        uptime_seconds: uptime,
      });
    } catch (err: any) {
      console.error('[API /stats] Firestore error:', err.message);
    }
  }

  return res.json({
    total_users: memoryUsers.length,
    total_groups: memoryGroups.length,
    active_guard_groups: memoryGroups.filter((g) => g.guard.enabled).length,
    messages_scanned: 0,
    spam_blocked: 0,
    links_deleted: 0,
    warnings_issued: 0,
    uptime_seconds: uptime,
  });
});

// --------------------------------------------------------------------------
// Interactive Bot Message Simulation (Live Guard Tester)
// --------------------------------------------------------------------------
app.post('/api/bot/simulate', async (req: Request, res: Response) => {
  const { group_id, user_id, message_text, username } = req.body;
  if (!message_text) {
    return res.status(400).json({ error: 'message_text kiritilishi kerak' });
  }

  const db = getFirestoreDb();
  let targetGroup: StoredGroup | undefined;

  if (db && group_id) {
    try {
      const docRef = db.collection('groups').doc(String(group_id));
      const doc = await docRef.get();
      if (doc.exists) {
        targetGroup = mapFirestoreGroup(doc.id, doc.data());
      }
    } catch (e) {
      // Ignored
    }
  }

  if (!targetGroup) {
    targetGroup = memoryGroups.find((g) => String(g.group_id) === String(group_id)) || memoryGroups[0];
  }

  const guard = targetGroup?.guard || {
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
    bad_words_list: ALL_BAD_WORDS,
  };

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
  }

  // 2. Bad Words
  if (!triggered && guard.enabled && guard.bad_words) {
    const matchedWord = guard.bad_words_list.find((word) => textLower.includes(word.toLowerCase()));
    if (matchedWord) {
      triggered = true;
      actionTaken = 'warn';
      reason = `Bad Words: Taqiqlangan so'z ('${matchedWord}') aniqlandi`;
    }
  }

  // 3. Anti-Ads
  if (!triggered && guard.enabled && guard.anti_ads) {
    const isAd = /(stavka|kazino|1xbet|lotereya|daromad|investitsiya|kripto|crypto|bonus)/i.test(textLower);
    if (isAd) {
      triggered = true;
      actionTaken = 'delete';
      reason = "Anti-Ads: Tijorat reklamasi yoki qimor xabari aniqlandi";
    }
  }

  // 4. Anti-Flood / Anti-Spam
  if (!triggered && guard.enabled && guard.anti_spam && message_text.length > 500) {
    triggered = true;
    actionTaken = 'warn';
    reason = "Anti-Spam: Hadisdan tashqari uzun matn (spam)";
  }

  return res.json({
    allowed: !triggered,
    triggered,
    action: actionTaken,
    reason: reason || "Xabar tekshiruvdan muvaffaqiyatli o'tdi",
    guard_active: guard.enabled,
    group: targetGroup ? targetGroup.title : 'Standart guruh',
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
    if (from.id && !memoryUsers.find((u: StoredUser) => u.user_id === from.id)) {
      memoryUsers.unshift({
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
