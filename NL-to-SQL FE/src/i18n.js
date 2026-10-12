
import i18n from "i18next";
import { initReactI18next } from "react-i18next";

// Translation dictionaries
import en from "./locales/en.json";
import de from "./locales/de.json";
import fr from "./locales/fr.json";
import es from "./locales/es.json";
import it from "./locales/it.json";
import pt from "./locales/pt.json";
import ar from "./locales/ar.json";
import ur from "./locales/ur.json";
import romanUr from "./locales/roman_ur.json";
import hi from "./locales/hi.json";
import zh from "./locales/zh.json";
import ja from "./locales/ja.json";
import ko from "./locales/ko.json";
import tr from "./locales/tr.json";
import ru from "./locales/ru.json";
import nl from "./locales/nl.json";
import sv from "./locales/sv.json";
import pl from "./locales/pl.json";
import id from "./locales/id.json";
import bn from "./locales/bn.json";

export const LANGUAGE_OPTIONS = [
  { code: "en", name: "English", nativeName: "English", dir: "ltr" },
  { code: "de", name: "German", nativeName: "Deutsch", dir: "ltr" },
  { code: "fr", name: "French", nativeName: "Français", dir: "ltr" },
  { code: "es", name: "Spanish", nativeName: "Español", dir: "ltr" },
  { code: "it", name: "Italian", nativeName: "Italiano", dir: "ltr" },
  { code: "pt", name: "Portuguese", nativeName: "Português", dir: "ltr" },
  { code: "ar", name: "Arabic", nativeName: "العربية", dir: "rtl" },
  { code: "ur", name: "Urdu", nativeName: "اردو", dir: "rtl" },
  { code: "roman_ur", name: "Roman Urdu", nativeName: "Roman Urdu", dir: "ltr" },
  { code: "hi", name: "Hindi", nativeName: "हिन्दी", dir: "ltr" },
  { code: "zh", name: "Chinese", nativeName: "中文", dir: "ltr" },
  { code: "ja", name: "Japanese", nativeName: "日本語", dir: "ltr" },
  { code: "ko", name: "Korean", nativeName: "한국어", dir: "ltr" },
  { code: "tr", name: "Turkish", nativeName: "Türkçe", dir: "ltr" },
  { code: "ru", name: "Russian", nativeName: "Русский", dir: "ltr" },
  { code: "nl", name: "Dutch", nativeName: "Nederlands", dir: "ltr" },
  { code: "sv", name: "Swedish", nativeName: "Svenska", dir: "ltr" },
  { code: "pl", name: "Polish", nativeName: "Polski", dir: "ltr" },
  { code: "id", name: "Indonesian", nativeName: "Bahasa Indonesia", dir: "ltr" },
  { code: "bn", name: "Bengali", nativeName: "বাংলা", dir: "ltr" },
];

const STORAGE_KEY = "datapilot-language";

const translations = {
  en, de, fr, es, it, pt, ar, ur,
  roman_ur: romanUr,
  hi, zh, ja, ko, tr, ru, nl, sv, pl, id, bn,
};

const resources = Object.fromEntries(
  Object.entries(translations).map(([code, translation]) => [
    code,
    { translation },
  ])
);

function getInitialLanguage() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);

    if (LANGUAGE_OPTIONS.some((item) => item.code === saved)) {
      return saved;
    }
  } catch {
    // Storage may be unavailable.
  }

  // Always use English on first visit.
  return "en";
}

function applyDocumentLanguage(code) {
  const selected = LANGUAGE_OPTIONS.find(
    (item) => item.code === code
  ) || LANGUAGE_OPTIONS[0];

  document.documentElement.lang =
    selected.code === "roman_ur"
      ? "ur-Latn"
      : selected.code;

  document.documentElement.dir = selected.dir;
}

// Restore direction immediately on page load.
const initialLanguage = getInitialLanguage();

applyDocumentLanguage(initialLanguage);

i18n.use(initReactI18next).init({
  resources,
  lng: initialLanguage,
  fallbackLng: "en",
  supportedLngs: LANGUAGE_OPTIONS.map((item) => item.code),
  load: "currentOnly",
  interpolation: {
    escapeValue: false,
  },
  returnNull: false,
});

export async function setAppLanguage(language) {
  const selected = LANGUAGE_OPTIONS.find(
    (item) => item.code === language
  );

  if (!selected) {
    return false;
  }

  await i18n.changeLanguage(selected.code);

  applyDocumentLanguage(selected.code);

  try {
    localStorage.setItem(STORAGE_KEY, selected.code);
  } catch {
    // Preference remains active until refresh.
  }

  return true;
}

export default i18n;
