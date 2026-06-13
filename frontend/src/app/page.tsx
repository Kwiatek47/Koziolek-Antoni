"use client";

import { useState, useRef, useEffect } from "react";
import dynamic from "next/dynamic";
import Image from "next/image";

const MapEmbed = dynamic(() => import("@/components/MapEmbed"), { ssr: false });

interface WhereInfo {
  address?: string;
  room?: string;
  phone?: string;
  hours?: string;
  department?: string;
  lat?: number;
  lng?: number;
}

interface HowInfo {
  steps?: string[];
  required_documents?: string[];
  forms?: string[];
  submission_method?: string;
}

interface HowMuchInfo {
  cost?: string;
  time_estimate?: string;
  legal_basis?: string;
}

interface WhoInfo {
  name?: string;
  role?: string;
  department?: string;
  gender?: string;
}

interface StructuredResponse {
  intent?: string;
  summary: string;
  where?: WhereInfo;
  how?: HowInfo;
  how_much?: HowMuchInfo;
  who?: WhoInfo;
  booking?: boolean;
  additional_info?: string;
  sources?: Array<{ url: string; title: string; department?: string }>;
  suggestions?: string[];
}

interface Message {
  role: "user" | "assistant";
  content: string;
  structured?: StructuredResponse;
}

const SUGGESTIONS = [
  "Jak wyrobić dowód osobisty?",
  "Gdzie zarejestrować samochód?",
  "Ile kosztuje ślub cywilny?",
  "Pozwolenie na budowę",
  "Kto jest prezydentem Lublina?",
  "Meldunek czasowy – procedura",
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

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: data.summary || data.answer || "Nie udało się uzyskać odpowiedzi.",
          structured: data,
        },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Błąd połączenia z serwerem. Spróbuj ponownie." },
      ]);
    }
    setLoading(false);
    inputRef.current?.focus();
  }

  return (
    <div className="min-h-[100dvh] flex flex-col bg-lublin-surface">
      {/* Header */}
      <header className="sticky top-0 z-50 bg-white/95 backdrop-blur-md border-b border-lublin-border">
        <div className="max-w-2xl mx-auto flex items-center gap-3 px-4 py-2.5">
          <Image src="/logo.png" alt="Koziołek Antek" width={44} height={44} className="rounded-xl" />
          <div className="flex-1 min-w-0">
            <h1 className="text-[17px] font-bold leading-tight text-lublin-text">Koziołek Antek</h1>
            <p className="text-[12px] text-lublin-muted">Inteligentny asystent Urzędu Miasta Lublin</p>
          </div>
          <div className="w-2.5 h-2.5 rounded-full bg-emerald-500 ring-2 ring-emerald-500/20" title="Online" />
        </div>
      </header>

      {/* Messages */}
      <main className="flex-1 overflow-y-auto">
        <div className="max-w-2xl mx-auto px-4 py-5">
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
                    <AssistantMessage msg={msg} onFollowUp={send} />
                  )}
                </div>
              ))}
              {loading && <LoadingIndicator />}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>
      </main>

      {/* Input */}
      <footer className="sticky bottom-0 bg-white border-t border-lublin-border px-4 py-3 pb-[max(env(safe-area-inset-bottom),12px)]">
        <div className="max-w-2xl mx-auto flex items-center gap-2.5">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()}
            placeholder="Zapytaj Koziołka Antka..."
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

/* ============ STRUCTURED ANSWER ============ */

