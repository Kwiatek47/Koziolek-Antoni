export type ConversationRole = "user" | "assistant";

export interface ConversationTurn {
  role: ConversationRole;
  content: string;
}

export type FeedbackVote = "up" | "down";

export interface FeedbackEntry {
  messageId: string;
  vote: FeedbackVote;
  question: string;
  answer: string;
  lang: string;
  createdAt: string;
}

export const FEEDBACK_STORAGE_KEY = "koziolek-feedback";

const DEFAULT_HISTORY_LIMIT = 6;
const MAX_TURN_LENGTH = 700;
const MAX_FEEDBACK_ENTRIES = 100;

function cleanText(value: unknown, maxLength = MAX_TURN_LENGTH): string {
  if (typeof value !== "string") return "";
  const normalized = value.replace(/\s+/g, " ").trim();
  if (normalized.length <= maxLength) return normalized;
  return `${normalized.slice(0, maxLength - 3).trim()}...`;
}

function isConversationRole(value: unknown): value is ConversationRole {
  return value === "user" || value === "assistant";
}

export function getQueryHistory(messages: ConversationTurn[], limit = DEFAULT_HISTORY_LIMIT): ConversationTurn[] {
  return messages
    .filter((message) => isConversationRole(message.role))
    .map((message) => ({
      role: message.role,
      content: cleanText(message.content),
    }))
    .filter((message) => message.content.length > 0)
    .slice(-limit);
}

export function buildContextualQuestion(question: string, history: ConversationTurn[] = []): string {
  const currentQuestion = cleanText(question, 1000);
  const turns = getQueryHistory(history);

  if (turns.length === 0) {
    return currentQuestion;
  }

  const context = turns
    .map((turn) => `${turn.role === "user" ? "Mieszkaniec" : "Koziolek"}: ${turn.content}`)
    .join("\n");

  return [
    "Kontekst rozmowy (uzyj go tylko do zrozumienia aktualnego pytania):",
    context,
    "",
    `Aktualne pytanie mieszkańca: ${currentQuestion}`,
    "",
    "Odpowiedz na aktualne pytanie. Jezeli jest krotkim follow-upem, odczytaj temat z kontekstu rozmowy.",
  ].join("\n");
}

export function readFeedbackEntries(storage: Pick<Storage, "getItem"> | null): FeedbackEntry[] {
  if (!storage) return [];

  try {
    const raw = storage.getItem(FEEDBACK_STORAGE_KEY);
    if (!raw) return [];

    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];

    return parsed.filter((entry): entry is FeedbackEntry => {
      return (
        entry &&
        typeof entry.messageId === "string" &&
        (entry.vote === "up" || entry.vote === "down") &&
        typeof entry.question === "string" &&
        typeof entry.answer === "string" &&
        typeof entry.lang === "string" &&
        typeof entry.createdAt === "string"
      );
    });
  } catch {
    return [];
  }
}

export function saveFeedbackEntry(
  storage: Pick<Storage, "getItem" | "setItem"> | null,
  entry: FeedbackEntry
): FeedbackEntry[] {
  if (!storage) return [];

  const entries = readFeedbackEntries(storage).filter((item) => item.messageId !== entry.messageId);
  const updated = [...entries, entry].slice(-MAX_FEEDBACK_ENTRIES);
  storage.setItem(FEEDBACK_STORAGE_KEY, JSON.stringify(updated));
  return updated;
}
