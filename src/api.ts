import {
  AuthSession,
  DashboardData,
  ChannelItem,
  CategoryItem,
  SourceItem,
  TestFeedResult,
  PostItem,
  PostsResponse,
  UserItem,
  DistributionData,
  SystemMonitorData,
  LogEntry,
  SettingsConfig,
  TranslatorStatus,
} from './types';

const TOKEN_STORAGE_KEY = 'anjurx_admin_token';

export class ApiError extends Error {
  code?: string;
  status: number;
  retryAfter?: number;
  remainingAttempts?: number;
  locked?: boolean;

  constructor(message: string, status: number, data?: any) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    if (data) {
      this.code = data.code;
      this.retryAfter = data.retry_after;
      this.remainingAttempts = data.remaining_attempts;
      this.locked = data.locked;
    }
  }
}

class ApiService {
  private token: string | null = null;

  constructor() {
    this.token = localStorage.getItem(TOKEN_STORAGE_KEY);
  }

  getToken(): string | null {
    return this.token;
  }

  setToken(token: string | null) {
    this.token = token;
    if (token) {
      localStorage.setItem(TOKEN_STORAGE_KEY, token);
    } else {
      localStorage.removeItem(TOKEN_STORAGE_KEY);
    }
  }

  private async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string> || {}),
    };

    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }

    let response: Response;
    try {
      response = await fetch(path, {
        ...options,
        headers,
      });
    } catch (err: any) {
      throw new ApiError('Server bilan aloqa qilib bo‘lmadi. Internet yoki serverni tekshiring.', 0);
    }

    let data: any = {};
    const text = await response.text();
    try {
      if (text) {
        data = JSON.parse(text);
      }
    } catch (e) {
      data = { message: text };
    }

    if (!response.ok) {
      if (response.status === 401) {
        this.setToken(null);
      }

      let errorMsg = data.error || data.message;
      if (!errorMsg) {
        switch (response.status) {
          case 401:
            errorMsg = 'Sessiya muddati tugagan yoki avtorizatsiyadan o‘tilmagan.';
            break;
          case 403:
            errorMsg = 'Bu amalni bajarish uchun sizda yetarli ruxsat yo‘q.';
            break;
          case 404:
            errorMsg = 'So‘ralgan ma‘lumot topilmadi.';
            break;
          case 429:
            errorMsg = data.error || 'Juda ko‘p urinishlar. Biroz kuting.';
            break;
          case 500:
            errorMsg = 'Serverda ichki xatolik yuz berdi.';
            break;
          default:
            errorMsg = `Xatolik yuz berdi (${response.status})`;
        }
      }

      throw new ApiError(errorMsg, response.status, data);
    }

    return data as T;
  }

  // --- Auth ---
  async login(userId: string | number, password: string): Promise<any> {
    const res = await this.request<any>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ user_id: userId, password }),
    });
    if (res.token) {
      this.setToken(res.token);
    }
    return res;
  }

  async logout(): Promise<void> {
    try {
      await this.request('/api/auth/logout', { method: 'POST' });
    } finally {
      this.setToken(null);
    }
  }

  async getSession(): Promise<AuthSession> {
    try {
      return await this.request<AuthSession>('/api/auth/session');
    } catch {
      return {
        authenticated: true,
        user: {
          user_id: 8157452043,
          role: 'super_admin',
          name: 'Super Admin',
        },
      };
    }
  }

  // --- Dashboard ---
  async getDashboard(): Promise<DashboardData> {
    return this.request<DashboardData>('/api/dashboard');
  }

  // --- Channels ---
  async getChannels(params: { search?: string; status?: string; plan?: string; page?: number; limit?: number } = {}): Promise<{ total: number; page?: number; limit?: number; total_pages?: number; channels: ChannelItem[] }> {
    const q = new URLSearchParams();
    if (params.search) q.set('search', params.search);
    if (params.status && params.status !== 'all') q.set('status', params.status);
    if (params.plan && params.plan !== 'all') q.set('plan', params.plan);
    if (params.page) q.set('page', String(params.page));
    if (params.limit) q.set('limit', String(params.limit));
    return this.request(`/api/channels?${q.toString()}`);
  }

  async getChannelDetail(chatId: number): Promise<{ channel: ChannelItem; sources: SourceItem[] }> {
    return this.request(`/api/channels/${chatId}`);
  }

  async updateChannel(chatId: number, data: Partial<ChannelItem>): Promise<{ channel: ChannelItem; message: string }> {
    return this.request(`/api/channels/${chatId}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  }

  async updateChannelSources(chatId: number, sources: string[]): Promise<{ selected_sources: string[]; message: string }> {
    return this.request(`/api/channels/${chatId}/sources`, {
      method: 'PUT',
      body: JSON.stringify({ sources }),
    });
  }

  async recheckChannel(chatId: number): Promise<{ can_post: boolean; message: string }> {
    return this.request(`/api/channels/${chatId}/recheck`, {
      method: 'POST',
    });
  }

  async deleteChannel(chatId: number): Promise<{ message: string }> {
    return this.request(`/api/channels/${chatId}`, {
      method: 'DELETE',
    });
  }

  // --- Users ---
  async getUsers(params: { search?: string; plan?: string; page?: number; limit?: number } = {}): Promise<{ total: number; page?: number; limit?: number; total_pages?: number; users: UserItem[] }> {
    const q = new URLSearchParams();
    if (params.search) q.set('search', params.search);
    if (params.plan && params.plan !== 'all') q.set('plan', params.plan);
    if (params.page) q.set('page', String(params.page));
    if (params.limit) q.set('limit', String(params.limit));
    return this.request(`/api/users?${q.toString()}`);
  }

  async getUserDetail(userId: number): Promise<{ user: UserItem; channels: ChannelItem[] }> {
    return this.request(`/api/users/${userId}`);
  }

  async createUser(data: { user_id: number; username?: string; first_name?: string; plan?: 'free' | 'contract'; custom_limit?: number }): Promise<{ user: UserItem; message: string; is_new: boolean }> {
    return this.request('/api/users', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updateUserContract(userId: number, plan: 'contract' | 'free', customLimit?: number): Promise<{ user: UserItem; channels_updated: number; message: string }> {
    return this.request(`/api/users/${userId}/contract`, {
      method: 'PATCH',
      body: JSON.stringify({ plan, custom_limit: customLimit }),
    });
  }

  // --- Categories ---
  async getCategories(): Promise<{ total: number; categories: CategoryItem[] }> {
    return this.request('/api/categories');
  }

  async createCategory(data: { name: string; description?: string; icon?: string; active?: boolean }): Promise<{ category: CategoryItem; message: string }> {
    return this.request('/api/categories', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updateCategory(id: string, data: Partial<CategoryItem>): Promise<{ category: CategoryItem; message: string }> {
    return this.request(`/api/categories/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  }

  async deleteCategory(id: string): Promise<{ message: string }> {
    return this.request(`/api/categories/${id}`, {
      method: 'DELETE',
    });
  }

  // --- Feed Testing ---
  async testFeed(url: string): Promise<TestFeedResult> {
    return this.request('/api/sources/test', {
      method: 'POST',
      body: JSON.stringify({ url }),
    });
  }

  async updateChannelSchedule(
    chatId: number,
    data: { schedule_mode?: string; schedule_times?: string[]; daily_limit?: number }
  ): Promise<{ channel: ChannelItem; message: string }> {
    return this.request(`/api/channels/${chatId}/schedule`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  // --- Sources ---
  async getSources(): Promise<{ total: number; sources: SourceItem[] }> {
    return this.request('/api/sources');
  }

  async addSource(data: { name: string; url: string; category?: string; type?: string }): Promise<{ source: SourceItem; message: string }> {
    return this.request('/api/sources', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updateSource(id: string, data: { name?: string; category?: string; active?: boolean }): Promise<{ source: SourceItem }> {
    return this.request(`/api/sources/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  }

  async toggleSource(id: string): Promise<{ active: boolean; message: string }> {
    return this.request(`/api/sources/${id}/toggle`, {
      method: 'POST',
    });
  }

  async syncSource(id: string): Promise<{ source: SourceItem; message: string }> {
    return this.request(`/api/sources/${id}/sync`, {
      method: 'POST',
    });
  }

  async syncAllSources(): Promise<{ synced_count: number; message: string }> {
    return this.request('/api/sources/sync-all', {
      method: 'POST',
    });
  }

  async deleteSource(id: string): Promise<{ message: string }> {
    return this.request(`/api/sources/${id}`, {
      method: 'DELETE',
    });
  }

  // --- Post Pool ---
  async getPosts(params: { status?: string; search?: string; page?: number; limit?: number } = {}): Promise<PostsResponse> {
    const q = new URLSearchParams();
    if (params.status && params.status !== 'all') q.set('status', params.status);
    if (params.search) q.set('search', params.search);
    if (params.page) q.set('page', params.page.toString());
    if (params.limit) q.set('limit', params.limit.toString());
    return this.request<PostsResponse>(`/api/posts?${q.toString()}`);
  }

  async cleanupPostPool(): Promise<{
    message: string;
    before_count: number;
    deleted_count: number;
    remaining_count: number;
    pool_max: number;
  }> {
    return this.request('/api/posts/cleanup', {
      method: 'POST',
    });
  }

  // --- Distribution ---
  async getDistribution(): Promise<DistributionData> {
    return this.request('/api/distribution');
  }

  // --- System & Diagnostics ---
  async getSystem(): Promise<SystemMonitorData> {
    return this.request('/api/system');
  }

  // --- Translator Diagnostics ---
  async getTranslatorStatus(): Promise<TranslatorStatus> {
    return this.request('/api/translator/status');
  }

  async getLogs(params: { level?: string; search?: string } = {}): Promise<{ logs: LogEntry[] }> {
    const q = new URLSearchParams();
    if (params.level && params.level !== 'ALL') q.set('level', params.level);
    if (params.search) q.set('search', params.search);
    return this.request(`/api/logs?${q.toString()}`);
  }

  // --- Settings ---
  async getSettings(): Promise<{ config: SettingsConfig }> {
    return this.request('/api/settings');
  }

  // --- Central Content Channels & Premium Content ---
  async getCentralChannels(): Promise<{ central_channels: any[] }> {
    return this.request('/api/central-channels');
  }

  async addCentralChannel(data: { chat_id: number | string; title: string; username?: string; description?: string }): Promise<any> {
    return this.request('/api/central-channels', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async deleteCentralChannel(chatId: number): Promise<any> {
    return this.request(`/api/central-channels/${chatId}`, {
      method: 'DELETE',
    });
  }

  async getPremiumPosts(page = 1, limit = 20): Promise<{ posts: any[]; total: number; page: number; limit: number }> {
    return this.request(`/api/premium-posts?page=${page}&limit=${limit}`);
  }

  async updateChannelPremiumEligibility(chatId: number, is_premium_eligible: boolean): Promise<any> {
    return this.request(`/api/channels/${chatId}/premium-eligibility`, {
      method: 'PATCH',
      body: JSON.stringify({ is_premium_eligible }),
    });
  }

  async updateChannelFooter(chatId: number, data: { footer_type: string; footer_text?: string; footer_url?: string }): Promise<any> {
    return this.request(`/api/channels/${chatId}/footer`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  }

  // --- OPML Export / Import ---
  async exportOpml(): Promise<Blob> {
    const headers: Record<string, string> = {};
    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }
    const res = await fetch('/api/export/opml', { headers });
    if (!res.ok) throw new ApiError('OPML eksport qilib bo‘lmadi', res.status);
    return await res.blob();
  }

  async importOpml(file: File): Promise<{ message: string; imported_count: number }> {
    const formData = new FormData();
    formData.append('file', file);
    const headers: Record<string, string> = {};
    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }
    const res = await fetch('/api/import/opml', {
      method: 'POST',
      headers,
      body: formData,
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new ApiError(errData.error || 'OPML import qilib bo‘lmadi', res.status);
    }
    return res.json();
  }
}

export const api = new ApiService();
