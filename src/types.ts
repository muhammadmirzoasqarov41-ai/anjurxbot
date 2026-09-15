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
  can_post: boolean;
  daily_limit: number;
  plan: 'free' | 'contract';
  schedule_mode: 'instant' | 'custom' | string;
  schedule_times: string[];
  selected_sources: string[];
  post_language?: 'uz' | 'ru' | 'en' | 'auto' | string;
  today_delivered_count: number;
  today_delivered_slots?: string[];
  today_date: string;
  last_delivered_at: string | null;
  total_delivered_count: number;
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
  pool_queued: number;
  pool_delivered: number;
  pool_expired: number;
  pool_total: number;
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
  pulse: SystemPulse;
  recent_activity: ActivityItem[];
  alerts: AlertItem[];
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
