import { useParams } from "@tanstack/react-router"
import { motion, AnimatePresence } from "framer-motion"
import { 
  Beaker, 
  Brain, 
  Clock, 
  Info, 
  ChevronDown, 
  ChevronUp, 
  Trophy, 
  Target, 
  Zap 
} from "lucide-react"
import { useEffect, useState } from "react"
import ReactMarkdown from "react-markdown"
import rehypeKatex from "rehype-katex"
import remarkMath from "remark-math"
import SmilesRenderer from "@/components/Common/SmilesRenderer"
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
import { cn } from "@/lib/utils"
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

// Fetch helper (simulated for now, replace with actual fetch or client)
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

// Helper to format time
const formatTime = (seconds: number) => {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}m ${s}s`
}

export default function TestAnalysis() {
  const { attemptId } = useParams({ from: "/_layout/attempts/$attemptId" })
  const [attempt, setAttempt] = useState<AttemptPublic | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [expandedSolutions, setExpandedSolutions] = useState<Record<string, boolean>>({})

  const toggleSolution = (questionId: string) => {
    setExpandedSolutions(prev => ({
      ...prev,
      [questionId]: !prev[questionId]
    }))
  }

  useEffect(() => {
    if (attemptId) {
      fetchAttempt(attemptId)
        .then(setAttempt)
        .catch((err) => setError(err.message))
        .finally(() => setLoading(false))
    }
  }, [attemptId])

  if (loading) return <div className="p-8 text-center">Loading analysis...</div>
  if (error)
    return <div className="p-8 text-center text-red-500">Error: {error}</div>
  if (!attempt) return <div className="p-8 text-center">Attempt not found</div>

  const totalQuestions = attempt.answers.length
  const correctAnswers = attempt.answers.filter((a) => a.is_correct).length
  const incorrectAnswers = attempt.answers.filter(
    (a) => !a.is_correct && (a.selected_option || a.answer_text),
  ).length

  // Calculate accuracy
  const attemptedCount = correctAnswers + incorrectAnswers
  const accuracy =
    attemptedCount > 0 ? Math.round((correctAnswers / attemptedCount) * 100) : 0

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
                : "bg-zinc-800 text-zinc-400"
            )}
          >
            {attempt.status}
          </Badge>
        </motion.div>

        {/* Overview Grid */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {[
            { label: "Total Score", value: attempt.score, icon: Trophy, color: "text-blue-400" },
            { label: "Accuracy", value: `${accuracy}%`, icon: Target, color: "text-emerald-400" },
            { label: "Tab Switches", value: attempt.tab_switch_count, icon: Zap, color: "text-amber-400" },
            { label: "Attempted", value: `${attemptedCount} / ${totalQuestions}`, icon: Info, color: "text-zinc-400" },
          ].map((stat, i) => (
            <motion.div
              key={stat.label}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.1 }}
            >
              <Card className="bg-white/5 border-white/10 backdrop-blur-xl hover:bg-white/10 transition-all duration-300 group">
                <CardHeader className="pb-2 flex flex-row items-center justify-between space-y-0">
                  <span className="text-[10px] font-bold uppercase tracking-widest text-zinc-500">
                    {stat.label}
                  </span>
                  <stat.icon className={cn("size-4 opacity-50 group-hover:opacity-100 transition-opacity", stat.color)} />
                </CardHeader>
                <CardContent>
                  <div className="text-3xl font-black tracking-tighter italic">
                    {stat.value}
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>

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
                {Object.entries(attempt.section_results).map(
                  ([subject, sections]) => (
                    <div
                      key={subject}
                      className="p-4 border border-white/10 rounded-lg bg-white/5"
                    >
                      <h4 className="font-bold text-blue-400 uppercase mb-3 border-b border-white/10 pb-1">
                        {subject}
                      </h4>
                      <div className="space-y-2">
                        {Object.entries(sections).map(([section, score]) => (
                          <div
                            key={section}
                            className="flex justify-between items-center text-sm"
                          >
                            <span className="text-zinc-400">
                              {section}
                            </span>
                            <span
                              className={cn(
                                "font-bold",
                                (score as number) >= 0
                                  ? "text-emerald-400"
                                  : "text-red-400",
                              )}
                            >
                              {score as number} Marks
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  ),
                )}
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
                    <CardDescription className="text-blue-300/60 text-xs font-medium uppercase tracking-widest mt-1">
                      Synthesized by Google Gemini
                    </CardDescription>
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

        {/* List Header */}
        <div className="flex items-center gap-4 py-4">
          <h2 className="text-xl font-black tracking-widest uppercase text-zinc-400">
            Question Review
          </h2>
          <div className="h-px bg-white/10 flex-1" />
        </div>

        {/* Question List */}
        <div className="space-y-6 pb-24">
          {attempt.answers.map((ans, index) => (
            <motion.div
              key={ans.id}
              initial={{ opacity: 0, x: -20 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true }}
            >
              <Card className="bg-zinc-900/50 border-white/5 overflow-hidden group hover:border-white/10 transition-colors">
                {/* Question Header Bar */}
                <div className={cn(
                  "h-1 w-full",
                  ans.is_correct ? "bg-emerald-500" : (ans.selected_option || ans.answer_text) ? "bg-red-500" : "bg-zinc-700"
                )} />

                <CardHeader className="flex flex-row items-center justify-between pb-2 bg-white/2">
                  <div className="flex items-center gap-3">
                    <span className="text-lg font-black italic tracking-tighter opacity-30 group-hover:opacity-100 transition-opacity">
                      Q{index + 1}
                    </span>
                    {ans.is_correct ? (
                      <Badge className="bg-emerald-500/10 text-emerald-500 border-emerald-500/20 px-2 py-0 text-[10px] font-black uppercase">
                        Correct
                      </Badge>
                    ) : (ans.selected_option || ans.answer_text) ? (
                      <Badge className="bg-red-500/10 text-red-500 border-red-500/20 px-2 py-0 text-[10px] font-black uppercase">
                        Incorrect
                      </Badge>
                    ) : (
                      <Badge className="bg-zinc-800 text-zinc-500 border-zinc-700 px-2 py-0 text-[10px] font-black uppercase">
                        Skipped
                      </Badge>
                    )}
                  </div>
                  <div className="flex items-center gap-4 text-[10px] font-bold text-zinc-500 tracking-widest uppercase">
                    <div className="flex items-center gap-1.5">
                      <Clock className="size-3" />
                      {formatTime(ans.time_spent_seconds)}
                    </div>
                  </div>
                </CardHeader>

                <CardContent className="pt-6 space-y-6">
                  {/* Question Text */}
                  <div className="bg-white/3 p-6 rounded-2xl border border-white/5">
                    <div className="text-zinc-100 leading-relaxed font-medium prose prose-invert max-w-none">
                      <RichPdfContent
                        text={ans.question_text || "Question text not available"}
                        token={VISUAL_SNIPPET_TOKEN}
                        pdfUrl={ans.question_paper_url}
                        pageNumber={ans.page_number}
                        bbox={ans.visual_bbox}
                      />
                    </div>
                    {ans.image_url &&
                      !String(ans.question_text || "").includes(VISUAL_SNIPPET_TOKEN) && (
                        <div className="mt-4 flex justify-center">
                          <img
                            src={ans.image_url}
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
                            url={ans.question_paper_url || ""}
                            pageNumber={ans.page_number}
                            bbox={ans.visual_bbox}
                          />
                        </div>
                      )}
                  </div>

                  {/* Chemical Context if any */}
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
                        <div className="bg-white p-2 rounded-lg grayscale opacity-80 group-hover:grayscale-0 group-hover:opacity-100 transition-all">
                          <SmilesRenderer smiles={ans.organic_metadata.smiles} width={100} height={100} />
                        </div>
                      )}
                    </div>
                  )}

                  {/* Diagram Description */}
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

                  {/* Comparisons */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="p-4 bg-white/2 border border-white/5 rounded-xl space-y-2">
                       <span className="text-[10px] font-black uppercase tracking-widest text-zinc-500">
                        Your Performance
                      </span>
                      <div className="flex items-center justify-between">
                        <span className={cn(
                          "text-xl font-black italic tracking-tighter",
                          ans.is_correct ? "text-emerald-400" : (ans.selected_option || ans.answer_text) ? "text-red-400" : "text-zinc-600"
                        )}>
                          {ans.selected_option || ans.answer_text || "Skipped"}
                        </span>
                        <Badge className={cn(
                          "font-black border-0",
                          ans.marks_obtained > 0 ? "bg-emerald-500/20 text-emerald-400" : "bg-red-500/20 text-red-400"
                        )}>
                          {ans.marks_obtained > 0 ? "+" : ""}{ans.marks_obtained} Pts
                        </Badge>
                      </div>
                    </div>

                    <button 
                      type="button"
                      className="p-4 bg-blue-500/5 border border-blue-500/10 rounded-xl space-y-2 group/sol cursor-pointer hover:bg-blue-500/10 transition-colors w-full text-left"
                      onClick={() => toggleSolution(ans.id)}
                    >
                      <div className="flex justify-between items-center">
                        <span className="text-[10px] font-black uppercase tracking-widest text-blue-400">
                          Correct Outcome
                        </span>
                        {ans.solution_text && (
                          <div className="flex items-center gap-1 text-[10px] font-black text-blue-500 uppercase tracking-widest">
                            {expandedSolutions[ans.id] ? "Hide" : "Review"} Solution
                            {expandedSolutions[ans.id] ? <ChevronUp className="size-3" /> : <ChevronDown className="size-3" />}
                          </div>
                        )}
                      </div>
                      <div className="text-xl font-black italic tracking-tighter text-blue-100">
                         {ans.correct_option || ans.correct_answer_text || "N/A"}
                      </div>
                    </button>
                  </div>

                  {/* Expanded Solution */}
                  <AnimatePresence>
                    {expandedSolutions[ans.id] && ans.solution_text && (
                      <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: "auto", opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        className="overflow-hidden"
                      >
                        <div className="mt-4 p-6 bg-linear-to-br from-blue-600/10 to-transparent border border-blue-500/20 rounded-2xl relative">
                          <div className="flex items-center gap-2 text-blue-400 font-black text-xs uppercase tracking-[0.2em] mb-4">
                            <Brain className="size-4" /> Comprehensive Solution Extraction
                          </div>
                          <div className="text-zinc-200 text-sm leading-relaxed font-medium prose prose-blue prose-invert max-w-none">
                            <RichPdfContent
                              text={ans.solution_text}
                              token={SOLUTION_SNIPPET_TOKEN}
                              pdfUrl={ans.question_paper_url}
                              pageNumber={ans.page_number}
                              bbox={ans.solution_bbox}
                            />
                          </div>
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>
      </div>
    </div>
  )
}
