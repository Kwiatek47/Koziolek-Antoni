export type Locale = "pl" | "en" | "ua";

export const LOCALE_LABELS: Record<Locale, string> = {
  pl: "PL",
  en: "EN",
  ua: "UA",
};

export const LOCALE_FLAGS: Record<Locale, string> = {
  pl: "🇵🇱",
  en: "🇬🇧",
  ua: "🇺🇦",
};

interface Translations {
  header: {
    title: string;
    subtitle: string;
  };
  welcome: {
    title: string;
    description: string;
    popular: string;
  };
  suggestions: Array<{ text: string }>;
  input: {
    placeholder: string;
  };
  loading: string;
  cards: {
    where: string;
    how: string;
    howMuch: string;
    who: string;
    cost: string;
    time: string;
    requiredDocs: string;
    forms: string;
    submissionMethod: string;
    booking: string;
    bookingDesc: string;
    relatedQuestions: string;
    info: string;
    fillDocument: string;
    fieldName: string;
    whatToWrite: string;
    example: string;
    tips: string;
    generalTips: string;
    commonMistakes: string;
    whereToGet: string;
    whereToSubmit: string;
  };
  errors: {
    connection: string;
    noAnswer: string;
  };
  voice: {
    listening: string;
    tapToSpeak: string;
    notSupported: string;
  };
  tts: {
    speak: string;
    stop: string;
  };
  feedback: {
    responseActions: string;
    helpful: string;
    notHelpful: string;
  };
}

const pl: Translations = {
  header: {
    title: "Koziołek Antek",
    subtitle: "Asystent Urzędu Miasta Lublin",
  },
  welcome: {
    title: "Asystent Urzędu Miasta",
    description:
      "Pomogę Ci załatwić sprawę urzędową w\u00a0Lublinie. Powiem gdzie iść, co zabrać i\u00a0ile to zajmie.",
    popular: "Popularne pytania",
  },
  suggestions: [
    { text: "Jak wyrobić dowód osobisty?" },
    { text: "Gdzie zarejestrować samochód?" },
    { text: "Ile kosztuje ślub cywilny?" },
    { text: "Pozwolenie na budowę" },
    { text: "Kto jest prezydentem Lublina?" },
    { text: "Meldunek czasowy – procedura" },
  ],
  input: {
    placeholder: "Zapytaj o sprawę urzędową...",
  },
  loading: "Szukam odpowiedzi...",
  cards: {
    where: "Gdzie załatwić",
    how: "Jak załatwić",
    howMuch: "Koszt i czas",
    who: "Osoba odpowiedzialna",
    cost: "Koszt",
    time: "Czas",
    requiredDocs: "Wymagane dokumenty",
    forms: "Formularze",
    submissionMethod: "Sposób złożenia:",
    booking: "Umów wizytę online",
    bookingDesc: "Zarezerwuj termin bez kolejki",
    relatedQuestions: "Powiązane pytania",
    info: "Informacja",
    fillDocument: "Jak wypełnić dokument",
    fieldName: "Pole",
    whatToWrite: "Co wpisać",
    example: "Przykład",
    tips: "Wskazówka",
    generalTips: "Ogólne wskazówki",
    commonMistakes: "Częste błędy",
    whereToGet: "Gdzie pobrać formularz",
    whereToSubmit: "Gdzie złożyć",
  },
  errors: {
    connection: "Błąd połączenia z serwerem. Spróbuj ponownie.",
    noAnswer: "Nie udało się uzyskać odpowiedzi.",
  },
  voice: {
    listening: "Słucham...",
    tapToSpeak: "Naciśnij aby mówić",
    notSupported: "Twoja przeglądarka nie obsługuje rozpoznawania mowy.",
  },
  tts: {
    speak: "Czytaj odpowiedź",
    stop: "Zatrzymaj czytanie",
  },
  feedback: {
    responseActions: "Akcje odpowiedzi",
    helpful: "Pomocna odpowiedź",
    notHelpful: "Niepomocna odpowiedź",
  },
};

