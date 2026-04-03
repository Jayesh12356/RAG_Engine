export default function Loading() {
  return (
    <div className="flex h-[calc(100vh-3.5rem)] animate-pulse overflow-hidden bg-slate-50">
      <div className="w-[280px] bg-slate-100 border-r border-slate-200 hidden md:block" />
      <div className="flex-1 p-8">
        <div className="max-w-3xl mx-auto space-y-8 mt-10">
          <div className="h-12 bg-indigo-100/50 rounded-2xl w-1/2 ml-auto rounded-tr-sm" />
          <div className="h-24 bg-slate-200/50 rounded-2xl w-3/4 rounded-tl-sm" />
          <div className="h-12 bg-indigo-100/50 rounded-2xl w-1/3 ml-auto rounded-tr-sm" />
        </div>
      </div>
    </div>
  )
}
