export interface Idiom {
  id: string;
  category: 'idiom' | 'cheonjamun';
  hanja: string;
  reading: string;
  meaning: string;
}

export const SESSION_LIMIT = 20;
export { englishForms, englishLetters, englishCandidates, matchesEnglish, englishLength, englishHint, type EnglishWord } from './english.ts';

/** Search only: preserve the displayed Hanja, Korean reading and stable row ID. */
export function normalizeHanjaForSearch(value: string): string {
  // NFKC unifies CJK compatibility characters. 為/爲 is a separately reviewed variant pair.
  return value.normalize('NFKC').replace(/爲/g, '為');
}

const REVIEWED_ID_CHANGES: Readonly<Record<string, string>> = {
  '卷土重來': '捲土重來',
  '橘化爲枳': '橘化為枳',
  '麥秀之歎': '麥秀之嘆',
  '輕躁浮薄': '輕佻浮薄',
  '龍尾鳳湯': '龍味鳳湯',
  '李下不正冠': '李下不整冠',
  '耳懸令鼻懸令': '耳懸鈴鼻懸鈴',
  '前途遼遠': '前途遙遠',
  '弊袍破笠': '敝袍破笠',
};

/** Only these reviewed row corrections migrate IDs; unrelated homophones stay separate. */
export function migrateIdiomHistory(ids: readonly string[], validIds: ReadonlySet<string>): string[] {
  return [...new Set(ids.map(id => Object.hasOwn(REVIEWED_ID_CHANGES, id) ? REVIEWED_ID_CHANGES[id] : id))]
    .filter(id => validIds.has(id));
}

/** Quotes, embedded commas/newlines and UTF-8 BOM are supported. */
export function parseCsv(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [], value = '', quoted = false;
  const source = text.replace(/^\uFEFF/, '');
  for (let i = 0; i < source.length; i++) {
    const ch = source[i];
    if (ch === '"') {
      if (quoted && source[i + 1] === '"') { value += '"'; i++; }
      else quoted = !quoted;
    } else if (!quoted && (ch === ',' || ch === '\n')) {
      row.push(value.replace(/\r$/, '')); value = '';
      if (ch === '\n') { if (row.some(Boolean)) rows.push(row); row = []; }
    } else value += ch;
  }
  if (quoted) throw new Error('CSV의 따옴표가 닫히지 않았습니다.');
  row.push(value.replace(/\r$/, ''));
  if (row.some(Boolean)) rows.push(row);
  return rows;
}

export function loadIdioms(csv: string): Idiom[] {
  const [header, ...rows] = parseCsv(csv);
  const required = ['hanja', 'reading', 'meaning'];
  if (!header || required.some(key => !header.includes(key))) throw new Error('학습 데이터의 필수 열이 없습니다.');
  const ids = new Set<string>();
  return rows.map((row, index) => {
    if (row.length !== header.length) throw new Error(`CSV ${index + 2}행의 열 수가 다릅니다.`);
    const [hanja, reading, meaning] = required.map(key => row[header.indexOf(key)]?.trim());
    const category = header.includes('category') ? row[header.indexOf('category')]?.trim() : 'idiom';
    if (category !== 'idiom' && category !== 'cheonjamun') throw new Error(`CSV ${index + 2}행의 자료 종류가 올바르지 않습니다.`);
    if (!hanja || !reading || !meaning || ids.has(hanja)) throw new Error(`CSV ${index + 2}행이 비었거나 한자가 중복됩니다.`);
    ids.add(hanja);
    return { id: hanja, category, hanja, reading, meaning };
  });
}

export function candidatesFor(
  idioms: readonly Idiom[], character: string, sessionIds: ReadonlySet<string>, historyIds: ReadonlySet<string>,
): Idiom[] {
  if (!character) return [];
  const key = normalizeAnswer(character);
  if (!/^[가-힣]$/u.test(key)) return [];
  const eligible = idioms.filter(item => normalizeAnswer(item.reading).includes(key) && !sessionIds.has(item.id));
  const unseen = eligible.filter(item => !historyIds.has(item.id));
  return unseen.length ? unseen : eligible;
}

export function normalizeAnswer(value: string): string {
  return value.normalize('NFC').replace(/\s/g, '');
}

export function matchingAnswers(candidates: readonly Idiom[], answer: string): Idiom[] {
  const normalized = normalizeAnswer(answer);
  return normalized ? candidates.filter(item => normalizeAnswer(item.reading) === normalized) : [];
}

export function readingHint(reading: string, revealed: number): string {
  return [...reading].map((ch, index) => index < revealed ? ch : '○').join('');
}
