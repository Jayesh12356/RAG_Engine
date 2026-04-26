import { Suspense } from "react"
import { AuthShell } from "@/components/auth/auth-shell"

export const dynamic = "force-dynamic"

export default function SignUpPage() {
  return (
    <Suspense fallback={null}>
      <AuthShell mode="sign-up" />
    </Suspense>
  )
}
