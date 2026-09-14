import React from 'react';
import { NavTab } from './BottomNav';
import {
  Users,
  Send,
  Server,
  Terminal,
  Settings,
  Download,
  X,
  ChevronRight,
  Shield,
} from 'lucide-react';

interface MoreMenuModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectTab: (tab: NavTab) => void;
  onLogout?: () => void;
}

export const MoreMenuModal: React.FC<MoreMenuModalProps> = ({
  isOpen,
  onClose,
  onSelectTab,
}) => {
  if (!isOpen) return null;

  const menuItems: Array<{
    id: NavTab;
    label: string;
    description: string;
    icon: React.ComponentType<{ className?: string }>;
    color: string;
  }> = [
    {
      id: 'users',
      label: 'Foydalanuvchilar va Tariflar',
      description: 'Contract biriktirish va limitlarni boshqarish',
      icon: Users,
      color: 'text-blue-400 bg-blue-500/10 border-blue-500/20',
    },
    {
      id: 'distribution',
      label: 'Taqsimot Nazorati',
      description: 'Fair Queue va bugungi yetkazish jurnali',
      icon: Send,
      color: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20',
    },
    {
      id: 'system',
      label: 'Tizim Diagnostikasi',
      description: 'Bot, Gardener, Firestore va xotira holati',
      icon: Server,
      color: 'text-indigo-400 bg-indigo-500/10 border-indigo-500/20',
    },
    {
      id: 'logs',
      label: 'Operatsion Jurnallar',
      description: 'Tizim hodisalari va xatolar arxivi',
      icon: Terminal,
      color: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
    },
    {
      id: 'settings',
      label: 'Tizim Parametrlari',
      description: 'Timezone, intervallar va global sozlamalar',
      icon: Settings,
      color: 'text-zinc-300 bg-zinc-800 border-zinc-700',
    },
  ];

  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-end sm:items-center justify-center p-0 sm:p-4 animate-in fade-in duration-200">
      <div className="bg-zinc-950 border border-zinc-800 rounded-t-3xl sm:rounded-2xl w-full max-w-md p-4 pb-8 sm:pb-4 shadow-2xl animate-in slide-in-from-bottom duration-200">
        <div className="flex items-center justify-between pb-3 border-b border-zinc-800 mb-3">
          <div className="flex items-center gap-2">
            <Shield className="w-4 h-4 text-emerald-400" />
            <span className="text-sm font-bold text-white">Qo‘shimcha Bo‘limlar</span>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-zinc-400 hover:text-white rounded-xl bg-zinc-900"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="space-y-2">
          {menuItems.map((item) => {
            const Icon = item.icon;
            return (
              <div
                key={item.id}
                onClick={() => {
                  onSelectTab(item.id);
                  onClose();
                }}
                className="p-3 bg-zinc-900/80 hover:bg-zinc-800/90 border border-zinc-800/80 rounded-xl cursor-pointer flex items-center justify-between gap-3 transition-colors"
              >
                <div className="flex items-center gap-3">
                  <div className={`p-2 rounded-xl border ${item.color}`}>
                    <Icon className="w-4 h-4" />
                  </div>
                  <div>
                    <h4 className="text-xs font-semibold text-white">{item.label}</h4>
                    <p className="text-[11px] text-zinc-400">{item.description}</p>
                  </div>
                </div>
                <ChevronRight className="w-4 h-4 text-zinc-600 shrink-0" />
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