function AssistantMessage({ msg, onFollowUp }: { msg: Message; onFollowUp: (t: string) => void }) {
  const s = msg.structured;

  return (
    <div className="flex gap-2.5 justify-start items-start">
      <Image src="/logo.png" alt="" width={32} height={32} className="rounded-lg shrink-0 mt-1" />
      <div className="flex-1 min-w-0 space-y-3">
        {/* Summary bubble */}
        <div className="chat-ai">
          <p className="text-[15px] leading-relaxed">{msg.content}</p>
        </div>

        {/* Structured cards - only for procedure intent */}
        {s && (
          <div className="space-y-2.5">
            {s.intent !== "simple" && s.where && hasData(s.where) && <WhereCard data={s.where} />}
            {s.intent !== "simple" && s.booking && <BookingCard department={s.where?.department} />}
            {s.intent !== "simple" && s.how && hasData(s.how) && <HowCard data={s.how} />}
            {s.intent !== "simple" && s.how_much && hasData(s.how_much) && <HowMuchCard data={s.how_much} />}
            {s.intent !== "simple" && s.who && hasData(s.who) && <WhoCard data={s.who} />}
            {s.intent !== "simple" && s.additional_info && <InfoCard text={s.additional_info} />}
            {s.sources && s.sources.length > 0 && <SourcesBar sources={s.sources} />}
            {s.suggestions && s.suggestions.length > 0 && <SuggestionsBar suggestions={s.suggestions} onSelect={onFollowUp} />}
          </div>
        )}
      </div>
    </div>
  );
}

function hasData(obj: object): boolean {
  return Object.values(obj).some((v) => v !== null && v !== undefined && v !== "" && !(Array.isArray(v) && v.length === 0));
}

/* --- WHERE --- */
function WhereCard({ data }: { data: WhereInfo }) {
  return (
    <div className="card">
      <div className="card-header bg-lublin-green/5">
        <span className="card-icon">📍</span>
        <span className="card-title text-lublin-green">Gdzie załatwić?</span>
      </div>
      <div className="card-body">
        {data.department && <p className="font-semibold text-lublin-text mb-1">{data.department}</p>}
        {data.address && (
          <div className="flex items-start gap-2 mb-1.5">
            <span className="text-lublin-muted text-xs mt-0.5">ADRES</span>
            <span className="text-sm">{data.address}{data.room && `, ${data.room}`}</span>
          </div>
        )}
        {data.phone && (
          <div className="flex items-start gap-2 mb-1.5">
            <span className="text-lublin-muted text-xs mt-0.5">TEL</span>
            <span className="text-sm">{data.phone}</span>
          </div>
        )}
        {data.hours && (
          <div className="flex items-start gap-2 mb-2">
            <span className="text-lublin-muted text-xs mt-0.5">GODZ</span>
            <span className="text-sm">{data.hours}</span>
          </div>
        )}
        {data.lat && data.lng && (
          <div className="mt-2 rounded-xl overflow-hidden h-[160px] border border-lublin-border">
            <MapEmbed center={[data.lat, data.lng]} zoom={16} markers={[{ lat: data.lat, lng: data.lng, label: data.department || "Urząd" }]} />
          </div>
        )}
      </div>
    </div>
  );
}

