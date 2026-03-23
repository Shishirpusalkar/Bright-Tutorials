import { Link } from "@tanstack/react-router"
import { motion, useScroll, useSpring, useTransform } from "framer-motion"
import {
  BrainCircuit,
  ChevronDown,
  ChevronRight,
  Rocket,
  Target,
} from "lucide-react"
import { useRef } from "react"
import useAuth from "@/hooks/useAuth"
import { SITE_CONFIG } from "@/lib/site-config"

export default function LandingPage() {
  const containerRef = useRef<HTMLDivElement>(null)
  const { scrollYProgress } = useScroll({
    target: containerRef,
    offset: ["start start", "end end"],
  })

  const smoothProgress = useSpring(scrollYProgress, {
    stiffness: 100,
    damping: 30,
    restDelta: 0.001,
  })

  const opacity = useTransform(smoothProgress, [0, 0.2], [1, 0])
  const scale = useTransform(smoothProgress, [0, 0.2], [1, 0.8])

  const { user } = useAuth()

  const getDashboardLink = () => {
    if (!user) return "/login"
    if (user.is_superuser) return "/admin"
    if (user.role === "teacher") return "/teacher-dashboard"
    if (user.role === "student") return "/student-dashboard"
    return "/student-dashboard"
  }

  return (
    <div
      ref={containerRef}
      className="relative min-h-screen bg-zinc-950 text-white overflow-hidden selection:bg-orange-500/30"
    >
      {/* Dynamic Background Mesh */}
      <div className="fixed inset-0 z-0 pointer-events-none">
        <div className="absolute top-0 left-0 w-full h-full bg-[radial-gradient(circle_at_50%_50%,rgba(255,165,0,0.1),transparent_50%)] animate-glowPulse" />
        <div className="absolute top-[20%] right-[10%] w-[500px] h-[500px] bg-orange-600/10 blur-[120px] rounded-full animate-float" />
        <div
          className="absolute bottom-[10%] left-[-5%] w-[600px] h-[600px] bg-yellow-500/10 blur-[150px] rounded-full animate-float"
          style={{ animationDelay: "-4s" }}
        />
      </div>

      {/* Hero Section */}
      <section className="relative min-h-screen flex flex-col items-center justify-center px-6 overflow-hidden">
        <motion.div
          style={{ opacity, scale }}
          className="z-10 flex flex-col items-center text-center gap-8 max-w-5xl"
        >
          {/* Logo Animation Block */}
          <div className="relative mb-8">
            {/* SVG Orbit Elements */}
            <svg
              className="absolute inset-0 w-full h-full -m-20 pointer-events-none overflow-visible"
              viewBox="0 0 400 400"
              role="img"
              aria-label="Orbiting Atoms Logo Animation"
            >
              <title>Orbiting Atoms Logo Animation</title>
              <motion.circle
                cx="200"
                cy="200"
                r="120"
                stroke="rgba(255,165,0,0.2)"
                strokeWidth="1"
                fill="none"
              />
              <motion.ellipse
                cx="200"
                cy="200"
                rx="180"
                ry="70"
                stroke="rgba(255,215,0,0.15)"
                strokeWidth="1"
                fill="none"
                animate={{ rotate: 360 }}
                transition={{ duration: 20, repeat: Infinity, ease: "linear" }}
              />
              <motion.ellipse
                cx="200"
                cy="200"
                rx="70"
                ry="180"
                stroke="rgba(255,69,0,0.15)"
                strokeWidth="1"
                fill="none"
                animate={{ rotate: -360 }}
                transition={{ duration: 25, repeat: Infinity, ease: "linear" }}
              />

              {/* Floating Icons on Orbits */}
              <motion.g
                animate={{ rotate: 360 }}
                transition={{ duration: 15, repeat: Infinity, ease: "linear" }}
                style={{ originX: "200px", originY: "200px" }}
              >
                <circle
                  cx="200"
                  cy="20"
                  r="4"
                  fill="#FFD700"
                  className="blur-[1px]"
                />
                <circle cx="200" cy="20" r="8" fill="rgba(255,215,0,0.3)" />
              </motion.g>
            </svg>

            {/* Central Logo */}
            <motion.div
              initial={{ scale: 0.8, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ duration: 1, ease: "easeOut" }}
              className="relative z-20"
            >
              <div className="absolute inset-0 bg-orange-500/20 rounded-full blur-[80px] animate-pulse" />
              <img
                src="/btc_logo.png"
                alt="Bright Tutorials - Empowering JEE & NEET Students"
                className="h-48 md:h-64 w-auto relative drop-shadow-[0_0_40px_rgba(255,165,0,0.5)] transition-transform duration-700 hover:scale-110"
              />
            </motion.div>
          </div>

          <motion.div
            initial={{ y: 40, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ delay: 0.5, duration: 0.8 }}
            className="space-y-4"
          >
            <h1 className="text-6xl md:text-8xl font-black tracking-tighter bg-clip-text text-transparent bg-linear-to-b from-white via-white to-white/40 leading-none">
              BRIGHT{" "}
              <span className="text-orange-500 drop-shadow-[0_0_15px_rgba(255,165,0,0.3)]">
                TUTORIALS
              </span>
            </h1>
            <p className="text-xl md:text-2xl text-orange-200/60 font-medium max-w-2xl mx-auto tracking-wide">
              The ultimate AI-powered preparation platform for{" "}
              <span className="text-white border-b border-orange-500/50">
                JEE & NEET
              </span>{" "}
              aspirants.
            </p>
          </motion.div>

          <motion.div
            initial={{ y: 20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ delay: 1, duration: 0.6 }}
            className="flex flex-col md:flex-row gap-4 mt-8"
          >
            {user ? (
              <Link
                to={getDashboardLink() as any}
                className="group relative px-10 py-5 bg-orange-600 rounded-full font-bold text-lg overflow-hidden transition-all hover:pr-12 shadow-[0_0_30px_rgba(234,88,12,0.4)]"
              >
                <span className="relative z-10 flex items-center gap-2">
                  Go to Dashboard{" "}
                  <ChevronRight className="group-hover:translate-x-1 transition-transform" />
                </span>
                <div className="absolute inset-0 bg-linear-to-r from-yellow-400 to-orange-500 opacity-0 group-hover:opacity-100 transition-opacity" />
              </Link>
            ) : (
              <Link
                to="/login"
                className="group relative px-10 py-5 bg-orange-600 rounded-full font-bold text-lg overflow-hidden transition-all hover:pr-12 shadow-[0_0_30px_rgba(234,88,12,0.4)]"
              >
                <span className="relative z-10 flex items-center gap-2">
                  Go to Dashboard{" "}
                  <ChevronRight className="group-hover:translate-x-1 transition-transform" />
                </span>
                <div className="absolute inset-0 bg-linear-to-r from-yellow-400 to-orange-500 opacity-0 group-hover:opacity-100 transition-opacity" />
              </Link>
            )}
          </motion.div>
        </motion.div>

        <motion.div
          animate={{ y: [0, 10, 0] }}
          transition={{ duration: 2, repeat: Infinity }}
          className="absolute bottom-10 left-1/2 -ml-3 text-white/30"
        >
          <ChevronDown />
        </motion.div>
      </section>

      {/* Feature Grid */}
      <section className="relative z-10 max-w-7xl mx-auto py-32 px-6">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
          <FeatureCard
            icon={<BrainCircuit className="w-10 h-10" />}
            title="AI Extraction"
            description="Upload any PDF and watch our AI extract questions, options, and solutions instantly with perfect LaTeX rendering."
            color="orange"
          />
          <FeatureCard
            icon={<Target className="w-10 h-10" />}
            title="Precision Analysis"
            description="Get deep insights into your performance with AI-generated feedback tailored to your strengths and weaknesses."
            color="yellow"
            delay={0.2}
          />
          <FeatureCard
            icon={<Rocket className="w-10 h-10" />}
            title="Real Exam Simulation"
            description="Experience a high-stakes computer-based test environment designed to match JEE and NEET standards."
            color="orange"
            delay={0.4}
          />
        </div>
      </section>

      {/* CTA Footer */}
      <section className="relative z-10 py-40 text-center">
        <div className="max-w-3xl mx-auto px-6 space-y-8">
          <h2 className="text-4xl md:text-6xl font-bold tracking-tight">
            Ready to <span className="text-orange-500 italic">dominate</span>{" "}
            the exams?
          </h2>
          <p className="text-xl text-white/50">
            Join thousands of students who are already using Bright Tutorials to
            crush their JEE & NEET goals.
          </p>
          <div className="pt-8">
            {user ? (
              <Link
                to={getDashboardLink() as any}
                className="px-12 py-6 bg-white text-zinc-950 rounded-full font-black text-xl hover:bg-orange-500 hover:text-white transition-all duration-300 transform hover:scale-105"
              >
                Go to Dashboard
              </Link>
            ) : (
              <Link
                to="/login"
                className="px-12 py-6 bg-white text-zinc-950 rounded-full font-black text-xl hover:bg-orange-500 hover:text-white transition-all duration-300 transform hover:scale-105"
              >
                Go to Dashboard
              </Link>
            )}
          </div>
        </div>
      </section>

      <footer className="relative z-10 border-t border-white/5 py-12 px-6">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row justify-between items-center gap-6 text-white/30 text-sm">
          <div className="flex items-center gap-4">
            <img
              src={SITE_CONFIG.brandLogo}
              className="h-8 opacity-50 grayscale"
              alt={`${SITE_CONFIG.name} Footer Logo`}
            />
            <span>
              &copy; {new Date().getFullYear()} {SITE_CONFIG.name}. All rights
              reserved.
            </span>
          </div>
          <div className="flex gap-8 font-medium">
            <button
              type="button"
              onClick={() => alert("Privacy Policy coming soon!")}
              className="hover:text-white transition-colors"
            >
              Privacy Policy
            </button>
            <button
              type="button"
              onClick={() => alert("Terms of Service coming soon!")}
              className="hover:text-white transition-colors"
            >
              Terms of Service
            </button>
            <a
              href={SITE_CONFIG.links.contactUs}
              className="hover:text-white transition-colors"
            >
              Contact Us
            </a>
          </div>
        </div>
      </footer>
    </div>
  )
}

function FeatureCard({
  icon,
  title,
  description,
  delay = 0,
}: {
  icon: React.ReactNode
  title: string
  description: string
  color?: string
  delay?: number
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 30 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ delay, duration: 0.6 }}
      whileHover={{ y: -10 }}
      className="group relative p-8 glass-dark rounded-3xl border border-white/10 hover:border-orange-500/50 transition-colors overflow-hidden"
    >
      <div
        className={`absolute top-0 right-0 -m-8 w-40 h-40 bg-orange-500/10 blur-[60px] group-hover:bg-orange-500/20 transition-all`}
      />
      <div className="relative z-10 space-y-4">
        <div className="inline-flex p-3 bg-white/5 rounded-2xl text-orange-400 group-hover:scale-110 group-hover:text-orange-300 transition-all duration-500">
          {icon}
        </div>
        <h3 className="text-2xl font-bold text-white group-hover:text-orange-400 transition-colors">
          {title}
        </h3>
        <p className="text-white/40 leading-relaxed font-medium group-hover:text-white/60 transition-colors">
          {description}
        </p>
      </div>
    </motion.div>
  )
}
