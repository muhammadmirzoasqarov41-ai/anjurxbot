import { DatabaseSync } from 'node:sqlite';
import path from 'path';
import fs from 'fs';

const QUEUE_DB_PATH = path.resolve(process.cwd(), './data/recovery_queue.db');

export type HealthState = 'HEALTHY' | 'DEGRADED' | 'QUOTA_EXCEEDED' | 'RECOVERING';

const BACKOFF_SCHEDULE = [30, 60, 120, 300, 600, 900]; // seconds

export interface QueueTableStats {
  pending: number;
  processing: number;
  failed_permanent: number;
  total: number;
}

export interface RecoveryQueueStats {
  total_pending: number;
  total_processing: number;
  total_failed_permanent: number;
  total_queue_size: number;
  oldest_item_age_seconds: number;
  oldest_item_created_at: string | null;
  tables: Record<string, QueueTableStats>;
}

export interface DiagnosticsSummary {
  firestore_status: HealthState;
  is_stale: boolean;
  message: string;
  firestore_429_count: number;
  firestore_read_errors: number;
  firestore_write_errors: number;
  recovery_success_count: number;
  recovery_failure_count: number;
  last_successful_operation: string | null;
  last_quota_error_at: string | null;
  next_health_check_at: string | null;
  backoff_seconds: number;
  queue: RecoveryQueueStats;
}

class NodeRecoveryQueue {
  private db: DatabaseSync | null = null;
  private state: HealthState = 'HEALTHY';
  private backoffIndex = 0;
  private nextHealthCheckTime = 0;
  private lastQuotaTime: number | null = null;
  private lastSuccessTime: number | null = Date.now();
  private count429 = 0;
  private readErrors = 0;
  private writeErrors = 0;
  private recoverySuccesses = 0;
  private recoveryFailures = 0;

  constructor() {
    this.initDb();
  }

