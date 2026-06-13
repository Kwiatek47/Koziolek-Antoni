"use client";

import { useState, useRef, useCallback, useEffect, useSyncExternalStore } from "react";
import { Mic, MicOff } from "lucide-react";
import { Locale, SPEECH_LOCALES } from "@/i18n/translations";

interface VoiceInputProps {
  onTranscript: (text: string) => void;
  locale: Locale;
  disabled?: boolean;
  t: { listening: string; tapToSpeak: string; notSupported: string };
}

interface SpeechRecognitionEventLike {
  results: {
    0: {
      0: {
        transcript: string;
      };
    };
  };
}

interface SpeechRecognitionLike {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onerror: (() => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
}

type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;

interface SpeechRecognitionWindow extends Window {
  SpeechRecognition?: SpeechRecognitionConstructor;
  webkitSpeechRecognition?: SpeechRecognitionConstructor;
}

function subscribeToSpeechRecognition(): () => void {
  return () => undefined;
}

function getSpeechRecognitionConstructor(): SpeechRecognitionConstructor | undefined {
  if (typeof window === "undefined") return undefined;
  const win = window as SpeechRecognitionWindow;
  return win.SpeechRecognition || win.webkitSpeechRecognition;
}

export default function VoiceInput({ onTranscript, locale, disabled, t }: VoiceInputProps) {
  const [listening, setListening] = useState(false);
  const supported = useSyncExternalStore(
    subscribeToSpeechRecognition,
    () => Boolean(getSpeechRecognitionConstructor()),
    () => false
  );
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);

  useEffect(() => {
    const SpeechRecognitionCtor = getSpeechRecognitionConstructor();
    if (!SpeechRecognitionCtor) return;

    const recognition = new SpeechRecognitionCtor();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = SPEECH_LOCALES[locale];

    recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript;
      if (transcript.trim()) {
        onTranscript(transcript.trim());
      }
      setListening(false);
    };

    recognition.onerror = () => {
      setListening(false);
    };

    recognition.onend = () => {
      setListening(false);
    };

    recognitionRef.current = recognition;
  }, [locale, onTranscript]);

  useEffect(() => {
    if (recognitionRef.current) {
      recognitionRef.current.lang = SPEECH_LOCALES[locale];
    }
  }, [locale]);

  const toggle = useCallback(() => {
    if (!supported || disabled) return;
    const recognition = recognitionRef.current;
    if (!recognition) return;

    if (listening) {
      recognition.stop();
      setListening(false);
    } else {
      recognition.lang = SPEECH_LOCALES[locale];
      recognition.start();
      setListening(true);
    }
  }, [listening, supported, disabled, locale]);

  if (!supported) return null;

  return (
    <button
      type="button"
      onClick={toggle}
      disabled={disabled}
      className={`voice-btn ${listening ? "voice-btn--active" : ""}`}
      title={listening ? t.listening : t.tapToSpeak}
      aria-label={listening ? t.listening : t.tapToSpeak}
    >
      {listening ? (
        <>
          <MicOff size={18} strokeWidth={2.5} />
          <span className="voice-pulse" />
        </>
      ) : (
        <Mic size={18} strokeWidth={2.5} />
      )}
    </button>
  );
}
