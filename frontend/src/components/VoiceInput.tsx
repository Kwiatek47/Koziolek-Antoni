"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { Mic, MicOff } from "lucide-react";
import { Locale, SPEECH_LOCALES } from "@/i18n/translations";

interface VoiceInputProps {
  onTranscript: (text: string) => void;
  locale: Locale;
  disabled?: boolean;
  t: { listening: string; tapToSpeak: string; notSupported: string };
}

/* eslint-disable @typescript-eslint/no-explicit-any */
export default function VoiceInput({ onTranscript, locale, disabled, t }: VoiceInputProps) {
  const [listening, setListening] = useState(false);
  const [supported, setSupported] = useState(true);
  const recognitionRef = useRef<any>(null);

  useEffect(() => {
    const win = window as any;
    const SpeechRecognitionCtor = win.SpeechRecognition || win.webkitSpeechRecognition;

    if (!SpeechRecognitionCtor) {
      setSupported(false);
      return;
    }

    const recognition = new SpeechRecognitionCtor();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = SPEECH_LOCALES[locale];

    recognition.onresult = (event: any) => {
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
