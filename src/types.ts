export interface AuthUser {
  user_id: number;
  role: 'super_admin';
  name: string;
}

export interface AuthSession {
  authenticated: boolean;
  user?: AuthUser;
  token?: string;
  expires_at?: string;
}

export interface ChannelItem {
  chat_id: number;
  title: string;
  username: string | null;
  owner_user_id: number;
  active: boolean;
  status: 'ACTIVE' | 'PAUSED' | 'BLOCKED';
  premium: boolean;
  can_post: boolean;
  daily_limit: number;
  plan: 'free' | 'contract';
  schedule_mode: 'instant' | 'custom' | string;
  schedule_times: string[];
  selected_sources: string[];
  post_language?: 'uz' | 'uz_cyrl' | 'ru' | 'en' | 'auto' | string;
  is_premium_eligible?: boolean;
  premium_enabled?: boolean;
  footer_type?: 'none' | 'text' | 'text_link' | 'inline_button';
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

export interface CategoryItem {
  id: string;
  name: string;
  slug: string;
  description: string;
  icon: string;
  active: boolean;
  sort_order: number;
  source_count?: number;
  created_at: string;
  updated_at: string;
}

export interface SourceItem {
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
}

export interface TestFeedResult {
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

export interface PostItem {
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

export interface CentralChannel {
  id: string; // chat_id as string
  chat_id: number;
  title: string;
  username: string | null;
  added_by: number;
  active: boolean;
  bot_is_admin: boolean;
  can_post?: boolean;
  post_count: number;
  last_post_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface PremiumMediaItem {
  type: string;
  file_id: string;
  caption?: string;
}

export interface PremiumPost {
  id: string; // prem_{central_chat_id}_{central_message_id}
  source_chat_id?: number;
  source_message_id?: number;
  central_chat_id: number;
  central_message_id: number;
  media_type: 'text' | 'photo' | 'video' | 'document' | 'audio' | 'voice' | 'animation' | 'media_group' | string;
  text: string;
  media_file_id: string | null;
  media_group_id: string | null;
  media_items?: PremiumMediaItem[];
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

export interface ScheduleSlot {
  id: string;
  time: string; // "08:00", "13:00", "20:30"
  label: string;
  active: boolean;
  timezone: string; // "Asia/Tashkent"
  created_at: string;
  updated_at: string;
}

export interface CentralPostBaseStatus {
  chat_id: number;
  title: string;
  username: string | null;
  bot_is_admin: boolean;
  can_post_messages: boolean;
  status_message: string;
  action_required: boolean;
  post_count: number;
  last_post_at: string | null;
}

export interface PostDistributionItem {
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

export interface UserItem {
  user_id: number;
  username: string | null;
  first_name: string;
  plan: 'free' | 'contract';
  custom_limit: number | null;
  created_at: string;
  updated_at: string;
  channels_count?: number;
  channels?: Array<{
    chat_id: number;
    title: string;
    plan: string;
    daily_limit: number;
  }>;
}

export interface AlertItem {
  id: string;
  severity: 'critical' | 'warning' | 'info';
  title: string;
  message: string;
  count?: number;
  action?: string;
}

export interface ActivityItem {
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

export interface DashboardMetrics {
  total_channels: number;
  active_channels: number;
  permission_issues: number;
  total_sources: number;
  active_sources: number;
  error_sources: number;
  total_users: number;
  contract_users: number;
  posts_delivered_today: number;
  total_delivered: number;
  total_posts: number;
  queued_posts: number;
  assigned_posts: number;
  delivered_posts: number;
  failed_posts: number;
  expired_posts: number;
  pool_queued: number;
  pool_assigned?: number;
  pool_delivered: number;
  pool_expired: number;
  pool_failed?: number;
  pool_total: number;
  pool_max: number;
}

export interface FirestoreHealth {
  status: 'online' | 'quota_exceeded' | 'standby' | 'healthy' | 'degraded' | 'recovering' | string;
  canonical_status?: string;
  message: string;
  last_quota_notice?: string | null;
  queue?: {
    total_pending: number;
    total_processing: number;
    total_failed_permanent: number;
    total_queue_size: number;
    oldest_item_age_seconds: number;
    oldest_item_created_at: string | null;
  };
  diagnostics?: {
    firestore_status: string;
    is_stale: boolean;
    message: string;
    firestore_429_count: number;
    firestore_read_errors: number;
    firestore_write_errors: number;
    next_health_check_at: string | null;
    backoff_seconds: number;
  };
}

export interface SystemPulse {
  bot: 'online' | 'standby' | 'error';
  gardener: 'running' | 'stopped';
  storage_mode: string;
  uptime_seconds: number;
  last_sync: string;
}

export interface DashboardData {
  metrics: DashboardMetrics;
  firestore_health?: FirestoreHealth;
  pulse: SystemPulse;
  recent_activity: ActivityItem[];
  alerts: AlertItem[];
}

export interface PostsResponse {
  status: string;
  total: number;
  page: number;
  limit: number;
  total_pages: number;
  counts: {
    all: number;
    queued: number;
    assigned: number;
    delivered: number;
    failed: number;
    expired: number;
  };
  pool_max: number;
  firestore_status?: 'online' | 'quota_exceeded' | 'standby';
  firestore_message?: string;
  posts: PostItem[];
}

export interface DistributionChannelSummary {
  chat_id: number;
  title: string;
  plan: string;
  daily_limit: number;
  today_delivered: number;
  schedule_mode: string;
  last_delivered_at: string | null;
  ready: boolean;
}

export interface DistributionData {
  engine_state: string;
  fair_queue_policy: string;
  today_date: string;
  recent_deliveries: ActivityItem[];
  channels_summary: DistributionChannelSummary[];
}

export interface SystemComponent {
  status: 'online' | 'standby' | 'error';
  name: string;
}

export interface SystemMonitorData {
  components: Record<string, SystemComponent>;
  metrics: {
    uptime_seconds: number;
    memory_heap_mb?: number;
    memory_rss_mb?: number;
    node_version?: string;
    python_version?: string;
  };
}

export interface LogEntry {
  timestamp: string;
  level: 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL';
  component: string;
  message: string;
}

export interface TranslatorStatus {
  status: string;
  configured: boolean;
  model: string;
  cache_enabled: boolean;
  supported_languages: string[];
  last_success_at: string | null;
  last_error_at: string | null;
  message: string;
}

export interface SettingsConfig {
  timezone: string;
  super_admin_id: number;
  default_free_limit: number;
  retention_days: number;
  fetch_interval_sec: number;
  distribution_interval_sec: number;
  cleanup_interval_sec: number;
  database_path?: string;
  storage_type: string;
}
