export interface HanjaReading { hun: string; eum: string }
/** Keep all source meanings; do not infer a contextual sense from the word. */
export function hanjaReadings(data: Record<string, HanjaReading[]>, character: string): HanjaReading[] {
  return data[character] ?? [];
}
