import { lazy, Suspense, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { readSessions, SessionStars, STEP_COLORS } from './LearningMilestones';
import { candidatesFor, matchingAnswers, readingHint, migrateIdiomHistory, SESSION_LIMIT, type Idiom } from '@idioms/shared';
import data from './data/idioms.json';
import englishSource from '../../../data/english/source.json';
import { applyUpdate } from './register-pwa';
import IdiomBook from './IdiomBook';
import ContentSource from './ContentSource';
import './styles.css';

const EnglishLearning = lazy(() => import('./EnglishLearning'));

const idioms: Idiom[] = data.map(item => {
  const category = item.category;
  if (category !== 'idiom' && category !== 'cheonjamun') throw new Error('학습 자료의 종류가 올바르지 않습니다.');
  return { ...item, category };
});
const HISTORY_KEY = 'idioms:web:history:v1';
const SESSIONS_KEY = 'idioms:web:hanja:completed-sessions:v1';
function currentPage() {
  return location.hash === '#english' ? 'english' : location.hash === '#idioms' ? 'book' : location.hash === '#main' ? 'quiz' : 'home';
}

function readHistory(key = HISTORY_KEY): { ids: string[]; warning: string } {
  try {
    const saved: unknown = JSON.parse(localStorage.getItem(key) ?? '[]');
    if (!Array.isArray(saved) || !saved.every(id => typeof id === 'string')) throw new Error();
    const valid = new Set(idioms.map(item => item.id));
    return { ids: migrateIdiomHistory(saved, valid), warning: '' };
  } catch {
    return { ids: [], warning: '이전 학습 기록을 읽지 못했습니다. 이번 학습은 계속할 수 있어요.' };
  }
}

function pickStart(history: Set<string>): Idiom {
  const available = idioms.filter(item => [...item.reading].some(ch =>
    candidatesFor(idioms, ch, new Set([item.id]), history).length > 0));
  const unseen = available.filter(item => !history.has(item.id));
  const pool = unseen.length ? unseen : available;
  return pool[Math.floor(Math.random() * pool.length)] ?? idioms[0];
}

export default function App() {
  const [savedSessions] = useState(() => readSessions(SESSIONS_KEY));
  const [sessionCount, setSessionCount] = useState(savedSessions.count);
  const [sessionWarning, setSessionWarning] = useState(savedSessions.warning);
  const [saved] = useState(() => readHistory());
  const [savedFavorites] = useState(() => readHistory('idioms:web:favorites:v1'));
  const [savedCompleted] = useState(() => readHistory('idioms:web:completed:v1'));
  const [savedMistakes] = useState(() => readHistory('idioms:web:mistakes:v2'));
  const [legacyMistakes] = useState(() => readHistory('idioms:web:mistakes:v1'));
  const [favorites, setFavorites] = useState(() => new Set(savedFavorites.ids));
  const [completed, setCompleted] = useState(() => new Set(savedCompleted.ids));
  const [mistakes, setMistakes] = useState(() => new Set(savedMistakes.ids));
  const [page, setPage] = useState(currentPage);
  const [englishOpened, setEnglishOpened] = useState(() => location.hash === '#english');
  const [hanjaPage, setHanjaPage] = useState(() => location.hash === '#idioms' ? 'book' : 'quiz');
  const [history, setHistory] = useState(() => new Set(saved.ids));
  const [warning, setWarning] = useState([saved.warning, savedFavorites.warning, savedCompleted.warning, savedMistakes.warning].filter(Boolean).join(' '));
  const [start, setStart] = useState(() => pickStart(new Set(saved.ids)));
  const [chain, setChain] = useState<Idiom[]>([]);
  const [connections, setConnections] = useState<string[]>([]);
  const [character, setCharacter] = useState('');
  const [answer, setAnswer] = useState('');
  const [meaningOpen, setMeaningOpen] = useState(false);
  const [attempts, setAttempts] = useState<Record<string, number>>({});
  const [message, setMessage] = useState('마음에 드는 한 글자를 골라 시작해 보세요.');
  const [selectedId, setSelectedId] = useState('');
  const [confirmRestart, setConfirmRestart] = useState(false);
  const [update, setUpdate] = useState<ServiceWorker | null>(null);
  const [offline, setOffline] = useState(!navigator.onLine);
  const input = useRef<HTMLInputElement>(null);
  const currentCard = useRef<HTMLDivElement>(null);
  const [floating, setFloating] = useState<{ top: number; left: number; width: number; maxHeight?: number } | null>(null);
  const anchor = useRef<HTMLLIElement | null>(null);
  const opening = useRef(false);
  const openingFrame = useRef(0);
  const keyboardTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const title = useRef<HTMLHeadingElement>(null);
  const locked = useRef(false);

  const current = chain.at(-1) ?? start;
  const used = new Set([start.id, ...chain.map(item => item.id)]);
  const candidates = candidatesFor(idioms, character, used, history);
  const selected = candidates.find(item => item.id === selectedId);
  const hasNext = [...current.reading].some(ch => candidatesFor(idioms, ch, used, history).length > 0);
  const finished = chain.length >= SESSION_LIMIT || !hasNext;

  useEffect(() => {
    const navigate = () => {
      setPage(currentPage());
      if (location.hash === '#english') setEnglishOpened(true);
      else if (location.hash === '#idioms' || location.hash === '#main') setHanjaPage(location.hash === '#idioms' ? 'book' : 'quiz');
    };
    window.addEventListener('hashchange', navigate);
    return () => window.removeEventListener('hashchange', navigate);
  }, []);

  useEffect(() => {
    const available = (event: Event) => setUpdate((event as CustomEvent<ServiceWorker>).detail);
    const network = () => setOffline(!navigator.onLine);
    const pwaError = () => setWarning('오프라인 준비를 완료하지 못했어요. 연결 상태를 확인하고 다시 접속해 주세요.');
    window.addEventListener('idioms-update', available);
    window.addEventListener('online', network);
    window.addEventListener('offline', network);
    window.addEventListener('idioms-pwa-error', pwaError);
    return () => {
      window.removeEventListener('idioms-update', available);
      window.removeEventListener('online', network);
      window.removeEventListener('offline', network);
      window.removeEventListener('idioms-pwa-error', pwaError);
    };
  }, []);

  useEffect(() => {
    if (selectedId && floating && page === 'quiz') input.current?.focus({ preventScroll: true });
    else if (chain.length && page === 'quiz') title.current?.focus({ preventScroll: true });
  }, [selectedId, chain.length, Boolean(floating), page]);
  useLayoutEffect(() => {
    if (!chain.length) return;
    const frame = requestAnimationFrame(() => currentCard.current?.scrollIntoView({ block: 'start', behavior: 'instant' }));
    return () => cancelAnimationFrame(frame);
  }, [chain.length]);

  function fitFloating(alignCandidate = false) {
    const form = input.current?.closest('form');
    if (!form || !anchor.current || !form.classList.contains('floating-answer')) return;
    const candidate = anchor.current;
    const viewport = window.visualViewport;
    const topEdge = (viewport?.offsetTop ?? 0) + 12;
    // Leave room for the iOS input accessory bar above the software keyboard.
    const bottomEdge = (viewport ? viewport.offsetTop + viewport.height : window.innerHeight) - 56;
    const height = form.scrollHeight + 2;
    const list = candidate.closest('ol');
    if (alignCandidate) {
      opening.current = true;
      cancelAnimationFrame(openingFrame.current);
    }
    if (alignCandidate && list) {
      const row = candidate.getBoundingClientRect();
      const bounds = list.getBoundingClientRect();
      if (row.bottom > bounds.bottom) list.scrollTop += row.bottom - bounds.bottom;
      else if (row.top < bounds.top) list.scrollTop += row.top - bounds.top;
    }
    let row = candidate.getBoundingClientRect();
    const available = Math.max(1, bottomEdge - topEdge);
    const candidateHeight = Math.min(row.height, Math.max(44, available - 120));
    const maxHeight = Math.max(1, available - candidateHeight - 8);
    const formHeight = Math.min(height, maxHeight);
    const targetTop = bottomEdge - candidateHeight;
    if (alignCandidate && Math.abs(row.top - targetTop) > 2) {
      window.scrollBy({ top: row.top - targetTop, behavior: 'instant' });
    }
    row = candidate.getBoundingClientRect();
    const top = Math.max(topEdge, Math.min(row.top - 8 - formHeight, bottomEdge - formHeight));
    if (alignCandidate) {
      openingFrame.current = requestAnimationFrame(() => {
        openingFrame.current = requestAnimationFrame(() => { opening.current = false; });
      });
    }
    setFloating(value => value && (value.top !== top || value.maxHeight !== maxHeight) ? { ...value, top, maxHeight } : value);
  }
  useLayoutEffect(() => { if (floating) fitFloating(true); }, [Boolean(floating), selectedId]);
  useLayoutEffect(() => { if (floating) fitFloating(); }, [attempts]);
  useEffect(() => {
    const close = () => { setFloating(null); input.current?.blur(); };
    const fit = () => fitFloating();
    let lastHeight = window.visualViewport?.height ?? window.innerHeight;
    const resize = () => {
      fitFloating();
      const height = window.visualViewport?.height ?? window.innerHeight;
      if (Math.abs(height - lastHeight) < 2) return;
      lastHeight = height;
      if (keyboardTimer.current) clearTimeout(keyboardTimer.current);
      keyboardTimer.current = setTimeout(() => fitFloating(true), 180);
    };
    window.addEventListener('hashchange', close);
    window.addEventListener('resize', resize);
    window.visualViewport?.addEventListener('resize', resize);
    window.visualViewport?.addEventListener('scroll', fit);
    return () => { cancelAnimationFrame(openingFrame.current); if (keyboardTimer.current) clearTimeout(keyboardTimer.current); window.removeEventListener('hashchange', close); window.removeEventListener('resize', resize); window.visualViewport?.removeEventListener('resize', resize); window.visualViewport?.removeEventListener('scroll', fit); };
  }, []);

  function closeFloating() { opening.current = false; cancelAnimationFrame(openingFrame.current); if (keyboardTimer.current) clearTimeout(keyboardTimer.current); setFloating(null); if (document.activeElement === input.current) input.current?.blur(); }
  function selectCandidate(item: Idiom, element: HTMLInputElement) {
    opening.current = true;
    cancelAnimationFrame(openingFrame.current);
    openingFrame.current = requestAnimationFrame(() => {
      openingFrame.current = requestAnimationFrame(() => { opening.current = false; });
    });
    anchor.current = element.closest('li');
    const row = element.closest('li')!.getBoundingClientRect();
    const list = element.closest('ol')!.getBoundingClientRect();
    const width = Math.min(list.width, window.innerWidth - 24);
    setSelectedId(item.id); setAnswer('');
    setMessage('선택한 후보의 한글 독음를 입력해 주세요.');
    setFloating({ top: Math.max(12, Math.min(row.bottom + 6, window.innerHeight - 220)), left: Math.max(12, Math.min(list.left, window.innerWidth - width - 12)), width });
  }

  function remember(ids: string[]) {
    const next = new Set([...history, ...ids]);
    setHistory(next);
    try { localStorage.setItem(HISTORY_KEY, JSON.stringify([...next])); setWarning(''); }
    catch { setWarning('학습 기록을 저장하지 못했습니다. 다음 접속에서는 같은 문제가 나올 수 있어요.'); }
  }

  function saveCollection(key: string, ids: Set<string>, version = 1) {
    try { localStorage.setItem(`idioms:web:${key}:v${version}`, JSON.stringify([...ids])); }
    catch { setWarning('한자성어장 기록을 저장하지 못했어요. 다음 접속에서는 변경 사항이 남지 않을 수 있어요.'); }
  }

  function toggleFavorite(id: string) {
    const next = new Set(favorites);
    if (next.has(id)) next.delete(id); else next.add(id);
    setFavorites(next); saveCollection('favorites', next);
  }

  function choose(ch: string) {
    closeFloating();
    locked.current = false;
    setCharacter(ch); setAnswer(''); setAttempts({}); setSelectedId('');
    setMessage(`‘${ch}’가 들어가는 후보 중 풀고 싶은 한자성어를 선택해 주세요.`);
  }

  function accept(item: Idiom) {
    if (locked.current || finished || selected?.id !== item.id) return;
    locked.current = true;
    closeFloating();
    remember([start.id, item.id]);
    const learned = new Set([...completed, item.id]);
    setCompleted(learned); saveCollection('completed', learned);
    if (chain.length + 1 === SESSION_LIMIT) {
      const count = Math.min(Number.MAX_SAFE_INTEGER, sessionCount + 1);
      setSessionCount(count);
      try { localStorage.setItem(SESSIONS_KEY, JSON.stringify(count)); setSessionWarning(''); }
      catch { setSessionWarning('완주 횟수를 저장하지 못했어요. 현재 별은 다음 접속에 남지 않을 수 있어요.'); }
    }
    setConnections([...connections, character]);
    setMeaningOpen(false);
    setChain([...chain, item]); setCharacter(''); setAnswer(''); setAttempts({}); setSelectedId('');
    setMessage(`${item.reading}, 정답이에요! 다음에 이어갈 글자를 골라 주세요.`);
    title.current?.focus({ preventScroll: true });
  }

  function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!selected || finished || locked.current) return;
    if (!answer.trim()) { setMessage('한글 독음을 먼저 입력해 주세요.'); input.current?.focus(); return; }
    if (matchingAnswers([selected], answer).length) accept(selected);
    else {
      const review = new Set([...mistakes, selected.id]);
      setMistakes(review); saveCollection('mistakes', review, 2);
      setAttempts(value => ({ ...value, [selected.id]: (value[selected.id] ?? 0) + 1 }));
      setMessage('선택한 후보의 독음과 달라요. 이 후보의 추가 힌트를 보고 다시 도전해 보세요.');
    }
  }

  function restart() {
    closeFloating();
    setMeaningOpen(false);
    locked.current = false;
    setStart(pickStart(history)); setChain([]); setCharacter(''); setAnswer('');
    setConnections([]);
    setAttempts({}); setSelectedId(''); setConfirmRestart(false);
    setMessage('새로운 이음을 시작해 볼까요? 한 글자를 골라 주세요.');
    title.current?.focus();
  }

  return (
    <main className={`app${page === 'home' ? ' home-page' : ''}`}>
      <header className="page-header">
        <a className="brand" href="#home">모두의 이음 <span>{page === 'home' ? '한자와 영어, 이어지는 배움' : page === 'english' ? '영어 학습' : '한자 학습'}</span></a>
        <span className="edition">하루 한 번, 즐거운 배움</span>
      </header>
      <section className="home-screen" hidden={page !== 'home'} aria-label="홈">
        <div className="intro home-intro">
          <span className="eyebrow">한 글자에서 시작하는 발견</span>
          <h1>아는 말이 이어지면,<br />배움이 되는 순간.</h1>
          <p>한자도 영어도, 한 글자씩 이어 보세요.<br />오늘의 작은 발견이 다음 배움으로 이어집니다.</p>
        </div>
        <div className="home-courses">
          <a className="home-course panel" href="#main">
            <span className="home-symbol" aria-hidden="true">字</span>
            <span className="eyebrow">한자성어 · 천자문</span>
            <h2>한자 학습</h2><p>글자를 고르고 뜻을 읽으며<br />한자성어를 이어 보세요.</p>
            <span className="home-course-action">{idioms.length}개 한자어 · 시작하기 <span aria-hidden="true">↗</span></span>
          </a>
          <a className="home-course home-course-english panel" href="#english">
            <span className="home-symbol" aria-hidden="true">Aa</span>
            <span className="eyebrow">알파벳으로 잇는 단어</span>
            <h2>영어 학습</h2><p>알파벳을 고르고 뜻을 읽으며<br />영어 단어를 이어 보세요.</p>
            <span className="home-course-action">{englishSource.rows}개 단어 · 시작하기 <span aria-hidden="true">↗</span></span>
          </a>
        </div>
        <section className="home-guide" aria-labelledby="home-guide-title">
          <h2 id="home-guide-title">이렇게 시작해요</h2>
          <ol><li><strong>01</strong> 이어갈 글자 고르기</li><li><strong>02</strong> 뜻을 보고 후보 선택하기</li><li><strong>03</strong> 정답을 입력하고 이어가기</li></ol>
          <p>한 번에 최대 10문제. 각 학습의 ‘나의 단어장’에서 즐겨찾기와 오답을 다시 살펴볼 수 있어요.</p>
        </section>
      </section>
      <section className="intro learning-intro" hidden={page === 'home'} aria-label="학습 소개">
        <span className="eyebrow">{page === 'english' ? '한 알파벳에서 시작하는 발견' : '한 글자에서 시작하는 발견'}</span>
        <h1>{page === 'english' ? '아는 단어가 이어지면,' : '아는 말이 이어지면,'}<br />배움이 되는 순간.</h1>
        <p>{page === 'english' ? '알파벳을 고르고, 뜻을 읽고, 아는 영어 단어를 적어 보세요.' : '글자를 고르고, 뜻을 읽고, 아는 한자성어를 적어 보세요.'}<br />정답이 다음 배움의 시작이 됩니다.</p>
      </section>
      <section className="learning-shell panel" hidden={page !== 'quiz' && page !== 'book'} aria-label="한자 학습">
      <div className="book-heading english-rank-heading"><h1>한자 글자잇기</h1><SessionStars count={sessionCount} /></div>
      <p className="english-word-total">{idioms.length}개 한자어 · 10문제를 모두 이으면 작은 별 하나</p>
      <nav className="learning-tabs" aria-label="한자 학습 메뉴">
        <a href="#main" aria-current={page === 'quiz' ? 'page' : undefined}>퀴즈 풀기</a>
        <a href="#idioms" aria-current={page === 'book' ? 'page' : undefined}>나의 단어장</a>
      </nav>
      <div hidden={page !== 'quiz'}>
      <p className="book-description">한글 글자 선택 → 후보 선택 → 한글 독음 입력</p>
      <div className="workspace">
        <section className="game" id="main" aria-label="한자성어 이음 퀴즈">
          <p className="learning-count">{chain.length} / {SESSION_LIMIT} 문제</p>
          <progress value={chain.length} max={SESSION_LIMIT} aria-label="맞힌 문제 수" />
          {chain.length > 0 && <section className="completed-chain" aria-label="이어 온 문제 사슬">
            <div className="english-journey-heading"><h3>지금까지 이어 온 한자성어</h3><span>이번 이음 {chain.length} / {SESSION_LIMIT}</span></div>
            <ol className="hanja-chain english-chain">{[start, ...chain].map((item, index) => {
              const row = Math.floor(index / 2);
              const column = row % 2 === 0 ? index % 2 + 1 : 2 - index % 2;
              const vertical = index > 0 && index % 2 === 0;
              return <li key={item.id} data-step={index} className={index === SESSION_LIMIT ? 'chain-complete' : undefined} style={{ gridRow: row + 1, gridColumn: column, borderColor: index > 0 ? STEP_COLORS[index - 1] : undefined }}>
                {index > 0 && <span className={`english-chain-bridge ${vertical ? 'bridge-down' : column === 2 ? 'bridge-right' : 'bridge-left'}`} aria-label={`${connections[index - 1]}로 이어짐`}><span>{connections[index - 1]}</span><span aria-hidden="true">{vertical ? '↓' : column === 2 ? '→' : '←'}</span></span>}
                <span className={`chain-word-step${index > 0 ? ' chain-step-badge' : ''}`} style={index > 0 ? { backgroundColor: STEP_COLORS[index - 1], color: index <= 2 || index === SESSION_LIMIT ? '#243a36' : '#fff' } : undefined}>{index === 0 ? '시작' : `${index} / ${SESSION_LIMIT}`}</span>
                {index === SESSION_LIMIT && <span className="chain-complete-label">10개 이음 완성</span>}
                <strong lang="zh">{item.hanja}</strong><span className="hanja-chain-reading">{item.reading}</span><p>{item.meaning}</p><ContentSource item={item} />
              </li>;
            })}</ol>
          </section>}
          <div className="idiom-card" ref={currentCard}>
            <span className="card-caption">{chain.length ? '방금 맞힌 한자성어' : '이음의 시작'}</span>
            <h2 ref={title} tabIndex={-1} lang="zh">{current.hanja}</h2>
            <div className="card-reading"><strong>{current.reading}</strong><button type="button" className="meaning-toggle" aria-expanded={meaningOpen} aria-controls="hanja-meaning" onClick={() => setMeaningOpen(value => !value)}>{meaningOpen ? '뜻 접기' : '뜻 보기'} <span aria-hidden="true">ⓘ</span></button></div>
            <p id="hanja-meaning" hidden={!meaningOpen}>{current.meaning}</p>
            <ContentSource item={current} />
          </div>
          {finished ? <div className="summary">
            <span className="eyebrow">나만의 배움 한 줄</span>
            <h2>{chain.length >= SESSION_LIMIT ? '10개의 한자성어를 이었어요!' : '이번 이음은 여기까지예요.'}</h2>
            <p>{chain.length >= SESSION_LIMIT ? '오늘 알게 된 말들이 다음 도전에 힘이 될 거예요.' : '같은 한자성어를 반복하지 않고 이어갈 후보가 더 없어요.'}</p>
            <button className="primary" onClick={restart}>새 세션 시작하기 <span aria-hidden="true">↗</span></button>
          </div> : <>
            <div className="instruction"><h3>01 <span>이어갈 한 글자를 골라 주세요</span></h3><span>후보가 없는 글자는 쉬어 가요</span></div>
            <div className="characters">{[...current.reading].map((ch, index) => {
              const count = candidatesFor(idioms, ch, used, history).length;
              return <button key={`${current.id}-${index}`} aria-label={`${ch}, 후보 ${count}개`} aria-pressed={character === ch}
                disabled={!count} onClick={() => choose(ch)}><strong>{ch}</strong><span>{count ? `후보 ${count}개` : '후보 없음'}</span></button>;
            })}</div>
            <section className="hints" aria-label="정답 후보 힌트">
              <div className="hint-heading"><h3>02 <span>풀고 싶은 한자성어를 선택해 주세요</span></h3>{character && <span className="pill">{candidates.length}개 후보</span>}</div>
              {!character ? <p className="empty">위에서 한 글자를 고르면<br />그 글자가 들어간 한자성어의 힌트가 나타나요.</p> : <>
                <p className="hint-description">‘<b>{character}</b>’가 들어가는 후보를 하나 선택한 뒤, 그 후보의 한글 독음을 입력하세요.</p>
                <ol className="candidate-list hanja-candidates" onWheel={closeFloating} onTouchMove={closeFloating} onScroll={() => { if (!opening.current) closeFloating(); }}>{candidates.map((item, index) => <li key={item.id} className={selectedId === item.id ? 'selected-candidate' : ''} onClick={event => { if ((event.target as HTMLElement).tagName === 'LABEL') return; selectCandidate(item, event.currentTarget.querySelector('input')!); }}>
                  <label className="candidate-choice hanja-candidate-choice"><input type="radio" name="candidate" value={item.id} aria-label={`후보 ${index + 1}, ${item.hanja} 선택`} checked={selectedId === item.id} onChange={() => {}} /><span className="candidate-number">{String(index + 1).padStart(2, '0')}</span><strong lang="zh">{item.hanja}</strong></label>
                  <p>{item.meaning}</p>{selectedId === item.id && (attempts[item.id] ?? 0) > 0 && <span className="reading-hint">독음 힌트 · {readingHint(item.reading, attempts[item.id])}</span>}
                  <ContentSource item={item} />
                </li>)}</ol>
              </>}
            </section>
            <form onSubmit={submit} className={`answer-form${floating ? ' floating-answer' : ''}`} style={floating ? { top: floating.top, left: floating.left, width: floating.width, maxHeight: floating.maxHeight } : undefined} onKeyDown={event => { if (event.key === 'Escape') closeFloating(); }}>
              <div className="floating-answer-heading"><label htmlFor="answer">03 <span>{selected ? <>선택한 후보: {selected.hanja} · <span className="answer-label-phrase">한글 독음 입력</span></> : '후보를 먼저 선택해 주세요'}</span></label>{floating && <button type="button" className="floating-close" onClick={closeFloating} aria-label="입력창 닫기">×</button>}</div>
              <div className="input-row"><input id="answer" ref={input} value={answer} onChange={event => setAnswer(event.target.value)}
                disabled={!selected} autoComplete="off" spellCheck={false} placeholder="선택한 후보의 한글 독음" aria-describedby={floating ? 'hanja-floating-feedback' : 'feedback'}
                onKeyDown={event => { if (event.key === 'Enter' && event.nativeEvent.isComposing) event.preventDefault(); }} />
                <button type="submit" className="primary" disabled={!selected}>확인 <span aria-hidden="true">↗</span></button></div>
              {floating && <p id="hanja-floating-feedback" role="status">{selected && attempts[selected.id] ? `독음 힌트 · ${readingHint(selected.reading, attempts[selected.id])}` : '후보 목록을 스크롤하면 입력창이 닫혀요.'}</p>}
            </form>
          </>}
          <p id="feedback" className="feedback" role="status">{finished ? `${chain.length}개의 한자성어를 정답으로 이었어요.` : message}</p>
        </section>
        <aside className="sidebar">
          <section className="guide"><span className="eyebrow">이렇게 이어가요</span><p>선택한 한글 글자가 독음에 들어간 후보를 고르고<br />전체 독음을 입력하면 정답!</p><ul><li>한자는 달라도 같은 한글이면 이어져요.</li><li>한 세션은 최대 10문제예요.</li><li>같은 세션의 한자성어는 다시 나오지 않아요.</li><li>처음 만나는 한자성어를 먼저 보여드려요.</li><li>오답이면 독음 힌트가 하나씩 열려요.</li></ul></section>
          <div className="session-actions">{confirmRestart ? <div className="restart-confirm"><p>지금 이음을 마치고 새로 시작할까요?</p><button onClick={restart}>새로 시작</button><button onClick={() => setConfirmRestart(false)}>계속 풀기</button></div> : <button className="text-button" onClick={() => setConfirmRestart(true)}>새 세션으로 시작하기 ↻</button>}</div>
        </aside>
      </div>
      </div>
      <div hidden={page !== 'book'} id="idioms">
        <IdiomBook idioms={idioms} favorites={favorites} completed={completed} mistakes={mistakes} legacyMistakeCount={legacyMistakes.ids.length} onFavorite={toggleFavorite} />
      </div>
      </section>
      <div hidden={page !== 'english'} id="english">{englishOpened && <Suspense fallback={<p role="status">영어 학습을 준비하고 있어요.</p>}><EnglishLearning /></Suspense>}</div>
      {warning && <p className="notice" role="alert">{warning}</p>}
      {sessionWarning && <p className="notice" role="alert">{sessionWarning}</p>}
      {offline && <p className="notice" role="status">오프라인이에요. 저장된 학습 자료로 계속할 수 있어요.</p>}
      {update && <div className="notice">새 버전이 준비됐어요. 적용하면 현재 세션이 종료됩니다. <button onClick={() => applyUpdate(update)}>지금 업데이트</button></div>}
      <footer><span>{page === 'home' ? '모두의 이음 · 한자와 영어 학습' : page === 'english' ? `모두의 이음 · 영어 학습 ${englishSource.rows}개` : `모두의 이음 · 한자 학습 ${idioms.length}개`}</span><span>이전 학습 이력은 이 브라우저에 저장돼요. 진행 중인 이음은 새로고침하면 초기화돼요.</span></footer>
      <nav className="bottom-nav" aria-label="학습 선택"><a href="#home" aria-current={page === 'home' ? 'page' : undefined}><span aria-hidden="true">⌂</span>홈</a><a href={hanjaPage === 'book' ? '#idioms' : '#main'} aria-current={page === 'quiz' || page === 'book' ? 'page' : undefined}><span aria-hidden="true">字</span>한자 학습</a><a href="#english" aria-current={page === 'english' ? 'page' : undefined}><span aria-hidden="true">Aa</span>영어 학습</a></nav>
    </main>
  );
}
