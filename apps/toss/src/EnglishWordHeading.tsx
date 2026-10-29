import { useLayoutEffect, useRef } from 'react';

export function EnglishWordHeading({ word }: { word: string }) {
  const heading = useRef<HTMLHeadingElement>(null);
  const text = useRef<HTMLSpanElement>(null);
  useLayoutEffect(() => {
    const element = heading.current;
    const content = text.current;
    if (!element || !content) return;
    let disposed = false;
    let previousWidth = -1;
    const fit = () => {
      if (disposed || !element.clientWidth) return;
      previousWidth = element.clientWidth;
      element.style.fontSize = '';
      const maximum = parseFloat(getComputedStyle(element).fontSize);
      let size = maximum;
      // Font hinting/rounding can make the first proportional estimate too wide.
      for (let attempt = 0; attempt < 8; attempt++) {
        const width = content.getBoundingClientRect().width;
        if (width <= element.clientWidth) break;
        size *= Math.max(1, element.clientWidth - 1) / width * 0.98;
        element.style.fontSize = `${size}px`;
      }
    };
    const observer = new ResizeObserver(() => {
      if (element.clientWidth !== previousWidth) fit();
    });
    observer.observe(element);
    fit();
    // Refit after a font loads, even when the card width did not change.
    void document.fonts.ready.then(fit);
    window.addEventListener('resize', fit);
    return () => { disposed = true; observer.disconnect(); window.removeEventListener('resize', fit); };
  }, [word]);
  return <h2 ref={heading}><span ref={text}>{word}</span></h2>;
}
