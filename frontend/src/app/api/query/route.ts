import { NextRequest, NextResponse } from "next/server";
import { buildContextualQuestion } from "@/lib/conversation";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";
const BACKEND_TIMEOUT_MS = 8000;

export async function POST(req: NextRequest) {
  const body = await req.json();
  const question = typeof body.question === "string" ? body.question.trim() : "";

  if (!question) {
    return NextResponse.json({ answer: "Brakuje pytania.", sources: [] }, { status: 400 });
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), BACKEND_TIMEOUT_MS);

  try {
    const res = await fetch(`${BACKEND_URL}/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      signal: controller.signal,
      body: JSON.stringify({
        ...body,
        question: buildContextualQuestion(question, body.history),
        original_question: question,
      }),
    });
    const data = await res.json();
    return NextResponse.json(data);
  } catch {
    return NextResponse.json(
      { answer: "Serwer RAG jest niedostępny. Upewnij się, że backend działa.", sources: [] },
      { status: 502 }
    );
  } finally {
    clearTimeout(timeoutId);
  }
}
