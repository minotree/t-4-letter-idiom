import entries from '../../../data/stdict/entries.json';

type DictionaryEntry = {
  targetCode: string; word: string; hanja: string; pronunciations: string[];
  senses: { code: string; pos: string; definition: string; relations: { word: string; type: string }[] }[];
};
const dictionary: Record<string, DictionaryEntry> = entries;
export default function DictionaryDetails({ id }: { id: string }) {
  const entry = dictionary[id];
  if (!entry) return null;
  return <details className="dictionary-details" key={id}>
    <summary>표준국어대사전 더 보기</summary>
    <div className="dictionary-content">
      <strong>{entry.word} ({entry.hanja})</strong>
      {entry.pronunciations.length > 0 && <p>발음: {entry.pronunciations.join(' / ')}</p>}
      <ol>{entry.senses.map(sense => <li key={sense.code}>
        {sense.pos && <span className="dictionary-pos">{sense.pos}</span>}
        <p>{sense.definition}</p>
        {sense.relations.length > 0 && <p className="dictionary-relations">{sense.relations.map(relation => `${relation.type}: ${relation.word}`).join(' · ')}</p>}
      </li>)}</ol>
    </div>
  </details>;
}

