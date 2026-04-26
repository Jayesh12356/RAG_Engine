import { Suspense } from "react"
import { AuthShell } from "@/components/auth/auth-shell"

export const dynamic = "force-dynamic"

export default function SignInPage() {
  return (
    <Suspense fallback={null}>
      <AuthShell mode="sign-in" />
    </Suspense>
  )
}
