import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { Button as TDSButton, type ButtonProps } from '@toss/tds-mobile';
import { candidatesFor, matchingAnswers, readingHint, normalizeReadingForSearch, englishCandidates, englishLetters, englishLength, englishHint, matchesEnglish, SESSION_LIMIT, type Idiom, type EnglishWord } from '@idioms/shared';
import idiomData from './data/idioms.json';
import englishData from '../../../data/english/words.json';
import { useExampleSpeech } from './useExampleSpeech';
import { BottomBanner } from './BottomBanner';
import { CompletionCelebration } from './CompletionCelebration';

type Mode = 'hanja' | 'english';
function Button({ size = 'medium', variant = 'weak', ...props }: ButtonProps) {
  return <TDSButton size={size} variant={variant} {...props} />;
}
type Entry = Idiom | EnglishWord;
const idioms = idiomData as Idiom[];
const words = englishData as EnglishWord[];
const entries = (mode: Mode): Entry[] => mode === 'hanja' ? idioms : words;
const label = (item: Entry) => 'hanja' in item ? item.hanja : item.word;
const letters = (item: Entry) => 'hanja' in item ? [...item.reading] : englishLetters(item);
function candidates(mode: Mode, letter: string, used: Set<string>, history: Set<string>): Entry[] {
  return mode === 'hanja' ? candidatesFor(idioms, letter, used, history) : englishCandidates(words, letter, used, history);
}
interface Saved { history: string[]; completed: string[]; mistakes: string[]; favorites: string[]; sessions: number }
function readSaved(mode: Mode): { value: Saved; warning: string } {
  const empty: Saved = { history: [], completed: [], mistakes: [], favorites: [], sessions: 0 };
  try {
    const raw = localStorage.getItem(`idioms:toss:${mode}:v1`);
    if (!raw) return { value: empty, warning: '' };
    const value = JSON.parse(raw) as Saved;
    const valid = new Set(entries(mode).map(item => item.id));
    if (!value || !Number.isSafeInteger(value.sessions) || value.sessions < 0) throw new Error();
    for (const field of ['history', 'completed', 'mistakes', 'favorites'] as const) {
      if (!Array.isArray(value[field]) || !value[field].every(id => typeof id === 'string')) throw new Error();
      value[field] = [...new Set(value[field])].filter(id => valid.has(id));
    }
    return { value, warning: '' };
  } catch { return { value: empty, warning: '저장된 기록을 읽지 못했어요. 이번 학습은 계속할 수 있어요.' }; }
}
function chooseStart(mode: Mode, history: Set<string>) {
  const available = entries(mode).filter(item => letters(item).some(letter => candidates(mode, letter, new Set([item.id]), history).length));
  const unseen = available.filter(item => !history.has(item.id));
  const pool = unseen.length ? unseen : available;
  return pool[Math.floor(Math.random() * pool.length)];
}

