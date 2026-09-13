export interface RSSFeed {
  id: string;
  url: string;
  title: string;
  link: string;
  description: string;
  subscribers_count: number;
  subscribers: number[];
  error_count: number;
  last_error?: string;
  last_check?: string;
  etag?: string;
  last_modified?: string;
  format?: string;
}

export interface RSSSubscriber {
  chat_id: number;
  title: string;
  type: 'private' | 'group' | 'supergroup' | 'channel';
  feed_count: number;
  feeds: string[];
  joined_at: string;
}

export interface DeliveredPost {
  id: string;
  title: string;
  link: string;
  feed_title: string;
  feed_id: string;
  published_at: string;
  delivered_at: string;
  recipients_count: number;
}

export interface RSSStats {
  total_feeds: number;
  total_subscribers: number;
  active_subscriptions: number;
  posts_delivered: number;
  uptime_seconds?: number;
  bot_status?: string;
  bot_username?: string;
}
