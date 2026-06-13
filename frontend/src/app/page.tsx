"use client";

import { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import dynamic from "next/dynamic";
import Image from "next/image";

const MapEmbed = dynamic(() => import("@/components/MapEmbed"), { ssr: false });

interface Message {
  role: "user" | "assistant";
  content: string;
  sources?: Array<{ url: string; title: string }>;
  showMap?: boolean;
}

const SUGGESTIONS = [
  "Jak wyrobić dowód osobisty?",
  "Gdzie zarejestrować auto?",
  "Dokumenty do ślubu",
  "Pozwolenie na budowę",
  "Kto jest prezydentem?",
  "Meldunek czasowy",
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

      const showMap = /gdzie|adres|lokalizacja|mapa|dojazd|godzin/i.test(question);

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
    <div className="min-h-[100dvh] flex flex-col">
      {/* Header */}
      <header className="sticky top-0 z-50 bg-white/95 backdrop-blur-md border-b border-lublin-border">
        <div className="max-w-lg mx-auto flex items-center gap-3 px-4 py-2.5">
          <Image
            src="/logo.png"
            alt="Koziołek Antek"
            width={44}
            height={44}
            className="rounded-xl"
          />
          <div className="flex-1 min-w-0">
            <h1 className="text-[17px] font-bold leading-tight text-lublin-text">
              Koziołek Antek
            </h1>
            <p className="text-[12px] text-lublin-muted">Asystent Urzędu Miasta Lublin</p>
          </div>
          <div className="w-2.5 h-2.5 rounded-full bg-emerald-500 ring-2 ring-emerald-500/20" title="Online" />
        </div>
      </header>

      {/* Messages */}
      <main className="flex-1 overflow-y-auto bg-lublin-surface">
        <div className="max-w-lg mx-auto px-4 py-5">
          {messages.length === 0 ? (
            <Welcome onSuggestion={send} />
          ) : (
            <div className="space-y-3">
              {messages.map((msg, i) => (
                <div key={i}>
                  {msg.role === "user" ? (
                    <div className="flex justify-end">
                      <div className="chat-user">{msg.content}</div>
                    </div>
                  ) : (
                    <div className="flex gap-2.5 justify-start items-end">
                      <Image
                        src="/logo.png"
                        alt=""
                        width={28}
                        height={28}
                        className="rounded-lg shrink-0 mb-1"
                      />
                      <div className="chat-ai">
                        <div className="prose prose-sm max-w-none [&_p]:mb-2 [&_p:last-child]:mb-0 [&_ul]:mb-2 [&_li]:mb-0.5 [&_strong]:text-lublin-text">
                          <ReactMarkdown>{msg.content}</ReactMarkdown>
                        </div>
                        {msg.sources && msg.sources.length > 0 && (
                          <div className="flex flex-wrap gap-1.5 mt-3 pt-2.5 border-t border-lublin-border">
                            {msg.sources.slice(0, 3).map((s, j) => (
                              <a
                                key={j}
                                href={s.url}
                                target="_blank"
                                rel="noopener"
                                className="source-chip"
                              >
                                ↗ {s.title?.slice(0, 25) || "BIP"}
                              </a>
                            ))}
                          </div>
                        )}
                        {msg.showMap && (
                          <div className="mt-3 map-container h-[180px]">
                            <MapEmbed />
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              ))}
              {loading && (
                <div className="flex gap-2.5 items-end">
                  <Image src="/logo.png" alt="" width={28} height={28} className="rounded-lg shrink-0 mb-1" />
                  <div className="chat-ai py-4">
                    <div className="flex items-center gap-1.5">
                      <div className="w-2 h-2 bg-lublin-red rounded-full animate-bounce" />
                      <div className="w-2 h-2 bg-lublin-red rounded-full animate-bounce [animation-delay:0.15s]" />
                      <div className="w-2 h-2 bg-lublin-red rounded-full animate-bounce [animation-delay:0.3s]" />
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
      <footer className="sticky bottom-0 bg-white border-t border-lublin-border px-4 py-3 pb-[max(env(safe-area-inset-bottom),12px)]">
        <div className="max-w-lg mx-auto flex items-center gap-2.5">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()}
            placeholder="Zapytaj Koziołka..."
            className="input-bar"
            disabled={loading}
          />
          <button onClick={() => send()} disabled={loading || !input.trim()} className="send-btn">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
              <path d="M5 12h14M12 5l7 7-7 7" />
            </svg>
          </button>
        </div>
      </footer>
    </div>
  );
}

function Welcome({ onSuggestion }: { onSuggestion: (t: string) => void }) {
  return (
    <div className="flex flex-col items-center text-center pt-6 pb-2">
      <Image
        src="/logo.png"
        alt="Koziołek Antek"
        width={80}
        height={80}
        className="rounded-2xl mb-4 shadow-lg"
      />
      <h2 className="text-2xl font-bold mb-1.5 text-lublin-text">Cześć! Jestem Antek</h2>
      <p className="text-lublin-muted text-[15px] mb-6 max-w-[280px]">
        Twój przewodnik po sprawach urzędowych w Lublinie. Pytaj śmiało!
      </p>
      <div className="grid grid-cols-2 gap-2 w-full">
        {SUGGESTIONS.map((s) => (
          <button key={s} onClick={() => onSuggestion(s)} className="suggestion-btn">
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}
