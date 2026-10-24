import { readSessions, SessionStars, STEP_COLORS } from './LearningMilestones';
import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { englishLetters, englishCandidates, matchesEnglish, englishLength, englishHint, SESSION_LIMIT, type EnglishWord } from '@idioms/shared';
import raw from '../../../data/english/words.json';

const words: EnglishWord[] = raw.map(item => {
  if (item.category !== 'english' || !item.id || !item.word || !item.meaning) throw new Error('영어 자료 형식 오류');
  return { ...item, category: 'english' };
});
const KEY = 'idioms:web:english:v1';
const SESSIONS_KEY = 'idioms:web:english:completed-sessions:v1';
type Records = { history: string[]; favorites: string[]; completed: string[]; mistakes: string[] };
const empty = (): Records => ({ history: [], favorites: [], completed: [], mistakes: [] });
function readRecords(): { records: Records; warning: string } {
  try {
    const value = JSON.parse(localStorage.getItem(KEY) ?? JSON.stringify(empty())) as Records;
    const valid = new Set(words.map(item => item.id));
    for (const key of ['history', 'favorites', 'completed', 'mistakes'] as const) {
      if (!Array.isArray(value[key]) || !value[key].every(id => typeof id === 'string')) throw new Error();
      value[key] = [...new Set(value[key])].filter(id => valid.has(id));
    }
    return { records: value, warning: '' };
  } catch { return { records: empty(), warning: '영어 학습 기록을 읽지 못했어요. 새 기록으로 계속할 수 있어요.' }; }
}
function pickStart(records: Records): EnglishWord {
  const unseen = words.filter(item => !records.history.includes(item.id));
  const pool = unseen.length ? unseen : words;
  return pool[Math.floor(Math.random() * pool.length)];
}

