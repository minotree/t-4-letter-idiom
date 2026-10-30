import { forwardRef, useEffect, useRef, useState } from 'react';
import { hanjaReadings } from '@idioms/shared';
import readings from './data/hanja-readings.json';

const HanjaCardHeading = forwardRef<HTMLHeadingElement, { word: string; active: boolean }>(function HanjaCardHeading({ word, active }, headingRef) {
  const root = useRef<HTMLDivElement>(null);
  const opener = useRef<HTMLButtonElement | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const character = selected === null ? '' : [...word][selected];
  const facts = hanjaReadings(readings, character ?? '');
  useEffect(() => { setSelected(null); }, [word, active]);
  useEffect(() => {
    if (selected === null) return;
    const outside = (event: PointerEvent) => { if (!root.current?.contains(event.target as Node)) setSelected(null); };
    const escape = (event: KeyboardEvent) => { if (event.key === 'Escape') { setSelected(null); opener.current?.focus(); } };
    document.addEventListener('pointerdown', outside);
    document.addEventListener('keydown', escape);
    return () => { document.removeEventListener('pointerdown', outside); document.removeEventListener('keydown', escape); };
  }, [selected]);
  return <div className="hanja-reading-root" ref={root}>
    <h2 ref={headingRef} tabIndex={-1} className="hanja-reading-heading">{[...word].map((char, index) => <button type="button" key={index} aria-label={`${char} 음과 훈`} aria-expanded={selected === index} onClick={event => { opener.current = event.currentTarget; setSelected(selected === index ? null : index); }}>{char}</button>)}</h2>
    {selected !== null && active && <div className="hanja-reading-popup" role="region" aria-label={`${character} 음과 훈`}>
      <div className="hanja-reading-top"><strong>{character}</strong><button type="button" aria-label="한자 정보 닫기" onClick={() => { setSelected(null); opener.current?.focus(); }}>닫기</button></div>
      {facts.length ? facts.map(({ hun, eum }, index) => <p key={index}><b>훈:</b> {hun}　<b>음:</b> {eum}</p>) : <p>음과 훈을 확인 중이에요.</p>}
    </div>}
  </div>;
});
export default HanjaCardHeading;
