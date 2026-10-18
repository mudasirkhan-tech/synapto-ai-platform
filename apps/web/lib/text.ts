export type Dir = "ltr" | "rtl";

// Strong right-to-left letters: Hebrew, Arabic (+supplements), Syriac, Thaana, N'Ko, Arabic presentation forms.
const RTL_LETTER = /[\u0590-\u08FF\uFB1D-\uFDFF\uFE70-\uFEFF]/;

/** First-strong-letter rule (what browsers use for dir="auto"): the first letter decides the direction. */
export function detectDir(text: string): Dir {
  for (const ch of text.slice(0, 400)) {
    if (!/\p{L}/u.test(ch)) continue; // skip digits, punctuation, emoji, spaces
    return RTL_LETTER.test(ch) ? "rtl" : "ltr";
  }
  return "ltr";
}

// Letters used by Urdu (and Punjabi in Shahmukhi) but not by Arabic or Persian.
const URDU_LETTER = /[\u0679\u0688\u0691\u06BA\u06BE\u06C1\u06D2\u06D3]/;
const ARABIC_SCRIPT = /[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]/;

/** CSS class (see globals.css) with a suitable typeface for the dominant script of `text`. */
export function scriptClass(text: string): string {
  const sample = text.slice(0, 600);
  if (URDU_LETTER.test(sample)) return "font-urdu"; // Noto Nastaliq Urdu
  if (ARABIC_SCRIPT.test(sample)) return "font-arabic"; // Noto Naskh Arabic (Arabic, Persian, Pashto)
  if (/[\u0900-\u097F]/.test(sample)) return "font-deva"; // Hindi, Marathi, Nepali
  if (/[\u0590-\u05FF]/.test(sample)) return "font-hebrew";
  return "";
}
