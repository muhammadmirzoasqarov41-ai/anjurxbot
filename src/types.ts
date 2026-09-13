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

export interface TelegramGroup {
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
  guard: GuardSettings;
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
  violations_blocked: number;
  spams_prevented: number;
  links_removed: number;
  uptime_seconds?: number;
  spam_blocked?: number;
  links_deleted?: number;
}
