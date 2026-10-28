import { useEffect, useRef, useState } from 'react';
import { TossAds } from '@apps-in-toss/web-framework';

const AD_GROUP_ID = 'ait.v2.live.e2aee41b54214449';

export function BottomBanner() {
  const target = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState<'loading' | 'ready' | 'hidden'>('loading');

  useEffect(() => {
    let disposed = false;
    let banner: ReturnType<typeof TossAds.attachBanner> | undefined;
    const fail = () => {
      if (!disposed) {
        setStatus('hidden');
        console.warn('[Toss banner] 광고를 표시하지 못해 광고 영역을 접었습니다.');
      }
    };
    try {
      if (!TossAds.initialize.isSupported() || !TossAds.attachBanner.isSupported()) {
        setStatus('hidden');
        return;
      }
      TossAds.initialize({ callbacks: {
        onInitialized: () => {
          if (disposed || !target.current) return;
          try {
            banner = TossAds.attachBanner(AD_GROUP_ID, target.current, {
              theme: 'light', tone: 'blackAndWhite', variant: 'expanded',
              callbacks: {
                onAdRendered: () => { if (!disposed) setStatus('ready'); },
                onNoFill: () => { if (!disposed) setStatus('hidden'); },
                onAdFailedToRender: fail,
              },
            });
          } catch { fail(); }
        },
        onInitializationFailed: fail,
      } });
    } catch { fail(); }
    return () => { disposed = true; banner?.destroy(); };
  }, []);

  return <aside className="bottom-banner" aria-label="광고" hidden={status === 'hidden'} style={{ visibility: status === 'ready' ? 'visible' : 'hidden' }}>
    <div ref={target} />
  </aside>;
}
