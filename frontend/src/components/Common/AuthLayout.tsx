import { Appearance } from "@/components/Common/Appearance"
import { Footer } from "./Footer"

interface AuthLayoutProps {
  children: React.ReactNode
}

export function AuthLayout({ children }: AuthLayoutProps) {
  return (
    <div className="grid min-h-svh lg:grid-cols-2 bg-zinc-950 overflow-hidden font-sans">
      {/* Dynamic Sun Animation Side */}
      <div className="relative hidden lg:flex lg:items-center lg:justify-center overflow-hidden bg-black">
        {/* Core Sun */}
        <div className="absolute w-[500px] h-[500px] rounded-full bg-linear-to-br from-yellow-400 via-orange-500 to-red-600 animate-sun-pulse opacity-80" />

        {/* Solar Flares / Rings */}
        <div className="absolute w-[700px] h-[700px] border-2 border-orange-500/20 rounded-full animate-flare-rotate" />
        <div className="absolute w-[800px] h-[800px] border border-yellow-500/10 rounded-full animate-flare-rotate animation-duration-[30s] direction-[reverse]" />

        {/* Particle Overlay */}
        <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-20 contrast-150 brightness-100 mix-blend-screen" />

        <div
          className="relative z-10 text-center space-y-6 animate-in-fade"
          style={{ animationDelay: "0.2s" }}
        >
          <div className="relative inline-block">
            <div className="absolute -inset-8 bg-white/20 rounded-full blur-3xl animate-pulse" />
            <img
              src="/btc_logo.png"
              alt="Bright Tutorials"
              className="h-48 w-auto relative drop-shadow-[0_0_30px_rgba(255,255,255,0.5)]"
            />
          </div>
          <div className="space-y-2">
            <h2 className="text-4xl font-black text-white tracking-tighter drop-shadow-lg">
              <span className="text-yellow-400">BRIGHT</span> TUTORIALS
            </h2>
            <p className="text-orange-100 font-bold tracking-[0.2em] uppercase text-sm drop-shadow-md">
              Brighten Your Future With Us
            </p>
          </div>
        </div>
      </div>

      {/* Login Form Side */}
      <div className="relative flex flex-col gap-4 p-6 md:p-10 bg-zinc-950 lg:bg-transparent">
        {/* Background glow for mobile */}
        <div className="lg:hidden absolute inset-0 bg-linear-to-b from-orange-500/10 to-transparent pointer-events-none" />

        <div className="flex justify-end relative z-10">
          <Appearance />
        </div>

        <div className="flex flex-1 items-center justify-center relative z-10">
          <div className="w-full max-w-sm p-8 rounded-3xl glass-sun border-white/5 shadow-2xl animate-in-fade">
            {children}
          </div>
        </div>

        <div className="relative z-10 opacity-60 hover:opacity-100 transition-opacity">
          <Footer />
        </div>
      </div>
    </div>
  )
}
