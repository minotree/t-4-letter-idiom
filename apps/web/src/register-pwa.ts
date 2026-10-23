let updateRequested = false;
export function applyUpdate(worker: ServiceWorker) {
  updateRequested = true;
  worker.postMessage({ type: 'SKIP_WAITING' });
}

if (import.meta.env.PROD && 'serviceWorker' in navigator) {
  window.addEventListener('load', async () => {
    let refreshing = false;
    navigator.serviceWorker.addEventListener('controllerchange', () => {
      if (refreshing || !navigator.serviceWorker.controller) return;
      // The first install claims this page without interrupting a quiz.
      if (updateRequested) {
        refreshing = true;
        window.location.reload();
      }
    });
    try {
      const registration = await navigator.serviceWorker.register(`${import.meta.env.BASE_URL}sw.js`);
      function announce(worker: ServiceWorker | null) {
        if (worker) window.dispatchEvent(new CustomEvent('idioms-update', { detail: worker }));
      }
      if (registration.waiting) announce(registration.waiting);
      registration.addEventListener('updatefound', () => {
        const worker = registration.installing;
        worker?.addEventListener('statechange', () => {
          if (worker.state === 'installed' && navigator.serviceWorker.controller) announce(registration.waiting);
        });
      });
    } catch {
      window.dispatchEvent(new CustomEvent('idioms-pwa-error'));
    }
  });
}
