export interface TelegramUser {
  _id: string;
  user_id: number;
  username?: string;
  first_name?: string;
  last_name?: string;
  created_at: string;
  warnings_count?: number;
  is_banned?: boolean;
  is_muted?: boolean;
  language_code?: string;
}

export interface GuardSettings {
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
}

export interface ForceSubChannel {
  channel_id: string | number;
  username: string;
  title: string;
  invite_link?: string;
  is_active: boolean;
}

export interface TelegramGroup {
  _id: string;
  group_id: number;
  title: string;
  username?: string;
  members_count: number;
  guard: GuardSettings;
  fsub_channels: ForceSubChannel[];
  created_at: string;
}

export interface ModerationLog {
  id: string;
  group_id: number;
  group_title: string;
  user_id: number;
  username?: string;
  action: 'warn' | 'mute' | 'ban' | 'delete' | 'clear_warns';
  reason: string;
  timestamp: string;
}

export interface SystemStats {
  total_users: number;
  total_groups: number;
  active_guard_groups: number;
  messages_scanned: number;
  spam_blocked: number;
  links_deleted: number;
  warnings_issued: number;
  uptime_seconds: number;
}
