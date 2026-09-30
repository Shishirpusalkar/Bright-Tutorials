import { useParams } from "@tanstack/react-router"
import { motion, AnimatePresence } from "framer-motion"
import {
  Beaker,
  Brain,
  Clock,
  Info,
  ChevronDown,
  ChevronUp,
  Timer,
  Trophy,
  Target,
  Zap,
} from "lucide-react"
import { useEffect, useMemo, useState } from "react"
import ReactMarkdown from "react-markdown"
import rehypeKatex from "rehype-katex"
import remarkMath from "remark-math"
import SmilesRenderer from "@/components/Common/SmilesRenderer"
import {
  type ExtractedContent,
  isExtractedContent,
  QuestionContent,
  type SolutionContent,
  SolutionView,
} from "@/components/Test/QuestionContent"
import {
  PdfSnippet,
  RichPdfContent,
  SOLUTION_SNIPPET_TOKEN,
  VISUAL_SNIPPET_TOKEN,
} from "@/components/Test/RichPdfContent"
import { Badge } from "@/components/ui/badge"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { cn, toAbsoluteBackendUrl } from "@/lib/utils"
import "katex/dist/katex.min.css"

// Types (should eventually be in types.gen.ts, but defining here for speed)
interface AttemptAnswerPublic {
  id: string
  question_id: string
  selected_option: string | null
  answer_text: string | null
  is_correct: boolean
  marks_obtained: number
  time_spent_seconds: number
  question_text?: string
  solution_text?: string
  correct_option?: string
  correct_answer_text?: string
  organic_metadata?: {
    iupac_name?: string
    molecular_formula?: string
    smiles?: string
  } | null
  diagram_description?: string | null
  has_visual?: boolean
  visual_tag?: string | null
  question_type?: string | null
  page_number?: number | null
  visual_bbox?: {
    x0: number
    y0: number
    x1: number
    y1: number
  } | null
  solution_bbox?: {
    x0: number
    y0: number
    x1: number
    y1: number
  } | null
  image_url?: string | null
  question_paper_url?: string | null
  options?: Record<string, string> | null
  content?: ExtractedContent | null
  solution_content?: SolutionContent | null
  subject?: string | null
  section?: string | null
  question_number?: number | null
  display_order?: number | null
}

interface AttemptPublic {
  id: string
  student_id: string
  test_id: string
  score: number
  status: string
  started_at: string
  submitted_at: string | null
  tab_switch_count: number
  ai_analysis?: string | null
  section_results?: Record<string, Record<string, number>> | null
  answers: AttemptAnswerPublic[]
}

type Outcome = "correct" | "incorrect" | "skipped"

const fetchAttempt = async (id: string): Promise<AttemptPublic> => {
  const token = localStorage.getItem("access_token")
  const response = await fetch(
    `${import.meta.env.VITE_API_URL || "http://localhost:8000"}/api/v1/attempts/${id}`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    },
  )
  if (!response.ok) {
    throw new Error("Failed to fetch attempt")
  }
  return response.json()
}

const formatTime = (seconds: number) => {
  const s = Math.max(0, Math.round(seconds))
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = s % 60
  if (h) return `${h}h ${m}m`
  if (m) return `${m}m ${sec}s`
  return `${sec}s`
}

const outcomeOf = (a: AttemptAnswerPublic): Outcome =>
  a.is_correct ? "correct" : a.selected_option || a.answer_text ? "incorrect" : "skipped"

const OUTCOME_STYLE: Record<Outcome, { bar: string; badge: string; label: string }> = {
  correct: {
    bar: "bg-emerald-500",
    badge: "bg-emerald-500/10 text-emerald-500 border-emerald-500/20",
    label: "Correct",
  },
  incorrect: {
    bar: "bg-red-500",
    badge: "bg-red-500/10 text-red-500 border-red-500/20",
    label: "Incorrect",
  },
  skipped: {
    bar: "bg-zinc-700",
    badge: "bg-zinc-800 text-zinc-500 border-zinc-700",
    label: "Skipped",
  },
}

