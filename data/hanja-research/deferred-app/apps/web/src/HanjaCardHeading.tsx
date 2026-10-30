import { forwardRef, useEffect, useRef, useState } from 'react';
import hee from './hanja-pilot/32690-zhhans.svg?raw';
import hwi from './hanja-pilot/26249-ja.svg?raw';
import lang from './hanja-pilot/26391.svg?raw';
import yo from './hanja-pilot/26332.svg?raw';

type Fact = { reading: string; radical: string; strokes: string; svg: string; region: string; source: string; sourceLabel: string; reference?: string; radicalSource?: string };
const facts: Record<string, Fact> = {
  羲: { reading: '숨 희 · 복희 희', radical: '羊 (양 양)', strokes: '16획', svg: '32690-zhhans.svg', region: '중국', source: 'https://github.com/libhangul/libhangul/blob/23d2cd9d10d516d523d60c562dbcc7ea08139a09/data/hanja/hanja.txt', sourceLabel: 'libhangul 한자 사전', reference: 'https://encykorea.aks.ac.kr/Article/E0066119' },
  暉: { reading: '빛 휘 · 햇빛 휘', radical: '日 (날 일)', strokes: '13획', svg: '26249-ja.svg', region: '일본', source: 'https://github.com/libhangul/libhangul/blob/23d2cd9d10d516d523d60c562dbcc7ea08139a09/data/hanja/hanja.txt', sourceLabel: 'libhangul 한자 사전', reference: 'https://encykorea.aks.ac.kr/Article/E0042716' },
  朗: { reading: '밝을 랑 · 밝을 낭', radical: '月 (달 월)', strokes: '11획 (한국어기초사전 기준)', svg: '26391.svg', region: '한국', source: 'https://krdict.korean.go.kr/eng/dicSearch/SearchView?ParaWordNo=41252', sourceLabel: '국립국어원 한국어기초사전', radicalSource: 'https://krdict.korean.go.kr/kor/dicSearch/SearchView?ParaWordNo=26894' },
  曜: { reading: '빛날 요', radical: '日 (날 일)', strokes: '18획', svg: '26332.svg', region: '한국', source: 'https://krdict.korean.go.kr/kor/dicSearch/SearchView?ParaWordNo=67865', sourceLabel: '국립국어원 한국어기초사전' },
};
const assets = `${import.meta.env.BASE_URL}hanja-pilot/`;
const graphics: Record<string, string> = { '32690-zhhans.svg': hee, '26249-ja.svg': hwi, '26391.svg': lang, '26332.svg': yo };

const HanjaCardHeading = forwardRef<HTMLHeadingElement, { word: string; active: boolean }>(function HanjaCardHeading({ word, active }, headingRef) {
  const dialog = useRef<HTMLDialogElement>(null);
  const object = useRef<HTMLDivElement>(null);
  const opener = useRef<HTMLButtonElement | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);
  const fact = selected ? facts[selected] : undefined;
  useEffect(() => {
    if (!active || !selected) return;
    const modal = dialog.current;
    if (modal && !modal.open) modal.showModal();
    modal?.querySelector<HTMLButtonElement>('.hanja-dialog-close')?.focus();
  }, [selected, active]);
  useEffect(() => {
    if (!active || !word.includes(selected ?? '')) {
      if (dialog.current?.open) dialog.current.close();
      setSelected(null);
    }
  }, [active, word, selected]);
  function close() { if (dialog.current?.open) dialog.current.close(); }
  function playback(state: 'paused' | 'running') {
    object.current?.querySelectorAll<SVGElement>('path[clip-path]').forEach(path => { path.style.animationPlayState = state; });
  }
  return <>
    <h2 ref={headingRef} tabIndex={-1} lang="zh" className="hanja-card-title">{Array.from(word, (char, index) => <button type="button" key={`${index}-${char}`} aria-label={`${char} 한자 정보`} onClick={event => { opener.current = event.currentTarget; setRevision(0); setSelected(char); }}>{char}</button>)}</h2>
    <dialog ref={dialog} className="hanja-dialog" aria-labelledby="hanja-detail-title" onClose={() => { setSelected(null); if (active) opener.current?.focus(); }}>
      <div className="hanja-dialog-heading"><h2 id="hanja-detail-title" lang="zh">{selected}</h2><button type="button" className="hanja-dialog-close" onClick={close} aria-label="한자 정보 닫기">닫기</button></div>
      {fact ? <>
        <dl><dt>훈음</dt><dd>{fact.reading}</dd><dt>부수</dt><dd>{fact.radical}</dd><dt>총획수</dt><dd>{fact.strokes}</dd></dl>
        <section className="hanja-stroke" aria-label="획순"><h3>획순</h3><p>{fact.region} 자료의 참고용 획순이에요. 한국 학습 기준 대조는 진행 중이에요.</p>
          <div ref={object} className="hanja-stroke-image" key={`${selected}-${revision}`} role="img" aria-label={`${selected} 획순 참고 애니메이션`} dangerouslySetInnerHTML={{ __html: graphics[fact.svg] }} />
          <div className="hanja-stroke-controls"><button type="button" onClick={() => playback('running')}>재생</button><button type="button" onClick={() => playback('paused')}>일시정지</button><button type="button" onClick={() => setRevision(value => value + 1)}>다시 보기</button></div>
        </section>
        <p className="hanja-source">훈음 등 출처: <a href={fact.source} target="_blank" rel="noreferrer">{fact.sourceLabel}</a>{fact.radicalSource && <> · <a href={fact.radicalSource} target="_blank" rel="noreferrer">부수 훈음</a></>}{fact.reference && <> · <a href={fact.reference} target="_blank" rel="noreferrer">부수·획수 대조</a></>}. {fact.reference ? <a href={`${assets}libhangul-license.txt`}>libhangul 이용 조건</a> : <a href="https://creativecommons.org/licenses/by-sa/2.0/kr/" target="_blank" rel="noreferrer">CC BY-SA 2.0 대한민국</a>}</p>
        <p className="hanja-source">획순: AnimCJK · Arphic Public License · <a href={`${assets}COPYING.txt`}>저작권 고지</a> · <a href={`${assets}ARPHICPL.TXT`}>라이선스</a></p>
      </> : <p className="hanja-pending">이 한자의 정보와 획순은 준비 중이에요.</p>}
    </dialog>
  </>;
});
export default HanjaCardHeading;
