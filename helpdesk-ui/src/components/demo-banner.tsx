import { Beaker } from 'lucide-react'

export function DemoBanner({ demoMode }: { demoMode?: boolean }) {
  if (!demoMode) return null
  return (
    <div className="bg-amber-50/80 text-amber-700 border border-amber-200/60 py-2 px-6 flex items-center gap-2 justify-center w-full rounded-xl mt-4 animate-fade-in">
      <Beaker className="w-3.5 h-3.5" />
      <span className="text-xs font-semibold tracking-wide">Demo Mode Active — responses use sample data</span>
    </div>
  )
}