export default function EnglishLearning() {
  const [saved] = useState(readRecords);
  const [savedSessions] = useState(() => readSessions(SESSIONS_KEY));
  const [sessionCount, setSessionCount] = useState(savedSessions.count);
  const [sessionWarning, setSessionWarning] = useState(savedSessions.warning);
  const sessionAwarded = useRef(false);
  const [records, setRecords] = useState(saved.records);
  const [warning, setWarning] = useState(saved.warning);
  const [start, setStart] = useState(() => pickStart(saved.records));
  const [chain, setChain] = useState<{ item: EnglishWord; letter: string }[]>([]);
  const [letter, setLetter] = useState('');
  const [targetId, setTargetId] = useState('');
  const [answer, setAnswer] = useState('');
  const [meaningOpen, setMeaningOpen] = useState(false);
  const [translationOpen, setTranslationOpen] = useState(false);
  const [attempts, setAttempts] = useState<Record<string, number>>({});
  const [message, setMessage] = useState('이어갈 알파벳을 골라 주세요.');
  const [book, setBook] = useState(false);
  const [confirmRestart, setConfirmRestart] = useState(false);
  const [filter, setFilter] = useState<keyof Records | 'all'>('all');
  const [query, setQuery] = useState('');
  const [limit, setLimit] = useState(40);
  const [floating, setFloating] = useState<{ top: number; left: number; width: number; maxHeight?: number } | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const currentCard = useRef<HTMLDivElement>(null);
  const anchor = useRef<HTMLLIElement | null>(null);
  const opening = useRef(false);
  const openingFrame = useRef(0);
  const keyboardTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const current = chain.at(-1)?.item ?? start;
  const used = new Set([start.id, ...chain.map(link => link.item.id)]);
  const history = new Set(records.history);
  const candidates = englishCandidates(words, letter, used, history);
  const selected = candidates.find(item => item.id === targetId);
  const finished = chain.length >= SESSION_LIMIT || !englishLetters(current).some(ch => englishCandidates(words, ch, used, history).length);
  useEffect(() => { if (targetId && !book && floating) input.current?.focus({ preventScroll: true }); }, [targetId, book, Boolean(floating)]);
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
  useLayoutEffect(() => { if (floating) fitFloating(true); }, [Boolean(floating), targetId]);
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
  function selectCandidate(item: EnglishWord, element: HTMLInputElement) {
    opening.current = true;
    cancelAnimationFrame(openingFrame.current);
    openingFrame.current = requestAnimationFrame(() => {
      openingFrame.current = requestAnimationFrame(() => { opening.current = false; });
    });
    anchor.current = element.closest('li');
    const row = element.closest('li')!.getBoundingClientRect();
    const list = element.closest('ol')!.getBoundingClientRect();
    const width = Math.min(list.width, window.innerWidth - 24);
    setTargetId(item.id); setAnswer('');
    setMessage('선택한 후보의 영어 단어를 입력해 주세요.');
    setFloating({ top: Math.max(12, Math.min(row.bottom + 6, window.innerHeight - 220)), left: Math.max(12, Math.min(list.left, window.innerWidth - width - 12)), width });
  }

  function save(next: Records) {
    setRecords(next);
    try { localStorage.setItem(KEY, JSON.stringify(next)); setWarning(''); }
    catch { setWarning('영어 학습 기록을 저장하지 못했어요. 다음 접속에서는 남지 않을 수 있어요.'); }
  }
  function choose(ch: string) { setFloating(null); setLetter(ch); setTargetId(''); setAnswer(''); setAttempts({}); setLimit(40); setMessage('글자 수·동의어·뜻을 보고 풀 후보를 선택하세요.'); }
  function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!selected || finished) return;
    if (!answer.trim()) { setMessage('영어 단어를 먼저 입력해 주세요.'); return; }
    if (matchesEnglish(selected, answer, letter)) {
      setFloating(null);
      setMeaningOpen(false);
      setTranslationOpen(false);
      save({ ...records, history: [...new Set([...records.history, start.id, selected.id])], completed: [...new Set([...records.completed, selected.id])] });
      if (chain.length + 1 === SESSION_LIMIT && !sessionAwarded.current) {
        sessionAwarded.current = true;
        const nextCount = Math.min(Number.MAX_SAFE_INTEGER, sessionCount + 1);
        setSessionCount(nextCount);
        try { localStorage.setItem(SESSIONS_KEY, JSON.stringify(nextCount)); setSessionWarning(''); }
        catch { setSessionWarning('완주 횟수를 저장하지 못했어요. 현재 별은 다음 접속에 남지 않을 수 있어요.'); }
      }
      setChain([...chain, { item: selected, letter }]); setLetter(''); setTargetId(''); setAnswer(''); setAttempts({}); setLimit(40);
      setMessage(`${selected.word}, 정답이에요! 다음 알파벳을 골라 주세요.`);
    } else {
      save({ ...records, mistakes: [...new Set([...records.mistakes, selected.id])] });
      setAttempts(value => ({ ...value, [selected.id]: (value[selected.id] ?? 0) + 1 }));
      setMessage('선택한 후보의 철자와 달라요. 추가 힌트를 확인해 주세요.');
    }
  }
  function restart() {
    closeFloating();
    setConfirmRestart(false);
    if (chain.length && !finished && !window.confirm('진행 중인 이음을 마치고 새로 시작할까요?')) return;
    sessionAwarded.current = false;
    setMeaningOpen(false);
    setTranslationOpen(false);
    setStart(pickStart(records)); setChain([]); choose(''); setMessage('새로운 이음을 시작해 보세요.');
  }
  const listed = words.filter(item => (filter === 'all' || records[filter].includes(item.id)) && `${item.word} ${item.meaning} ${item.partOfSpeech}`.toLowerCase().includes(query.trim().toLowerCase()));
  return <section className="english-learning learning-shell panel" aria-label="영어 단어 이음 학습">
    <div className="book-heading english-rank-heading"><h1>영어 글자잇기</h1><SessionStars count={sessionCount} /></div>
    <p className="english-word-total">{words.length}개 단어 · 10문제를 모두 이으면 작은 별 하나</p>
    <div className="learning-tabs"><button aria-pressed={!book} onClick={() => { closeFloating(); setBook(false); setLimit(40); }}>퀴즈 풀기</button><button aria-pressed={book} onClick={() => { closeFloating(); setBook(true); setLimit(40); }}>나의 단어장</button></div>
    <div hidden={book}>
      <p className="book-description">알파벳 선택 → 후보 선택 → 영어 단어 입력</p>
      <p className="learning-count">{chain.length} / {SESSION_LIMIT} 문제</p>
      <progress value={chain.length} max={SESSION_LIMIT} aria-label="영어 정답 수" />
      {chain.length > 0 && <section className="english-journey" aria-label="이어 온 영어 단어">
        <div className="english-journey-heading"><h3>지금까지 이어 온 단어</h3><span>이번 이음 {chain.length} / {SESSION_LIMIT}</span></div>
        <ol className="english-chain">{[start, ...chain.map(link => link.item)].map((item, index) => {
          const row = Math.floor(index / 2);
          const column = row % 2 === 0 ? index % 2 + 1 : 2 - index % 2;
          const vertical = index > 0 && index % 2 === 0;
          return <li key={item.id} data-step={index} className={index === SESSION_LIMIT ? 'chain-complete' : undefined} style={{ gridRow: row + 1, gridColumn: column, borderColor: index > 0 ? STEP_COLORS[index - 1] : undefined }}>
            {index > 0 && <span className={`english-chain-bridge ${vertical ? 'bridge-down' : column === 2 ? 'bridge-right' : 'bridge-left'}`} aria-label={`${chain[index - 1].letter}로 이어짐`}><span>{chain[index - 1].letter}</span><span aria-hidden="true">{vertical ? '↓' : column === 2 ? '→' : '←'}</span></span>}
            <span className={`chain-word-step${index > 0 ? ' chain-step-badge' : ''}`} style={index > 0 ? { backgroundColor: STEP_COLORS[index - 1], color: index <= 2 || index === SESSION_LIMIT ? '#243a36' : '#fff' } : undefined}>{index === 0 ? '시작' : `${index} / ${SESSION_LIMIT}`}</span>
            {index === SESSION_LIMIT && <span className="chain-complete-label">10개 이음 완성</span>}
            <strong lang="en">{item.word}</strong><p>{item.meaning}</p>
          </li>;
        })}</ol>
      </section>}
      <div className="idiom-card" ref={currentCard}><span className="card-caption">{chain.length ? '방금 맞힌 단어' : '이음의 시작'}</span><h2>{current.word}</h2><div className="card-reading"><strong>{current.partOfSpeech}</strong><button type="button" className="meaning-toggle" aria-expanded={meaningOpen} aria-controls="english-meaning" onClick={() => setMeaningOpen(value => !value)}>{meaningOpen ? '뜻 접기' : '뜻 보기'} <span aria-hidden="true">ⓘ</span></button></div><p id="english-meaning" hidden={!meaningOpen}>{current.meaning}</p>
        {current.synonym.trim() && <div className="word-example word-synonyms" aria-label="동의어"><span>동의어</span><p>{current.synonym}</p></div>}
        {(current.example || current.exampleMeaning) && <div className="word-example" aria-label="예문"><div className="example-heading"><span>예문</span>{current.exampleMeaning && <button type="button" className="meaning-toggle" aria-expanded={translationOpen} aria-controls="english-example-translation" onClick={() => setTranslationOpen(value => !value)}>{translationOpen ? '해석 접기' : '해석 보기'} <span aria-hidden="true">ⓘ</span></button>}</div>{current.example && <p lang="en">{current.example}</p>}{current.exampleMeaning && <p id="english-example-translation" hidden={!translationOpen}>{current.exampleMeaning}</p>}</div>}
      </div>
      {finished ? <div className="summary"><span className="eyebrow">나만의 배움 한 줄</span><h2>{chain.length === SESSION_LIMIT ? '10개 단어를 이었어요!' : '이번 이음은 여기까지예요.'}</h2><p>{chain.length === SESSION_LIMIT ? '오늘 알게 된 단어들이 다음 배움의 시작이 될 거예요.' : '같은 단어를 반복하지 않고 이어갈 후보가 더 없어요.'}</p><button className="primary" onClick={restart}>새 이음 시작하기 <span aria-hidden="true">↗</span></button></div> : <>
        <div className="instruction"><h3>01 <span>이어갈 알파벳을 골라 주세요</span></h3><span>후보가 없는 글자는 쉬어 가요</span></div>
        <div className="characters">{englishLetters(current).map((ch, index) => {
          const count = englishCandidates(words, ch, used, history).length;
          return <button key={`${index}-${ch}`} aria-label={count ? ch : `${ch}, 후보 없음`} aria-pressed={letter === ch} disabled={!count} onClick={() => choose(ch)}><strong>{ch}</strong></button>;
        })}</div>
        <section className="hints" aria-label="영어 정답 후보 힌트">
        <div className="hint-heading"><h3>02 <span>풀고 싶은 영어 단어를 선택해 주세요</span></h3>{letter && <span className="pill">{candidates.length}개 후보</span>}</div>
        {!letter && <p className="empty">위에서 알파벳을 고르면<br />그 글자가 들어간 영어 단어의 힌트가 나타나요.</p>}
        {letter && <p className="hint-description">‘<b>{letter}</b>’가 들어가는 후보를 선택한 뒤, 그 후보의 영어 단어를 입력하세요.</p>}
        <ol className="candidate-list english-candidates" onWheel={closeFloating} onTouchMove={closeFloating} onScroll={() => { if (!opening.current) closeFloating(); }}>{candidates.slice(0, limit).map((item, index) => <li key={item.id} className={targetId === item.id ? 'selected-candidate' : ''} onClick={event => { if ((event.target as HTMLElement).tagName === 'LABEL') return; selectCandidate(item, event.currentTarget.querySelector('input')!); }}>
          <label className="candidate-choice english-candidate-choice"><input type="radio" name="english-candidate" value={item.id} aria-label={`후보 ${index + 1} 선택`} checked={targetId === item.id} onChange={() => {}} /><span className="candidate-number">{String(index + 1).padStart(2, '0')}</span><span className="candidate-length">{englishLength(item)}글자</span>{item.synonym.trim() && <span className="candidate-synonym"><span>동의어: </span><span className="candidate-synonym-value">{item.synonym}</span></span>}</label>
          <p>{item.meaning}</p>{targetId === item.id && !!attempts[item.id] && <span className="reading-hint">철자 힌트 · {englishHint(item, letter, attempts[item.id])}</span>}
        </li>)}</ol>
        {candidates.length > limit && <button className="book-more" onClick={() => setLimit(value => value + 40)}>후보 40개 더 보기</button>}
        </section>
        <form onSubmit={submit} className={`answer-form${floating ? ' floating-answer' : ''}`} style={floating ? { top: floating.top, left: floating.left, width: floating.width, maxHeight: floating.maxHeight } : undefined} onKeyDown={event => { if (event.key === 'Escape') closeFloating(); }}><div className="floating-answer-heading"><label htmlFor="english-answer">03 {selected ? `후보 ${candidates.indexOf(selected) + 1}의 영어 단어` : '후보를 먼저 선택해 주세요'}</label>{floating && <button type="button" className="floating-close" onClick={closeFloating} aria-label="입력창 닫기">×</button>}</div><div className="input-row"><input ref={input} id="english-answer" value={answer} onChange={event => setAnswer(event.target.value)} disabled={!selected} autoComplete="off" autoCapitalize="none" spellCheck={false} aria-describedby={floating ? 'english-floating-feedback' : 'english-feedback'} placeholder="영어 단어 입력" /><button className="primary" disabled={!selected}>확인</button></div>{floating && <p id="english-floating-feedback" role="status">{selected && attempts[selected.id] ? `철자 힌트 · ${englishHint(selected, letter, attempts[selected.id])}` : '후보 목록을 스크롤하면 입력창이 닫혀요.'}</p>}</form>
      </>}
      <p id="english-feedback" className="feedback" role="status">{finished ? `${chain.length}개의 영어 단어를 정답으로 이었어요.` : message}</p>
      <aside className="sidebar">
        <section className="guide"><span className="eyebrow">이렇게 이어가요</span><p>선택한 알파벳이 들어간 후보를 고르고<br />전체 영어 단어를 입력하면 정답!</p><ul><li>대소문자는 구분하지 않아요.</li><li>한 이음은 최대 {SESSION_LIMIT}문제예요.</li><li>같은 이음의 단어는 다시 나오지 않아요.</li><li>처음 만나는 단어를 먼저 보여드려요.</li><li>오답이면 철자 힌트가 하나씩 열려요.</li></ul></section>
        <div className="session-actions">{confirmRestart ? <div className="restart-confirm"><p>지금 이음을 마치고 새로 시작할까요?</p><button onClick={restart}>새로 시작</button><button onClick={() => setConfirmRestart(false)}>계속 풀기</button></div> : <button className="text-button" onClick={() => { closeFloating(); setConfirmRestart(true); }}>새 이음 시작하기 ↻</button>}</div>
      </aside>
    </div>
    <section className="english-book" hidden={!book} aria-labelledby="english-book-title">
      <div className="book-heading"><div><span className="eyebrow">한 글자씩 쌓이는 배움</span><h1 id="english-book-title">나의 영어 단어장</h1></div><span>전체 {words.length}개</span></div>
      <p className="book-description">영어 단어와 뜻을 살펴보고, 다시 보고 싶은 단어를 모아 보세요.</p>
      <div className="book-tabs" role="group" aria-label="영어 단어장 분류">{([['all', '전체'], ['favorites', '즐겨찾기'], ['completed', '학습완료'], ['mistakes', '오답노트']] as const).map(([value, label]) => <button key={value} aria-pressed={filter === value} onClick={() => { setFilter(value); setLimit(40); }}>{label}</button>)}</div>
      <label className="book-search" htmlFor="english-search">영어 단어 검색</label><input className="book-search-input" id="english-search" type="search" placeholder="영어 단어 또는 뜻 검색" value={query} onChange={event => { setQuery(event.target.value); setLimit(40); }} />
      {filter === 'completed' && <p className="book-note">퀴즈에서 직접 정답을 맞힌 영어 단어예요.</p>}
      {filter === 'mistakes' && <p className="book-note">선택한 후보의 철자를 틀렸던 영어 단어예요. 정답을 맞힌 뒤에도 복습할 수 있도록 남겨 두어요.</p>}
      <p className="book-result">{listed.length}개 단어</p><ul className="book-list">{listed.slice(0, limit).map(item => <li key={item.id}><div className="book-item-heading"><h2>{item.word}</h2><button className="favorite-button" aria-label={`${item.word} 즐겨찾기`} aria-pressed={records.favorites.includes(item.id)} onClick={() => save({ ...records, favorites: records.favorites.includes(item.id) ? records.favorites.filter(id => id !== item.id) : [...records.favorites, item.id] })}>{records.favorites.includes(item.id) ? '★' : '☆'}</button></div><strong className="book-reading">{item.partOfSpeech}</strong><p>{item.meaning}</p>{item.synonym.trim() && <p className="book-synonyms">동의어 · {item.synonym}</p>}<p className="book-note">{item.example}<br />{item.exampleMeaning}</p>{records.completed.includes(item.id) && <span className="book-badge">학습완료</span>}{records.mistakes.includes(item.id) && <span className="book-badge">오답 복습</span>}</li>)}</ul>
      {!listed.length && <p className="book-empty">{query ? '검색 결과가 없어요. 다른 단어나 뜻으로 찾아보세요.' : filter === 'favorites' ? '별표를 눌러 다시 보고 싶은 영어 단어를 담아 보세요.' : filter === 'completed' ? '퀴즈에서 정답을 맞히면 여기에 쌓여요.' : '아직 기록된 오답이 없어요.'}</p>}{listed.length > limit && <button className="book-more" onClick={() => setLimit(value => value + 40)}>40개 더 보기 ({Math.min(limit, listed.length)} / {listed.length})</button>}
    </section>
    {warning && <p className="notice" role="alert">{warning}</p>}
    {sessionWarning && <p className="notice" role="alert">{sessionWarning}</p>}
  </section>;
}
