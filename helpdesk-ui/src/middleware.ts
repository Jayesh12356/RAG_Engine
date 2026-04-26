import { NextResponse, type NextRequest } from "next/server"

const COOKIE_KEY = "rag_engine_uid"

export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl
  if (!pathname.startsWith("/app")) {
    return NextResponse.next()
  }
  const uid = req.cookies.get(COOKIE_KEY)?.value
  if (uid) {
    return NextResponse.next()
  }
  const url = req.nextUrl.clone()
  url.pathname = "/sign-in"
  url.searchParams.set("from", pathname)
  return NextResponse.redirect(url)
}

export const config = {
  matcher: ["/app/:path*"],
}
