/**
 * Lightweight fuzzy subsequence scorer used by the command palette.
 * Returns a score in [0, 1] — 0 means "does not match", 1 means "perfect match".
 *
 * Heuristics, all hand-tuned for tiny menus:
 *   • Empty query → 1 (everything matches).
 *   • Substring → 0.95 (case-insensitive contains).
 *   • Subsequence with dense matches → smooth 0..0.85 score.
 *   • No subsequence match → 0.
 */
export function fuzzyScore(query: string, target: string): number {
  if (!query) return 1
  const q = query.toLowerCase()
  const t = target.toLowerCase()
  if (!t) return 0
  if (t.includes(q)) {
    // Substrings get a strong score; word-start substrings get slightly higher.
    const idx = t.indexOf(q)
    const isWordStart = idx === 0 || /[\s/_-]/.test(t[idx - 1] || "")
    return isWordStart ? 0.99 : 0.92
  }

  // Subsequence pass.
  let qi = 0
  let lastMatch = -1
  let dense = 0 // count of consecutive same-position matches
  for (let ti = 0; ti < t.length && qi < q.length; ti++) {
    if (t[ti] === q[qi]) {
      if (lastMatch === ti - 1) dense += 1
      lastMatch = ti
      qi += 1
    }
  }
  if (qi < q.length) return 0

  // Score: density / target length, plus a small bias for shorter targets.
  const density = dense / Math.max(1, q.length)
  const lenBias = 1 / Math.max(8, t.length / 2)
  return Math.min(0.85, 0.35 + density * 0.45 + lenBias)
}
