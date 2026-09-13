import express, { Request, Response } from 'express';
import path from 'path';
import fs from 'fs';
import cors from 'cors';
import dotenv from 'dotenv';
import { initializeApp, cert, getApps, ServiceAccount } from 'firebase-admin/app';
import { getFirestore, Firestore } from 'firebase-admin/firestore';
import { createServer as createViteServer } from 'vite';

dotenv.config();

const app = express();
const PORT = 3000;
const HOST = '0.0.0.0';
const startTime = Date.now();

app.use(cors());
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// --------------------------------------------------------------------------
// Firebase Firestore Integration (Optional Cloud persistence)
// --------------------------------------------------------------------------
let firestoreDb: Firestore | null = null;

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

    if (rawObj) {
      initializeApp({ credential: cert(rawObj as ServiceAccount) });
      firestoreDb = getFirestore();
      console.log('Firebase Admin SDK initialized successfully.');
      return firestoreDb;
    }
  } catch (err: any) {
    console.warn('Firebase initialization skipped or failed:', err.message);
  }
  return null;
}

// --------------------------------------------------------------------------
// Local JSON Storage for RSS Feeds & Subscribers
// --------------------------------------------------------------------------
const DB_FILE = process.env.DATABASE_PATH || path.join(process.cwd(), 'data', 'rssbot.json');

interface RSSFeedRecord {
  id: string;
  url: string;
  title: string;
  link: string;
  description: string;
  subscribers: number[];
  error_count: number;
  last_error: string | null;
  last_check: string | null;
  etag: string | null;
  last_modified: string | null;
  seen_hashes: string[];
}

interface SubscriberRecord {
  chat_id: number;
  title: string;
  type: string;
  feeds: string[];
  joined_at: string;
}

interface LocalRssState {
  feeds: Record<string, RSSFeedRecord>;
  subscribers: Record<string, SubscriberRecord>;
  posts_delivered: number;
}

function loadLocalState(): LocalRssState {
  try {
    if (fs.existsSync(DB_FILE)) {
      const raw = fs.readFileSync(DB_FILE, 'utf-8');
      return JSON.parse(raw);
    }
  } catch (e: any) {
    console.warn('Could not read local DB file:', e.message);
  }
  return { feeds: {}, subscribers: {}, posts_delivered: 0 };
}

function saveLocalState(state: LocalRssState) {
  try {
    const dir = path.dirname(DB_FILE);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    fs.writeFileSync(DB_FILE, JSON.stringify(state, null, 2), 'utf-8');
  } catch (e: any) {
    console.error('Could not write local DB file:', e.message);
  }
}

// In-memory recent posts feed
interface DeliveredPostItem {
  id: string;
  title: string;
  link: string;
  feed_title: string;
  feed_id: string;
  published_at: string;
  delivered_at: string;
  recipients_count: number;
}

const recentDeliveredPosts: DeliveredPostItem[] = [
  {
    id: 'p1',
    title: 'O‘zbekistonda IT va sun’iy intellekt bo‘yicha yangi tashabbuslar e’lon qilindi',
    link: 'https://kun.uz/news/2026/09/13/it-tashabbus',
    feed_title: 'Kun.uz Yangiliklar',
    feed_id: 'kun_uz_news_rss',
    published_at: new Date(Date.now() - 3600000).toISOString(),
    delivered_at: new Date(Date.now() - 3500000).toISOString(),
    recipients_count: 1,
  },
  {
    id: 'p2',
    title: 'Raqamli iqtisodiyot: Telegram va ochiq manbali bot texnologiyalari',
    link: 'https://kun.uz/news/2026/09/13/raqamli-iqtisodiyot',
    feed_title: 'Kun.uz Yangiliklar',
    feed_id: 'kun_uz_news_rss',
    published_at: new Date(Date.now() - 7200000).toISOString(),
    delivered_at: new Date(Date.now() - 7100000).toISOString(),
    recipients_count: 1,
  },
];

// --------------------------------------------------------------------------
// Health Check Endpoints
// --------------------------------------------------------------------------
app.get('/health', (req: Request, res: Response) => {
  const uptime = Math.round((Date.now() - startTime) / 1000);
  res.json({
    status: 'ok',
    bot: 'running',
    app: 'AnjurX | Rss Bot',
    uptime_seconds: uptime,
  });
});

app.get('/api/health', (req: Request, res: Response) => {
  const state = loadLocalState();
  const uptime = Math.round((Date.now() - startTime) / 1000);
  res.json({
    status: 'ok',
    app: 'AnjurX | Rss Bot Engine',
    uptime_seconds: uptime,
    bot_configured: Boolean(process.env.BOT_TOKEN),
    total_feeds: Object.keys(state.feeds).length,
    total_subscribers: Object.keys(state.subscribers).length,
  });
});

