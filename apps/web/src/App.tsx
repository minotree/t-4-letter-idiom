import { lazy, Suspense, useEffect, useRef, useState } from 'react';
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
  const [saved] = useState(() => readHistory());
  const [savedFavorites] = useState(() => readHistory('idioms:web:favorites:v1'));
  const [savedCompleted] = useState(() => readHistory('idioms:web:completed:v1'));
  const [savedMistakes] = useState(() => readHistory('idioms:web:mistakes:v2'));
  const [legacyMistakes] = useState(() => readHistory('idioms:web:mistakes:v1'));
  const [favorites, setFavorites] = useState(() => new Set(savedFavorites.ids));
  const [completed, setCompleted] = useState(() => new Set(savedCompleted.ids));
  const [mistakes, setMistakes] = useState(() => new Set(savedMistakes.ids));
  const [page, setPage] = useState(() => location.hash === '#english' ? 'english' : location.hash === '#idioms' ? 'book' : 'quiz');
  const [englishOpened, setEnglishOpened] = useState(() => location.hash === '#english');
  const [hanjaPage, setHanjaPage] = useState(() => location.hash === '#idioms' ? 'book' : 'quiz');
  const [history, setHistory] = useState(() => new Set(saved.ids));
  const [warning, setWarning] = useState([saved.warning, savedFavorites.warning, savedCompleted.warning, savedMistakes.warning].filter(Boolean).join(' '));
  const [start, setStart] = useState(() => pickStart(new Set(saved.ids)));
  const [chain, setChain] = useState<Idiom[]>([]);
  const [connections, setConnections] = useState<string[]>([]);
  const [character, setCharacter] = useState('');
  const [answer, setAnswer] = useState('');
  const [attempts, setAttempts] = useState<Record<string, number>>({});
  const [message, setMessage] = useState('마음에 드는 한 글자를 골라 시작해 보세요.');
  const [selectedId, setSelectedId] = useState('');
  const [confirmRestart, setConfirmRestart] = useState(false);
  const [update, setUpdate] = useState<ServiceWorker | null>(null);
  const [offline, setOffline] = useState(!navigator.onLine);
  const input = useRef<HTMLInputElement>(null);
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
      setPage(location.hash === '#english' ? 'english' : location.hash === '#idioms' ? 'book' : 'quiz');
      if (location.hash === '#english') setEnglishOpened(true);
      else setHanjaPage(location.hash === '#idioms' ? 'book' : 'quiz');
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
    if (selectedId) input.current?.focus();
    else if (chain.length) title.current?.focus();
  }, [selectedId, chain.length]);

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
    locked.current = false;
    setCharacter(ch); setAnswer(''); setAttempts({}); setSelectedId('');
    setMessage(`‘${ch}’가 들어가는 후보 중 풀고 싶은 한자성어를 선택해 주세요.`);
  }

  function accept(item: Idiom) {
    if (locked.current || finished || selected?.id !== item.id) return;
    locked.current = true;
    remember([start.id, item.id]);
    const learned = new Set([...completed, item.id]);
    setCompleted(learned); saveCollection('completed', learned);
    setConnections([...connections, character]);
    setChain([...chain, item]); setCharacter(''); setAnswer(''); setAttempts({}); setSelectedId('');
    setMessage(`${item.reading}, 정답이에요! 다음 연결 글자를 골라 주세요.`);
    title.current?.focus();
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
    locked.current = false;
    setStart(pickStart(history)); setChain([]); setCharacter(''); setAnswer('');
    setConnections([]);
    setAttempts({}); setSelectedId(''); setConfirmRestart(false);
    setMessage('새로운 연결을 시작해 볼까요? 한 글자를 골라 주세요.');
    title.current?.focus();
  }

  return (
    <main className="app">
      <header className="page-header">
        <a className="brand" href="#main">글자잇기 <span>{page === 'english' ? '영어 학습' : '한자 학습'}</span></a>
        <span className="edition">하루 한 번, 즐거운 배움</span>
      </header>
      <section className="intro learning-intro" aria-label="학습 소개">
        <span className="eyebrow">{page === 'english' ? '한 알파벳에서 시작하는 발견' : '한 글자에서 시작하는 발견'}</span>
        <h1>{page === 'english' ? '아는 단어가 이어지면,' : '아는 말이 이어지면,'}<br />배움이 되는 순간.</h1>
        <p>{page === 'english' ? '알파벳을 고르고, 뜻을 읽고, 아는 영어 단어를 적어 보세요.' : '글자를 고르고, 뜻을 읽고, 아는 한자성어를 적어 보세요.'}<br />정답이 다음 배움의 시작이 됩니다.</p>
      </section>
      <section className="learning-shell panel" hidden={page === 'english'} aria-label="한자 학습">
      <div className="book-heading"><h1>한자 글자잇기</h1><span>{idioms.length}개 한자어</span></div>
      <nav className="learning-tabs" aria-label="한자 학습 메뉴">
        <a href="#main" aria-current={page === 'quiz' ? 'page' : undefined}>퀴즈 풀기</a>
        <a href="#idioms" aria-current={page === 'book' ? 'page' : undefined}>나의 단어장</a>
      </nav>
      <div hidden={page !== 'quiz'}>
      <p className="book-description">한글 글자 선택 → 후보 선택 → 한글 독음 입력</p>
      <div className="workspace">
        <section className="game" id="main" aria-label="한자성어 연결 퀴즈">
          <p className="learning-count">{chain.length} / {SESSION_LIMIT} 문제</p>
          <progress value={chain.length} max={SESSION_LIMIT} aria-label="맞힌 문제 수" />
          {chain.length > 0 && <section className="completed-chain" aria-label="이어 온 문제 사슬">
            <h3>지금까지 이어 온 한자성어</h3>
            <ol className="chain-links">{chain.map((item, index) => {
              const previous = index === 0 ? start : chain[index - 1];
              return <li key={item.id}>
                <span className="link-step">{index + 1}번째 연결</span>
                <div className="link-pair">
                  <div className="link-idiom"><strong lang="zh">{previous.hanja}</strong><span>{previous.reading}</span><p>{previous.meaning}</p><ContentSource item={previous} /></div>
                  <div className="link-bridge"><span>{connections[index]}</span><span aria-hidden="true">→</span><small>연결 글자</small></div>
                  <div className="link-idiom"><strong lang="zh">{item.hanja}</strong><span>{item.reading}</span><p>{item.meaning}</p><ContentSource item={item} /></div>
                </div>
              </li>;
            })}</ol>
          </section>}
          <div className="idiom-card">
            <span className="card-caption">{chain.length ? '방금 맞힌 한자성어' : '연결의 시작'}</span>
            <h2 ref={title} tabIndex={-1} lang="zh">{current.hanja}</h2>
            <strong>{current.reading}</strong><p>{current.meaning}</p>
            <ContentSource item={current} />
          </div>
          {finished ? <div className="summary">
            <span className="eyebrow">나만의 배움 한 줄</span>
            <h2>{chain.length >= SESSION_LIMIT ? '20개의 한자성어를 이었어요!' : '이번 연결은 여기까지예요.'}</h2>
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
                <ol className="candidate-list">{candidates.map((item, index) => <li key={item.id} className={selectedId === item.id ? 'selected-candidate' : ''}>
                  <label className="candidate-choice"><input type="radio" name="candidate" value={item.id} checked={selectedId === item.id} onChange={() => { setSelectedId(item.id); setAnswer(''); setMessage('선택한 후보의 한글 독음을 입력해 주세요.'); }} /><span>후보 {index + 1} 선택</span></label>
                  <div><span className="candidate-number">{String(index + 1).padStart(2, '0')}</span><strong lang="zh">{item.hanja}</strong></div>
                  <p>{item.meaning}</p>{selectedId === item.id && (attempts[item.id] ?? 0) > 0 && <span className="reading-hint">독음 힌트 · {readingHint(item.reading, attempts[item.id])}</span>}
                  <ContentSource item={item} />
                </li>)}</ol>
              </>}
            </section>
            <form onSubmit={submit} className="answer-form">
              <label htmlFor="answer">03 <span>{selected ? `선택한 후보: ${selected.hanja} · 한글 독음 입력` : '후보를 먼저 선택해 주세요'}</span></label>
              <div className="input-row"><input id="answer" ref={input} value={answer} onChange={event => setAnswer(event.target.value)}
                disabled={!selected} autoComplete="off" spellCheck={false} placeholder="선택한 후보의 한글 독음" aria-describedby="feedback"
                onKeyDown={event => { if (event.key === 'Enter' && event.nativeEvent.isComposing) event.preventDefault(); }} />
                <button type="submit" className="primary" disabled={!selected}>확인 <span aria-hidden="true">↗</span></button></div>
            </form>
          </>}
          <p id="feedback" className="feedback" role="status">{finished ? `${chain.length}개의 한자성어를 정답으로 연결했어요.` : message}</p>
        </section>
        <aside className="sidebar">
          <section className="guide"><span className="eyebrow">이렇게 이어가요</span><p>선택한 한글 글자가 독음에 들어간 후보를 고르고<br />전체 독음을 입력하면 정답!</p><ul><li>한자는 달라도 같은 한글이면 이어져요.</li><li>한 세션은 최대 20문제예요.</li><li>같은 세션의 한자성어는 다시 나오지 않아요.</li><li>처음 만나는 한자성어를 먼저 보여드려요.</li><li>오답이면 독음 힌트가 하나씩 열려요.</li></ul></section>
          <div className="session-actions">{confirmRestart ? <div className="restart-confirm"><p>지금 연결을 마치고 새로 시작할까요?</p><button onClick={restart}>새로 시작</button><button onClick={() => setConfirmRestart(false)}>계속 풀기</button></div> : <button className="text-button" onClick={() => setConfirmRestart(true)}>새 세션으로 시작하기 ↻</button>}</div>
        </aside>
      </div>
      </div>
      <div hidden={page !== 'book'} id="idioms">
        <IdiomBook idioms={idioms} favorites={favorites} completed={completed} mistakes={mistakes} legacyMistakeCount={legacyMistakes.ids.length} onFavorite={toggleFavorite} />
      </div>
      </section>
      <div hidden={page !== 'english'} id="english">{englishOpened && <Suspense fallback={<p role="status">영어 학습을 준비하고 있어요.</p>}><EnglishLearning /></Suspense>}</div>
      {warning && <p className="notice" role="alert">{warning}</p>}
      {offline && <p className="notice" role="status">오프라인이에요. 저장된 학습 자료로 계속할 수 있어요.</p>}
      {update && <div className="notice">새 버전이 준비됐어요. 적용하면 현재 세션이 종료됩니다. <button onClick={() => applyUpdate(update)}>지금 업데이트</button></div>}
      <footer><span>{page === 'english' ? `글자잇기 · 영어 학습 ${englishSource.rows}개` : `글자잇기 · 한자 학습 ${idioms.length}개`}</span><span>이전 학습 이력은 이 브라우저에 저장돼요. 진행 중인 연결은 새로고침하면 초기화돼요.</span></footer>
      <nav className="bottom-nav" aria-label="학습 선택"><a href={hanjaPage === 'book' ? '#idioms' : '#main'} aria-current={page !== 'english' ? 'page' : undefined}><span aria-hidden="true">字</span>한자 학습</a><a href="#english" aria-current={page === 'english' ? 'page' : undefined}><span aria-hidden="true">Aa</span>영어 학습</a></nav>
    </main>
  );
}
