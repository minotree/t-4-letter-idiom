import type { Idiom } from '@idioms/shared';

export default function ContentSource({ item }: { item: Idiom }) {
  return item.category === 'cheonjamun' ? <span className="content-source">출처: 천자문</span> : null;
}