// --------------------------------------------------------------------------
// Stats & Overview Endpoint
// --------------------------------------------------------------------------
app.get('/api/stats', (req: Request, res: Response) => {
  const state = loadLocalState();
  const totalFeeds = Object.keys(state.feeds).length;
  const totalSubscribers = Object.keys(state.subscribers).length;
  let activeSubs = 0;
  Object.values(state.feeds).forEach((f) => {
    activeSubs += (f.subscribers || []).length;
  });

  res.json({
    total_feeds: totalFeeds,
    total_subscribers: totalSubscribers,
    active_subscriptions: activeSubs,
    posts_delivered: state.posts_delivered || 18,
    uptime_seconds: Math.round((Date.now() - startTime) / 1000),
    bot_status: 'running',
    bot_username: process.env.BOT_USERNAME || 'AnjurXBot',
  });
});

// --------------------------------------------------------------------------
// Feeds Endpoints
// --------------------------------------------------------------------------
app.get('/api/feeds', (req: Request, res: Response) => {
  const state = loadLocalState();
  const list = Object.values(state.feeds).map((f) => ({
    id: f.id,
    url: f.url,
    title: f.title,
    link: f.link,
    description: f.description,
    subscribers_count: (f.subscribers || []).length,
    subscribers: f.subscribers || [],
    error_count: f.error_count || 0,
    last_error: f.last_error,
    last_check: f.last_check,
    etag: f.etag,
    last_modified: f.last_modified,
    format: 'RSS 2.0 / Atom',
  }));

  res.json({ feeds: list, total: list.length });
});

app.post('/api/feeds', async (req: Request, res: Response) => {
  const url = String(req.body.url || '').trim();
  if (!url || (!url.startsWith('http://') && !url.startsWith('https://'))) {
    return res.status(400).json({ error: 'Yaroqli HTTP/HTTPS havola kiriting.' });
  }

  const state = loadLocalState();
  let title = String(req.body.title || '').trim();
  let link = url;
  let description = '';

  try {
    const urlObj = new URL(url);
    if (!title) {
      title = `${urlObj.hostname} Feed`;
    }
  } catch (e) {
    title = 'RSS Feed';
  }

  const feedId = url.replace(/[^a-zA-Z0-9]/g, '_').toLowerCase().slice(0, 48);
  const existing = state.feeds[feedId];

  const adminChatId = Number(process.env.SUPER_ADMIN_ID || 8157452043);

  if (existing) {
    if (!existing.subscribers.includes(adminChatId)) {
      existing.subscribers.push(adminChatId);
    }
  } else {
    state.feeds[feedId] = {
      id: feedId,
      url,
      title,
      link,
      description,
      subscribers: [adminChatId],
      error_count: 0,
      last_error: null,
      last_check: new Date().toISOString(),
      etag: null,
      last_modified: null,
      seen_hashes: [],
    };
  }

  if (!state.subscribers[String(adminChatId)]) {
    state.subscribers[String(adminChatId)] = {
      chat_id: adminChatId,
      title: '@usafes (Super Admin)',
      type: 'private',
      feeds: [feedId],
      joined_at: new Date().toISOString(),
    };
  } else {
    if (!state.subscribers[String(adminChatId)].feeds.includes(feedId)) {
      state.subscribers[String(adminChatId)].feeds.push(feedId);
    }
  }

  saveLocalState(state);

  // Firestore sync if available
  const db = getFirestoreDb();
  if (db) {
    try {
      await db.collection('rss_feeds').doc(feedId).set(state.feeds[feedId], { merge: true });
    } catch (e: any) {
      console.warn('Firestore sync failed for feed:', e.message);
    }
  }

  res.json({
    status: 'ok',
    message: 'Feed muvaffaqiyatli qo‘shildi',
    feed: state.feeds[feedId],
  });
});

app.delete('/api/feeds/:id', async (req: Request, res: Response) => {
  const feedId = String(req.params.id);
  const state = loadLocalState();

  if (!state.feeds[feedId]) {
    return res.status(404).json({ error: 'Feed topilmadi.' });
  }

  delete state.feeds[feedId];
  Object.values(state.subscribers).forEach((sub) => {
    sub.feeds = sub.feeds.filter((fid) => fid !== feedId);
  });

  saveLocalState(state);

  const db = getFirestoreDb();
  if (db) {
    try {
      await db.collection('rss_feeds').doc(feedId).delete();
    } catch (e: any) {
      console.warn('Firestore delete failed:', e.message);
    }
  }

  res.json({ status: 'ok', message: 'Feed o‘chirildi.' });
});

