import { useState } from 'react';
import { normalizeHanjaForSearch, type Idiom } from '@idioms/shared';
import ContentSource from './ContentSource';

type Props = {
  idioms: Idiom[];
  favorites: Set<string>;
  completed: Set<string>;
  mistakes: Set<string>;
  legacyMistakeCount: number;
  onFavorite: (id: string) => void;
};
const tabs = ['전체', '즐겨찾기', '학습완료', '오답노트'] as const;

export default function IdiomBook({ idioms, favorites, completed, mistakes, legacyMistakeCount, onFavorite }: Props) {
  const [tab, setTab] = useState<typeof tabs[number]>('전체');
  const [query, setQuery] = useState('');
  const [limit, setLimit] = useState(40);
  const term = normalizeHanjaForSearch(query).replace(/\s/g, '').toLowerCase();
  const filtered = idioms.filter(item => {
    const included = tab === '전체' || (tab === '즐겨찾기' ? favorites : tab === '학습완료' ? completed : mistakes).has(item.id);
    return included && normalizeHanjaForSearch(`${item.hanja} ${item.reading} ${item.meaning}`).replace(/\s/g, '').toLowerCase().includes(term);
  });
  return <section className="idiom-book panel" aria-labelledby="book-title">
    <div className="book-heading"><div><span className="eyebrow">한 글자씩 쌓이는 배움</span><h1 id="book-title">나의 한자성어장</h1></div><span>전체 {idioms.length}개</span></div>
    <p className="book-description">한자와 뜻을 살펴보고, 다시 보고 싶은 한자성어를 모아 보세요.</p>
    <div className="book-tabs" role="group" aria-label="한자성어장 분류">{tabs.map(value => <button key={value} aria-pressed={tab === value} onClick={() => { setTab(value); setLimit(40); }}>{value}</button>)}</div>
    <label className="book-search" htmlFor="book-search">한자성어 검색</label>
    <input className="book-search-input" id="book-search" type="search" placeholder="한자, 독음 또는 뜻 검색" value={query} onChange={event => { setQuery(event.target.value); setLimit(40); }} />
    {tab === '학습완료' && <p className="book-note">퀴즈에서 직접 정답을 맞힌 한자성어예요. 이 기능을 추가한 뒤의 정답부터 기록해요.</p>}
    {tab === '오답노트' && <p className="book-note">선택한 후보의 독음을 틀렸던 한자성어예요. 정답을 맞힌 뒤에도 복습할 수 있도록 남겨 두어요.{legacyMistakeCount > 0 && ` 이전 방식의 기록 ${legacyMistakeCount}개는 틀린 후보를 확인할 수 없어 이 목록에서 제외했어요.`}</p>}
    <p className="book-result" role="status">{filtered.length}개 한자성어</p>
    <ul className="book-list">{filtered.slice(0, limit).map(item => <li key={item.id}>
      <div className="book-item-heading"><h2 lang="zh">{item.hanja}</h2><button className="favorite-button" aria-label={`${item.reading} 즐겨찾기`} aria-pressed={favorites.has(item.id)} onClick={() => onFavorite(item.id)}>{favorites.has(item.id) ? '★' : '☆'}</button></div>
      <strong className="book-reading">{item.reading}</strong>
      <p>{item.meaning}</p>
      <ContentSource item={item} />
      {completed.has(item.id) && <span className="book-badge">학습완료</span>}
      {mistakes.has(item.id) && <span className="book-badge">오답 복습</span>}
    </li>)}</ul>
    {!filtered.length && <p className="book-empty">{query ? '검색 결과가 없어요. 다른 글자나 뜻으로 찾아보세요.' : tab === '즐겨찾기' ? '별표를 눌러 다시 보고 싶은 한자성어를 담아 보세요.' : tab === '학습완료' ? '퀴즈에서 정답을 맞히면 여기에 쌓여요.' : '아직 기록된 오답이 없어요.'}</p>}
    {filtered.length > limit && <button className="book-more" onClick={() => setLimit(value => value + 40)}>40개 더 보기 ({Math.min(limit, filtered.length)} / {filtered.length})</button>}
  </section>;
}
