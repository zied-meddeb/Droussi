import { createContext, useContext, useEffect, useState } from "react";
import type { Lang } from "../lib/i18n";
import { isRtl } from "../lib/i18n";

interface LanguageContextValue {
  lang: Lang;
  setLang: (lang: Lang) => void;
}

const LanguageContext = createContext<LanguageContextValue>({
  lang: "en",
  setLang: () => {},
});

const SUPPORTED: Lang[] = ["en", "fr", "ar"];

function readStoredLang(): Lang {
  const stored = localStorage.getItem("droussi_lang");
  return SUPPORTED.includes(stored as Lang) ? (stored as Lang) : "en";
}

export function LanguageProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLangState] = useState<Lang>(readStoredLang);

  // Keep the document's language and text direction in sync with the choice so
  // screen readers announce the right language and RTL scripts (e.g. Arabic)
  // lay out correctly.
  useEffect(() => {
    document.documentElement.lang = lang;
    document.documentElement.dir = isRtl(lang) ? "rtl" : "ltr";
  }, [lang]);

  const setLang = (l: Lang) => {
    localStorage.setItem("droussi_lang", l);
    setLangState(l);
  };

  return (
    <LanguageContext.Provider value={{ lang, setLang }}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage() {
  return useContext(LanguageContext);
}
