"use client";

import { Locale, LOCALE_FLAGS, LOCALE_LABELS } from "@/i18n/translations";

interface LangSwitcherProps {
  locale: Locale;
  onChange: (locale: Locale) => void;
}

const LOCALES: Locale[] = ["pl", "en", "ua"];

export default function LangSwitcher({ locale, onChange }: LangSwitcherProps) {
  return (
    <div className="lang-switcher">
      {LOCALES.map((loc) => (
        <button
          key={loc}
          onClick={() => onChange(loc)}
          className={`lang-btn ${locale === loc ? "lang-btn--active" : ""}`}
          aria-label={LOCALE_LABELS[loc]}
        >
          <span className="text-[13px]">{LOCALE_FLAGS[loc]}</span>
          <span className="text-[11px] font-semibold tracking-wide">{LOCALE_LABELS[loc]}</span>
        </button>
      ))}
    </div>
  );
}
