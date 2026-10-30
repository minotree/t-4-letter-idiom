import source from '../../../data/stdict/source.json';

export default function DictionaryLicense() {
  return <section className="dictionary-license" aria-label="표준국어대사전 출처·이용조건">
    <h2>표준국어대사전</h2>
    <p>출처: {source.author} {source.title} · {source.exportDate} 내려받기</p>
    <p>{source.license}</p>
    <p>학습용 항목·필드를 추출하고 표제어 구분 기호를 제거하여 형식을 변환했습니다.</p>
    <p>이 사전 자료와 가공한 자료는 저작자표시-동일조건변경허락 2.0 대한민국 조건으로 이용할 수 있습니다. 출처와 이용조건을 표시하고, 가공한 자료를 배포할 때 같은 조건을 적용해야 합니다.</p>
    <p>라이선스: {source.licenseUrl}</p>
    <p>출처: {source.url}</p>
  </section>;
}