const stepColors = ['#b8d9b0', '#8fc78c', '#367e52', '#21867f', '#2476aa', '#514782', '#7c3b8e', '#ba5134', '#ba641e', '#d6ab39'];
function Source({ item }: { item: Entry }) {
  return item.category === 'cheonjamun' ? <small className="content-source">출처: 천자문</small> : null;
}
function SessionStars({ count }: { count: number }) {
  return <div className="session-rank" aria-label={`10문제 완주 ${count}회`}>
    {count ? <div className="session-stars">{[{ size: 'large', count: Math.floor(count / 100), label: '큰 별' }, { size: 'medium', count: Math.floor(count / 10) % 10, label: '중간 별' }, { size: 'small', count: count % 10, label: '작은 별' }].filter(group => group.count).map(group => <span key={group.size} className={`star-${group.size}`} aria-label={`${group.label} ${group.count}개`}>{group.count > 9 ? `★ ×${group.count}` : '★'.repeat(group.count)}</span>)}</div> : <span>첫 별을 모아 보세요</span>}
    <span>10문제 완주 {count}회</span>
  </div>;
}
function Learning({ mode, active }: { mode: Mode; active: boolean }) {
  const [initial] = useState(() => readSaved(mode));
  const [saved, setSaved] = useState(initial.value);
  const [warning, setWarning] = useState(initial.warning);
  const [start, setStart] = useState(() => chooseStart(mode, new Set(initial.value.history)));
  const [chain, setChain] = useState<Entry[]>([]);
  const [connections, setConnections] = useState<string[]>([]);
  const [letter, setLetter] = useState('');
  const [selectedId, setSelectedId] = useState('');
  const [answer, setAnswer] = useState('');
  const [attempts, setAttempts] = useState<Record<string, number>>({});
  const [message, setMessage] = useState('이어갈 글자를 골라 주세요.');
  const [meaning, setMeaning] = useState(false);
  const [translation, setTranslation] = useState(false);
  const [page, setPage] = useState<'quiz' | 'book'>('quiz');
  const [filter, setFilter] = useState<'all' | 'favorites' | 'completed' | 'mistakes'>('all');
  const [search, setSearch] = useState('');
  const [limit, setLimit] = useState(40);
  const [candidateLimit, setCandidateLimit] = useState(40);
  const speech = useExampleSpeech();
  useEffect(() => { speech.stop(); }, [active, page, filter, search, speech.stop]);
  useEffect(() => { setCandidateLimit(40); }, [letter, start.id, chain.length]);
  const [restart, setRestart] = useState(false);
  const [celebrating, setCelebrating] = useState(false);
  useEffect(() => {
    if (!celebrating) return;
    const timer = setTimeout(() => setCelebrating(false), 4500);
    return () => clearTimeout(timer);
  }, [celebrating]);
  useEffect(() => { if (!active || page !== 'quiz') setCelebrating(false); }, [active, page]);
  const input = useRef<HTMLInputElement>(null);
  const currentCard = useRef<HTMLElement>(null);
  const formRef = useRef<HTMLFormElement>(null);

  const focusFrame = useRef(0);


  const keyboardTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [floating, setFloating] = useState<{ top: number; left: number; width: number; maxHeight: number } | null>(null);
  const lock = useRef(false);
  const history = new Set(saved.history);
  const current = chain.at(-1) ?? start;
  const used = new Set([start.id, ...chain.map(item => item.id)]);
  const options = candidates(mode, letter, used, history);
  const selected = options.find(item => item.id === selectedId);
  const finished = chain.length >= SESSION_LIMIT || !letters(current).some(ch => candidates(mode, ch, used, history).length);
  const name = mode === 'hanja' ? '한자성어' : '영어 단어';
  const hint = selected && attempts[selected.id] ? ('hanja' in selected ? readingHint(selected.reading, attempts[selected.id]) : englishHint(selected, letter, attempts[selected.id])) : '';
  useEffect(() => {
    if (!active || page !== 'quiz') { closeFloating(); cancelAnimationFrame(focusFrame.current); }
  }, [active, page]);
  useEffect(() => () => cancelAnimationFrame(focusFrame.current), []);
  function fitFloating() {
    const form = formRef.current;
    if (!form?.classList.contains('floating-answer')) return;
    const viewport = window.visualViewport;
    const topEdge = (viewport?.offsetTop ?? 0) + 12;
    // Keep clear of the iOS keyboard accessory bar.
    const bottomEdge = (viewport ? viewport.offsetTop + viewport.height : innerHeight) - 56;
    const maxHeight = Math.max(1, bottomEdge - topEdge);
    const width = Math.max(1, Math.min(520, (viewport?.width ?? innerWidth) - 24));
    const left = (viewport?.offsetLeft ?? 0) + ((viewport?.width ?? innerWidth) - width) / 2;
    const top = Math.max(topEdge, bottomEdge - Math.min(form.scrollHeight + 2, maxHeight));
    setFloating(value => value && (Math.abs(value.top - top) >= 1 || value.maxHeight !== maxHeight || value.left !== left || value.width !== width) ? { top, maxHeight, left, width } : value);
  }
  useLayoutEffect(() => { if (floating) fitFloating(); }, [Boolean(floating), selectedId, attempts]);
  useEffect(() => {
    const fit = () => {
      if (keyboardTimer.current) clearTimeout(keyboardTimer.current);
      keyboardTimer.current = setTimeout(() => { keyboardTimer.current = null; fitFloating(); }, 16);
    };
    window.addEventListener('hashchange', closeFloating);
    window.addEventListener('resize', fit);
    window.visualViewport?.addEventListener('resize', fit);
    window.visualViewport?.addEventListener('scroll', fit);
    return () => {
      if (keyboardTimer.current) clearTimeout(keyboardTimer.current);
      window.removeEventListener('hashchange', closeFloating);
      window.removeEventListener('resize', fit);
      window.visualViewport?.removeEventListener('resize', fit);
      window.visualViewport?.removeEventListener('scroll', fit);
    };
  }, []);
  function closeFloating() { if (keyboardTimer.current) clearTimeout(keyboardTimer.current); setFloating(null); if (document.activeElement === input.current) input.current?.blur(); }
  function selectCandidate(item: Entry) {
    lock.current = false; setSelectedId(item.id); setAnswer('');
    setMessage(`선택한 후보의 ${mode === 'hanja' ? '한글 독음을' : '영어 단어를'} 입력해 주세요.`);
    setFloating({ top: 12, left: 12, width: Math.min(520, innerWidth - 24), maxHeight: innerHeight - 24 });
    cancelAnimationFrame(focusFrame.current);
    focusFrame.current = requestAnimationFrame(() => input.current?.focus({ preventScroll: true }));
  }
  function persist(next: Saved) {
    setSaved(next);
    try { localStorage.setItem(`idioms:toss:${mode}:v1`, JSON.stringify(next)); }
    catch { setWarning('기록을 저장하지 못했어요. 앱을 닫으면 이번 기록이 사라질 수 있어요.'); }
  }
  function submit() {
    if (!selected || !answer.trim() || finished || lock.current) return;
    const correct = 'hanja' in selected ? matchingAnswers([selected], answer).length > 0 : matchesEnglish(selected, answer, letter);
    if (!correct) {
      setAttempts(prev => ({ ...prev, [selected.id]: (prev[selected.id] ?? 0) + 1 }));
      persist({ ...saved, mistakes: [...new Set([...saved.mistakes, selected.id])] });
      setMessage('다시 생각해 보세요. 선택한 낱말의 힌트를 확인해 주세요.');
      return;
    }
    lock.current = true;
    const next = [...chain, selected];
    if (next.length === SESSION_LIMIT) setCelebrating(true);
    persist({ ...saved, history: [...new Set([...saved.history, start.id, selected.id])], completed: [...new Set([...saved.completed, selected.id])], sessions: saved.sessions + (next.length === SESSION_LIMIT ? 1 : 0) });
    setChain(next); setConnections(prev => [...prev, letter]); setLetter(''); setSelectedId(''); setAnswer(''); setAttempts({}); setMeaning(false); setTranslation(false); setFloating(null);
    input.current?.blur();
    requestAnimationFrame(() => currentCard.current?.scrollIntoView({ block: 'start' }));
    setMessage('정답이에요! 다음 글자를 골라 주세요.');
  }
  function reset() {
    setCelebrating(false);
    setStart(chooseStart(mode, history)); setChain([]); setConnections([]); setLetter(''); setSelectedId(''); setAnswer(''); setAttempts({}); setMeaning(false); setTranslation(false); setFloating(null); setRestart(false); lock.current = false;
    setMessage('이어갈 글자를 골라 주세요.');
  }
  const normalizeSearch = (value: string) => mode === 'hanja' ? normalizeReadingForSearch(value) : value.normalize('NFKC').replace(/\s/g, '').toLowerCase();
  const query = normalizeSearch(search);
  const book = entries(mode).filter(item => (filter === 'all' || saved[filter].includes(item.id)) && normalizeSearch('hanja' in item ? item.reading : `${item.word} ${item.meaning} ${item.partOfSpeech}`).includes(query));
  return <section className="learning-shell panel" aria-label={mode === 'hanja' ? '한자 학습' : '영어 학습'}>
    {celebrating && active && page === 'quiz' && <CompletionCelebration />}
    <div className="section-heading"><h1>{mode === 'hanja' ? '한자' : '영어'} 글자잇기</h1><SessionStars count={saved.sessions} /></div>
    <p className="word-total">{entries(mode).length}개 {mode === 'hanja' ? '한자어' : '단어'} · 10문제를 모두 이으면 작은 별 하나</p>
    <nav className="learning-tabs" aria-label="학습 메뉴"><Button variant={page === 'quiz' ? 'fill' : 'weak'} aria-pressed={page === 'quiz'} onClick={() => setPage('quiz')}>퀴즈 풀기</Button><Button variant={page === 'book' ? 'fill' : 'weak'} aria-pressed={page === 'book'} onClick={() => setPage('book')}>나의 단어장</Button></nav>
    {warning && <p role="alert">{warning}</p>}
    {page === 'book' ? <section className={`book${mode === 'english' ? ' english-book' : ''}`}>
      {speech.error && <p role="alert">{speech.error}</p>}
      <div className="section-heading"><div><span className="eyebrow">한 글자씩 쌓이는 배움</span><h2>나의 {mode === 'hanja' ? '한자성어장' : '영어 단어장'}</h2></div><span>전체 {entries(mode).length}개</span></div>
      <p className="description">뜻을 살펴보고, 다시 보고 싶은 {name}를 모아 보세요.</p>
      <div className="book-tabs" role="group" aria-label="단어장 분류">{([['all', '전체'], ['favorites', '즐겨찾기'], ['completed', '학습완료'], ['mistakes', '오답노트']] as const).map(([value, text]) => <Button key={value} aria-pressed={filter === value} onClick={() => { setFilter(value); setLimit(40); }}>{text}</Button>)}</div>
      <label className="search-label">{mode === 'hanja' ? '한글 독음' : '영어 단어'} 검색<input type="search" value={search} onChange={e => { setSearch(e.target.value); setLimit(40); }} placeholder={mode === 'hanja' ? '한글 독음 검색' : '영어 단어 또는 뜻 검색'} /></label>
      {filter === 'completed' && <p className="description">퀴즈에서 직접 정답을 맞힌 {name}예요.</p>}
      {filter === 'mistakes' && <p className="description">선택한 후보의 답을 틀렸던 낱말이에요. 정답을 맞힌 뒤에도 복습할 수 있어요.</p>}
      <p className="description">{book.length}개 {mode === 'hanja' ? '한자어' : '단어'}</p>
      <ul className="book-list">{book.slice(0, limit).map(item => <li key={item.id}>
        <div className="book-item-heading"><h3>{label(item)}</h3><Button className="favorite-button" aria-label={`${label(item)} 즐겨찾기`} aria-pressed={saved.favorites.includes(item.id)} onClick={() => persist({ ...saved, favorites: saved.favorites.includes(item.id) ? saved.favorites.filter(id => id !== item.id) : [...saved.favorites, item.id] })}>{saved.favorites.includes(item.id) ? '★' : '☆'}</Button></div>
        <strong className="book-reading">{'hanja' in item ? item.reading : item.partOfSpeech}</strong>
        <p>{item.meaning}</p><Source item={item} />
        {'synonym' in item && item.synonym && <p className="description">동의어 · {item.synonym}</p>}
        {'example' in item && item.example && <div className="book-example"><p>{item.example}</p>{item.exampleMeaning && <p>{item.exampleMeaning}</p>}</div>}
        {'example' in item && item.example.trim() && <div className="example-speech" role="group" aria-label={`${label(item)} 예문 읽기`}><button type="button" aria-label={`${label(item)} 예문 듣기`} onClick={() => speech.speak(item.id, item.example)}>듣기</button><button type="button" aria-label={`${label(item)} 예문 느리게 듣기`} onClick={() => speech.speak(item.id, item.example, true)}>느리게</button>{speech.activeId === item.id && <><button type="button" onClick={speech.stop}>정지</button><span role="status">예문 읽는 중…</span></>}</div>}
        {saved.completed.includes(item.id) && <span className="book-badge">학습완료</span>}{saved.mistakes.includes(item.id) && <span className="book-badge">오답 복습</span>}
      </li>)}</ul>
      {!book.length && <p className="empty">해당하는 낱말이 없어요.</p>}{book.length > limit && <Button className="book-more" onClick={() => setLimit(limit + 40)}>더 보기</Button>}
    </section> : <div className="workspace">
      <p className="description">{mode === 'hanja' ? '한글 글자 선택 → 후보 선택 → 한글 독음 입력' : '알파벳 선택 → 후보 선택 → 영어 단어 입력'}</p>
      <p className="learning-count">{chain.length} / {SESSION_LIMIT} 문제</p><progress value={chain.length} max={SESSION_LIMIT} aria-label="이번 이음 진행" />
      {chain.length > 0 && <section className="completed-chain" aria-label="이어 온 문제 사슬"><div className="journey-heading"><h3>지금까지 이어 온 {name}</h3><span>이번 이음 {chain.length}/{SESSION_LIMIT}</span></div>
        <ol className="chain">{[start, ...chain].map((item, index) => {
          const row = Math.floor(index / 2);
          const column = row % 2 === 0 ? index % 2 + 1 : 2 - index % 2;
          const down = index > 0 && index % 2 === 0;
          return <li key={item.id} data-step={index} className={index === SESSION_LIMIT ? 'chain-complete' : ''} style={{ gridRow: row + 1, gridColumn: column, borderColor: index ? stepColors[index - 1] : undefined }}>
            {index > 0 && <span className={`chain-bridge ${down ? 'bridge-down' : column === 2 ? 'bridge-right' : 'bridge-left'}`} aria-label={`연결 글자: ${connections[index - 1]}`}><span>{connections[index - 1]}</span><span aria-hidden="true">{down ? '↓' : column === 2 ? '→' : '←'}</span></span>}
            <span className="chain-step" style={index ? { backgroundColor: stepColors[index - 1], color: index <= 2 || index === SESSION_LIMIT ? '#243a36' : '#fff' } : undefined}>{index ? `${index} / ${SESSION_LIMIT}` : '시작'}</span>
            {index === SESSION_LIMIT && <span className="chain-complete-label">10개 이음 완성</span>}
            <strong>{label(item)}</strong>{'hanja' in item && <span className="chain-reading">{item.reading}</span>}<p>{item.meaning}</p><Source item={item} />
          </li>;
        })}</ol>
      </section>}
      <article className={`current current-${mode}`} ref={currentCard}>
        <span className="card-caption">{chain.length ? `방금 맞힌 ${name}` : '이음의 시작'}</span><h2>{label(current)}</h2>
        <div className="card-reading"><strong>{'hanja' in current ? current.reading : current.partOfSpeech}</strong><button className="meaning-toggle" aria-expanded={meaning} onClick={() => setMeaning(!meaning)}>{meaning ? '뜻 접기' : '뜻 보기'} ⓘ</button></div>
        {meaning && <p>{current.meaning}</p>}<Source item={current} />
        {'synonym' in current && current.synonym.trim() && <div className="word-example word-synonyms" aria-label="동의어"><span>동의어</span><p>{current.synonym}</p></div>}
        {'example' in current && current.example && <div className="word-example"><div className="example-heading"><span>예문</span>{current.exampleMeaning && <button className="meaning-toggle" aria-expanded={translation} onClick={() => setTranslation(!translation)}>{translation ? '해석 접기' : '해석 보기'}</button>}</div><p>{current.example}</p>{translation && <p>{current.exampleMeaning}</p>}</div>}
      </article>
      {finished ? <div className="summary" role="status"><span className="eyebrow">나만의 배움 한 줄</span><h2>{chain.length === SESSION_LIMIT ? `10개의 ${name}를 이었어요!` : '이번 이음은 여기까지예요.'}</h2><p>{chain.length === SESSION_LIMIT ? '오늘 알게 된 말들이 다음 도전에 힘이 될 거예요.' : '같은 낱말을 반복하지 않고 이어갈 후보가 더 없어요.'}</p><Button onClick={reset}>새 이음 시작하기 ↗</Button></div> : <>
        <div className="instruction"><h3>01 <span>이어갈 {mode === 'hanja' ? '한 글자를' : '알파벳을'} 골라 주세요</span></h3><p>후보가 없는 글자는 쉬어 가요</p></div>
        <div className={`letters single-line-letters${mode === 'hanja' ? ' hanja-letters' : ''}`}>{letters(current).map((ch, index) => {
          const count = candidates(mode, ch, used, history).length;
          return <Button key={index} variant={letter === ch ? 'fill' : 'weak'} aria-label={`${ch}, 후보 ${count}개`} aria-pressed={letter === ch} disabled={!count} onClick={() => { lock.current = false; setLetter(ch); setSelectedId(''); setAnswer(''); setFloating(null); }}><span className="letter-content"><strong>{ch}</strong>{mode === 'hanja' && <span>{count ? `후보 ${count}개` : '후보 없음'}</span>}</span></Button>;
        })}</div>
        <section className="hints"><div className="hint-heading"><h3>02 <span>풀고 싶은 {name}를 선택해 주세요</span></h3>{letter && <span className="pill">{options.length}개 후보</span>}</div>
          {!letter ? <p className="empty">위에서 한 글자를 고르면<br />그 글자가 들어간 낱말의 힌트가 나타나요.</p> : <>
            <p className="hint-description">‘<b>{letter}</b>’와 이어지는 후보를 선택하세요.{mode === 'hanja' && ' 두음법칙을 적용해 녹/록·유/류·이/리도 함께 찾아요.'}</p>
            <ol className={`cards ${mode === 'english' ? 'english-candidates' : 'hanja-candidates'}`} onWheel={closeFloating} onTouchMove={closeFloating} onScroll={closeFloating}>{(mode === 'english' ? options.slice(0, candidateLimit) : options).map((item, index) => <li key={item.id} data-id={item.id} className={selectedId === item.id ? 'selected-candidate' : ''}>
              <label className="candidate"><input type="radio" name={`${mode}-candidate`} checked={selectedId === item.id} onClick={() => selectCandidate(item)} onChange={() => {}} /><span className="candidate-number">{String(index + 1).padStart(2, '0')}</span>{'hanja' in item ? <span className="candidate-title">{item.hanja}</span> : <><span className="candidate-length">{englishLength(item)}글자</span>{item.synonym.trim() && <span className="candidate-synonym">동의어: {item.synonym}</span>}</>}</label>
              <p>{item.meaning}</p><Source item={item} />{selectedId === item.id && attempts[item.id] > 0 && <p className="reading-hint">힌트: {'hanja' in item ? readingHint(item.reading, attempts[item.id]) : englishHint(item, letter, attempts[item.id])}</p>}
            </li>)}</ol>
            {mode === 'english' && options.length > candidateLimit && <Button className="candidate-more book-more" onClick={() => { setFloating(null); setCandidateLimit(value => value + 40); }}>후보 40개 더 보기</Button>}
          </>}
        </section>
        <form ref={formRef} className={`answer-form${floating ? ' floating-answer' : ''}`} style={floating ?? undefined} onKeyDown={e => { if (e.key === 'Escape') closeFloating(); }} onSubmit={e => { e.preventDefault(); submit(); }}>
          {floating && selected && <div className={`answer-candidate${mode === 'hanja' ? ' answer-candidate-hanja' : ''}`} aria-label="선택한 후보"><strong>{'hanja' in selected ? selected.hanja : `${englishLength(selected)}글자${selected.synonym.trim() ? ` · 동의어: ${selected.synonym}` : ''}`}</strong><p>{selected.meaning}</p></div>}
          <div className="answer-heading"><label htmlFor={`${mode}-answer`}>03 <span>{selected ? `선택한 후보 · ${mode === 'hanja' ? label(selected) + ' · 한글 독음 입력' : '영어 단어 입력'}` : '후보를 먼저 선택해 주세요'}</span></label>{floating && <button type="button" className="floating-close" aria-label="입력창 닫기" onClick={closeFloating}>×</button>}</div>
          <div className="input-row"><input id={`${mode}-answer`} ref={input} value={answer} disabled={!selected} onChange={e => setAnswer(e.target.value)} autoComplete="off" autoCapitalize="off" spellCheck={false} placeholder={mode === 'hanja' ? '선택한 후보의 한글 독음' : '영어 단어 입력'} onKeyDown={e => { if (e.key === 'Enter' && e.nativeEvent.isComposing) e.preventDefault(); }} /><Button type="submit" disabled={!selected || !answer.trim()}>확인 ↗</Button></div>
          {floating && <p role="status">{hint ? `힌트: ${hint}` : '후보 목록을 스크롤하면 입력창이 닫혀요.'}</p>}
        </form>
      </>}
      <p className="feedback" role="status">{finished ? `${chain.length}개의 ${name}를 정답으로 이었어요.` : message}</p>
      <aside className="guide"><span className="eyebrow">이렇게 이어가요</span><p>선택한 {mode === 'hanja' ? '한글 글자가 독음에' : '알파벳이'} 들어간 후보를 고르고<br />전체 {mode === 'hanja' ? '독음을' : '영어 단어를'} 입력하면 정답!</p><ul><li>한 이음은 최대 10문제예요.</li><li>같은 이음의 낱말은 다시 나오지 않아요.</li><li>처음 만나는 낱말을 먼저 보여드려요.</li><li>오답이면 힌트가 하나씩 열려요.</li></ul></aside>
      {!finished && <div className="session-actions"><Button onClick={() => { setFloating(null); setRestart(true); }}>새 이음 시작하기 ↻</Button></div>}
      {restart && <div role="alert"><p>진행 중인 이음을 마치고 새로 시작할까요?</p><Button onClick={reset}>새로 시작</Button><Button onClick={() => setRestart(false)}>계속 학습</Button></div>}
    </div>}
  </section>;
}
export default function App() {
  const appRef = useRef<HTMLElement>(null);
  const dockRef = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    const dock = dockRef.current;
    if (!dock) return;
    const measure = () => appRef.current?.style.setProperty('--bottom-dock-height', `${dock.getBoundingClientRect().height}px`);
    const observer = new ResizeObserver(measure);
    observer.observe(dock);
    measure();
    return () => observer.disconnect();
  }, []);
  const [page, setPage] = useState<'home' | Mode>('home');
  const [opened, setOpened] = useState<Mode[]>([]);
  function open(mode: Mode) { setOpened(prev => prev.includes(mode) ? prev : [...prev, mode]); setPage(mode); window.scrollTo(0, 0); }
  function home() { setPage('home'); window.scrollTo(0, 0); }
  return <main ref={appRef} className={`app ${page === 'home' ? 'home-page' : ''}`}>
    <header className="page-header"><button className="brand" onClick={home}>모두의 이음 <span>{page === 'home' ? '한자와 영어, 이어지는 배움' : page === 'hanja' ? '한자 학습' : '영어 학습'}</span></button><span className="edition">하루 한 번, 즐거운 배움</span></header>
    {page === 'home' ? <section className="home-screen" aria-label="홈">
      <div className="intro home-intro"><span className="eyebrow">한 글자에서 시작하는 발견</span><h1>아는 말이 이어지면,<br />배움이 되는 순간.</h1><p>한자도 영어도, 한 글자씩 이어 보세요.<br />오늘의 작은 발견이 다음 배움으로 이어집니다.</p></div>
      <div className="home-courses">{(['hanja', 'english'] as const).map(mode => <article className={`home-course panel ${mode === 'english' ? 'home-course-english' : ''}`} key={mode}>
        <span className="home-symbol" aria-hidden="true">{mode === 'hanja' ? '字' : 'Aa'}</span><span className="eyebrow">{mode === 'hanja' ? '한자성어 · 천자문' : '알파벳으로 잇는 단어'}</span><h2>{mode === 'hanja' ? '한자' : '영어'} 학습</h2><p>{mode === 'hanja' ? '글자를 고르고 뜻을 읽으며' : '알파벳을 고르고 뜻을 읽으며'}<br />{mode === 'hanja' ? '한자성어' : '영어 단어'}를 이어 보세요.</p><div className="home-course-action"><span>{entries(mode).length}개 {mode === 'hanja' ? '한자어' : '단어'}</span><Button onClick={() => open(mode)}>{mode === 'hanja' ? '한자' : '영어'} 이음 시작 ↗</Button></div>
      </article>)}</div>
      <section className="home-guide"><h2>이렇게 시작해요</h2><ol><li><strong>01</strong> 이어갈 글자 고르기</li><li><strong>02</strong> 뜻을 보고 후보 선택하기</li><li><strong>03</strong> 정답을 입력하고 이어가기</li></ol><p>한 번에 최대 10문제. 각 학습의 ‘나의 단어장’에서 즐겨찾기와 오답을 다시 살펴볼 수 있어요.</p></section>
    </section> : <section className="intro learning-intro"><span className="eyebrow">{page === 'hanja' ? '한 글자' : '한 알파벳'}에서 시작하는 발견</span><h1>아는 {page === 'hanja' ? '말이' : '단어가'} 이어지면,<br />배움이 되는 순간.</h1><p>{page === 'hanja' ? '글자를 고르고, 뜻을 읽고, 아는 한자성어를 적어 보세요.' : '알파벳을 고르고, 뜻을 읽고, 아는 영어 단어를 적어 보세요.'}<br />정답이 다음 배움의 시작이 됩니다.</p></section>}
    {opened.map(mode => <div key={mode} hidden={page !== mode}><Learning mode={mode} active={page === mode} /></div>)}
    <footer><span>모두의 이음 · {page === 'home' ? '한자와 영어 학습' : page === 'hanja' ? `한자 학습 ${idioms.length}개` : `영어 학습 ${words.length}개`}</span><span>이전 학습 이력은 이 기기에 저장돼요. 진행 중인 이음은 새로고침하면 초기화돼요.</span></footer>
    <div className="bottom-dock" ref={dockRef}>
      <BottomBanner />
      <nav className="bottom-nav" aria-label="학습 선택"><button aria-current={page === 'home' ? 'page' : undefined} onClick={home}><span aria-hidden="true">⌂</span>홈</button><button aria-current={page === 'hanja' ? 'page' : undefined} onClick={() => open('hanja')}><span aria-hidden="true">字</span>한자 학습</button><button aria-current={page === 'english' ? 'page' : undefined} onClick={() => open('english')}><span aria-hidden="true">Aa</span>영어 학습</button></nav>
    </div>
  </main>;
}
