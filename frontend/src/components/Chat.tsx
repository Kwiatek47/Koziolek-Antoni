"use client";

import { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";

interface Message {
  role: "user" | "assistant";
  content: string;
  sources?: Array<{ url: string; title: string }>;
}

interface ChatProps {
  onLocationMention?: (location: string | null) => void;
}

const SUGGESTIONS = [
  "Jak wyrobić dowód osobisty?",
  "Gdzie zarejestrować samochód?",
  "Jakie dokumenty do ślubu cywilnego?",
  "Ile kosztuje wypis z rejestru gruntów?",
  "Kto jest prezydentem Lublina?",
  "Jak uzyskać pozwolenie na budowę?",
];

export default function Chat({ onLocationMention }: ChatProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function sendMessage(text?: string) {
    const question = text || input.trim();
    if (!question) return;

    setInput("");
    const userMsg: Message = { role: "user", content: question };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    try {
      const res = await fetch("/api/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });
      const data = await res.json();
      const aiMsg: Message = {
        role: "assistant",
        content: data.answer || "Przepraszam, nie mogę teraz odpowiedzieć.",
        sources: data.sources || [],
      };
      setMessages((prev) => [...prev, aiMsg]);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "Wystąpił błąd połączenia z serwerem. Spróbuj ponownie.",
        },
      ]);
    }
    setLoading(false);
  }

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {messages.length === 0 ? (
        <WelcomeScreen onSuggestionClick={sendMessage} />
      ) : (
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {messages.map((msg, i) => (
            <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
              <div className={msg.role === "user" ? "chat-bubble-user" : "chat-bubble-ai"}>
                {msg.role === "assistant" ? (
                  <div className="prose prose-sm max-w-none">
                    <ReactMarkdown>{msg.content}</ReactMarkdown>
                  </div>
                ) : (
                  <p>{msg.content}</p>
                )}
                {msg.sources && msg.sources.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-lublin-border">
                    <p className="text-xs text-lublin-muted mb-1">Źródła:</p>
                    <div className="space-y-1">
                      {msg.sources.map((s, j) => (
                        <a
                          key={j}
                          href={s.url}
                          target="_blank"
                          rel="noopener"
                          className="text-xs text-lublin-green hover:underline block truncate"
                        >
                          {s.title || s.url}
                        </a>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          ))}
          {loading && (
            <div className="flex justify-start">
              <div className="chat-bubble-ai">
                <div className="flex gap-1">
                  <span className="w-2 h-2 bg-lublin-green rounded-full animate-bounce" />
                  <span className="w-2 h-2 bg-lublin-green rounded-full animate-bounce [animation-delay:0.1s]" />
                  <span className="w-2 h-2 bg-lublin-green rounded-full animate-bounce [animation-delay:0.2s]" />
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
      )}

      <div className="p-4 border-t border-lublin-border bg-white">
        <div className="flex items-center gap-3 max-w-3xl mx-auto">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && sendMessage()}
            placeholder="Zadaj pytanie o sprawy urzędowe w Lublinie..."
            className="flex-1 px-5 py-3.5 rounded-full border border-lublin-border bg-white shadow-lg focus:outline-none focus:ring-2 focus:ring-lublin-green/20 focus:border-lublin-green"
            disabled={loading}
          />
          <button
            onClick={() => sendMessage()}
            disabled={loading || !input.trim()}
            className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M22 2L11 13" />
              <path d="M22 2L15 22L11 13L2 9L22 2Z" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}

function WelcomeScreen({ onSuggestionClick }: { onSuggestionClick: (text: string) => void }) {
  return (
    <div className="flex-1 flex items-center justify-center p-6">
      <div className="max-w-2xl w-full text-center">
        <div className="w-16 h-16 bg-lublin-green-light rounded-2xl flex items-center justify-center mx-auto mb-6">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#006643" strokeWidth="2">
            <path d="M12 2L2 7l10 5 10-5-10-5z" />
            <path d="M2 17l10 5 10-5" />
            <path d="M2 12l10 5 10-5" />
          </svg>
        </div>
        <h2 className="text-3xl font-bold mb-3">Jak mogę Ci pomóc?</h2>
        <p className="text-lublin-muted mb-8 text-lg">
          Zapytaj o dowolną sprawę urzędową w Lublinie. Podpowiem gdzie, jak i ile to zajmie.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              onClick={() => onSuggestionClick(s)}
              className="text-left px-4 py-3 rounded-xl border border-lublin-border hover:bg-lublin-surface hover:border-lublin-green/30 transition-colors text-sm"
            >
              {s}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
