"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { Volume2, VolumeX } from "lucide-react";
import { Locale, SPEECH_LOCALES } from "@/i18n/translations";

interface VoiceOutputProps {
  text: string;
  locale: Locale;
  t: {
    readAloud: string;
    stopReading: string;
    notSupportedTts: string;
  };
}

function pickVoice(langPrefix: string): SpeechSynthesisVoice | null {
  const voices = window.speechSynthesis.getVoices();
  return (
    voices.find((v) => v.lang === langPrefix) ||
    voices.find((v) => v.lang.startsWith(langPrefix.split("-")[0])) ||
    null
  );
}

export function stopAllSpeech() {
  if (typeof window !== "undefined" && "speechSynthesis" in window) {
    window.speechSynthesis.cancel();
  }
}

export default function VoiceOutput({ text, locale, t }: VoiceOutputProps) {
  const [speaking, setSpeaking] = useState(false);
  const [supported, setSupported] = useState(true);
  const utteranceRef = useRef<SpeechSynthesisUtterance | null>(null);

  useEffect(() => {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) {
      setSupported(false);
      return;
    }

    const loadVoices = () => {
      window.speechSynthesis.getVoices();
    };
    loadVoices();
    window.speechSynthesis.addEventListener("voiceschanged", loadVoices);
    return () => {
      window.speechSynthesis.removeEventListener("voiceschanged", loadVoices);
      stopAllSpeech();
    };
  }, []);

  const toggle = useCallback(() => {
    if (!supported || !text.trim()) return;

    if (speaking) {
      stopAllSpeech();
      setSpeaking(false);
      return;
    }

    stopAllSpeech();

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = SPEECH_LOCALES[locale];
    utterance.rate = 0.95;
    utterance.pitch = 1;

    const voice = pickVoice(SPEECH_LOCALES[locale]);
    if (voice) utterance.voice = voice;

    utterance.onend = () => setSpeaking(false);
    utterance.onerror = () => setSpeaking(false);

    utteranceRef.current = utterance;
    setSpeaking(true);
    window.speechSynthesis.speak(utterance);
  }, [supported, text, locale, speaking]);

  if (!supported || !text.trim()) return null;

  return (
    <button
      type="button"
      onClick={toggle}
      className={`read-aloud-btn ${speaking ? "read-aloud-btn--active" : ""}`}
      title={speaking ? t.stopReading : t.readAloud}
      aria-label={speaking ? t.stopReading : t.readAloud}
    >
      {speaking ? <VolumeX size={15} strokeWidth={2.5} /> : <Volume2 size={15} strokeWidth={2.5} />}
      <span>{speaking ? t.stopReading : t.readAloud}</span>
    </button>
  );
}
