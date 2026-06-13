"use client";

import { useState } from "react";
import Chat from "@/components/Chat";
import MapPanel from "@/components/MapPanel";
import Sidebar from "@/components/Sidebar";
import Header from "@/components/Header";

type Tab = "chat" | "map" | "services";

export default function Home() {
  const [activeTab, setActiveTab] = useState<Tab>("chat");
  const [mapHighlight, setMapHighlight] = useState<string | null>(null);

  return (
    <div className="h-screen flex flex-col overflow-hidden">
      <Header />
      <div className="flex-1 flex overflow-hidden">
        <Sidebar activeTab={activeTab} setActiveTab={setActiveTab} />
        <main className="flex-1 flex overflow-hidden">
          {activeTab === "chat" && (
            <Chat onLocationMention={setMapHighlight} />
          )}
          {activeTab === "map" && <MapPanel highlight={mapHighlight} />}
          {activeTab === "services" && <ServicesPanel />}
        </main>
      </div>
    </div>
  );
}

function ServicesPanel() {
  const [search, setSearch] = useState("");
  const [results, setResults] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  async function handleSearch() {
    if (!search.trim()) return;
    setLoading(true);
    try {
      const res = await fetch("/api/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: search, top_k: 10 }),
      });
      const data = await res.json();
      setResults(data.results || []);
    } catch {
      setResults([]);
    }
    setLoading(false);
  }

  return (
    <div className="flex-1 flex flex-col p-6 overflow-hidden">
      <h2 className="text-2xl font-bold mb-4">Usługi urzędowe</h2>
      <div className="flex gap-3 mb-6">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSearch()}
          placeholder="Czego szukasz? np. dowód osobisty, meldunek..."
          className="flex-1 px-5 py-3 rounded-full border border-lublin-border focus:outline-none focus:border-lublin-green"
        />
        <button onClick={handleSearch} className="btn-primary" disabled={loading}>
          {loading ? "..." : "Szukaj"}
        </button>
      </div>
      <div className="flex-1 overflow-y-auto space-y-4">
        {results.map((r, i) => (
          <div key={i} className="card">
            <h3 className="font-semibold text-lg mb-2">
              {r.metadata?.title || "Dokument"}
            </h3>
            <p className="text-lublin-muted text-sm mb-2">
              {r.metadata?.department} • {r.metadata?.type}
            </p>
            <p className="text-sm line-clamp-3">{r.content}</p>
            {r.metadata?.source_url && (
              <a
                href={r.metadata.source_url}
                target="_blank"
                rel="noopener"
                className="text-lublin-green text-sm mt-2 inline-block hover:underline"
              >
                Źródło BIP →
              </a>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
