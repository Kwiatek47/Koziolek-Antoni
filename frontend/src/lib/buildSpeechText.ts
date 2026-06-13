import type { translations } from "@/i18n/translations";

type T = (typeof translations)["pl"];

export interface SpeechStructured {
  intent?: string;
  summary?: string;
  where?: {
    address?: string;
    room?: string;
    phone?: string;
    hours?: string;
    department?: string;
  };
  how?: {
    steps?: string[];
    required_documents?: string[];
    forms?: string[];
    submission_method?: string;
  };
  how_much?: {
    cost?: string;
    time_estimate?: string;
    legal_basis?: string;
  };
  who?: {
    name?: string;
    role?: string;
    department?: string;
  };
  booking?: boolean;
  additional_info?: string;
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
}

function push(parts: string[], text?: string | null) {
  const value = text?.trim();
  if (value && value !== "null") parts.push(value);
}

function pushList(parts: string[], label: string, items?: string[]) {
  if (!items?.length) return;
  parts.push(`${label}: ${items.join(". ")}`);
}

export function buildAssistantSpeechText(
  content: string,
  structured: SpeechStructured | undefined,
  t: T
): string {
  const parts: string[] = [];

  push(parts, content || structured?.summary);

  if (!structured) {
    return parts.join(". ");
  }

  const { intent } = structured;

  if (intent === "fill_document" && structured.fields?.length) {
    push(parts, structured.document_name);
    structured.fields.forEach((field, i) => {
      const fieldParts = [`${t.cards.fieldName} ${i + 1}, ${field.name}. ${field.description}`];
      if (field.example) fieldParts.push(`${t.cards.example}: ${field.example}`);
      if (field.tips) fieldParts.push(`${t.cards.tips}: ${field.tips}`);
      parts.push(fieldParts.join(". "));
    });
    pushList(parts, t.cards.generalTips, structured.general_tips);
    pushList(parts, t.cards.commonMistakes, structured.common_mistakes);
    if (structured.where_to_get) {
      parts.push(`${t.cards.whereToGet}: ${structured.where_to_get}`);
    }
    if (structured.where_to_submit) {
      parts.push(`${t.cards.whereToSubmit}: ${structured.where_to_submit}`);
    }
    return parts.join(". ");
  }

  if (intent !== "simple" && intent !== "fill_document") {
    const where = structured.where;
    if (where) {
      const whereParts: string[] = [t.cards.where];
      push(whereParts, where.department);
      if (where.address) {
        whereParts.push(where.room ? `${where.address}, ${where.room}` : where.address);
      }
      push(whereParts, where.phone ? `telefon ${where.phone}` : undefined);
      push(whereParts, where.hours);
      if (whereParts.length > 1) parts.push(whereParts.join(". "));
    }

    if (structured.booking) {
      parts.push(`${t.cards.booking}. ${t.cards.bookingDesc}`);
    }

    const how = structured.how;
    if (how) {
      if (how.steps?.length) {
        parts.push(
          `${t.cards.how}: ${how.steps.map((step, i) => `krok ${i + 1}, ${step.replace(/^(Krok \d+:\s*)/i, "")}`).join(". ")}`
        );
      }
      pushList(parts, t.cards.requiredDocs, how.required_documents);
      pushList(parts, t.cards.forms, how.forms);
      if (how.submission_method) {
        parts.push(`${t.cards.submissionMethod} ${how.submission_method}`);
      }
    }

    const howMuch = structured.how_much;
    if (howMuch) {
      const costParts: string[] = [t.cards.howMuch];
      if (howMuch.cost) costParts.push(`${t.cards.cost}: ${howMuch.cost}`);
      if (howMuch.time_estimate) costParts.push(`${t.cards.time}: ${howMuch.time_estimate}`);
      if (howMuch.legal_basis) costParts.push(howMuch.legal_basis);
      if (costParts.length > 1) parts.push(costParts.join(". "));
    }

    const who = structured.who;
    if (who) {
      const whoParts: string[] = [t.cards.who];
      push(whoParts, who.name);
      push(whoParts, who.role);
      push(whoParts, who.department);
      if (whoParts.length > 1) parts.push(whoParts.join(". "));
    }

    push(parts, structured.additional_info);
  }

  return parts.join(". ");
}
