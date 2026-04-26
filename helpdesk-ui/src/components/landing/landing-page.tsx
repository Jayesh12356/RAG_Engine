import { SiteHeader } from "./site-header"
import { Hero } from "./hero"
import { Features } from "./features"
import { DeepDive } from "./deep-dive"
import { ProvidersMarquee } from "./providers-marquee"
import { Testimonial } from "./testimonial"
import { SiteFooter } from "./footer"

export default function LandingPage() {
  return (
    <div className="flex min-h-screen flex-col bg-bg text-fg">
      <SiteHeader />
      <main className="flex-1">
        <Hero />
        <Features />
        <DeepDive />
        <ProvidersMarquee />
        <Testimonial />
      </main>
      <SiteFooter />
    </div>
  )
}
