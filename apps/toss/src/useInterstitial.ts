import { useEffect, useRef, useState } from 'react';
import { loadFullScreenAd, showFullScreenAd } from '@apps-in-toss/web-framework';
import { createInterstitial } from './interstitial';

export function useInterstitial(active: boolean) {
  const controller = useRef<ReturnType<typeof createInterstitial> | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    setBusy(false);
    if (!active) return;
    const instance = createInterstitial({ load: loadFullScreenAd, show: showFullScreenAd }, setBusy);
    controller.current = instance;
    return () => { controller.current = null; instance.dispose(); };
  }, [active]);
  return { busy, start: (next: () => void) => controller.current?.start(next) };
}
