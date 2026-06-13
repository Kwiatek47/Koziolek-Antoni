"use client";

import { useState, useRef, useEffect, useCallback, useSyncExternalStore } from "react";
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
  PenLine,
  Lightbulb,
  AlertTriangle,
  Download,
  ThumbsDown,
  ThumbsUp,
  Square,
  Volume2,
  Zap,
} from "lucide-react";
import { Locale, SPEECH_LOCALES, translations } from "@/i18n/translations";
import LangSwitcher from "@/components/LangSwitcher";
import VoiceInput from "@/components/VoiceInput";
import { type FeedbackVote, getQueryHistory, saveFeedbackEntry } from "@/lib/conversation";

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
  document_name?: string;
  fields?: Array<{
    name: string;
    description: string;
    example?: string;
    tips?: string;
  }>;
  general_tips?: string[];
  common_mistakes?: string[];
  where_to_get?: string;
  where_to_submit?: string;
  cached?: boolean;
}

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  structured?: StructuredResponse;
  question?: string;
  responseTimeMs?: number;
}

const SUGGESTION_ICONS = [FileText, MapPin, Banknote, Building2, User, ListChecks];

function isLocale(value: string | null): value is Locale {
  return value === "pl" || value === "en" || value === "ua";
}

function getStoredLocale(): Locale {
  if (typeof window === "undefined") return "pl";
  const saved = window.localStorage.getItem("koziolek-lang");
  return isLocale(saved) ? saved : "pl";
}

function subscribeToLocaleStore(callback: () => void): () => void {
  if (typeof window === "undefined") return () => undefined;
  window.addEventListener("storage", callback);
  return () => window.removeEventListener("storage", callback);
}

function subscribeToBrowserFeature(): () => void {
  return () => undefined;
}

function getSpeechSynthesisSupport(): boolean {
  return typeof window !== "undefined" && "speechSynthesis" in window && "SpeechSynthesisUtterance" in window;
}

