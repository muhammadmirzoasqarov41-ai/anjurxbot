import React from 'react';
import { Send, ExternalLink, Clock, CheckCircle2 } from 'lucide-react';
import { DeliveredPost } from '../types';

interface PostsViewProps {
  posts: DeliveredPost[];
}

export const PostsView: React.FC<PostsViewProps> = ({ posts }) => {
  return (
    <div className="space-y-6">
      <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-5">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-bold text-white uppercase tracking-wider flex items-center space-x-2">
              <Send className="w-4 h-4 text-orange-400" />
              <span>Yetkazilgan Yangiliklar va Maqolalar Oqimi</span>
            </h3>
            <p className="text-xs text-zinc-400 mt-0.5">
              Gardener foni tomonidan qayta ishlanib, Telegram kanallari va guruhlariga yuborilgan so'nggi xabarlar
            </p>
          </div>
          <div className="text-right">
            <span className="text-xs text-zinc-500">So'nggi yozuvlar:</span>
            <span className="text-lg font-mono font-bold text-emerald-400 ml-2">{posts.length} ta</span>
          </div>
        </div>
      </div>

      <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl overflow-hidden">
        {posts.length === 0 ? (
          <div className="p-12 text-center text-zinc-500">
            <Send className="w-8 h-8 mx-auto mb-3 opacity-30 text-orange-400" />
            <p className="text-sm">Hozircha yetkazilgan maqolalar jurnali bo'sh.</p>
            <p className="text-xs text-zinc-600 mt-1">Lentalarga yangi maqolalar chiqqanda ular shu yerda qayd etiladi.</p>
          </div>
        ) : (
          <div className="divide-y divide-zinc-800/60">
            {posts.map((post) => (
              <div key={post.id} className="p-4 hover:bg-zinc-800/30 transition-colors flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
                <div className="space-y-1">
                  <div className="flex items-center space-x-2">
                    <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-orange-500/10 text-orange-400 border border-orange-500/20">
                      {post.feed_title}
                    </span>
                    <a
                      href={post.link}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="font-bold text-white hover:text-orange-400 flex items-center space-x-1"
                    >
                      <span>{post.title}</span>
                      <ExternalLink className="w-3 h-3 text-zinc-500" />
                    </a>
                  </div>
                  <div className="flex items-center space-x-4 text-zinc-500 text-[11px]">
                    <span className="flex items-center">
                      <Clock className="w-3 h-3 mr-1 text-zinc-600" />
                      E'lon qilingan: {post.published_at ? new Date(post.published_at).toLocaleTimeString() : 'Noma’lum'}
                    </span>
                    <span className="flex items-center text-emerald-400">
                      <CheckCircle2 className="w-3 h-3 mr-1" />
                      Yetkazilgan: {post.delivered_at ? new Date(post.delivered_at).toLocaleTimeString() : 'Hozir'}
                    </span>
                  </div>
                </div>

                <div className="flex items-center space-x-2 sm:self-center">
                  <span className="px-2.5 py-1 rounded bg-zinc-800 text-zinc-300 font-mono text-[11px]">
                    {post.recipients_count} ta chatga
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
