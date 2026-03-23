import {
  createFileRoute,
  Outlet,
  redirect,
  useLocation,
} from "@tanstack/react-router"
import { useEffect } from "react"
import { UsersService } from "@/client"
import { Footer } from "@/components/Common/Footer"
import { Logo } from "@/components/Common/Logo"
import AppSidebar from "@/components/Sidebar/AppSidebar"
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar"
import { isLoggedIn } from "@/hooks/useAuth"
import { cn } from "@/lib/utils"

export const Route = createFileRoute("/_layout")({
  component: Layout,
  beforeLoad: async () => {
    if (!isLoggedIn()) {
      throw redirect({
        to: "/login",
      })
    }
  },
})

function Layout() {
  const location = useLocation()
  const isTestMode = location.pathname.startsWith("/tests/")

  // Real-time heartbeat tracking
  useEffect(() => {
    const sendHeartbeat = async () => {
      try {
        if (!isLoggedIn()) return
        await UsersService.userHeartbeat({ path: location.pathname })
      } catch (e) {
        console.error("Heartbeat failed", e)
      }
    }

    // Send immediately on path change
    sendHeartbeat()

    // And then every minute
    const interval = setInterval(sendHeartbeat, 60000)
    return () => clearInterval(interval)
  }, [location.pathname])

  return (
    <SidebarProvider>
      {!isTestMode && <AppSidebar />}
      <SidebarInset
        className={cn(
          "bg-background relative overflow-hidden",
          isTestMode && "w-full flex-none",
        )}
      >
        {/* Soft branded background glow */}
        <div className="absolute top-0 right-0 -mr-40 -mt-40 size-96 bg-primary/5 blur-3xl rounded-full pointer-events-none" />
        <div className="absolute bottom-0 left-0 -ml-40 -mb-40 size-96 bg-primary/10 blur-3xl rounded-full pointer-events-none" />

        {!isTestMode && (
          <header className="sticky top-0 z-10 flex h-16 shrink-0 items-center justify-between px-4 border-b glass">
            <div className="flex items-center gap-2">
              <SidebarTrigger className="-ml-1 text-muted-foreground" />
              <div className="h-4 w-px bg-border mx-2" />
              <Logo variant="icon" asLink={false} />
            </div>
          </header>
        )}
        <main
          className={cn("flex-1 relative z-0", !isTestMode && "p-6 md:p-8")}
        >
          <div
            className={cn(
              "mx-auto animate-in-fade",
              !isTestMode && "max-w-7xl",
            )}
          >
            <Outlet />
          </div>
        </main>
        {!isTestMode && <Footer />}
      </SidebarInset>
    </SidebarProvider>
  )
}

export default Layout