function createMessageId(role: Message["role"]): string {
  const randomId =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : Math.random().toString(36).slice(2);
  return `${role}-${Date.now()}-${randomId}`;
}

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const storedLocale = useSyncExternalStore<Locale>(subscribeToLocaleStore, getStoredLocale, () => "pl");
  const [localeOverride, setLocaleOverride] = useState<Locale | null>(null);
  const locale = localeOverride || storedLocale;
  const [feedbackByMessageId, setFeedbackByMessageId] = useState<Record<string, FeedbackVote>>({});
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const t = translations[locale];

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  function handleLocaleChange(loc: Locale) {
    setLocaleOverride(loc);
    localStorage.setItem("koziolek-lang", loc);
  }

  const send = useCallback(
    async (text?: string) => {
      const question = text || input.trim();
      if (!question || loading) return;

      const history = getQueryHistory(messages);
      const userMessage: Message = { id: createMessageId("user"), role: "user", content: question };

      setInput("");
      setMessages((prev) => [...prev, userMessage]);
      setLoading(true);

      const startTime = performance.now();
      try {
        const res = await fetch("/api/query", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ question, lang: locale, history }),
        });
        const data = await res.json();
        const elapsed = Math.round(performance.now() - startTime);

        setMessages((prev) => [
          ...prev,
          {
            id: createMessageId("assistant"),
            role: "assistant",
            content: data.summary || data.answer || t.errors.noAnswer,
            structured: data,
            question,
            responseTimeMs: elapsed,
          },
        ]);
      } catch {
        setMessages((prev) => [
          ...prev,
          { id: createMessageId("assistant"), role: "assistant", content: t.errors.connection, question },
        ]);
      }
      setLoading(false);
      inputRef.current?.focus();
    },
    [input, loading, locale, messages, t.errors]
  );

  const handleFeedback = useCallback(
    (msg: Message, vote: FeedbackVote) => {
      const entry = {
        messageId: msg.id,
        vote,
        question: msg.question || "",
        answer: msg.content,
        lang: locale,
        createdAt: new Date().toISOString(),
      };

      saveFeedbackEntry(window.localStorage, entry);
      setFeedbackByMessageId((prev) => ({ ...prev, [msg.id]: vote }));

      fetch("/api/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(entry),
      }).catch(() => undefined);
    },
    [locale]
  );

  const handleVoiceTranscript = useCallback(
    (transcript: string) => {
      setInput(transcript);
      send(transcript);
    },
    [send]
  );

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
            <h1 className="text-[15px] font-semibold leading-tight text-lublin-text tracking-[-0.01em]">{t.header.title}</h1>
            <p className="text-[12px] text-lublin-muted leading-tight mt-0.5">{t.header.subtitle}</p>
          </div>
          <LangSwitcher locale={locale} onChange={handleLocaleChange} />
        </div>
      </header>

      {/* Messages */}
      <main className="flex-1 overflow-y-auto">
        <div className="max-w-[680px] mx-auto px-4 py-6">
          {messages.length === 0 ? (
            <Welcome onSuggestion={send} t={t} />
          ) : (
            <div className="space-y-5">
              {messages.map((msg, i) => (
                <div key={i}>
                  {msg.role === "user" ? (
                    <div className="flex justify-end user-enter">
                      <div className="chat-user">{msg.content}</div>
                    </div>
                  ) : (
                    <div className="msg-enter">
                    <AssistantMessage
                      msg={msg}
                      onFollowUp={send}
                      onFeedback={handleFeedback}
                      feedbackVote={feedbackByMessageId[msg.id]}
                      locale={locale}
                      t={t}
                    />
                    </div>
                  )}
                </div>
              ))}
              {loading && <LoadingIndicator t={t} />}
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
            placeholder={t.input.placeholder}
            className="input-bar"
            disabled={loading}
          />
          <VoiceInput
            onTranscript={handleVoiceTranscript}
            locale={locale}
            disabled={loading}
            t={t.voice}
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

type T = (typeof translations)["pl"];

function AssistantMessage({
  msg,
  onFollowUp,
  onFeedback,
  feedbackVote,
  locale,
  t,
}: {
  msg: Message;
  onFollowUp: (t: string) => void;
  onFeedback: (msg: Message, vote: FeedbackVote) => void;
  feedbackVote?: FeedbackVote;
  locale: Locale;
  t: T;
}) {
  const s = msg.structured;

  return (
    <div className="flex gap-3 justify-start items-start">
      <Image src="/logo.png" alt="" width={32} height={32} className="rounded-lg shrink-0 mt-0.5 ring-1 ring-lublin-border" />
      <div className="flex-1 min-w-0 space-y-3">
        <div className="chat-ai">
          <p className="text-[15px] leading-[1.65] text-lublin-text/90">
            {msg.content}
            {s?.cached && <span className="instant-badge"><Zap size={10} /> Instant</span>}
          </p>
        </div>
        <div className="message-actions" aria-label={t.feedback.responseActions}>
          {msg.responseTimeMs != null && (
            <span className="text-[10px] text-lublin-muted/60 font-mono tabular-nums mr-1">
              {msg.responseTimeMs < 1000 ? `${msg.responseTimeMs}ms` : `${(msg.responseTimeMs / 1000).toFixed(1)}s`}
            </span>
          )}
          <ReadAloudButton text={msg.content} locale={locale} t={t.tts} />
          <button
            type="button"
            onClick={() => onFeedback(msg, "up")}
            className={`message-action-btn ${feedbackVote === "up" ? "message-action-btn--up" : ""}`}
            aria-label={t.feedback.helpful}
            aria-pressed={feedbackVote === "up"}
            title={t.feedback.helpful}
          >
            <ThumbsUp size={15} strokeWidth={2.4} />
          </button>
          <button
            type="button"
            onClick={() => onFeedback(msg, "down")}
            className={`message-action-btn ${feedbackVote === "down" ? "message-action-btn--down" : ""}`}
            aria-label={t.feedback.notHelpful}
            aria-pressed={feedbackVote === "down"}
            title={t.feedback.notHelpful}
          >
            <ThumbsDown size={15} strokeWidth={2.4} />
          </button>
        </div>

        {s && (
          <div className="space-y-2.5 pl-0.5">
            {s.intent === "fill_document" && s.fields && s.fields.length > 0 && (
              <div className="card-enter">
              <FillDocumentCard
                documentName={s.document_name}
                fields={s.fields}
                generalTips={s.general_tips}
                commonMistakes={s.common_mistakes}
                whereToGet={s.where_to_get}
                whereToSubmit={s.where_to_submit}
                t={t}
              />
              </div>
            )}
            {s.intent !== "simple" && s.intent !== "fill_document" && s.where && hasData(s.where) && <div className="card-enter"><WhereCard data={s.where} t={t} /></div>}
            {s.intent !== "simple" && s.intent !== "fill_document" && s.booking && <div className="card-enter"><BookingCard department={s.where?.department} t={t} /></div>}
            {s.intent !== "simple" && s.intent !== "fill_document" && s.how && hasData(s.how) && <div className="card-enter"><HowCard data={s.how} t={t} /></div>}
            {s.intent !== "simple" && s.intent !== "fill_document" && s.how_much && hasData(s.how_much) && <div className="card-enter"><HowMuchCard data={s.how_much} t={t} /></div>}
            {s.intent !== "simple" && s.intent !== "fill_document" && s.who && hasData(s.who) && <div className="card-enter"><WhoCard data={s.who} t={t} /></div>}
            {s.intent !== "simple" && s.intent !== "fill_document" && s.additional_info && <div className="card-enter"><InfoCard text={s.additional_info} /></div>}
            {s.sources && s.sources.length > 0 && <div className="card-enter"><SourcesBar sources={s.sources} /></div>}
            {s.suggestions && s.suggestions.length > 0 && <div className="card-enter"><SuggestionsBar suggestions={s.suggestions} onSelect={onFollowUp} t={t} /></div>}
          </div>
        )}
      </div>
    </div>
  );
}

function ReadAloudButton({ text, locale, t }: { text: string; locale: Locale; t: T["tts"] }) {
  const supported = useSyncExternalStore(subscribeToBrowserFeature, getSpeechSynthesisSupport, () => false);
  const [speaking, setSpeaking] = useState(false);
  const utteranceRef = useRef<SpeechSynthesisUtterance | null>(null);

  useEffect(() => {
    return () => {
      if (utteranceRef.current) {
        window.speechSynthesis.cancel();
      }
    };
  }, []);

  const toggleSpeech = useCallback(() => {
    if (!supported) return;

    if (speaking) {
      window.speechSynthesis.cancel();
      setSpeaking(false);
      return;
    }

    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = SPEECH_LOCALES[locale];
    utterance.rate = 0.95;
    utterance.onend = () => setSpeaking(false);
    utterance.onerror = () => setSpeaking(false);
    utteranceRef.current = utterance;
    setSpeaking(true);
    window.speechSynthesis.speak(utterance);
  }, [locale, speaking, supported, text]);

  if (!supported) return null;

  return (
    <button
      type="button"
      onClick={toggleSpeech}
      className={`message-action-btn ${speaking ? "message-action-btn--speaking" : ""}`}
      aria-label={speaking ? t.stop : t.speak}
      aria-pressed={speaking}
      title={speaking ? t.stop : t.speak}
    >
      {speaking ? <Square size={13} strokeWidth={2.5} /> : <Volume2 size={15} strokeWidth={2.4} />}
    </button>
  );
}

function hasData(obj: object): boolean {
  return Object.values(obj).some(
    (v) => v !== null && v !== undefined && v !== "" && v !== "null" && !(Array.isArray(v) && v.length === 0)
  );
}

/* --- WHERE --- */
function WhereCard({ data, t }: { data: WhereInfo; t: T }) {
  return (
    <div className="card">
      <div className="card-label">
        <MapPin size={14} strokeWidth={2.5} />
        <span>{t.cards.where}</span>
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
          <div className="mt-3 rounded-xl overflow-hidden h-[140px] ring-1 ring-lublin-border map-container">
            <MapEmbed center={[data.lat, data.lng]} zoom={16} markers={[{ lat: data.lat, lng: data.lng, label: data.department || "Urząd" }]} />
          </div>
        )}
      </div>
    </div>
  );
}