  private initDb() {
    try {
      const dir = path.dirname(QUEUE_DB_PATH);
      if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
      }
      this.db = new DatabaseSync(QUEUE_DB_PATH);
      this.db.exec('PRAGMA journal_mode=WAL;');
      this.db.exec('PRAGMA synchronous=NORMAL;');
    } catch (err: any) {
      console.warn('[RecoveryQueue] SQLite init notice:', err.message);
    }
  }

  public isQuotaError(err: any): boolean {
    if (!err) return false;
    const msg = String(err.message || err).toLowerCase();
    const code = err.code || err.status;
    return (
      code === 8 ||
      code === 429 ||
      code === 'RESOURCE_EXHAUSTED' ||
      msg.includes('quota exceeded') ||
      msg.includes('resource_exhausted') ||
      msg.includes('too many requests') ||
      msg.includes('429')
    );
  }

  public getState(): HealthState {
    return this.state;
  }

  public isQuotaExceeded(): boolean {
    return this.state === 'QUOTA_EXCEEDED';
  }

  public recordSuccess(op: 'read' | 'write' = 'write') {
    this.lastSuccessTime = Date.now();
    if (this.state === 'RECOVERING') {
      const q = this.getQueueStats();
      if (q.total_pending === 0) {
        this.state = 'HEALTHY';
        this.backoffIndex = 0;
        console.log('[RecoveryQueue] Queue empty & verified. Health state restored to HEALTHY.');
      }
    } else if (this.state === 'DEGRADED') {
      this.state = 'HEALTHY';
    }
  }

  public recordQuotaError(err: any) {
    this.count429++;
    this.lastQuotaTime = Date.now();
    const backoffSec = BACKOFF_SCHEDULE[Math.min(this.backoffIndex, BACKOFF_SCHEDULE.length - 1)];
    this.nextHealthCheckTime = Date.now() + backoffSec * 1000;
    this.backoffIndex = Math.min(this.backoffIndex + 1, BACKOFF_SCHEDULE.length - 1);
    this.state = 'QUOTA_EXCEEDED';
    console.warn(
      `[RecoveryQueue] Firestore quota exceeded! Backoff set to ${backoffSec}s. Next check at: ${new Date(this.nextHealthCheckTime).toISOString()}`
    );
  }

  public recordError(op: 'read' | 'write', err: any) {
    if (this.isQuotaError(err)) {
      this.recordQuotaError(err);
      return;
    }
    if (op === 'read') this.readErrors++;
    else this.writeErrors++;
    if (this.state === 'HEALTHY') {
      this.state = 'DEGRADED';
    }
  }

  public canAttemptHealthCheck(): boolean {
    if (this.state === 'HEALTHY') return true;
    return Date.now() >= this.nextHealthCheckTime;
  }

  public transitionToRecovering() {
    this.state = 'RECOVERING';
  }

  public enqueueEvent(table: string, entityId: string, eventType: string, payload: any): boolean {
    if (!this.db) {
      this.initDb();
      if (!this.db) return false;
    }
    try {
      const eventId = `evt_${table}_${entityId}_${Date.now()}`;
      const nowIso = new Date().toISOString();
      const payloadStr = JSON.stringify(payload);

      const stmt = this.db.prepare(`
        INSERT INTO ${table} (event_id, entity_id, event_type, payload, created_at, retry_count, next_retry_at, status)
        VALUES (?, ?, ?, ?, ?, 0, ?, 'pending')
      `);
      stmt.run(eventId, String(entityId), eventType, payloadStr, nowIso, nowIso);
      return true;
    } catch (err: any) {
      console.error(`[RecoveryQueue] Failed to enqueue into ${table}:`, err.message);
      return false;
    }
  }

  public getQueueStats(): RecoveryQueueStats {
    const emptyStats: RecoveryQueueStats = {
      total_pending: 0,
      total_processing: 0,
      total_failed_permanent: 0,
      total_queue_size: 0,
      oldest_item_age_seconds: 0,
      oldest_item_created_at: null,
      tables: {},
    };

    if (!this.db) {
      this.initDb();
      if (!this.db) return emptyStats;
    }

    const tables = [
      'pending_users',
      'pending_channels',
      'pending_posts',
      'pending_deliveries',
      'pending_stats',
      'pending_sources',
      'pending_categories',
    ];

    let totalPending = 0;
    let totalProcessing = 0;
    let totalFailed = 0;
    let totalSize = 0;
    let oldestCreatedTime: number | null = null;
    let oldestCreatedIso: string | null = null;

    for (const tbl of tables) {
      try {
        const rows = this.db
          .prepare(
            `SELECT status, count(*) as c, MIN(created_at) as oldest FROM ${tbl} GROUP BY status`
          )
          .all() as Array<{ status: string; c: number; oldest: string | null }>;

        let tPending = 0;
        let tProcessing = 0;
        let tFailed = 0;

        for (const r of rows) {
          const c = Number(r.c || 0);
          if (r.status === 'pending') tPending += c;
          else if (r.status === 'processing') tProcessing += c;
          else if (r.status === 'failed_permanent') tFailed += c;

          if (r.oldest && r.status === 'pending') {
            const time = new Date(r.oldest).getTime();
            if (oldestCreatedTime === null || time < oldestCreatedTime) {
              oldestCreatedTime = time;
              oldestCreatedIso = r.oldest;
            }
          }
        }

        const tTotal = tPending + tProcessing + tFailed;
        totalPending += tPending;
        totalProcessing += tProcessing;
        totalFailed += tFailed;
        totalSize += tTotal;

        emptyStats.tables[tbl] = {
          pending: tPending,
          processing: tProcessing,
          failed_permanent: tFailed,
          total: tTotal,
        };
      } catch (err: any) {
        emptyStats.tables[tbl] = { pending: 0, processing: 0, failed_permanent: 0, total: 0 };
      }
    }

    emptyStats.total_pending = totalPending;
    emptyStats.total_processing = totalProcessing;
    emptyStats.total_failed_permanent = totalFailed;
    emptyStats.total_queue_size = totalSize;
    emptyStats.oldest_item_created_at = oldestCreatedIso;
    emptyStats.oldest_item_age_seconds = oldestCreatedTime
      ? Math.max(0, Math.floor((Date.now() - oldestCreatedTime) / 1000))
      : 0;

    return emptyStats;
  }

  public getDiagnostics(): DiagnosticsSummary {
    const queue = this.getQueueStats();
    let message = 'Firestore barqaror va aloqada';
    if (this.state === 'QUOTA_EXCEEDED') {
      const waitSec = Math.max(0, Math.ceil((this.nextHealthCheckTime - Date.now()) / 1000));
      message = `Firestore bepul kvotasi (50,000 read) to‘ldi. SQLite navbatida ${queue.total_pending} ta amal xavfsiz saqlanmoqda. Qayta tekshiruv: ${waitSec}s dan so‘ng.`;
    } else if (this.state === 'RECOVERING') {
      message = `Firestore tiklanmoqda. SQLite navbati (${queue.total_pending} ta) bosqichma-bosqich sinxronlanmoqda.`;
    } else if (this.state === 'DEGRADED') {
      message = 'Firestore aloqasida vaqtincha sekinlashuv kuzatilmoqda.';
    }

    return {
      firestore_status: this.state,
      is_stale: this.state === 'QUOTA_EXCEEDED' || this.state === 'DEGRADED',
      message,
      firestore_429_count: this.count429,
      firestore_read_errors: this.readErrors,
      firestore_write_errors: this.writeErrors,
      recovery_success_count: this.recoverySuccesses,
      recovery_failure_count: this.recoveryFailures,
      last_successful_operation: this.lastSuccessTime
        ? new Date(this.lastSuccessTime).toISOString()
        : null,
      last_quota_error_at: this.lastQuotaTime
        ? new Date(this.lastQuotaTime).toISOString()
        : null,
      next_health_check_at: this.nextHealthCheckTime
        ? new Date(this.nextHealthCheckTime).toISOString()
        : null,
      backoff_seconds: BACKOFF_SCHEDULE[Math.max(0, this.backoffIndex - 1)],
      queue,
    };
  }
}

export const recoveryQueueNode = new NodeRecoveryQueue();
