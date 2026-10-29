import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createInterstitial, INTERSTITIAL_ID } from '../apps/toss/src/interstitial.ts';

function setup({ supported = true, sync = false, loadError = false, showError = false } = {}) {
  const state = { loads: [], shows: [], busy: [], starts: 0, cleaned: 0 };
  const ads = {
    load: Object.assign(params => {
      assert.equal(params.options.adGroupId, INTERSTITIAL_ID);
      state.loads.push(params);
      if (loadError) params.onError(new Error('no fill'));
      else if (sync) params.onEvent({ type: 'loaded' });
      return () => state.cleaned++;
    }, { isSupported: () => supported }),
    show: Object.assign(params => {
      assert.equal(params.options.adGroupId, INTERSTITIAL_ID);
      state.shows.push(params);
      if (showError) throw new Error('show failed');
      if (sync) params.onEvent({ type: 'dismissed' });
      return () => state.cleaned++;
    }, { isSupported: () => supported }),
  };
  const controller = createInterstitial(ads, value => state.busy.push(value));
  const start = () => controller.start(() => state.starts++);
  return { state, controller, start };
}

test('dismissal starts once; clicks, impressions and repeated taps do not restart', () => {
  const { state, controller, start } = setup();
  try {
    state.loads[0].onEvent({ type: 'loaded' });
    start(); start();
    assert.equal(state.shows.length, 1);
    for (const type of ['requested', 'show', 'impression', 'clicked', 'userEarnedReward']) state.shows[0].onEvent({ type });
    assert.equal(state.starts, 0);
    state.shows[0].onEvent({ type: 'dismissed' });
    state.shows[0].onError(new Error());
    assert.equal(state.starts, 1);
    assert.deepEqual(state.busy, [true, false]);
    assert.equal(state.loads.length, 2);
  } finally { controller.dispose(); }
});
test('unsupported, not ready, no-fill, show failure and synchronous callbacks continue learning', () => {
  for (const config of [{ supported: false }, {}, { loadError: true }, { sync: true }, { sync: true, showError: true }]) {
    const { state, controller, start } = setup(config);
    try { start(); assert.equal(state.starts, 1); }
    finally { controller.dispose(); }
  }
  const { state, controller, start } = setup();
  try {
    state.loads[0].onEvent({ type: 'loaded' }); start();
    state.shows[0].onEvent({ type: 'failedToShow' });
    assert.equal(state.starts, 1);
  } finally { controller.dispose(); }
});
test('late callbacks after navigation or replacement cannot reset a session', () => {
  const { state, controller, start } = setup();
  start(); // not loaded: continue immediately, replace the pending load
  state.loads[0].onEvent({ type: 'loaded' });
  start();
  assert.equal(state.shows.length, 0);
  state.loads.at(-1).onEvent({ type: 'loaded' }); start();
  controller.dispose();
  state.shows[0].onEvent({ type: 'dismissed' });
  assert.equal(state.starts, 2);
});
test('silent load expires and stale loaded callback is ignored', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const { state, controller, start } = setup();
  try {
    t.mock.timers.tick(8000);
    state.loads[0].onEvent({ type: 'loaded' }); start();
    assert.equal(state.starts, 1);
    assert.equal(state.shows.length, 0);
  } finally { controller.dispose(); }
});
test('silent show times out; visible ad waits for dismissal', t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  for (const visible of [false, true]) {
    const { state, controller, start } = setup();
    try {
      state.loads[0].onEvent({ type: 'loaded' }); start();
      if (visible) state.shows[0].onEvent({ type: 'show' });
      t.mock.timers.tick(8000);
      assert.equal(state.starts, visible ? 0 : 1);
      state.shows[0].onEvent({ type: 'dismissed' });
      assert.equal(state.starts, 1);
    } finally { controller.dispose(); }
  }
});