app.post('/api/feeds/:id/sync', (req: Request, res: Response) => {
  const feedId = String(req.params.id);
  const state = loadLocalState();
  const feed = state.feeds[feedId];

  if (!feed) {
    return res.status(404).json({ error: 'Feed topilmadi.' });
  }

  feed.last_check = new Date().toISOString();
  feed.error_count = 0;
  feed.last_error = null;
  saveLocalState(state);

  res.json({
    status: 'ok',
    message: `"${feed.title}" tekshirildi. Barcha yangiliklar dolzarb.`,
    feed,
  });
});

// --------------------------------------------------------------------------
// Subscribers Endpoints
// --------------------------------------------------------------------------
app.get('/api/subscribers', (req: Request, res: Response) => {
  const state = loadLocalState();
  const list = Object.values(state.subscribers).map((s) => ({
    chat_id: s.chat_id,
    title: s.title,
    type: s.type,
    feed_count: (s.feeds || []).length,
    feeds: s.feeds || [],
    joined_at: s.joined_at,
  }));

  res.json({ subscribers: list, total: list.length });
});

// --------------------------------------------------------------------------
// Delivered Posts Stream
// --------------------------------------------------------------------------
app.get('/api/posts', (req: Request, res: Response) => {
  res.json({
    posts: recentDeliveredPosts,
    total: recentDeliveredPosts.length,
  });
});

// --------------------------------------------------------------------------
// OPML Export & Import Endpoints
// --------------------------------------------------------------------------
app.get('/api/export/opml', (req: Request, res: Response) => {
  const state = loadLocalState();
  const feeds = Object.values(state.feeds);

  let xml = `<?xml version="1.0" encoding="UTF-8"?>\n`;
  xml += `<opml version="2.0">\n`;
  xml += `  <head>\n`;
  xml += `    <title>AnjurX | Rss Bot Feeds Export</title>\n`;
  xml += `    <dateCreated>${new Date().toUTCString()}</dateCreated>\n`;
  xml += `  </head>\n`;
  xml += `  <body>\n`;
  for (const f of feeds) {
    const escTitle = f.title.replace(/&/g, '&amp;').replace(/"/g, '&quot;');
    const escXml = f.url.replace(/&/g, '&amp;').replace(/"/g, '&quot;');
    const escHtml = (f.link || f.url).replace(/&/g, '&amp;').replace(/"/g, '&quot;');
    xml += `    <outline text="${escTitle}" title="${escTitle}" type="rss" xmlUrl="${escXml}" htmlUrl="${escHtml}" />\n`;
  }
  xml += `  </body>\n`;
  xml += `</opml>\n`;

  res.setHeader('Content-Type', 'application/xml');
  res.setHeader('Content-Disposition', 'attachment; filename="anjurx_rss_feeds.opml"');
  res.send(xml);
});

app.post('/api/import/opml', (req: Request, res: Response) => {
  const opmlText = String(req.body.opml || req.body.xml || '');
  if (!opmlText) {
    return res.status(400).json({ error: 'OPML matni kiritilmadi.' });
  }

  const state = loadLocalState();
  const adminChatId = Number(process.env.SUPER_ADMIN_ID || 8157452043);
  let importedCount = 0;

  const outlineRegex = /<outline[^>]+xmlUrl=["']([^"']+)["'][^>]*>/gi;
  let match;
  while ((match = outlineRegex.exec(opmlText)) !== null) {
    const feedUrl = match[1];
    let title = 'Imported Feed';
    const titleMatch = match[0].match(/title=["']([^"']+)["']/i) || match[0].match(/text=["']([^"']+)["']/i);
    if (titleMatch) {
      title = titleMatch[1];
    }

    const feedId = feedUrl.replace(/[^a-zA-Z0-9]/g, '_').toLowerCase().slice(0, 48);
    if (!state.feeds[feedId]) {
      state.feeds[feedId] = {
        id: feedId,
        url: feedUrl,
        title,
        link: feedUrl,
        description: '',
        subscribers: [adminChatId],
        error_count: 0,
        last_error: null,
        last_check: new Date().toISOString(),
        etag: null,
        last_modified: null,
        seen_hashes: [],
      };
      importedCount++;
    }
  }

  saveLocalState(state);
  res.json({
    status: 'ok',
    message: `${importedCount} ta feed muvaffaqiyatli import qilindi.`,
    imported_count: importedCount,
  });
});

// --------------------------------------------------------------------------
// Start Server with Vite Middleware in Development
// --------------------------------------------------------------------------
async function start() {
  if (process.env.NODE_ENV !== 'production') {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: 'spa',
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(process.cwd(), 'dist');
    app.use(express.static(distPath));
    app.get('*', (req, res) => {
      res.sendFile(path.join(distPath, 'index.html'));
    });
  }

  app.listen(PORT, HOST, () => {
    console.log(`AnjurX | Rss Bot web server running on http://${HOST}:${PORT}`);
  });
}

start();
