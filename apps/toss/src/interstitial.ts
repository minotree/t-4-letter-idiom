import type { loadFullScreenAd, showFullScreenAd } from '@apps-in-toss/web-framework';

export const INTERSTITIAL_ID = 'ait.v2.live.d71009b2ef5a4d21';
type Ads = { load: typeof loadFullScreenAd; show: typeof showFullScreenAd };

// One controller belongs to one active learning screen. SDK callbacks may be synchronous.
export function createInterstitial(ads: Ads, busy: (value: boolean) => void) {
  let disposed = false;
  let ready = false;
  let showing = false;
  let generation = 0;
  let cancel: (() => void) | undefined;
  let timer: ReturnType<typeof setTimeout> | undefined;
  function clear() { clearTimeout(timer); cancel?.(); cancel = undefined; }
  function load() {
    if (disposed) return;
    const current = ++generation;
    clear(); ready = false;
    try {
      if (!ads.load.isSupported() || !ads.show.isSupported()) return;
      let settled = false;
      const settle = (loaded: boolean) => {
        if (disposed || settled || current !== generation) return;
        settled = true; ready = loaded; clear();
        if (!loaded) console.warn('[Toss interstitial] 광고를 준비하지 못해 학습을 계속합니다.');
      };
      timer = setTimeout(() => settle(false), 8000);
      const cleanup = ads.load({ options: { adGroupId: INTERSTITIAL_ID }, onEvent: () => settle(true), onError: () => settle(false) });
      if (settled || disposed) cleanup(); else cancel = cleanup;
    } catch { clear(); console.warn('[Toss interstitial] 광고 미지원 또는 로드 실패'); }
  }
  load();
  return {
    start(next: () => void) {
      if (disposed || showing) return;
      if (!ready) { next(); load(); return; }
      ready = false; showing = true; busy(true); clear();
      const current = ++generation;
      let settled = false;
      const finish = (failed: boolean) => {
        if (disposed || settled || current !== generation) return;
        settled = true; showing = false; clear(); busy(false);
        if (failed) console.warn('[Toss interstitial] 광고 표시 실패로 학습을 계속합니다.');
        next(); load();
      };
      try {
        // Once visible, only the SDK's dismissal/error may resume learning.
        timer = setTimeout(() => finish(true), 8000);
        const cleanup = ads.show({
          options: { adGroupId: INTERSTITIAL_ID },
          onEvent: event => {
            if (disposed || settled || current !== generation) return;
            if (event.type === 'show' || event.type === 'impression') clearTimeout(timer);
            if (event.type === 'dismissed') finish(false);
            if (event.type === 'failedToShow') finish(true);
          },
          onError: () => finish(true),
        });
        if (settled || disposed) cleanup(); else cancel = cleanup;
      } catch { finish(true); }
    },
    dispose() { disposed = true; ready = false; clear(); },
  };
}