function LegacyQuestion({ ans, index }: { ans: AttemptAnswerPublic; index: number }) {
  return (
    <div className="bg-white/3 p-6 rounded-2xl border border-white/5">
      <div className="text-zinc-100 leading-relaxed font-medium max-w-none">
        <RichPdfContent
          text={ans.question_text || "Question text not available"}
          token={VISUAL_SNIPPET_TOKEN}
          pdfUrl={toAbsoluteBackendUrl(ans.question_paper_url)}
          pageNumber={ans.page_number}
          bbox={ans.visual_bbox}
        />
      </div>
      {ans.image_url &&
        !String(ans.question_text || "").includes(VISUAL_SNIPPET_TOKEN) && (
          <div className="mt-4 flex justify-center">
            <img
              src={toAbsoluteBackendUrl(ans.image_url) || ""}
              alt={`Question ${index + 1} visual`}
              className="max-w-[88%] rounded-lg border border-white/10 bg-white shadow-sm"
            />
          </div>
        )}
      {ans.has_visual &&
        ans.page_number &&
        ans.visual_bbox &&
        !ans.image_url &&
        !String(ans.question_text || "").includes(VISUAL_SNIPPET_TOKEN) && (
          <div className="mt-4 flex justify-center">
            <PdfSnippet
              url={toAbsoluteBackendUrl(ans.question_paper_url) || ""}
              pageNumber={ans.page_number}
              bbox={ans.visual_bbox}
            />
          </div>
        )}
      {ans.options && Object.keys(ans.options).length > 0 && (
        <div className="mt-4 grid gap-2 sm:grid-cols-2 text-sm text-zinc-300">
          {Object.entries(ans.options).map(([label, text]) => (
            <div
              key={label}
              className={cn(
                "rounded-lg border p-3",
                (ans.correct_option || "").includes(label)
                  ? "border-emerald-500/50 bg-emerald-500/10"
                  : (ans.selected_option || "").includes(label)
                    ? "border-red-500/50 bg-red-500/10"
                    : "border-white/10",
              )}
            >
              <span className="font-bold mr-2">({label})</span>
              <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
                {text || ""}
              </ReactMarkdown>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default function TestAnalysis() {
  const { attemptId } = useParams({ from: "/_layout/attempts/$attemptId" })
  const [attempt, setAttempt] = useState<AttemptPublic | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showAllSolutions, setShowAllSolutions] = useState(true)
  const [toggled, setToggled] = useState<Record<string, boolean>>({})
  const [outcomeFilter, setOutcomeFilter] = useState<Outcome | "all">("all")
  const [subjectFilter, setSubjectFilter] = useState<string>("all")

  useEffect(() => {
    if (attemptId) {
      fetchAttempt(attemptId)
        .then(setAttempt)
        .catch((err) => setError(err.message))
        .finally(() => setLoading(false))
    }
  }, [attemptId])

  const answers = useMemo(() => {
    if (!attempt) return []
    return [...attempt.answers].sort(
      (a, b) =>
        (a.display_order ?? Number.MAX_SAFE_INTEGER) -
          (b.display_order ?? Number.MAX_SAFE_INTEGER) ||
        (a.page_number || 0) - (b.page_number || 0) ||
        (a.question_number || 0) - (b.question_number || 0),
    )
  }, [attempt])

  const stats = useMemo(() => {
    const total = answers.reduce((s, a) => s + (a.time_spent_seconds || 0), 0)
    const bySubject: Record<
      string,
      { time: number; count: number; correct: number; attempted: number }
    > = {}
    const byOutcome: Record<Outcome, { time: number; count: number }> = {
      correct: { time: 0, count: 0 },
      incorrect: { time: 0, count: 0 },
      skipped: { time: 0, count: 0 },
    }
    for (const a of answers) {
      const subj = a.subject || "General"
      bySubject[subj] ??= { time: 0, count: 0, correct: 0, attempted: 0 }
      bySubject[subj].time += a.time_spent_seconds || 0
      bySubject[subj].count += 1
      const o = outcomeOf(a)
      if (o !== "skipped") bySubject[subj].attempted += 1
      if (o === "correct") bySubject[subj].correct += 1
      byOutcome[o].time += a.time_spent_seconds || 0
      byOutcome[o].count += 1
    }
    const avg = answers.length ? total / answers.length : 0
    const slowest = answers
      .map((a, i) => ({ a, n: i + 1 }))
      .filter(({ a }) => (a.time_spent_seconds || 0) > 0)
      .sort((x, y) => (y.a.time_spent_seconds || 0) - (x.a.time_spent_seconds || 0))
      .slice(0, 5)
    const maxTime = Math.max(1, ...answers.map((a) => a.time_spent_seconds || 0))
    return { total, avg, bySubject, byOutcome, slowest, maxTime }
  }, [answers])

  if (loading) return <div className="p-8 text-center">Loading analysis...</div>
  if (error)
    return <div className="p-8 text-center text-red-500">Error: {error}</div>
  if (!attempt) return <div className="p-8 text-center">Attempt not found</div>

  const totalQuestions = answers.length
  const correctAnswers = answers.filter((a) => a.is_correct).length
  const incorrectAnswers = answers.filter(
    (a) => !a.is_correct && (a.selected_option || a.answer_text),
  ).length
  const attemptedCount = correctAnswers + incorrectAnswers
  const accuracy =
    attemptedCount > 0 ? Math.round((correctAnswers / attemptedCount) * 100) : 0
  const subjects = Object.keys(stats.bySubject)

  const visible = answers
    .map((ans, index) => ({ ans, index }))
    .filter(({ ans }) => outcomeFilter === "all" || outcomeOf(ans) === outcomeFilter)
    .filter(({ ans }) => subjectFilter === "all" || (ans.subject || "General") === subjectFilter)

  const solutionOpen = (id: string) => (toggled[id] === undefined ? showAllSolutions : toggled[id])

  return (
    <div className="min-h-screen bg-[#050505] text-white selection:bg-blue-500/30">
      <div className="container mx-auto p-6 space-y-8 max-w-5xl py-12">
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex justify-between items-end border-b border-white/10 pb-6"
        >
          <div>
            <h1 className="text-4xl font-black tracking-tighter bg-linear-to-r from-white via-white/80 to-white/40 bg-clip-text text-transparent">
              TEST ANALYSIS
            </h1>
            <p className="text-zinc-500 text-sm font-medium mt-1 uppercase tracking-widest">
              Performance Intelligence Report
            </p>
          </div>
          <Badge
            className={cn(
              "px-4 py-1 text-xs font-bold tracking-widest uppercase border-0 rounded-full",
              attempt.status === "submitted"
                ? "bg-blue-500 text-white shadow-[0_0_20px_rgba(59,130,246,0.5)]"
                : "bg-zinc-800 text-zinc-400",
            )}
          >
            {attempt.status}
          </Badge>
        </motion.div>

        {/* Overview Grid */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
          {[
            { label: "Total Score", value: attempt.score, icon: Trophy, color: "text-blue-400" },
            { label: "Accuracy", value: `${accuracy}%`, icon: Target, color: "text-emerald-400" },
            { label: "Attempted", value: `${attemptedCount} / ${totalQuestions}`, icon: Info, color: "text-zinc-400" },
            { label: "Time Taken", value: formatTime(stats.total), icon: Clock, color: "text-purple-400" },
            { label: "Avg / Question", value: formatTime(stats.avg), icon: Timer, color: "text-sky-400" },
            { label: "Tab Switches", value: attempt.tab_switch_count, icon: Zap, color: "text-amber-400" },
          ].map((stat, i) => (
            <motion.div
              key={stat.label}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.06 }}
            >
              <Card className="bg-white/5 border-white/10 backdrop-blur-xl hover:bg-white/10 transition-all duration-300 group h-full">
                <CardHeader className="pb-2 flex flex-row items-center justify-between space-y-0">
                  <span className="text-[10px] font-bold uppercase tracking-widest text-zinc-500">
                    {stat.label}
                  </span>
                  <stat.icon className={cn("size-4 opacity-50 group-hover:opacity-100 transition-opacity", stat.color)} />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-black tracking-tighter italic">
                    {stat.value}
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>

        {/* Time Analysis */}
        <Card className="bg-white/5 border-white/10 backdrop-blur-xl">
          <CardHeader>
            <CardTitle className="text-lg text-white flex items-center gap-2">
              <Clock className="size-5 text-purple-400" /> Time Analysis
            </CardTitle>
            <CardDescription className="text-zinc-400">
              Where your time went, question by question
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Per-question time strip */}
            <div>
              <div className="flex h-16 items-end gap-[2px]">
                {answers.map((a, i) => (
                  <button
                    type="button"
                    key={a.id}
                    title={`Q${i + 1}: ${formatTime(a.time_spent_seconds || 0)} (${OUTCOME_STYLE[outcomeOf(a)].label})`}
                    onClick={() =>
                      document.getElementById(`q-${a.id}`)?.scrollIntoView({ behavior: "smooth", block: "start" })
                    }
                    className={cn(
                      "flex-1 min-w-[2px] rounded-t-sm opacity-80 hover:opacity-100",
                      OUTCOME_STYLE[outcomeOf(a)].bar,
                    )}
                    style={{ height: `${Math.max(4, ((a.time_spent_seconds || 0) / stats.maxTime) * 100)}%` }}
                  />
                ))}
              </div>
              <div className="mt-2 flex gap-4 text-[10px] uppercase tracking-widest text-zinc-500">
                {(["correct", "incorrect", "skipped"] as Outcome[]).map((o) => (
                  <span key={o} className="flex items-center gap-1.5">
                    <span className={cn("size-2 rounded-full", OUTCOME_STYLE[o].bar)} />
                    {OUTCOME_STYLE[o].label}: avg{" "}
                    {formatTime(stats.byOutcome[o].count ? stats.byOutcome[o].time / stats.byOutcome[o].count : 0)}
                  </span>
                ))}
              </div>
            </div>

            <div className="grid gap-6 md:grid-cols-2">
              <div className="space-y-2">
                <h4 className="text-xs font-bold uppercase tracking-widest text-zinc-500">By subject</h4>
                {subjects.map((s) => {
                  const d = stats.bySubject[s]
                  return (
                    <div key={s} className="flex items-center justify-between rounded-lg border border-white/10 bg-white/[0.02] px-3 py-2 text-sm">
                      <span className="font-semibold text-zinc-200">{s}</span>
                      <span className="text-zinc-400">
                        {formatTime(d.time)} · {d.correct}/{d.attempted} correct · avg{" "}
                        {formatTime(d.count ? d.time / d.count : 0)}
                      </span>
                    </div>
                  )
                })}
              </div>
              <div className="space-y-2">
                <h4 className="text-xs font-bold uppercase tracking-widest text-zinc-500">Most time spent</h4>
                {stats.slowest.length === 0 && (
                  <p className="text-sm text-zinc-500">No timing data recorded.</p>
                )}
                {stats.slowest.map(({ a, n }) => (
                  <button
                    type="button"
                    key={a.id}
                    onClick={() =>
                      document.getElementById(`q-${a.id}`)?.scrollIntoView({ behavior: "smooth", block: "start" })
                    }
                    className="flex w-full items-center justify-between rounded-lg border border-white/10 bg-white/[0.02] px-3 py-2 text-sm hover:bg-white/5"
                  >
                    <span className="font-semibold text-zinc-200">
                      Q{n} <span className="text-zinc-500 font-normal">{a.subject}</span>
                    </span>
                    <span className="flex items-center gap-2">
                      <Badge className={cn("px-2 py-0 text-[10px] font-black uppercase", OUTCOME_STYLE[outcomeOf(a)].badge)}>
                        {OUTCOME_STYLE[outcomeOf(a)].label}
                      </Badge>
                      <span className="font-mono text-zinc-300">{formatTime(a.time_spent_seconds || 0)}</span>
                    </span>
                  </button>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Section-wise Breakdown */}
        {attempt.section_results && (
          <Card className="bg-white/5 border-white/10 backdrop-blur-xl">
            <CardHeader>
              <CardTitle className="text-lg text-white">Section Breakdown</CardTitle>
              <CardDescription className="text-zinc-400">
                Performance breakdown by Subject and Section
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {Object.entries(attempt.section_results).map(([subject, sections]) => (
                  <div key={subject} className="p-4 border border-white/10 rounded-lg bg-white/5">
                    <h4 className="font-bold text-blue-400 uppercase mb-3 border-b border-white/10 pb-1">
                      {subject}
                    </h4>
                    <div className="space-y-2">
                      {Object.entries(sections).map(([section, score]) => (
                        <div key={section} className="flex justify-between items-center text-sm">
                          <span className="text-zinc-400">{section}</span>
                          <span
                            className={cn(
                              "font-bold",
                              (score as number) >= 0 ? "text-emerald-400" : "text-red-400",
                            )}
                          >
                            {score as number} Marks
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* AI Analysis Section */}
        {attempt.ai_analysis && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.4 }}
          >
            <Card className="bg-linear-to-br from-blue-600/20 to-purple-600/20 border-blue-500/30 backdrop-blur-2xl relative overflow-hidden group">
              <div className="absolute top-0 right-0 p-8 opacity-10 pointer-events-none group-hover:scale-110 transition-transform duration-700">
                <Brain className="size-32" />
              </div>
              <CardHeader className="relative z-10">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-blue-500/20 rounded-lg border border-blue-500/30">
                    <Brain className="size-5 text-blue-400" />
                  </div>
                  <div>
                    <CardTitle className="text-xl font-bold tracking-tight text-blue-100">
                      AI PERFORMANCE INSIGHTS
                    </CardTitle>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="relative z-10 pt-2">
                <div className="text-sm text-blue-100/80 leading-relaxed max-w-3xl font-medium">
                  {attempt.ai_analysis}
                </div>
              </CardContent>
            </Card>
          </motion.div>
        )}

        {/* Review header + filters */}
        <div className="space-y-4 py-4">
          <div className="flex items-center gap-4">
            <h2 className="text-xl font-black tracking-widest uppercase text-zinc-400">
              Question Review
            </h2>
            <div className="h-px bg-white/10 flex-1" />
            <button
              type="button"
              onClick={() => {
                setShowAllSolutions((v) => !v)
                setToggled({})
              }}
              className="text-xs font-bold uppercase tracking-widest text-blue-400 hover:text-blue-300"
            >
              {showAllSolutions ? "Collapse all solutions" : "Show all solutions"}
            </button>
          </div>
          <div className="flex flex-wrap gap-2">
            {(["all", "correct", "incorrect", "skipped"] as const).map((o) => (
              <button
                type="button"
                key={o}
                onClick={() => setOutcomeFilter(o)}
                className={cn(
                  "rounded-full border px-3 py-1 text-xs font-bold uppercase tracking-wider",
                  outcomeFilter === o
                    ? "border-blue-500 bg-blue-500/20 text-blue-300"
                    : "border-white/10 text-zinc-400 hover:bg-white/5",
                )}
              >
                {o === "all" ? `All (${totalQuestions})` : `${OUTCOME_STYLE[o].label} (${stats.byOutcome[o].count})`}
              </button>
            ))}
            {subjects.length > 1 && <span className="mx-1 w-px bg-white/10" />}
            {subjects.length > 1 &&
              ["all", ...subjects].map((s) => (
                <button
                  type="button"
                  key={s}
                  onClick={() => setSubjectFilter(s)}
                  className={cn(
                    "rounded-full border px-3 py-1 text-xs font-bold uppercase tracking-wider",
                    subjectFilter === s
                      ? "border-purple-500 bg-purple-500/20 text-purple-300"
                      : "border-white/10 text-zinc-400 hover:bg-white/5",
                  )}
                >
                  {s === "all" ? "All subjects" : s}
                </button>
              ))}
          </div>
        </div>

        {/* Question List */}
        <div className="space-y-6 pb-24">
          {visible.map(({ ans, index }) => {
            const outcome = outcomeOf(ans)
            const isNumeric = ans.question_type === "NUMERIC" || ans.question_type === "INTEGER"
            const correctLetters = (ans.correct_option || "").toUpperCase().split(",").map((x) => x.trim()).filter(Boolean)
            const selectedLetters = (ans.selected_option || "").toUpperCase().split(",").map((x) => x.trim()).filter(Boolean)
            const slow = stats.avg > 0 && (ans.time_spent_seconds || 0) > stats.avg * 1.6
            const hasSolution = Boolean(ans.solution_content || ans.solution_text)
            const open = solutionOpen(ans.id)
            return (
              <motion.div
                key={ans.id}
                id={`q-${ans.id}`}
                initial={{ opacity: 0, x: -20 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true }}
                className="scroll-mt-6"
              >
                <Card className="bg-zinc-900/50 border-white/5 overflow-hidden group hover:border-white/10 transition-colors">
                  <div className={cn("h-1 w-full", OUTCOME_STYLE[outcome].bar)} />

                  <CardHeader className="flex flex-row items-center justify-between pb-2 bg-white/2">
                    <div className="flex flex-wrap items-center gap-3">
                      <span className="text-lg font-black italic tracking-tighter opacity-60 group-hover:opacity-100 transition-opacity">
                        Q{index + 1}
                      </span>
                      <Badge className={cn("px-2 py-0 text-[10px] font-black uppercase", OUTCOME_STYLE[outcome].badge)}>
                        {OUTCOME_STYLE[outcome].label}
                      </Badge>
                      {ans.subject && (
                        <span className="text-[10px] font-bold uppercase tracking-widest text-zinc-500">
                          {ans.subject}
                          {ans.section ? ` · ${ans.section}` : ""}
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-4 text-[10px] font-bold tracking-widest uppercase">
                      <span className={cn("flex items-center gap-1.5", slow ? "text-amber-400" : "text-zinc-500")}>
                        <Clock className="size-3" />
                        {formatTime(ans.time_spent_seconds || 0)}
                        {slow && " · slow"}
                      </span>
                      <span className={ans.marks_obtained > 0 ? "text-emerald-400" : ans.marks_obtained < 0 ? "text-red-400" : "text-zinc-500"}>
                        {ans.marks_obtained > 0 ? "+" : ""}
                        {ans.marks_obtained} pts
                      </span>
                    </div>
                  </CardHeader>

                  <CardContent className="pt-6 space-y-6">
                    {isExtractedContent(ans.content) ? (
                      <div className="rounded-2xl border border-white/5 bg-white/3 p-6">
                        <QuestionContent
                          content={ans.content}
                          questionType={ans.question_type}
                          selected={selectedLetters}
                          correct={isNumeric ? undefined : correctLetters}
                          tone="dark"
                        />
                      </div>
                    ) : (
                      <LegacyQuestion ans={ans} index={index} />
                    )}

                    {ans.organic_metadata && (
                      <div className="bg-emerald-500/5 border border-emerald-500/10 p-4 rounded-xl flex gap-6 items-center">
                        <div className="p-3 bg-emerald-500/10 rounded-lg border border-emerald-500/20">
                          <Beaker className="size-5 text-emerald-400" />
                        </div>
                        <div className="flex-1 space-y-1">
                          <span className="text-[10px] font-black uppercase tracking-[0.2em] text-emerald-500/60 block">
                            Molecular Identity
                          </span>
                          <div className="flex items-baseline gap-4">
                            <span className="text-xl font-black text-emerald-100 italic">
                              {ans.organic_metadata.iupac_name}
                            </span>
                            {ans.organic_metadata.molecular_formula && (
                              <span className="text-emerald-400/80 font-mono text-sm border-l border-white/10 pl-4">
                                <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
                                  {`$${ans.organic_metadata.molecular_formula}$`}
                                </ReactMarkdown>
                              </span>
                            )}
                          </div>
                        </div>
                        {ans.organic_metadata.smiles && (
                          <div className="bg-white p-2 rounded-lg">
                            <SmilesRenderer smiles={ans.organic_metadata.smiles} width={100} height={100} />
                          </div>
                        )}
                      </div>
                    )}

                    {/* Your answer vs correct (always shown for numeric; summary for MCQ) */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div className="p-4 bg-white/2 border border-white/5 rounded-xl space-y-2">
                        <span className="text-[10px] font-black uppercase tracking-widest text-zinc-500">
                          Your Answer
                        </span>
                        <div
                          className={cn(
                            "text-xl font-black italic tracking-tighter",
                            outcome === "correct" ? "text-emerald-400" : outcome === "incorrect" ? "text-red-400" : "text-zinc-600",
                          )}
                        >
                          {ans.selected_option || ans.answer_text || "Not answered"}
                        </div>
                      </div>
                      <div className="p-4 bg-blue-500/5 border border-blue-500/10 rounded-xl space-y-2">
                        <span className="text-[10px] font-black uppercase tracking-widest text-blue-400">
                          Correct Answer
                        </span>
                        <div className="text-xl font-black italic tracking-tighter text-blue-100">
                          {ans.correct_option || ans.correct_answer_text || "N/A"}
                        </div>
                      </div>
                    </div>

                    {/* Solution */}
                    {hasSolution && (
                      <div className="space-y-3">
                        <button
                          type="button"
                          onClick={() => setToggled((prev) => ({ ...prev, [ans.id]: !open }))}
                          className="flex items-center gap-1 text-[10px] font-black text-blue-400 uppercase tracking-widest hover:text-blue-300"
                        >
                          {open ? "Hide" : "Show"} Solution
                          {open ? <ChevronUp className="size-3" /> : <ChevronDown className="size-3" />}
                        </button>
                        <AnimatePresence initial={false}>
                          {open && (
                            <motion.div
                              initial={{ height: 0, opacity: 0 }}
                              animate={{ height: "auto", opacity: 1 }}
                              exit={{ height: 0, opacity: 0 }}
                              className="overflow-hidden"
                            >
                              <div className="p-6 bg-linear-to-br from-blue-600/10 to-transparent border border-blue-500/20 rounded-2xl text-zinc-200 text-[15px] leading-relaxed">
                                <div className="flex items-center gap-2 text-blue-400 font-black text-xs uppercase tracking-[0.2em] mb-4">
                                  <Brain className="size-4" /> Solution
                                </div>
                                {ans.solution_content ? (
                                  <SolutionView solution={ans.solution_content} tone="dark" />
                                ) : (
                                  <RichPdfContent
                                    text={ans.solution_text || ""}
                                    token={SOLUTION_SNIPPET_TOKEN}
                                    pdfUrl={toAbsoluteBackendUrl(ans.question_paper_url)}
                                    pageNumber={ans.page_number}
                                    bbox={ans.solution_bbox}
                                  />
                                )}
                              </div>
                            </motion.div>
                          )}
                        </AnimatePresence>
                      </div>
                    )}

                    {ans.diagram_description && (
                      <div className="p-4 bg-zinc-800/50 border border-zinc-700 rounded-xl">
                        <div className="flex items-center gap-2 text-zinc-400 font-bold text-xs mb-1">
                          <Info className="size-3 text-blue-500" />
                          Diagram Context
                        </div>
                        <div className="text-xs text-zinc-300 leading-relaxed italic">
                          {ans.diagram_description}
                        </div>
                      </div>
                    )}
                  </CardContent>
                </Card>
              </motion.div>
            )
          })}
          {visible.length === 0 && (
            <p className="text-center text-zinc-500 py-12">No questions match this filter.</p>
          )}
        </div>
      </div>
    </div>
  )
}
