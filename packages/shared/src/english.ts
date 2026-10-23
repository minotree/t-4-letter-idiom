export interface EnglishWord {
  id: string;
  category: 'english';
  word: string;
  meaning: string;
  partOfSpeech: string;
  level: string;
  example: string;
  exampleMeaning: string;
  synonym: string;
}

export function englishForms(item: EnglishWord): string[] {
  return item.word.split('/').map(value => value.trim().toUpperCase());
}

export function englishLetters(item: EnglishWord): string[] {
  return [...item.word.toUpperCase().replace(/[^A-Z]/g, '')];
}

export function englishCandidates(items: readonly EnglishWord[], letter: string, used: ReadonlySet<string>, history: ReadonlySet<string>): EnglishWord[] {
  if (!/^[A-Z]$/.test(letter)) return [];
  const available = items.filter(item => !used.has(item.id) && englishLetters(item).includes(letter));
  const unseen = available.filter(item => !history.has(item.id));
  return unseen.length ? unseen : available;
}

export function matchesEnglish(item: EnglishWord, answer: string, letter: string): boolean {
  const value = answer.trim().replace(/\s+/g, ' ').toUpperCase();
  return /^[A-Z]$/.test(letter) && value.includes(letter) && englishForms(item).includes(value);
}

export function englishLength(item: EnglishWord): string {
  return [...new Set(englishForms(item).map(form => form.replace(/[^A-Z]/g, '').length))].join(' / ');
}

export function englishHint(item: EnglishWord, letter: string, attempts: number): string {
  const form = englishForms(item).find(value => value.includes(letter)) ?? item.word;
  let position = 0;
  return [...form].map(ch => /[A-Z]/.test(ch) ? (position++ < attempts ? ch : '○') : ch).join('');
}
