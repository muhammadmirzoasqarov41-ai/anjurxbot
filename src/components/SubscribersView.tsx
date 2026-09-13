import React from 'react';
import { Users, Send, MessageSquare, Radio, Shield } from 'lucide-react';
import { RSSSubscriber } from '../types';

interface SubscribersViewProps {
  subscribers: RSSSubscriber[];
}

export const SubscribersView: React.FC<SubscribersViewProps> = ({ subscribers }) => {
  const getTypeBadge = (type: string) => {
    switch (type) {
      case 'channel':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold bg-purple-500/10 text-purple-400 border border-purple-500/20">
            <Radio className="w-3 h-3 mr-1" />
            Kanal
          </span>
        );
      case 'group':
      case 'supergroup':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20">
            <MessageSquare className="w-3 h-3 mr-1" />
            Guruh
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold bg-zinc-800 text-zinc-300 border border-zinc-700">
            <Users className="w-3 h-3 mr-1" />
            Shaxsiy Chat
          </span>
        );
    }
  };

  return (
    <div className="space-y-6">
      <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-5">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-bold text-white uppercase tracking-wider flex items-center space-x-2">
              <Users className="w-4 h-4 text-orange-400" />
              <span>Telegram Obunachilar Ro'yxati</span>
            </h3>
            <p className="text-xs text-zinc-400 mt-0.5">
              Lentalardan yangilik qabul qiluvchi shaxsiy chatlar, guruhlar va kanallar
            </p>
          </div>
          <div className="text-right">
            <span className="text-xs text-zinc-500">Jami obunachi chatlar:</span>
            <span className="text-lg font-mono font-bold text-white ml-2">{subscribers.length}</span>
          </div>
        </div>
      </div>

      <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl overflow-hidden">
        {subscribers.length === 0 ? (
          <div className="p-12 text-center text-zinc-500">
            <Users className="w-8 h-8 mx-auto mb-3 opacity-30 text-orange-400" />
            <p className="text-sm">Hozircha hech qanday obunachi chat mavjud emas.</p>
            <p className="text-xs text-zinc-600 mt-1">Botga Telegram orqali <code>/sub &lt;url&gt;</code> yuborilganda bu yerda paydo bo'ladi.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-zinc-950/70 border-b border-zinc-800 text-zinc-400 uppercase tracking-wider text-[10px]">
                <tr>
                  <th className="py-3 px-4">Chat ID</th>
                  <th className="py-3 px-4">Chat Nomi</th>
                  <th className="py-3 px-4">Chat Turi</th>
                  <th className="py-3 px-4 text-center">Faol Feedlar Soni</th>
                  <th className="py-3 px-4">Qo'shilgan Vaqti</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/60">
                {subscribers.map((sub) => (
                  <tr key={sub.chat_id} className="hover:bg-zinc-800/30 transition-colors">
                    <td className="py-3 px-4 font-mono text-zinc-400">
                      {sub.chat_id}
                    </td>
                    <td className="py-3 px-4 font-semibold text-white">
                      {sub.title || `Chat ${sub.chat_id}`}
                    </td>
                    <td className="py-3 px-4">
                      {getTypeBadge(sub.type)}
                    </td>
                    <td className="py-3 px-4 text-center">
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-mono font-semibold bg-orange-500/10 text-orange-400 border border-orange-500/20">
                        {sub.feed_count} ta
                      </span>
                    </td>
                    <td className="py-3 px-4 text-zinc-400 text-[11px]">
                      {sub.joined_at ? new Date(sub.joined_at).toLocaleDateString() : 'Noma’lum'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
