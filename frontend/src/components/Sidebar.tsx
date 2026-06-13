"use client";

import { MessageSquare, Map, FileText } from "lucide-react";

type Tab = "chat" | "map" | "services";

interface SidebarProps {
  activeTab: Tab;
  setActiveTab: (tab: Tab) => void;
}

const tabs = [
  { id: "chat" as Tab, label: "Czat", icon: MessageSquare },
  { id: "map" as Tab, label: "Mapa", icon: Map },
  { id: "services" as Tab, label: "Usługi", icon: FileText },
];

export default function Sidebar({ activeTab, setActiveTab }: SidebarProps) {
  return (
    <aside className="w-16 md:w-56 border-r border-lublin-border bg-lublin-surface flex flex-col shrink-0">
      <nav className="flex-1 p-2 md:p-3 space-y-1">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`w-full flex items-center gap-3 px-3 py-3 rounded-xl transition-colors ${
                isActive
                  ? "bg-lublin-green text-white"
                  : "text-lublin-muted hover:bg-white hover:text-lublin-text"
              }`}
            >
              <Icon size={20} />
              <span className="hidden md:inline text-sm font-medium">
                {tab.label}
              </span>
            </button>
          );
        })}
      </nav>
      <div className="p-3 border-t border-lublin-border">
        <div className="hidden md:block text-xs text-lublin-muted text-center">
          <p>399 usług • 55 wydziałów</p>
          <p className="mt-1">Powered by AI + BIP</p>
        </div>
      </div>
    </aside>
  );
}
