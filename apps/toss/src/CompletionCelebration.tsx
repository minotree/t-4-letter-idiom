import type { CSSProperties } from 'react';

// Adapted from t-crossword-app/apps/toss/src/components/CompletionConfetti.tsx.
const colors = ['#facc15', '#2563eb', '#7c3aed', '#f97316', '#ec4899', '#10b981'];
const pieces = Array.from({ length: 72 }, (_, index) => ({
  '--confetti-color': colors[index % colors.length],
  '--confetti-start': `${15 + (index % 3) * 35}%`,
  '--confetti-x': `${((index * 37) % 91) - 45}vw`,
  '--confetti-rise': `-${55 + ((index * 19) % 41)}dvh`,
  '--confetti-end': `-${20 + ((index * 13) % 35)}dvh`,
  '--confetti-spin': `${((index * 97) % 1080) - 540}deg`,
  animationDelay: `${Math.floor(index / 24) * 320 + (index % 8) * 35}ms`,
  animationDuration: `${2400 + (index % 5) * 140}ms`,
  borderRadius: index % 3 === 0 ? '50%' : '2px',
  width: index % 4 === 0 ? '7px' : '10px',
  height: index % 4 === 0 ? '22px' : '10px',
} satisfies CSSProperties & Record<`--confetti-${string}`, string>));

export function CompletionCelebration() {
  return <div className="completion-celebration" aria-hidden="true">
    {pieces.map((style, index) => <span key={index} className="completion-confetti-piece" style={style} />)}
  </div>;
}