const en: Translations = {
  header: {
    title: "Koziołek Antek",
    subtitle: "Lublin City Hall Assistant",
  },
  welcome: {
    title: "City Hall Assistant",
    description:
      "I'll help you handle administrative matters in\u00a0Lublin. I'll tell you where to go, what to bring, and\u00a0how long it takes.",
    popular: "Popular questions",
  },
  suggestions: [
    { text: "How to get an ID card?" },
    { text: "Where to register a car?" },
    { text: "How much does a civil wedding cost?" },
    { text: "Building permit" },
    { text: "Who is the mayor of Lublin?" },
    { text: "Temporary registration – procedure" },
  ],
  input: {
    placeholder: "Ask about an administrative matter...",
  },
  loading: "Searching for an answer...",
  cards: {
    where: "Where to go",
    how: "How to do it",
    howMuch: "Cost & time",
    who: "Responsible person",
    cost: "Cost",
    time: "Time",
    requiredDocs: "Required documents",
    forms: "Forms",
    submissionMethod: "Submission method:",
    booking: "Book an appointment online",
    bookingDesc: "Reserve a slot – skip the queue",
    relatedQuestions: "Related questions",
    info: "Information",
    fillDocument: "How to fill the document",
    fieldName: "Field",
    whatToWrite: "What to write",
    example: "Example",
    tips: "Tip",
    generalTips: "General tips",
    commonMistakes: "Common mistakes",
    whereToGet: "Where to get the form",
    whereToSubmit: "Where to submit",
  },
  errors: {
    connection: "Server connection error. Please try again.",
    noAnswer: "Could not get an answer.",
  },
  voice: {
    listening: "Listening...",
    tapToSpeak: "Tap to speak",
    notSupported: "Your browser does not support speech recognition.",
  },
  tts: {
    speak: "Read answer aloud",
    stop: "Stop reading",
  },
  feedback: {
    responseActions: "Answer actions",
    helpful: "Helpful answer",
    notHelpful: "Not helpful",
  },
};

const ua: Translations = {
  header: {
    title: "Козлик Антек",
    subtitle: "Помічник Міської Ради Любліна",
  },
  welcome: {
    title: "Помічник Міської Ради",
    description:
      "Я допоможу вам вирішити адміністративні справи в\u00a0Любліні. Скажу куди йти, що взяти і\u00a0скільки це займе.",
    popular: "Популярні запитання",
  },
  suggestions: [
    { text: "Як отримати посвідчення особи?" },
    { text: "Де зареєструвати автомобіль?" },
    { text: "Скільки коштує цивільне весілля?" },
    { text: "Дозвіл на будівництво" },
    { text: "Хто є мером Любліна?" },
    { text: "Тимчасова реєстрація – процедура" },
  ],
  input: {
    placeholder: "Запитайте про адміністративну справу...",
  },
  loading: "Шукаю відповідь...",
  cards: {
    where: "Де вирішити",
    how: "Як вирішити",
    howMuch: "Вартість та час",
    who: "Відповідальна особа",
    cost: "Вартість",
    time: "Час",
    requiredDocs: "Необхідні документи",
    forms: "Форми",
    submissionMethod: "Спосіб подання:",
    booking: "Записатися онлайн",
    bookingDesc: "Забронюйте час без черги",
    relatedQuestions: "Пов'язані запитання",
    info: "Інформація",
    fillDocument: "Як заповнити документ",
    fieldName: "Поле",
    whatToWrite: "Що вписати",
    example: "Приклад",
    tips: "Підказка",
    generalTips: "Загальні поради",
    commonMistakes: "Часті помилки",
    whereToGet: "Де отримати бланк",
    whereToSubmit: "Де подати",
  },
  errors: {
    connection: "Помилка з'єднання з сервером. Спробуйте ще раз.",
    noAnswer: "Не вдалося отримати відповідь.",
  },
  voice: {
    listening: "Слухаю...",
    tapToSpeak: "Натисніть, щоб говорити",
    notSupported: "Ваш браузер не підтримує розпізнавання мови.",
  },
  tts: {
    speak: "Прочитати відповідь",
    stop: "Зупинити читання",
  },
  feedback: {
    responseActions: "Дії з відповіддю",
    helpful: "Корисна відповідь",
    notHelpful: "Некорисна відповідь",
  },
};

export const translations: Record<Locale, Translations> = { pl, en, ua };

export const SPEECH_LOCALES: Record<Locale, string> = {
  pl: "pl-PL",
  en: "en-US",
  ua: "uk-UA",
};