/* --- HOW --- */
function HowCard({ data }: { data: HowInfo }) {
  return (
    <div className="card">
      <div className="card-header bg-blue-50">
        <span className="card-icon">📋</span>
        <span className="card-title text-blue-700">Jak załatwić?</span>
      </div>
      <div className="card-body">
        {data.steps && data.steps.length > 0 && (
          <div className="mb-3">
            <p className="text-xs font-medium text-lublin-muted mb-1.5 uppercase tracking-wide">Kroki</p>
            <ol className="space-y-1.5">
              {data.steps.map((step, i) => (
                <li key={i} className="flex gap-2.5 text-sm">
                  <span className="flex-none w-5 h-5 rounded-full bg-blue-100 text-blue-700 text-xs font-bold flex items-center justify-center">{i + 1}</span>
                  <span className="pt-0.5">{step.replace(/^(Krok \d+:\s*)/i, "")}</span>
                </li>
              ))}
            </ol>
          </div>
        )}
        {data.required_documents && data.required_documents.length > 0 && (
          <div className="mb-2">
            <p className="text-xs font-medium text-lublin-muted mb-1.5 uppercase tracking-wide">Wymagane dokumenty</p>
            <ul className="space-y-1">
              {data.required_documents.map((doc, i) => (
                <li key={i} className="flex items-start gap-2 text-sm">
                  <span className="text-lublin-green mt-0.5">✓</span>
                  <span>{doc}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
        {data.forms && data.forms.length > 0 && (
          <div className="mb-2">
            <p className="text-xs font-medium text-lublin-muted mb-1.5 uppercase tracking-wide">Formularze</p>
            {data.forms.map((form, i) => (
              <div key={i} className="flex items-center gap-2 text-sm bg-lublin-surface rounded-lg px-3 py-1.5 mb-1">
                <span>📄</span>
                <span>{form}</span>
              </div>
            ))}
          </div>
        )}
        {data.submission_method && (
          <div className="text-sm bg-lublin-surface rounded-lg px-3 py-2">
            <span className="text-lublin-muted text-xs">Sposób złożenia: </span>
            <span className="font-medium">{data.submission_method}</span>
          </div>
        )}
      </div>
    </div>
  );
}

/* --- HOW MUCH --- */
function HowMuchCard({ data }: { data: HowMuchInfo }) {
  return (
    <div className="card">
      <div className="card-header bg-amber-50">
        <span className="card-icon">💰</span>
        <span className="card-title text-amber-700">Ile to kosztuje / trwa?</span>
      </div>
      <div className="card-body">
        <div className="grid grid-cols-2 gap-3">
          {data.cost && (
            <div className="bg-lublin-surface rounded-xl p-3 text-center">
              <p className="text-xs text-lublin-muted mb-0.5">Koszt</p>
              <p className="text-lg font-bold text-lublin-text">{data.cost}</p>
            </div>
          )}
          {data.time_estimate && (
            <div className="bg-lublin-surface rounded-xl p-3 text-center">
              <p className="text-xs text-lublin-muted mb-0.5">Czas</p>
              <p className="text-lg font-bold text-lublin-text">{data.time_estimate}</p>
            </div>
          )}
        </div>
        {data.legal_basis && (
          <p className="text-xs text-lublin-muted mt-2 pt-2 border-t border-lublin-border">
            Podstawa prawna: {data.legal_basis}
          </p>
        )}
      </div>
    </div>
  );
}

/* --- WHO --- */
function WhoCard({ data }: { data: WhoInfo }) {
  const avatar = data.gender === "F" ? "👩‍💼" : "👨‍💼";

  return (
    <div className="card">
      <div className="card-header bg-purple-50">
        <span className="card-icon">👤</span>
        <span className="card-title text-purple-700">Kto jest odpowiedzialny?</span>
      </div>
      <div className="card-body">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-full bg-purple-100 flex items-center justify-center text-2xl">
            {avatar}
          </div>
          <div>
            {data.name && <p className="font-semibold text-lublin-text">{data.name}</p>}
            {data.role && <p className="text-sm text-lublin-muted">{data.role}</p>}
            {data.department && <p className="text-xs text-purple-600">{data.department}</p>}
          </div>
        </div>
      </div>
    </div>
  );
}

/* --- ADDITIONAL INFO --- */
function InfoCard({ text }: { text: string }) {
  return (
    <div className="card">
      <div className="card-header bg-lublin-surface">
        <span className="card-icon">ℹ️</span>
        <span className="card-title text-lublin-text">Ważne informacje</span>
      </div>
      <div className="card-body">
        <p className="text-sm text-lublin-text/80 leading-relaxed">{text}</p>
      </div>
    </div>
  );
}

/* --- BOOKING --- */
function BookingCard({ department }: { department?: string }) {
  const BOOKING_URL = "https://rezerwacja.lublin.eu/qmaticwebbooking/#/";

  return (
    <div className="card border-lublin-green/30 bg-gradient-to-br from-lublin-green-light to-white">
      <div className="card-body">
        <div className="flex items-center gap-3 mb-3">
          <div className="w-10 h-10 rounded-xl bg-lublin-green/10 flex items-center justify-center">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-lublin-green">
              <rect x="3" y="4" width="18" height="18" rx="2" />
              <line x1="16" y1="2" x2="16" y2="6" />
              <line x1="8" y1="2" x2="8" y2="6" />
              <line x1="3" y1="10" x2="21" y2="10" />
              <circle cx="12" cy="15" r="2" />
            </svg>
          </div>
          <div className="flex-1">
            <p className="font-semibold text-lublin-green text-[15px]">Umów wizytę online</p>
            <p className="text-xs text-lublin-muted">
              {department ? `${department} – ` : ""}Zarezerwuj termin bez kolejki
            </p>
          </div>
        </div>
        <a
          href={BOOKING_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="booking-btn"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
            <rect x="3" y="4" width="18" height="18" rx="2" />
            <line x1="16" y1="2" x2="16" y2="6" />
            <line x1="8" y1="2" x2="8" y2="6" />
            <line x1="3" y1="10" x2="21" y2="10" />
          </svg>
          Zarezerwuj termin
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" className="ml-auto">
            <path d="M7 17L17 7M17 7H7M17 7v10" />
          </svg>
        </a>
      </div>
    </div>
  );
}

/* --- SOURCES --- */
function SourcesBar({ sources }: { sources: Array<{ url: string; title: string; department?: string }> }) {
  return (
    <div className="flex flex-wrap gap-1.5 pt-1">
      {sources.slice(0, 3).map((s, i) => (
        <a
          key={i}
          href={s.url}
          target="_blank"
          rel="noopener"
          className="source-chip"
        >
          ↗ {s.title?.slice(0, 30) || "BIP Lublin"}
        </a>
      ))}
    </div>
  );
}

/* --- SUGGESTIONS (Perplexity-style) --- */
function SuggestionsBar({ suggestions, onSelect }: { suggestions: string[]; onSelect: (t: string) => void }) {
  return (
    <div className="pt-2 space-y-1.5">
      <p className="text-xs font-medium text-lublin-muted uppercase tracking-wide px-1">Powiązane pytania</p>
      {suggestions.map((s, i) => (
        <button
          key={i}
          onClick={() => onSelect(s)}
          className="suggestion-follow-up"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-lublin-muted shrink-0">
            <path d="M9 18l6-6-6-6" />
          </svg>
          <span>{s}</span>
        </button>
      ))}
    </div>
  );
}

/* --- LOADING --- */
function LoadingIndicator() {
  return (
    <div className="flex gap-2.5 items-start">
      <Image src="/logo.png" alt="" width={32} height={32} className="rounded-lg shrink-0 mt-1" />
      <div className="chat-ai py-4">
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5">
            <div className="w-2 h-2 bg-lublin-green rounded-full animate-bounce" />
            <div className="w-2 h-2 bg-lublin-green rounded-full animate-bounce [animation-delay:0.15s]" />
            <div className="w-2 h-2 bg-lublin-green rounded-full animate-bounce [animation-delay:0.3s]" />
          </div>
          <span className="text-xs text-lublin-muted ml-2">Antek szuka odpowiedzi...</span>
        </div>
      </div>
    </div>
  );
}

/* --- WELCOME --- */
function Welcome({ onSuggestion }: { onSuggestion: (t: string) => void }) {
  return (
    <div className="flex flex-col items-center text-center pt-8 pb-2">
      <Image src="/logo.png" alt="Koziołek Antek" width={88} height={88} className="rounded-2xl mb-5 shadow-lg" />
      <h2 className="text-2xl font-bold mb-1.5 text-lublin-text">Cześć! Jestem Antek</h2>
      <p className="text-lublin-muted text-[15px] mb-2 max-w-[320px]">
        Twój inteligentny przewodnik po sprawach urzędowych w Lublinie.
      </p>
      <p className="text-lublin-muted/60 text-[13px] mb-6 max-w-[300px]">
        Powiem Ci gdzie, jak, ile i kto – wszystko w jednym miejscu.
      </p>
      <div className="grid grid-cols-2 gap-2 w-full max-w-md">
        {SUGGESTIONS.map((s) => (
          <button key={s} onClick={() => onSuggestion(s)} className="suggestion-btn">
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}
