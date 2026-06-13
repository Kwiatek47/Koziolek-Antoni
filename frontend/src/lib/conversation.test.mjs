import assert from "node:assert/strict";
import test from "node:test";

import {
  FEEDBACK_STORAGE_KEY,
  buildContextualQuestion,
  getQueryHistory,
  readFeedbackEntries,
  saveFeedbackEntry,
} from "./conversation.ts";

class MemoryStorage {
  store = new Map();

  getItem(key) {
    return this.store.has(key) ? this.store.get(key) : null;
  }

  setItem(key, value) {
    this.store.set(key, value);
  }
}

test("buildContextualQuestion carries the previous topic into a follow-up question", () => {
  const question = buildContextualQuestion("a ile to kosztuje?", [
    { role: "user", content: "Jak wyrobić dowód osobisty?" },
    {
      role: "assistant",
      content: "Dowód osobisty można wyrobić w urzędzie lub online.",
    },
  ]);

  assert.match(question, /Jak wyrobić dowód osobisty\?/);
  assert.match(question, /Aktualne pytanie mieszkańca: a ile to kosztuje\?/);
});

test("buildContextualQuestion returns a plain question when there is no usable history", () => {
  assert.equal(buildContextualQuestion("  Ile kosztuje ślub cywilny? ", []), "Ile kosztuje ślub cywilny?");
});

test("getQueryHistory keeps only recent non-empty conversation turns", () => {
  const history = getQueryHistory(
    [
      { role: "user", content: "pierwsze" },
      { role: "assistant", content: "drugie" },
      { role: "user", content: "trzecie" },
      { role: "assistant", content: "czwarte" },
      { role: "user", content: "piąte" },
      { role: "assistant", content: "szóste" },
      { role: "user", content: "siódme" },
      { role: "assistant", content: "   " },
    ],
    4
  );

  assert.deepEqual(history, [
    { role: "assistant", content: "czwarte" },
    { role: "user", content: "piąte" },
    { role: "assistant", content: "szóste" },
    { role: "user", content: "siódme" },
  ]);
});

test("saveFeedbackEntry upserts the latest vote for a message in local storage", () => {
  const storage = new MemoryStorage();

  saveFeedbackEntry(storage, {
    messageId: "assistant-1",
    vote: "up",
    question: "Jak wyrobić dowód?",
    answer: "Wypełnij wniosek.",
    lang: "pl",
    createdAt: "2026-06-13T12:00:00.000Z",
  });

  saveFeedbackEntry(storage, {
    messageId: "assistant-1",
    vote: "down",
    question: "Jak wyrobić dowód?",
    answer: "Wypełnij wniosek.",
    lang: "pl",
    createdAt: "2026-06-13T12:01:00.000Z",
  });

  assert.deepEqual(readFeedbackEntries(storage), [
    {
      messageId: "assistant-1",
      vote: "down",
      question: "Jak wyrobić dowód?",
      answer: "Wypełnij wniosek.",
      lang: "pl",
      createdAt: "2026-06-13T12:01:00.000Z",
    },
  ]);
  assert.equal(JSON.parse(storage.getItem(FEEDBACK_STORAGE_KEY)).length, 1);
});
