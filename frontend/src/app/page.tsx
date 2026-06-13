"use client";

import { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import dynamic from "next/dynamic";

const MapEmbed = dynamic(() => import("@/components/MapEmbed"), { ssr: false });

interface Message {
  role: "user" | "assistant";
  content: string;
  sources?: Array<{ url: string; title: string }>;
  showMap?: boolean;
}

const SUGGESTIONS = [
  "Jak wyrobić dowód osobisty?",
  "Gdzie zarejestrować samochód?",
  "Jakie dokumenty do ślubu?",
  "Ile kosztuje wypis z rejestru?",
  "Kto jest prezydentem?",
  "Pozwolenie na budowę",
];

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function send(text?: string) {
    const question = text || input.trim();
    if (!question || loading) return;

    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: question }]);
    setLoading(true);

    try {
      const res = await fetch("/api/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });
      const data = await res.json();

      const showMap = /gdzie|adres|lokalizacja|mapa|dojazd|godziny/i.test(question);

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: data.answer || "Nie udało się uzyskać odpowiedzi.",
          sources: data.sources || [],
          showMap,
        },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Błąd połączenia. Spróbuj ponownie." },
      ]);
    }
    setLoading(false);
    inputRef.current?.focus();
  }

  return (
    <div className="min-h-[100dvh] flex flex-col bg-white">
      {/* Header */}
      <header className="sticky top-0 z-50 bg-white/90 backdrop-blur-md border-b border-lublin-border px-4 py-3">
        <div className="max-w-2xl mx-auto flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-lublin-green flex items-center justify-center shrink-0">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round">
              <path d="M3 21h18" />
              <path d="M5 21V7l7-4 7 4v14" />
              <path d="M9 21v-4h6v4" />
              <path d="M9 10h1" />
              <path d="M14 10h1" />
            </svg>
          </div>
          <div>
            <h1 className="text-[17px] font-bold leading-tight text-lublin-text">
              Asystent Miasta Lublin
            </h1>
            <p className="text-xs text-lublin-muted">Sprawy urzędowe • AI</p>
          </div>
          <div className="ml-auto">
            <span className="text-[11px] text-lublin-muted bg-lublin-surface border border-lublin-border px-2.5 py-1 rounded-full">
              BIP
            </span>
          </div>
        </div>
      </header>

      {/* Messages */}
      <main className="flex-1 overflow-y-auto">
        <div className="max-w-2xl mx-auto px-4 py-6">
          {messages.length === 0 ? (
            <Welcome onSuggestion={send} />
          ) : (
            <div className="space-y-4">
              {messages.map((msg, i) => (
                <div key={i}>
                  {msg.role === "user" ? (
                    <div className="flex justify-end">
                      <div className="chat-user">{msg.content}</div>
                    </div>
                  ) : (
                    <div className="flex justify-start">
                      <div className="chat-ai">
                        <div className="prose prose-sm max-w-none [&_p]:mb-2 [&_ul]:mb-2 [&_li]:mb-0.5">
                          <ReactMarkdown>{msg.content}</ReactMarkdown>
                        </div>
                        {msg.sources && msg.sources.length > 0 && (
                          <div className="flex flex-wrap gap-2 mt-3 pt-3 border-t border-lublin-border">
                            {msg.sources.slice(0, 4).map((s, j) => (
                              <a
                                key={j}
                                href={s.url}
                                target="_blank"
                                rel="noopener"
                                className="source-chip"
                              >
                                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                  <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                                  <polyline points="15 3 21 3 21 9" />
                                  <line x1="10" y1="14" x2="21" y2="3" />
                                </svg>
                                {s.title?.slice(0, 30) || "Źródło"}
                              </a>
                            ))}
                          </div>
                        )}
                        {msg.showMap && (
                          <div className="mt-4 map-container h-[200px]">
                            <MapEmbed />
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              ))}
              {loading && (
                <div className="flex justify-start">
                  <div className="chat-ai">
                    <div className="flex items-center gap-1.5">
                      <div className="w-2 h-2 bg-lublin-green rounded-full animate-bounce" />
                      <div className="w-2 h-2 bg-lublin-green rounded-full animate-bounce [animation-delay:0.15s]" />
                      <div className="w-2 h-2 bg-lublin-green rounded-full animate-bounce [animation-delay:0.3s]" />
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>
      </main>

      {/* Input */}
      <footer className="sticky bottom-0 bg-white border-t border-lublin-border px-4 py-3 pb-[env(safe-area-inset-bottom,12px)]">
        <div className="max-w-2xl mx-auto flex items-center gap-2">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()}
            placeholder="Zapytaj o sprawę urzędową..."
            className="flex-1 px-4 py-3 rounded-xl border border-lublin-border bg-lublin-surface text-[15px] placeholder:text-lublin-muted focus:outline-none focus:border-lublin-green focus:ring-2 focus:ring-lublin-green/10"
            disabled={loading}
          />
          <button
            onClick={() => send()}
            disabled={loading || !input.trim()}
            className="w-11 h-11 rounded-xl bg-lublin-green text-white flex items-center justify-center shrink-0 disabled:opacity-40 active:scale-95 transition-transform"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
              <path d="M22 2L11 13" />
              <path d="M22 2L15 22L11 13L2 9L22 2Z" />
            </svg>
          </button>
        </div>
      </footer>
    </div>
  );
}

function Welcome({ onSuggestion }: { onSuggestion: (t: string) => void }) {
  return (
    <div className="flex flex-col items-center text-center pt-8 pb-4">
      <div className="w-16 h-16 rounded-2xl bg-lublin-green/10 flex items-center justify-center mb-5">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#006B3F" strokeWidth="2" strokeLinecap="round">
          <path d="M3 21h18" />
          <path d="M5 21V7l7-4 7 4v14" />
          <path d="M9 21v-4h6v4" />
          <path d="M9 10h1" />
          <path d="M14 10h1" />
        </svg>
      </div>
      <h2 className="text-2xl font-bold mb-2">Jak mogę pomóc?</h2>
      <p className="text-lublin-muted text-[15px] mb-6 max-w-sm">
        Zapytaj o dowolną sprawę urzędową w Lublinie — podpowiem gdzie, jak i ile to zajmie.
      </p>
      <div className="grid grid-cols-2 gap-2 w-full max-w-sm">
        {SUGGESTIONS.map((s) => (
          <button key={s} onClick={() => onSuggestion(s)} className="suggestion-btn">
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}
