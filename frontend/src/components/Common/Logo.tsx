import { Link } from "@tanstack/react-router"

import { cn } from "@/lib/utils"

interface LogoProps {
  variant?: "full" | "icon" | "responsive"
  className?: string
  asLink?: boolean
}

export function Logo({ className, asLink = true }: LogoProps) {
  // const { resolvedTheme } = useTheme()
  // const isDark = resolvedTheme === "dark"

  const content = (
    <div className="flex items-center gap-3 px-1 group">
      <div className="relative">
        <div className="absolute inset-0 bg-orange-500/20 rounded-full blur-xl group-hover:bg-orange-500/30 transition-colors animate-pulse" />
        <img
          src="/btc_logo.png"
          alt="BT Logo"
          className="h-8 w-auto relative drop-shadow-[0_0_8px_var(--metallic-gold)] animate-in-fade animate-[float_6s_ease-in-out_infinite] group-hover:scale-110 transition-transform duration-500"
        />
      </div>
      <span
        className={cn(
          "font-bold text-xl tracking-tight group-data-[collapsible=icon]:hidden animate-in-fade",
          className,
        )}
      >
        <span className="text-orange-500 italic">Bright</span> Tutorials
      </span>
    </div>
  )

  if (!asLink) {
    return content
  }

  return <Link to="/">{content}</Link>
}
