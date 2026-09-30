import { AlertTriangle, CheckCircle2, Save } from "lucide-react"
import { useEffect, useMemo, useState } from "react"
import {
  type ExtractedContent,
  isExtractedContent,
  QuestionContent,
  type SolutionContent,
  SolutionView,
} from "@/components/Test/QuestionContent"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"

type ReviewQuestion = {
  id: string
  question_text: string
  question_type: string
  question_number: number | null
  subject: string | null
  section: string | null
  marks: number
  options: Record<string, string> | null
  content: ExtractedContent | null
  correct_option: string | null
  answer_source: string | null
  solution_text: string | null
  solution_content: SolutionContent | null
  needs_review: boolean
  review_reasons: string[] | null
}

type ReviewResponse = {
  test_id: string
  title: string
  parsing_report: Record<string, any> | null
  questions: ReviewQuestion[]
}

const API = import.meta.env.VITE_API_URL || "http://localhost:8000"

const SOURCE_LABEL: Record<string, string> = {
  solution_marker: "from solution copy",
  highlighted_option: "highlighted in solution copy",
  answer_key: "from answer key",
  solution_text: "read from solution",
  teacher_key: "from your answer key",
  teacher: "set by you",
}

function authHeaders(): HeadersInit {
  return { Authorization: `Bearer ${localStorage.getItem("access_token")}` }
}

function AnswerEditor({
  testId,
  question,
  onSaved,
}: {
  testId: string
  question: ReviewQuestion
  onSaved: (q: ReviewQuestion) => void
}) {
  const [value, setValue] = useState(question.correct_option || "")
  const [saving, setSaving] = useState(false)
  const dirty = value.trim().toUpperCase() !== (question.correct_option || "").toUpperCase()

  const save = async () => {
    setSaving(true)
    try {
      const res = await fetch(`${API}/api/v1/tests/${testId}/questions/${question.id}`, {
        method: "PATCH",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify({ correct_option: value }),
      })
      if (!res.ok) throw new Error((await res.json()).detail || "Save failed")
      onSaved(await res.json())
    } catch (e) {
      alert(e instanceof Error ? e.message : "Save failed")
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-xs text-zinc-400">Answer</span>
      <Input
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder={question.question_type === "NUMERIC" ? "e.g. 12.5" : "e.g. B or A,C"}
        className="h-8 w-32 bg-zinc-900 border-white/10 text-sm font-mono"
      />
      <Button
        size="sm"
        disabled={!dirty || !value.trim() || saving}
        onClick={save}
        className="h-8 bg-blue-600 hover:bg-blue-700 text-white"
      >
        <Save className="size-3.5 mr-1" /> Save
      </Button>
      {question.answer_source && (
        <span className="text-[11px] text-zinc-500">
          {SOURCE_LABEL[question.answer_source] || question.answer_source}
        </span>
      )}
    </div>
  )
}

export default function ExtractionReview({ testId }: { testId: string }) {
  const [data, setData] = useState<ReviewResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [onlyFlagged, setOnlyFlagged] = useState(false)

  useEffect(() => {
    fetch(`${API}/api/v1/tests/${testId}/review`, { headers: authHeaders() })
      .then(async (r) => {
        if (!r.ok) throw new Error((await r.json()).detail || "Failed to load questions")
        return r.json()
      })
      .then(setData)
      .catch((e) => setError(e.message))
  }, [testId])

  const flagged = useMemo(() => data?.questions.filter((q) => q.needs_review).length ?? 0, [data])

  if (error) return <p className="py-8 text-center text-red-400">{error}</p>
  if (!data) return <p className="py-8 text-center text-zinc-500">Loading questions...</p>
  if (!data.questions.length)
    return <p className="text-center text-zinc-500 py-8">No questions found for this test.</p>

  const extraction = data.parsing_report?.extraction
  const shown = data.questions.filter((q) => !onlyFlagged || q.needs_review)

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-white/10 bg-zinc-900/60 p-3 text-sm">
        <div className="flex flex-wrap gap-4 text-zinc-300">
          <span>{data.questions.length} questions</span>
          {extraction && <span>{extraction.figures} figures</span>}
          {extraction && <span>{extraction.with_solution} solutions</span>}
          <span className={flagged ? "text-amber-400" : "text-emerald-400"}>
            {flagged ? `${flagged} need review` : "All checks passed"}
          </span>
        </div>
        {flagged > 0 && (
          <label className="flex items-center gap-2 text-xs text-zinc-400">
            <input
              type="checkbox"
              checked={onlyFlagged}
              onChange={(e) => setOnlyFlagged(e.target.checked)}
            />
            Show only flagged
          </label>
        )}
      </div>

      {shown.map((q) => {
        const index = data.questions.indexOf(q)
        const correct = (q.correct_option || "").split(",").map((s) => s.trim()).filter(Boolean)
        return (
          <div
            key={q.id}
            className={cn(
              "rounded-xl border p-4 space-y-4",
              q.needs_review ? "border-amber-500/40 bg-amber-500/5" : "border-white/10 bg-zinc-800/40",
            )}
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2 text-sm font-semibold text-zinc-200">
                Q{index + 1}
                <span className="text-xs font-normal text-zinc-500">
                  {q.subject} · {q.section} · {q.question_type} · {q.marks} mark(s)
                </span>
              </div>
              {q.needs_review ? (
                <span className="flex items-center gap-1 text-xs text-amber-400">
                  <AlertTriangle className="size-3.5" /> {(q.review_reasons || []).join("; ")}
                </span>
              ) : (
                <CheckCircle2 className="size-4 text-emerald-500" />
              )}
            </div>

            {isExtractedContent(q.content) ? (
              <div className="rounded-lg bg-white p-4">
                <QuestionContent
                  content={q.content}
                  questionType={q.question_type}
                  correct={q.question_type === "NUMERIC" || q.question_type === "INTEGER" ? undefined : correct}
                  tone="light"
                />
              </div>
            ) : (
              <p className="text-sm text-zinc-300 whitespace-pre-wrap">{q.question_text}</p>
            )}

            <AnswerEditor
              testId={testId}
              question={q}
              onSaved={(updated) =>
                setData((prev) =>
                  prev
                    ? { ...prev, questions: prev.questions.map((x) => (x.id === updated.id ? updated : x)) }
                    : prev,
                )
              }
            />

            {q.solution_content && (
              <details className="rounded-lg border border-white/10 bg-zinc-900/60 p-3">
                <summary className="cursor-pointer text-xs font-semibold text-blue-400">Solution</summary>
                <div className="pt-3 text-sm text-zinc-200">
                  <SolutionView solution={q.solution_content} tone="dark" />
                </div>
              </details>
            )}
          </div>
        )
      })}
    </div>
  )
}
