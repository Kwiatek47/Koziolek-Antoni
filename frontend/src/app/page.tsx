"use client";

import { useState, useRef, useEffect } from "react";
import dynamic from "next/dynamic";
import Image from "next/image";
import {
  MapPin,
  Phone,
  Clock,
  FileText,
  CheckCircle2,
  ArrowUpRight,
  CalendarCheck,
  ListChecks,
  Banknote,
  Timer,
  Scale,
  User,
  Building2,
  Info,
  ChevronRight,
  Send,
  Sparkles,
  ArrowRight,
} from "lucide-react";

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
  { text: "Jak wyrobić dowód osobisty?", icon: FileText },
  { text: "Gdzie zarejestrować samochód?", icon: MapPin },
  { text: "Ile kosztuje ślub cywilny?", icon: Banknote },
  { text: "Pozwolenie na budowę", icon: Building2 },
  { text: "Kto jest prezydentem Lublina?", icon: User },
  { text: "Meldunek czasowy – procedura", icon: ListChecks },
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
      <header className="sticky top-0 z-50 bg-white/80 backdrop-blur-xl border-b border-lublin-border/60">
        <div className="max-w-[680px] mx-auto flex items-center gap-3 px-4 py-3">
          <div className="relative">
            <Image src="/logo.png" alt="Koziołek Antek" width={40} height={40} className="rounded-xl" />
            <div className="absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full bg-emerald-500 border-2 border-white" />
          </div>
          <div className="flex-1 min-w-0">
            <h1 className="text-[15px] font-semibold leading-tight text-lublin-text tracking-[-0.01em]">Koziołek Antek</h1>
            <p className="text-[12px] text-lublin-muted leading-tight mt-0.5">Asystent Urzędu Miasta Lublin</p>
          </div>
        </div>
      </header>

      {/* Messages */}
      <main className="flex-1 overflow-y-auto">
        <div className="max-w-[680px] mx-auto px-4 py-6">
          {messages.length === 0 ? (
            <Welcome onSuggestion={send} />
          ) : (
            <div className="space-y-5">
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
      <footer className="sticky bottom-0 bg-white/80 backdrop-blur-xl border-t border-lublin-border/60 px-4 py-3 pb-[max(env(safe-area-inset-bottom),12px)]">
        <div className="max-w-[680px] mx-auto flex items-center gap-2.5">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()}
            placeholder="Zapytaj o sprawę urzędową..."
            className="input-bar"
            disabled={loading}
          />
          <button onClick={() => send()} disabled={loading || !input.trim()} className="send-btn">
            <Send size={18} strokeWidth={2.5} />
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
    <div className="flex gap-3 justify-start items-start">
      <Image src="/logo.png" alt="" width={32} height={32} className="rounded-lg shrink-0 mt-0.5 ring-1 ring-lublin-border" />
      <div className="flex-1 min-w-0 space-y-3">
        <div className="chat-ai">
          <p className="text-[15px] leading-[1.65] text-lublin-text/90">{msg.content}</p>
        </div>

        {s && (
          <div className="space-y-2.5 pl-0.5">
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
      <div className="card-label">
        <MapPin size={14} strokeWidth={2.5} />
        <span>Gdzie załatwić</span>
      </div>
      <div className="p-4">
        {data.department && (
          <p className="font-semibold text-[15px] text-lublin-text mb-3">{data.department}</p>
        )}
        <div className="space-y-2">
          {data.address && (
            <div className="detail-row">
              <MapPin size={14} className="text-lublin-muted shrink-0" />
              <span>{data.address}{data.room && <span className="text-lublin-muted"> &middot; {data.room}</span>}</span>
            </div>
          )}
          {data.phone && (
            <div className="detail-row">
              <Phone size={14} className="text-lublin-muted shrink-0" />
              <span>{data.phone}</span>
            </div>
          )}
          {data.hours && (
            <div className="detail-row">
              <Clock size={14} className="text-lublin-muted shrink-0" />
              <span>{data.hours}</span>
            </div>
          )}
        </div>
        {data.lat && data.lng && (
          <div className="mt-3 rounded-xl overflow-hidden h-[140px] ring-1 ring-lublin-border">
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
      <div className="card-label">
        <ListChecks size={14} strokeWidth={2.5} />
        <span>Jak załatwić</span>
      </div>
      <div className="p-4 space-y-4">
        {data.steps && data.steps.length > 0 && (
          <div>
            <ol className="space-y-2.5">
              {data.steps.map((step, i) => (
                <li key={i} className="flex gap-3 text-[14px] leading-snug">
                  <span className="step-number">{i + 1}</span>
                  <span className="pt-0.5 text-lublin-text/85">{step.replace(/^(Krok \d+:\s*)/i, "")}</span>
                </li>
              ))}
            </ol>
          </div>
        )}
        {data.required_documents && data.required_documents.length > 0 && (
          <div>
            <p className="section-label">Wymagane dokumenty</p>
            <ul className="space-y-1.5">
              {data.required_documents.map((doc, i) => (
                <li key={i} className="flex items-start gap-2.5 text-[14px]">
                  <CheckCircle2 size={15} className="text-lublin-green shrink-0 mt-0.5" />
                  <span className="text-lublin-text/85">{doc}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
        {data.forms && data.forms.length > 0 && (
          <div>
            <p className="section-label">Formularze</p>
            <div className="space-y-1.5">
              {data.forms.map((form, i) => (
                <div key={i} className="flex items-center gap-2.5 text-[14px] bg-lublin-surface rounded-lg px-3 py-2">
                  <FileText size={14} className="text-lublin-muted shrink-0" />
                  <span className="text-lublin-text/85">{form}</span>
                </div>
              ))}
            </div>
          </div>
        )}
        {data.submission_method && (
          <div className="flex items-center gap-2.5 text-[13px] bg-lublin-surface rounded-lg px-3 py-2.5">
            <ArrowUpRight size={13} className="text-lublin-muted shrink-0" />
            <span className="text-lublin-muted">Sposób złożenia:</span>
            <span className="font-medium text-lublin-text">{data.submission_method}</span>
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
      <div className="card-label">
        <Banknote size={14} strokeWidth={2.5} />
        <span>Koszt i czas</span>
      </div>
      <div className="p-4">
        <div className="grid grid-cols-2 gap-2.5">
          {data.cost && (
            <div className="stat-block">
              <div className="flex items-center gap-1.5 mb-1">
                <Banknote size={13} className="text-lublin-muted" />
                <span className="text-[11px] font-medium text-lublin-muted uppercase tracking-wide">Koszt</span>
              </div>
              <p className="text-[16px] font-bold text-lublin-text leading-tight">{data.cost}</p>
            </div>
          )}
          {data.time_estimate && (
            <div className="stat-block">
              <div className="flex items-center gap-1.5 mb-1">
                <Timer size={13} className="text-lublin-muted" />
                <span className="text-[11px] font-medium text-lublin-muted uppercase tracking-wide">Czas</span>
              </div>
              <p className="text-[16px] font-bold text-lublin-text leading-tight">{data.time_estimate}</p>
            </div>
          )}
        </div>
        {data.legal_basis && (
          <div className="flex items-start gap-2 mt-3 pt-3 border-t border-lublin-border">
            <Scale size={12} className="text-lublin-muted shrink-0 mt-0.5" />
            <p className="text-[12px] text-lublin-muted leading-relaxed">{data.legal_basis}</p>
          </div>
        )}
      </div>
    </div>
  );
}

/* --- WHO --- */
function WhoCard({ data }: { data: WhoInfo }) {
  return (
    <div className="card">
      <div className="card-label">
        <User size={14} strokeWidth={2.5} />
        <span>Osoba odpowiedzialna</span>
      </div>
      <div className="p-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-lublin-green/8 border border-lublin-green/15 flex items-center justify-center">
            <User size={18} className="text-lublin-green" />
          </div>
          <div className="min-w-0">
            {data.name && <p className="font-semibold text-[14px] text-lublin-text truncate">{data.name}</p>}
            {data.role && <p className="text-[13px] text-lublin-muted truncate">{data.role}</p>}
            {data.department && (
              <div className="flex items-center gap-1.5 mt-0.5">
                <Building2 size={11} className="text-lublin-muted" />
                <p className="text-[12px] text-lublin-muted truncate">{data.department}</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

/* --- ADDITIONAL INFO --- */
function InfoCard({ text }: { text: string }) {
  return (
    <div className="card border-amber-200/60 bg-amber-50/30">
      <div className="p-4 flex gap-3">
        <div className="shrink-0 mt-0.5">
          <Info size={16} className="text-amber-600" />
        </div>
        <p className="text-[14px] text-lublin-text/80 leading-relaxed">{text}</p>
      </div>
    </div>
  );
}

/* --- BOOKING --- */
function BookingCard({ department }: { department?: string }) {
  const BOOKING_URL = "https://rezerwacja.lublin.eu/qmaticwebbooking/#/";

  return (
    <a
      href={BOOKING_URL}
      target="_blank"
      rel="noopener noreferrer"
      className="booking-card group"
    >
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-lublin-green/10 flex items-center justify-center group-hover:bg-lublin-green/15 transition-colors">
          <CalendarCheck size={20} className="text-lublin-green" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="font-semibold text-[14px] text-lublin-green">Umów wizytę online</p>
          <p className="text-[12px] text-lublin-muted mt-0.5">
            {department ? `${department} – ` : ""}Zarezerwuj termin bez kolejki
          </p>
        </div>
        <ArrowUpRight size={16} className="text-lublin-green/60 group-hover:text-lublin-green transition-colors shrink-0" />
      </div>
    </a>
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
          className="source-chip group"
        >
          <ArrowUpRight size={10} className="shrink-0 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-transform" />
          <span>{s.title?.slice(0, 35) || "BIP Lublin"}</span>
        </a>
      ))}
    </div>
  );
}

/* --- SUGGESTIONS (Perplexity-style) --- */
function SuggestionsBar({ suggestions, onSelect }: { suggestions: string[]; onSelect: (t: string) => void }) {
  return (
    <div className="pt-2 space-y-1.5">
      <p className="section-label px-1 !mb-1">Powiązane pytania</p>
      {suggestions.map((s, i) => (
        <button
          key={i}
          onClick={() => onSelect(s)}
          className="suggestion-follow-up group"
        >
          <ChevronRight size={14} className="text-lublin-muted/60 shrink-0 group-hover:text-lublin-green group-hover:translate-x-0.5 transition-all" />
          <span className="flex-1 text-left">{s}</span>
          <ArrowRight size={12} className="text-lublin-muted/0 group-hover:text-lublin-green/60 transition-all" />
        </button>
      ))}
    </div>
  );
}

/* --- LOADING --- */
function LoadingIndicator() {
  return (
    <div className="flex gap-3 items-start">
      <Image src="/logo.png" alt="" width={32} height={32} className="rounded-lg shrink-0 mt-0.5 ring-1 ring-lublin-border" />
      <div className="chat-ai">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1">
            <div className="w-1.5 h-1.5 bg-lublin-green/70 rounded-full animate-bounce" />
            <div className="w-1.5 h-1.5 bg-lublin-green/70 rounded-full animate-bounce [animation-delay:0.15s]" />
            <div className="w-1.5 h-1.5 bg-lublin-green/70 rounded-full animate-bounce [animation-delay:0.3s]" />
          </div>
          <span className="text-[13px] text-lublin-muted">Szukam odpowiedzi...</span>
        </div>
      </div>
    </div>
  );
}

/* --- WELCOME --- */
function Welcome({ onSuggestion }: { onSuggestion: (t: string) => void }) {
  return (
    <div className="flex flex-col items-center pt-12 pb-4">
      <div className="relative mb-6">
        <Image src="/logo.png" alt="Koziołek Antek" width={72} height={72} className="rounded-2xl shadow-md ring-1 ring-black/5" />
        <div className="absolute -bottom-1 -right-1 w-5 h-5 rounded-full bg-emerald-500 border-[2.5px] border-white flex items-center justify-center">
          <Sparkles size={10} className="text-white" />
        </div>
      </div>

      <h2 className="text-[22px] font-bold text-lublin-text tracking-[-0.02em] mb-1">
        Asystent Urzędu Miasta
      </h2>
      <p className="text-[15px] text-lublin-muted text-center max-w-[340px] leading-relaxed mb-8">
        Pomogę Ci załatwić sprawę urzędową w&nbsp;Lublinie. Powiem gdzie iść, co zabrać i&nbsp;ile to zajmie.
      </p>

      <div className="w-full max-w-md space-y-2">
        <p className="text-[11px] font-medium text-lublin-muted/70 uppercase tracking-widest px-1 mb-2">Popularne pytania</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {SUGGESTIONS.map(({ text, icon: Icon }) => (
            <button key={text} onClick={() => onSuggestion(text)} className="welcome-suggestion group">
              <Icon size={15} className="text-lublin-muted/70 group-hover:text-lublin-green shrink-0 transition-colors" />
              <span className="flex-1 text-left">{text}</span>
              <ChevronRight size={14} className="text-lublin-muted/30 group-hover:text-lublin-green/60 transition-colors" />
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
