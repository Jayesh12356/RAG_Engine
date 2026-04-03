import React from 'react'
import { Skeleton } from '@/components/skeleton'

export default function Loading() {
  return (
    <div className="flex flex-col gap-6 max-w-5xl mx-auto mt-6 w-full">
      <Skeleton className="h-8 w-32" />
      <Skeleton className="h-[400px] w-full" />
    </div>
  )
}
