export default function Header() {
  return (
    <header className="h-16 border-b border-lublin-border bg-white flex items-center px-6 shrink-0">
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 bg-lublin-green rounded-xl flex items-center justify-center">
          <svg
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            stroke="white"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M12 2L2 7l10 5 10-5-10-5z" />
            <path d="M2 17l10 5 10-5" />
            <path d="M2 12l10 5 10-5" />
          </svg>
        </div>
        <div>
          <h1 className="text-lg font-bold leading-tight">Asystent Miasta Lublin</h1>
          <p className="text-xs text-lublin-muted leading-tight">
            Urząd Miasta Lublin • AI
          </p>
        </div>
      </div>
      <div className="ml-auto flex items-center gap-4">
        <span className="text-xs text-lublin-muted bg-lublin-surface px-3 py-1 rounded-full">
          Dane z BIP Lublin
        </span>
      </div>
    </header>
  );
}