/* --- HOW --- */
function HowCard({ data, t }: { data: HowInfo; t: T }) {
  return (
    <div className="card">
      <div className="card-label">
        <ListChecks size={14} strokeWidth={2.5} />
        <span>{t.cards.how}</span>
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
            <p className="section-label">{t.cards.requiredDocs}</p>
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
            <p className="section-label">{t.cards.forms}</p>
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
            <span className="text-lublin-muted">{t.cards.submissionMethod}</span>
            <span className="font-medium text-lublin-text">{data.submission_method}</span>
          </div>
        )}
      </div>
    </div>
  );
}

/* --- HOW MUCH --- */
function HowMuchCard({ data, t }: { data: HowMuchInfo; t: T }) {
  return (
    <div className="card">
      <div className="card-label">
        <Banknote size={14} strokeWidth={2.5} />
        <span>{t.cards.howMuch}</span>
      </div>
      <div className="p-4">
        <div className="grid grid-cols-2 gap-2.5">
          {data.cost && (
            <div className="stat-block">
              <div className="flex items-center gap-1.5 mb-1">
                <Banknote size={13} className="text-lublin-muted" />
                <span className="text-[11px] font-medium text-lublin-muted uppercase tracking-wide">{t.cards.cost}</span>
              </div>
              <p className="text-[16px] font-bold text-lublin-text leading-tight">{data.cost}</p>
            </div>
          )}
          {data.time_estimate && (
            <div className="stat-block">
              <div className="flex items-center gap-1.5 mb-1">
                <Timer size={13} className="text-lublin-muted" />
                <span className="text-[11px] font-medium text-lublin-muted uppercase tracking-wide">{t.cards.time}</span>
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
function WhoCard({ data, t }: { data: WhoInfo; t: T }) {
  const name = data.name && data.name !== "null" ? data.name : null;
  const role = data.role && data.role !== "null" ? data.role : null;
  const dept = data.department && data.department !== "null" ? data.department : null;

  if (!name && !role && !dept) return null;

  return (
    <div className="card">
      <div className="card-label">
        <User size={14} strokeWidth={2.5} />
        <span>{t.cards.who}</span>
      </div>
      <div className="p-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-lublin-green/8 border border-lublin-green/15 flex items-center justify-center">
            <User size={18} className="text-lublin-green" />
          </div>
          <div className="min-w-0">
            {name && <p className="font-semibold text-[14px] text-lublin-text truncate">{name}</p>}
            {role && <p className="text-[13px] text-lublin-muted truncate">{role}</p>}
            {dept && (
              <div className="flex items-center gap-1.5 mt-0.5">
                <Building2 size={11} className="text-lublin-muted" />
                <p className="text-[12px] text-lublin-muted truncate">{dept}</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

/* --- FILL DOCUMENT --- */
function FillDocumentCard({
  documentName,
  fields,
  generalTips,
  commonMistakes,
  whereToGet,
  whereToSubmit,
  t,
}: {
  documentName?: string;
  fields: Array<{ name: string; description: string; example?: string; tips?: string }>;
  generalTips?: string[];
  commonMistakes?: string[];
  whereToGet?: string;
  whereToSubmit?: string;
  t: T;
}) {
  return (
    <div className="space-y-2.5">
      {/* Main fields card */}
      <div className="card">
        <div className="card-label">
          <PenLine size={14} strokeWidth={2.5} />
          <span>{t.cards.fillDocument}</span>
        </div>
        {documentName && (
          <div className="px-4 pt-3">
            <p className="font-semibold text-[15px] text-lublin-text">{documentName}</p>
          </div>
        )}
        <div className="p-4 space-y-3">
          {fields.map((field, i) => (
            <div key={i} className="fill-field">
              <div className="fill-field-header">
                <span className="fill-field-number">{i + 1}</span>
                <span className="font-medium text-[14px] text-lublin-text">{field.name}</span>
              </div>
              <div className="pl-8 space-y-1.5">
                <p className="text-[13px] text-lublin-text/80 leading-relaxed">{field.description}</p>
                {field.example && (
                  <div className="fill-example">
                    <span className="text-[11px] font-medium text-lublin-muted uppercase tracking-wide">{t.cards.example}:</span>
                    <span className="text-[13px] text-lublin-green font-medium ml-2">{field.example}</span>
                  </div>
                )}
                {field.tips && (
                  <div className="flex items-start gap-1.5">
                    <Lightbulb size={12} className="text-amber-500 shrink-0 mt-0.5" />
                    <span className="text-[12px] text-amber-700/80 italic">{field.tips}</span>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* General tips */}
      {generalTips && generalTips.length > 0 && (
        <div className="card border-emerald-200/60 bg-emerald-50/20">
          <div className="p-4">
            <div className="flex items-center gap-2 mb-3">
              <Lightbulb size={14} className="text-lublin-green" />
              <span className="text-[11px] font-semibold text-lublin-green uppercase tracking-wide">{t.cards.generalTips}</span>
            </div>
            <ul className="space-y-2">
              {generalTips.map((tip, i) => (
                <li key={i} className="flex items-start gap-2.5 text-[13px]">
                  <CheckCircle2 size={14} className="text-lublin-green shrink-0 mt-0.5" />
                  <span className="text-lublin-text/80">{tip}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {/* Common mistakes */}
      {commonMistakes && commonMistakes.length > 0 && (
        <div className="card border-red-200/60 bg-red-50/20">
          <div className="p-4">
            <div className="flex items-center gap-2 mb-3">
              <AlertTriangle size={14} className="text-red-500" />
              <span className="text-[11px] font-semibold text-red-600 uppercase tracking-wide">{t.cards.commonMistakes}</span>
            </div>
            <ul className="space-y-2">
              {commonMistakes.map((mistake, i) => (
                <li key={i} className="flex items-start gap-2.5 text-[13px]">
                  <span className="text-red-400 shrink-0 mt-0.5">&times;</span>
                  <span className="text-lublin-text/80">{mistake}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {/* Where to get/submit */}
      {(whereToGet || whereToSubmit) && (
        <div className="card">
          <div className="p-4 space-y-2.5">
            {whereToGet && (
              <div className="flex items-start gap-2.5 text-[13px]">
                <Download size={13} className="text-lublin-muted shrink-0 mt-0.5" />
                <div>
                  <span className="text-lublin-muted font-medium">{t.cards.whereToGet}: </span>
                  <span className="text-lublin-text/85">{whereToGet}</span>
                </div>
              </div>
            )}
            {whereToSubmit && (
              <div className="flex items-start gap-2.5 text-[13px]">
                <ArrowUpRight size={13} className="text-lublin-muted shrink-0 mt-0.5" />
                <div>
                  <span className="text-lublin-muted font-medium">{t.cards.whereToSubmit}: </span>
                  <span className="text-lublin-text/85">{whereToSubmit}</span>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
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
function BookingCard({ department, t }: { department?: string; t: T }) {
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
          <p className="font-semibold text-[14px] text-lublin-green">{t.cards.booking}</p>
          <p className="text-[12px] text-lublin-muted mt-0.5">
            {department ? `${department} – ` : ""}{t.cards.bookingDesc}
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
function SuggestionsBar({ suggestions, onSelect, t }: { suggestions: string[]; onSelect: (t: string) => void; t: T }) {
  return (
    <div className="pt-2 space-y-1.5">
      <p className="section-label px-1 !mb-1">{t.cards.relatedQuestions}</p>
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
function LoadingIndicator({ t }: { t: T }) {
  return (
    <div className="flex gap-3 items-start msg-enter">
      <Image src="/logo.png" alt="" width={32} height={32} className="rounded-lg shrink-0 mt-0.5 ring-1 ring-lublin-border" />
      <div className="chat-ai">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1">
            <div className="w-1.5 h-1.5 bg-lublin-green/70 rounded-full animate-bounce" />
            <div className="w-1.5 h-1.5 bg-lublin-green/70 rounded-full animate-bounce [animation-delay:0.15s]" />
            <div className="w-1.5 h-1.5 bg-lublin-green/70 rounded-full animate-bounce [animation-delay:0.3s]" />
          </div>
          <span className="text-[13px] text-lublin-muted">{t.loading}</span>
        </div>
        <div className="mt-3 flex justify-center">
          <Image
            src="/animacja/koziolek_biega.gif"
            alt="Koziołek szuka odpowiedzi"
            width={96}
            height={64}
            unoptimized
            className="h-16 w-auto object-contain"
          />
        </div>
      </div>
    </div>
  );
}

/* --- WELCOME --- */
function Welcome({ onSuggestion, t }: { onSuggestion: (t: string) => void; t: T }) {
  return (
    <div className="flex flex-col items-center pt-12 pb-4 welcome-hero">
      <div className="relative mb-6">
        <Image src="/logo.png" alt="Koziołek Antek" width={72} height={72} className="rounded-2xl shadow-md ring-1 ring-black/5" />
        <div className="absolute -bottom-1 -right-1 w-5 h-5 rounded-full bg-emerald-500 border-[2.5px] border-white flex items-center justify-center">
          <Sparkles size={10} className="text-white" />
        </div>
      </div>

      <h2 className="text-[22px] font-bold text-lublin-text tracking-[-0.02em] mb-1">
        {t.welcome.title}
      </h2>
      <p className="text-[15px] text-lublin-muted text-center max-w-[340px] leading-relaxed mb-8">
        {t.welcome.description}
      </p>

      <div className="w-full max-w-md space-y-2 welcome-suggestions-grid">
        <p className="text-[11px] font-medium text-lublin-muted/70 uppercase tracking-widest px-1 mb-2">{t.welcome.popular}</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {t.suggestions.map(({ text }, idx) => {
            const Icon = SUGGESTION_ICONS[idx] || FileText;
            return (
              <button key={text} onClick={() => onSuggestion(text)} className="welcome-suggestion group">
                <Icon size={15} className="text-lublin-muted/70 group-hover:text-lublin-green shrink-0 transition-colors" />
                <span className="flex-1 text-left">{text}</span>
                <ChevronRight size={14} className="text-lublin-muted/30 group-hover:text-lublin-green/60 transition-colors" />
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
