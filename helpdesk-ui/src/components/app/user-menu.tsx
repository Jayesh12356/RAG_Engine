"use client"

import { useRouter } from "next/navigation"
import { LogOut, Settings2, User2, BookOpenCheck } from "lucide-react"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { signOut, useSession } from "@/lib/auth"
import { initialsFromName } from "@/lib/utils"

export function UserMenu({ compact = false }: { compact?: boolean }) {
  const router = useRouter()
  const { user } = useSession()

  const onSignOut = () => {
    signOut()
    router.push("/sign-in")
    router.refresh()
  }

  if (!user) return null

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          className="relative h-auto px-2 py-1.5 hover:bg-muted"
          aria-label="Open user menu"
        >
          <span className="flex items-center gap-2.5">
            <Avatar className="h-8 w-8">
              <AvatarFallback>{initialsFromName(user.name)}</AvatarFallback>
            </Avatar>
            {!compact && (
              <span className="flex flex-col items-start leading-tight text-left">
                <span className="text-[13px] font-semibold text-fg">{user.name}</span>
                <span className="text-xs text-muted-fg truncate max-w-[140px]">
                  {user.email}
                </span>
              </span>
            )}
          </span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel>{user.name}</DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={() => router.push("/app/status")}>
          <Settings2 className="h-4 w-4 text-muted-fg" />
          System status
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => router.push("/app/documents")}>
          <BookOpenCheck className="h-4 w-4 text-muted-fg" />
          Manage documents
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => router.push("/app/chat")}>
          <User2 className="h-4 w-4 text-muted-fg" />
          My workspace
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={onSignOut} className="text-danger focus:text-danger">
          <LogOut className="h-4 w-4" />
          Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
