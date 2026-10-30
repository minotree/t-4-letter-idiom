export function readSessions(key: string): { count: number; warning: string } {
  try {
    const count: unknown = JSON.parse(localStorage.getItem(key) ?? '0');
    if (typeof count !== 'number' || !Number.isSafeInteger(count) || count < 0) throw new Error();
    return { count, warning: '' };
  } catch { return { count: 0, warning: '완주 횟수를 읽지 못했어요. 이번에는 0회부터 표시합니다.' }; }
}

export function SessionStars({ count, limit = 7 }: { count: number; limit?: number }) {
  const groups = [
    { size: 'large', label: '큰 별', count: Math.floor(count / 100) },
    { size: 'medium', label: '중간 별', count: Math.floor(count / 10) % 10 },
    { size: 'small', label: '작은 별', count: count % 10 },
  ];
  return <div className="session-rank" aria-label={`${limit}문제 완주 ${count}회`}>
    {count > 0 ? <div className="session-stars">{groups.filter(group => group.count > 0).map(group => <span key={group.size} className={`session-star-group star-${group.size}`} role="img" aria-label={`${group.label} ${group.count}개`}><span aria-hidden="true">{group.count > 9 ? '★' : '★'.repeat(group.count)}</span>{group.count > 9 && <span aria-hidden="true" className="star-multiplier">×{group.count}</span>}</span>)}</div> : <span className="session-rank-empty">첫 별을 모아 보세요</span>}
    <span className="session-rank-count">{limit}문제 완주 {count}회</span>
  </div>;
}
// Session milestones: green, blue, purple, warm colors, then gold completion.
export const STEP_COLORS = [
  '#b8d9b0', '#8fc78c', '#367e52', '#21867f', '#2476aa',
  '#514782', '#7c3b8e', '#ba5134', '#ba641e', '#d6ab39',
] as const;
