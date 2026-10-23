import { useEffect, useRef, useState } from 'react';
import { englishLetters, englishCandidates, matchesEnglish, englishLength, englishHint, SESSION_LIMIT, type EnglishWord } from '@idioms/shared';
import raw from '../../../data/english/words.json';

const words: EnglishWord[] = raw.map(item => {
  if (item.category !== 'english' || !item.id || !item.word || !item.meaning) throw new Error('영어 자료 형식 오류');
  return { ...item, category: 'english' };
});
const KEY = 'idioms:web:english:v1';
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
  const [records, setRecords] = useState(saved.records);
  const [warning, setWarning] = useState(saved.warning);
  const [start, setStart] = useState(() => pickStart(saved.records));
  const [chain, setChain] = useState<{ item: EnglishWord; letter: string }[]>([]);
  const [letter, setLetter] = useState('');
  const [targetId, setTargetId] = useState('');
  const [answer, setAnswer] = useState('');
  const [attempts, setAttempts] = useState<Record<string, number>>({});
  const [message, setMessage] = useState('연결할 알파벳을 골라 주세요.');
  const [book, setBook] = useState(false);
  const [filter, setFilter] = useState<keyof Records | 'all'>('all');
  const [query, setQuery] = useState('');
  const [limit, setLimit] = useState(40);
  const input = useRef<HTMLInputElement>(null);
  const current = chain.at(-1)?.item ?? start;
  const used = new Set([start.id, ...chain.map(link => link.item.id)]);
  const history = new Set(records.history);
  const candidates = englishCandidates(words, letter, used, history);
  const selected = candidates.find(item => item.id === targetId);
  const finished = chain.length >= SESSION_LIMIT || !englishLetters(current).some(ch => englishCandidates(words, ch, used, history).length);
  useEffect(() => { if (targetId && !book) input.current?.focus(); }, [targetId, book]);

  function save(next: Records) {
    setRecords(next);
    try { localStorage.setItem(KEY, JSON.stringify(next)); setWarning(''); }
    catch { setWarning('영어 학습 기록을 저장하지 못했어요. 다음 접속에서는 남지 않을 수 있어요.'); }
  }
  function choose(ch: string) { setLetter(ch); setTargetId(''); setAnswer(''); setAttempts({}); setLimit(40); setMessage('뜻·품사·글자 수를 보고 풀 후보를 선택하세요.'); }
  function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!selected || finished) return;
    if (!answer.trim()) { setMessage('영어 단어를 먼저 입력해 주세요.'); return; }
    if (matchesEnglish(selected, answer, letter)) {
      save({ ...records, history: [...new Set([...records.history, start.id, selected.id])], completed: [...new Set([...records.completed, selected.id])] });
      setChain([...chain, { item: selected, letter }]); setLetter(''); setTargetId(''); setAnswer(''); setAttempts({}); setLimit(40);
      setMessage(`${selected.word}, 정답이에요! 다음 알파벳을 골라 주세요.`);
    } else {
      save({ ...records, mistakes: [...new Set([...records.mistakes, selected.id])] });
      setAttempts(value => ({ ...value, [selected.id]: (value[selected.id] ?? 0) + 1 }));
      setMessage('선택한 후보의 철자와 달라요. 추가 힌트를 확인해 주세요.');
    }
  }
  function restart() {
    if (chain.length && !finished && !window.confirm('진행 중인 연결을 마치고 새로 시작할까요?')) return;
    setStart(pickStart(records)); setChain([]); choose(''); setMessage('새 연결을 시작해 보세요.');
  }
  const listed = words.filter(item => (filter === 'all' || records[filter].includes(item.id)) && `${item.word} ${item.meaning} ${item.partOfSpeech}`.toLowerCase().includes(query.trim().toLowerCase()));
  return <section className="english-learning learning-shell panel" aria-label="영어 단어 연결 학습">
    <div className="book-heading"><h1>영어 글자잇기</h1><span>{words.length}개 단어</span></div>
    <div className="learning-tabs"><button aria-pressed={!book} onClick={() => { setBook(false); setLimit(40); }}>퀴즈 풀기</button><button aria-pressed={book} onClick={() => { setBook(true); setLimit(40); }}>나의 단어장</button></div>
    <div hidden={book}>
      <p className="book-description">알파벳 선택 → 후보 선택 → 영어 단어 입력</p>
      <p className="learning-count">{chain.length} / {SESSION_LIMIT} 문제</p>
      <progress value={chain.length} max={SESSION_LIMIT} aria-label="영어 정답 수" />
      {chain.length > 0 && <ol className="english-chain">{chain.map((link, index) => <li key={link.item.id}><span>{index === 0 ? start.word : chain[index - 1].item.word}</span><small> {link.letter} → </small><strong>{link.item.word}</strong><p>{link.item.meaning}</p></li>)}</ol>}
      <div className="idiom-card"><span className="card-caption">{chain.length ? '방금 맞힌 단어' : '연결의 시작'}</span><h2>{current.word}</h2><strong>{current.partOfSpeech}</strong><p>{current.meaning}</p>
        {(current.example || current.exampleMeaning) && <div className="word-example" aria-label="예문"><span>예문</span>{current.example && <p lang="en">{current.example}</p>}{current.exampleMeaning && <p>{current.exampleMeaning}</p>}</div>}
      </div>
      {finished ? <div className="summary"><h2>{chain.length === SESSION_LIMIT ? '20개 단어를 이었어요!' : '이어갈 후보가 더 없어요.'}</h2><button className="primary" onClick={restart}>새 세션 시작</button></div> : <>
        <h3 className="english-step">01 알파벳을 골라 주세요</h3>
        <div className="characters">{englishLetters(current).map((ch, index) => <button key={`${index}-${ch}`} aria-pressed={letter === ch} disabled={!englishCandidates(words, ch, used, history).length} onClick={() => choose(ch)}><strong>{ch}</strong></button>)}</div>
        <h3 className="english-step">02 풀 후보를 선택하세요 {letter && `· ${candidates.length}개`}</h3>
        {!letter && <p className="empty">알파벳을 고르면 후보가 나타나요.</p>}
        <ol className="candidate-list english-candidates">{candidates.slice(0, limit).map((item, index) => <li key={item.id} className={targetId === item.id ? 'selected-candidate' : ''}>
          <label className="candidate-choice"><input type="radio" name="english-candidate" value={item.id} checked={targetId === item.id} onChange={() => { setTargetId(item.id); setAnswer(''); }} /><span>후보 {index + 1} · {item.partOfSpeech} · {englishLength(item)}글자</span></label>
          <p>{item.meaning}</p>{targetId === item.id && !!attempts[item.id] && <span className="reading-hint">철자 힌트 · {englishHint(item, letter, attempts[item.id])}</span>}
        </li>)}</ol>
        {candidates.length > limit && <button className="book-more" onClick={() => setLimit(value => value + 40)}>후보 40개 더 보기</button>}
        <form onSubmit={submit} className="answer-form"><label htmlFor="english-answer">03 {selected ? `후보 ${candidates.indexOf(selected) + 1}의 영어 단어` : '후보를 먼저 선택해 주세요'}</label><div className="input-row"><input ref={input} id="english-answer" value={answer} onChange={event => setAnswer(event.target.value)} disabled={!selected} autoComplete="off" autoCapitalize="none" spellCheck={false} aria-describedby="english-feedback" placeholder="영어 단어 입력" /><button className="primary" disabled={!selected}>확인</button></div></form>
      </>}
      <p id="english-feedback" className="feedback" role="status">{message}</p><button className="text-button" onClick={restart}>새 세션 시작하기 ↻</button>
    </div>
    <div hidden={!book}>
      <div className="book-tabs">{([['all', '전체'], ['favorites', '즐겨찾기'], ['completed', '학습완료'], ['mistakes', '오답노트']] as const).map(([value, label]) => <button key={value} aria-pressed={filter === value} onClick={() => { setFilter(value); setLimit(40); }}>{label}</button>)}</div>
      <label htmlFor="english-search">단어 또는 뜻 검색</label><input className="book-search-input" id="english-search" type="search" value={query} onChange={event => { setQuery(event.target.value); setLimit(40); }} />
      <p className="book-result">{listed.length}개 단어</p><ul className="book-list">{listed.slice(0, limit).map(item => <li key={item.id}><div className="book-item-heading"><h2>{item.word}</h2><button className="favorite-button" aria-label={`${item.word} 즐겨찾기`} aria-pressed={records.favorites.includes(item.id)} onClick={() => save({ ...records, favorites: records.favorites.includes(item.id) ? records.favorites.filter(id => id !== item.id) : [...records.favorites, item.id] })}>{records.favorites.includes(item.id) ? '★' : '☆'}</button></div><strong>{item.partOfSpeech}</strong><p>{item.meaning}</p><p className="book-note">{item.example}<br />{item.exampleMeaning}</p></li>)}</ul>
      {!listed.length && <p className="book-empty">해당하는 단어가 없어요.</p>}{listed.length > limit && <button className="book-more" onClick={() => setLimit(value => value + 40)}>40개 더 보기</button>}
    </div>
    {warning && <p className="notice" role="alert">{warning}</p>}
  </section>;
}
