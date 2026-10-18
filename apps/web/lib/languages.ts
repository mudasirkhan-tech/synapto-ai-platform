/** Languages offered for browser speech recognition. Actual support depends on the browser and its speech service. */
export const SPEECH_LANGS: [string, string][] = [
  ["en-US", "English (US)"], ["en-GB", "English (UK)"], ["ur-PK", "Urdu"], ["hi-IN", "Hindi"], ["ar-SA", "Arabic"],
  ["fa-IR", "Persian"], ["pa-IN", "Punjabi"], ["ps-AF", "Pashto (limited support)"], ["tr-TR", "Turkish"],
  ["fr-FR", "French"], ["es-ES", "Spanish"], ["de-DE", "German"], ["zh-CN", "Chinese (Mandarin)"],
];

export function defaultSpeechLang(saved: string | null): string {
  if (saved && SPEECH_LANGS.some(([c]) => c === saved)) return saved;
  const nav = typeof navigator !== "undefined" ? navigator.language : "en-US";
  return SPEECH_LANGS.find(([c]) => c === nav)?.[0] ?? SPEECH_LANGS.find(([c]) => c.startsWith(nav.split("-")[0]))?.[0] ?? "en-US";
}
