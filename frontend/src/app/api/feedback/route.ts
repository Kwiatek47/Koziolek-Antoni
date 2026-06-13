import { mkdir, appendFile } from "node:fs/promises";
import path from "node:path";
import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";

const FEEDBACK_DIR = "feedback";
const FEEDBACK_FILE = "feedback.jsonl";

function text(value: unknown, maxLength: number): string {
  if (typeof value !== "string") return "";
  return value.replace(/\s+/g, " ").trim().slice(0, maxLength);
}

export async function POST(req: NextRequest) {
  let body: unknown;

  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  const payload = body && typeof body === "object" ? (body as Record<string, unknown>) : {};
  const vote = payload.vote;

  if (vote !== "up" && vote !== "down") {
    return NextResponse.json({ error: "Invalid vote" }, { status: 400 });
  }

  const entry = {
    messageId: text(payload.messageId, 120),
    vote,
    question: text(payload.question, 1000),
    answer: text(payload.answer, 3000),
    lang: text(payload.lang, 12),
    createdAt: text(payload.createdAt, 40),
    receivedAt: new Date().toISOString(),
    userAgent: text(req.headers.get("user-agent"), 300),
  };

  if (!entry.messageId || !entry.answer) {
    return NextResponse.json({ error: "Missing feedback fields" }, { status: 400 });
  }

  try {
    const dir = path.join(process.cwd(), FEEDBACK_DIR);
    await mkdir(dir, { recursive: true });
    await appendFile(path.join(dir, FEEDBACK_FILE), `${JSON.stringify(entry)}\n`, "utf8");
  } catch (error) {
    console.error("Failed to save feedback", error);
    return NextResponse.json({ error: "Could not save feedback" }, { status: 500 });
  }

  return NextResponse.json({ ok: true }, { status: 201 });
}
