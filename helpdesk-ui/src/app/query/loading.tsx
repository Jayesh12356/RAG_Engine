import React from 'react'
import { Skeleton } from '@/components/skeleton'

export default function Loading() {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start mt-6 w-full">
      <div className="lg:col-span-5 bg-white p-6 border border-slate-200 rounded-lg shadow-sm">
        <Skeleton className="h-7 w-48 mb-6" />
        <Skeleton className="h-32 w-full mb-6" />
        <Skeleton className="h-10 w-full mb-6" />
        <Skeleton className="h-12 w-full" />
      </div>
      <div className="lg:col-span-7 bg-white border border-slate-200 rounded-lg p-6 shadow-sm flex flex-col gap-6">
        <div className="flex items-center justify-between">
          <Skeleton className="h-7 w-32" />
          <Skeleton className="h-16 w-24" />
        </div>
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-5/6" />
        <Skeleton className="h-4 w-4/6" />
        <Skeleton className="h-10 w-full mt-4" />
        <Skeleton className="h-10 w-full" />
      </div>
    </div>
  )
}
