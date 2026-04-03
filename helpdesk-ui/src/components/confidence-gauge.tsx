export function ConfidenceGauge({ confidence, label }: { confidence: number, label: string }) {
  const isRefused = label === "refused"
  const pct = isRefused ? 0 : Math.round(confidence * 100)
  
  const radius = 50
  const circumference = Math.PI * radius
  const filledArc = isRefused ? circumference : (pct / 100) * circumference
  const offset = circumference - filledArc
  
  let colorClass = "stroke-rose-400"
  let bgGlow = "text-rose-400"
  if (!isRefused) {
    if (confidence >= 0.85) { colorClass = "stroke-emerald-500"; bgGlow = "text-emerald-500" }
    else if (confidence >= 0.60) { colorClass = "stroke-indigo-500"; bgGlow = "text-indigo-500" }
    else if (confidence >= 0.40) { colorClass = "stroke-amber-500"; bgGlow = "text-amber-500" }
  }

  return (
    <div className="flex flex-col items-center justify-center w-[110px] shrink-0">
      <div className="relative w-full h-[60px] overflow-hidden -mb-1">
        <svg viewBox="0 0 120 80" className="w-[110px] h-[72px]">
          <path
            d="M 10 70 A 50 50 0 0 1 110 70"
            fill="none"
            className="stroke-slate-100"
            strokeWidth="8"
            strokeLinecap="round"
          />
          <path
            d="M 10 70 A 50 50 0 0 1 110 70"
            fill="none"
            className={colorClass}
            strokeWidth="8"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            style={{ transition: 'stroke-dashoffset 0.6s cubic-bezier(0.4, 0, 0.2, 1)' }}
          />
        </svg>
        <div className="absolute bottom-1 left-0 right-0 text-center">
          <span className="text-lg font-bold text-slate-900 leading-none tracking-tight">
            {isRefused ? "–" : `${pct}%`}
          </span>
        </div>
      </div>
      <span className={`text-[10px] font-semibold mt-0.5 uppercase tracking-widest ${bgGlow}`}>
        {label}
      </span>
    </div>
  )
}
