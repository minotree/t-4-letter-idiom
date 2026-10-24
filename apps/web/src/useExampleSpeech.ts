import { useCallback, useEffect, useRef, useState } from 'react';

export function useExampleSpeech() {
  const [activeId, setActiveId] = useState<string | null>(null);
  const [error, setError] = useState('');
  const current = useRef<SpeechSynthesisUtterance | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const cancel = useCallback(() => {
    const owned = current.current;
    current.current = null;
    if (timer.current) clearTimeout(timer.current);
    timer.current = null;
    if (owned) window.speechSynthesis.cancel();
  }, []);
  const stop = useCallback(() => { cancel(); setActiveId(null); }, [cancel]);
  const speak = useCallback((id: string, text: string, slow = false) => {
    stop();
    setError('');
    if (!text.trim()) return;
    if (!('speechSynthesis' in window) || !('SpeechSynthesisUtterance' in window)) {
      setError('이 기기에서는 예문 읽기를 지원하지 않아요.');
      return;
    }
    try {
      const synth = window.speechSynthesis;
      const utterance = new SpeechSynthesisUtterance(text.trim());
      utterance.lang = 'en-US';
      utterance.rate = slow ? 0.75 : 1;
      const voices = synth.getVoices().filter(voice => /^en(?:-|_)/i.test(voice.lang));
      const voice = voices.find(voice => voice.lang === 'en-US' && voice.localService)
        ?? voices.find(voice => voice.localService) ?? voices.find(voice => voice.lang === 'en-US') ?? voices[0];
      if (voice) { utterance.voice = voice; utterance.lang = voice.lang; }
      current.current = utterance;
      setActiveId(id);
      utterance.onstart = () => {
        if (current.current === utterance && timer.current) { clearTimeout(timer.current); timer.current = null; }
      };
      utterance.onend = () => { if (current.current === utterance) stop(); };
      utterance.onerror = () => {
        if (current.current !== utterance) return;
        stop();
        setError('예문을 읽지 못했어요. 기기의 영어 음성과 네트워크 상태를 확인한 뒤 다시 눌러 주세요.');
      };
      timer.current = setTimeout(() => {
        if (current.current !== utterance) return;
        stop();
        setError('음성 재생이 시작되지 않았어요. 다시 눌러 주세요.');
      }, 10000);
      synth.speak(utterance);
    } catch {
      stop();
      setError('예문을 읽지 못했어요. 잠시 후 다시 눌러 주세요.');
    }
  }, [stop]);
  useEffect(() => {
    const hidden = () => { if (document.hidden) stop(); };
    window.addEventListener('hashchange', stop);
    window.addEventListener('pagehide', stop);
    document.addEventListener('visibilitychange', hidden);
    return () => {
      cancel();
      window.removeEventListener('hashchange', stop);
      window.removeEventListener('pagehide', stop);
      document.removeEventListener('visibilitychange', hidden);
    };
  }, [cancel, stop]);
  return { activeId, error, speak, stop };
}
