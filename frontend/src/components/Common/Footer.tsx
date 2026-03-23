import { SITE_CONFIG } from "@/lib/site-config"

export function Footer() {
  return (
    <footer className="w-full py-6 mt-auto border-t border-white/5">
      <div className="container flex flex-col items-center justify-between gap-4 md:h-14 md:flex-row md:py-0">
        <p className="text-balance text-center text-sm leading-loose text-muted-foreground md:text-left">
          © {new Date().getFullYear()} {SITE_CONFIG.name}. All rights reserved.
        </p>
        <div className="flex items-center gap-4">
          {SITE_CONFIG.socials.map(({ icon: Icon, href, label, color }) => (
            <a
              key={label}
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              aria-label={label}
              className={`text-muted-foreground hover:${color} transition-colors`}
            >
              <Icon className="h-5 w-5" />
            </a>
          ))}
        </div>
      </div>
    </footer>
  )
}
