// Non-sensitive preferences only. API keys are never stored in the browser.
const read = (key: string) => (typeof window === "undefined" ? null : window.localStorage.getItem(key));

export function getReplyScale(): number {
  const v = Number(read("synapto.replyScale"));
  return v >= 0.8 && v <= 1.4 ? v : 1;
}
export function setReplyScale(v: number) {
  window.localStorage.setItem("synapto.replyScale", String(v));
  document.documentElement.style.setProperty("--reply-scale", String(v));
}

export const getFallback = () => read("synapto.fallback") !== "off"; // automatic provider fallback, on by default
export const setFallback = (on: boolean) => window.localStorage.setItem("synapto.fallback", on ? "on" : "off");

export const getAgentTools = () => read("synapto.agentTools") === "on";
export const setAgentTools = (on: boolean) => window.localStorage.setItem("synapto.agentTools", on ? "on" : "off");

export const getSpeechLang = () => read("synapto.speechLang");
export const setSpeechLang = (v: string) => window.localStorage.setItem("synapto.speechLang", v);

export const getVoiceURI = () => read("synapto.voiceURI");
export const setVoiceURI = (v: string) => (v ? window.localStorage.setItem("synapto.voiceURI", v) : window.localStorage.removeItem("synapto.voiceURI"));
