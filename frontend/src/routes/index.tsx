import { createFileRoute } from "@tanstack/react-router"
import LandingPage from "@/components/Landing/LandingPage"

// biome-ignore lint/suspicious/noExplicitAny: TanStack Router path generator sync issue
export const Route = createFileRoute("/" as any)({
  component: Index,
})

function Index() {
  return <LandingPage />
}
