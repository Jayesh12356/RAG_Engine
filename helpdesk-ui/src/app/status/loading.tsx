import React from 'react'
import { Skeleton } from '@/components/skeleton'

export default function Loading() {
  return (
    <div className="flex flex-col gap-6 max-w-5xl mx-auto mt-6 w-full">
      <Skeleton className="h-8 w-40" />
      <Skeleton className="h-[200px] w-full mt-2" />
    </div>
  )
}
