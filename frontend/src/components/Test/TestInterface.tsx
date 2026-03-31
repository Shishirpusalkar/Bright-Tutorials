import { useNavigate, useParams } from "@tanstack/react-router"
import {
  AlertTriangle,
  Beaker,
  Bookmark,
  Calculator,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  Clock,
  Info,
} from "lucide-react"
import { useCallback, useEffect, useMemo, useState } from "react"
import ReactMarkdown from "react-markdown"
import rehypeKatex from "rehype-katex"
import rehypeRaw from "rehype-raw"
import remarkMath from "remark-math"
import { TestsService } from "@/client"
import type { QuestionPublic, TestPublic } from "@/client/types.gen"
import SmilesRenderer from "@/components/Common/SmilesRenderer"
import {
  PdfSnippet,
  RichPdfContent,
  VISUAL_SNIPPET_TOKEN,
} from "@/components/Test/RichPdfContent"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { cn, toAbsoluteBackendUrl } from "@/lib/utils"
import "katex/dist/katex.min.css"

interface ExtendedQuestion extends QuestionPublic {
  organic_metadata?: {
    iupac_name?: string
    molecular_formula?: string
    smiles?: string
  } | null
  diagram_description?: string | null
  page_number?: number | null
  visual_bbox?: {
    x0: number
    y0: number
    x1: number
    y1: number
  } | null
}

// BTC Style Palette Colors (Dark Mode)
// BTC Style Palette Colors (Light Mode)
const PALETTE_COLORS = {
  not_visited: "bg-white text-zinc-500 border-zinc-200 hover:bg-zinc-50",
  not_answered: "bg-red-50 text-red-600 border-red-200",
  answered: "bg-green-50 text-green-600 border-green-200",
  marked_review: "bg-purple-50 text-purple-600 border-purple-200",
  answered_marked:
    "bg-purple-50 text-purple-700 ring-2 ring-green-500 ring-offset-1 ring-offset-white",
}

// Sub-component: Virtual Numeric Keypad
function NumericKeypad({
  value,
  onChange,
}: {
  value: string
  onChange: (val: string) => void
}) {
  const keys = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0", ".", "-"]

  const handleKeyClick = (key: string) => {
    if (key === "Clear") {
      onChange("")
    } else if (key === "Back") {
      onChange(value.slice(0, -1))
    } else {
      onChange(value + key)
    }
  }

  return (
    <div className="grid grid-cols-3 gap-2 w-full max-w-[240px] bg-white p-2 rounded-xl shadow-sm border border-zinc-200">
      {keys.map((key) => (
        <Button
          key={key}
          type="button"
          variant="ghost"
          className="bg-zinc-50 hover:bg-orange-50 hover:text-orange-600 text-xl font-bold h-12 shadow-sm border border-zinc-200 text-zinc-700"
          onClick={() => handleKeyClick(key)}
        >
          {key}
        </Button>
      ))}
      <Button
        type="button"
        variant="outline"
        className="h-12 shadow-sm bg-white text-zinc-600 border-zinc-200 hover:bg-zinc-50"
        onClick={() => handleKeyClick("Back")}
      >
        Back
      </Button>
      <Button
        type="button"
        variant="destructive"
        className="h-12 shadow-sm bg-red-50 text-red-600 hover:bg-red-100 border border-red-200"
        onClick={() => handleKeyClick("Clear")}
      >
        Clear
      </Button>
    </div>
  )
}

export default function TestInterface() {
  const { testId } = useParams({ strict: false }) as { testId: string }
  const navigate = useNavigate()

  // State
  const [test, setTest] = useState<TestPublic | null>(null)
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [markedReview, setMarkedReview] = useState<Record<string, boolean>>({})
  const [currentIndex, setCurrentIndex] = useState(0)
  const [tabSwitchCount, setTabSwitchCount] = useState(0)
  const [timeSpent, setTimeSpent] = useState<Record<string, number>>({})

  const [warningMessage, setWarningMessage] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [activeSubject, setActiveSubject] = useState<string>("")
  const [showDiagram, setShowDiagram] = useState(false)

  // New State for Instructions
  const [hasStarted, setHasStarted] = useState(false)
  const [instructionsRead, setInstructionsRead] = useState(false)
  // Timer state - in seconds
  const [timeLeft, setTimeLeft] = useState(0)

  useEffect(() => {
    const fetchTest = async () => {
      try {
        const data = (await TestsService.readTest({
          id: testId,
        })) as unknown as TestPublic
        setTest(data)

        // Initialize timer from duration (minutes -> seconds)
        if (data.duration_minutes) {
          setTimeLeft(data.duration_minutes * 60)
        }

        if (data.questions && data.questions.length > 0) {
          const firstSubject = data.questions[0].subject || "General"
          setActiveSubject(firstSubject)
        }
      } catch (err) {
        console.error("Failed to fetch test", err)
      } finally {
        setIsLoading(false)
      }
    }
    fetchTest()
  }, [testId])

  // Derived: Questions with normalized subject and ExtendedQuestion type
  const questionsWithSubject = useMemo(() => {
    if (!test?.questions) return []
    const sorted = [...test.questions].sort((a, b) => {
      const p1 = a.page_number || 0
      const p2 = b.page_number || 0
      if (p1 !== p2) return p1 - p2
      return (a.question_number || 0) - (b.question_number || 0)
    })
    return sorted.map((q) => {
      const eq = q as ExtendedQuestion
      const subj = eq.subject || "General"
      return { ...eq, subject: subj }
    })
  }, [test])

  // Derived: Subjects List
  const subjects = useMemo(() => {
    if (!questionsWithSubject) return []
    const unique = new Set(
      questionsWithSubject.map((q) => q.subject || "General"),
    )
    return Array.from(unique)
  }, [questionsWithSubject])

  // Derived: Current Question Object
  const currentQuestion: ExtendedQuestion | null = useMemo(() => {
    return (questionsWithSubject[currentIndex] as ExtendedQuestion) || null
  }, [questionsWithSubject, currentIndex])

  const renderQuestionTextWithSnippet = (question: ExtendedQuestion) => {
    return (
      <RichPdfContent
        text={question.question_text || ""}
        token={VISUAL_SNIPPET_TOKEN}
        pdfUrl={toAbsoluteBackendUrl(test?.question_paper_url) || ""}
        pageNumber={question.page_number}
        bbox={question.visual_bbox}
      />
    )
  }

  // Sync Active Subject with Current Question
  useEffect(() => {
    if (currentQuestion && hasStarted) {
      const subj = currentQuestion.subject || "General"
      if (activeSubject !== subj) {
        setActiveSubject(subj)
      }
      setShowDiagram(false)
    }
  }, [currentQuestion, activeSubject, hasStarted])

  // Navigation Helpers
  const jumpToSubject = (subject: string) => {
    const firstIdx = test?.questions?.findIndex(
      (q) => (q.subject || "General") === subject,
    )
    if (firstIdx !== undefined && firstIdx !== -1) {
      setCurrentIndex(firstIdx)
      setActiveSubject(subject)
    }
  }

  const handleAnswerChange = useCallback(
    (val: string) => {
      if (!currentQuestion) return
      setAnswers((prev) => ({ ...prev, [currentQuestion.id]: val }))
    },
    [currentQuestion],
  )

  const toggleReview = useCallback(() => {
    if (!currentQuestion) return
    setMarkedReview((prev) => ({
      ...prev,
      [currentQuestion.id]: !prev[currentQuestion.id],
    }))
  }, [currentQuestion])

  const clearResponse = useCallback(() => {
    if (!currentQuestion) return
    setAnswers((prev) => {
      const next = { ...prev }
      delete next[currentQuestion.id]
      return next
    })
  }, [currentQuestion])

  const handleSubmit = useCallback(async () => {
    if (!test || isSubmitting) return

    setIsSubmitting(true)
    try {
      const responses = Object.entries(answers).map(([questionId, answer]) => {
        const q = test.questions?.find((q) => q.id === questionId)
        const isNumeric =
          q?.question_type === "NUMERIC" || q?.question_type === "INTEGER"

        return {
          question_id: questionId,
          selected_option: !isNumeric ? answer : null,
          answer_text: isNumeric ? answer : null,
          time_spent_seconds: timeSpent[questionId] || 0,
        }
      })

      const payload = {
        test_id: testId,
        responses: responses,
        tab_switch_count: tabSwitchCount,
      }

      const token = localStorage.getItem("access_token")
      const response = await fetch(
        `${import.meta.env.VITE_API_URL || "http://localhost:8000"}/api/v1/attempts/submit`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify(payload),
        },
      )

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || "Submission failed")
      }

      const attempt = await response.json()
      navigate({
        to: "/attempts/$attemptId",
        params: { attemptId: attempt.id },
      })
    } catch (error: unknown) {
      console.error("Failed to submit test:", error)
      const errMsg = error instanceof Error ? error.message : "Unknown error"
      alert(`Failed to submit test: ${errMsg}`)
    } finally {
      setIsSubmitting(false)
    }
  }, [test, answers, timeSpent, testId, tabSwitchCount, isSubmitting, navigate])

  // Time Tracking & Countdown
  useEffect(() => {
    if (!hasStarted || timeLeft <= 0) return

    const timer = setInterval(() => {
      // Update countdown
      setTimeLeft((prev) => {
        if (prev <= 1) {
          clearInterval(timer)
          handleSubmit() // Auto submit
          return 0
        }
        return prev - 1
      })

      // Track time spent on current question
      if (currentQuestion) {
        setTimeSpent((prev) => ({
          ...prev,
          [currentQuestion.id]: (prev[currentQuestion.id] || 0) + 1,
        }))
      }
    }, 1000)
    return () => clearInterval(timer)
  }, [hasStarted, currentQuestion, timeLeft, handleSubmit])

  // Security
  useEffect(() => {
    if (!hasStarted) return

    const handleVisibilityChange = () => {
      if (document.hidden) {
        setTabSwitchCount((prev) => {
          const newCount = prev + 1
          setWarningMessage(
            `Warning: You have switched tabs ${newCount} times! Recorded.`,
          )
          return newCount
        })
      }
    }
    document.addEventListener("visibilitychange", handleVisibilityChange)
    return () =>
      document.removeEventListener("visibilitychange", handleVisibilityChange)
  }, [hasStarted])

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}:${secs.toString().padStart(2, "0")}`
  }

  // Prevent accidental refresh/close
  useEffect(() => {
    if (!hasStarted) return

    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      e.preventDefault()
      e.returnValue =
        "You have an active test session. Are you sure you want to leave? Your progress may not be saved."
      return e.returnValue
    }
    window.addEventListener("beforeunload", handleBeforeUnload)
    return () => window.removeEventListener("beforeunload", handleBeforeUnload)
  }, [hasStarted])

  if (isLoading)
    return (
      <div className="p-8 text-center text-zinc-400">
        <Clock className="animate-spin size-8 mx-auto mb-2" />
        Loading Test Environment...
      </div>
    )
  if (!test)
    return <div className="p-8 text-center text-red-400">Test not found.</div>

  // INSTRUCTIONS SCREEN
  if (!hasStarted) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-zinc-50 p-4 text-zinc-900">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_0%,rgba(0,0,0,0.02),transparent_50%)] pointer-events-none" />
        <Card className="w-full max-w-3xl shadow-xl border-zinc-200 bg-white relative z-10">
          <CardHeader className="bg-white border-b border-zinc-100 rounded-t-xl">
            <CardTitle className="flex justify-between items-center text-2xl">
              <div className="flex items-center gap-4">
                <img
                  src="/btc_logo.png"
                  alt="BTC Logo"
                  className="h-10 w-auto bg-zinc-100 p-1 rounded"
                />
                <span className="font-bold tracking-tight text-zinc-900">
                  {test.title}
                </span>
              </div>
              <span className="text-sm font-bold bg-zinc-100 px-3 py-1 rounded-full border border-zinc-200 text-zinc-600">
                Duration: {test.duration_minutes} Mins
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent className="p-8 space-y-6">
            <div className="space-y-4">
              <h3 className="text-xl font-bold border-b border-zinc-100 pb-2 text-zinc-800">
                General Instructions:
              </h3>
              <ul className="list-disc pl-5 space-y-3 text-zinc-600">
                <li>
                  The examination will comprise of Objective Type Questions.
                </li>
                <li>All questions are compulsory.</li>
                <li>
                  <strong className="text-zinc-900">Marking Scheme:</strong>{" "}
                  Correct Answer:{" "}
                  <span className="text-green-600 font-bold">+4</span>,
                  Incorrect Answer:{" "}
                  <span className="text-red-500 font-bold">-1</span> (or as
                  specified per question).
                </li>
                <li>
                  The clock will be set at the server. The countdown timer in
                  the top right corner will display the remaining time.
                </li>
                <li>
                  Navigate using the tabs (top left) or Question Palette
                  (right).
                </li>
                <li>
                  <strong className="text-zinc-900">Security:</strong> Switching
                  tabs is monitored and flagged.
                </li>
              </ul>
            </div>

            <Alert className="bg-amber-50 border-amber-200 text-amber-900">
              <Info className="h-4 w-4 text-amber-600" />
              <AlertTitle className="text-amber-800">Pro Tip</AlertTitle>
              <AlertDescription className="text-amber-700">
                Ensure a stable internet connection. Do not refresh the page.
              </AlertDescription>
            </Alert>

            <div className="flex items-center space-x-2 pt-4 border-t border-zinc-100">
              <Checkbox
                id="terms"
                checked={instructionsRead}
                onCheckedChange={(c) => setInstructionsRead(!!c)}
                className="border-zinc-300 data-[state=checked]:bg-blue-600 data-[state=checked]:border-blue-600"
              />
              <label
                htmlFor="terms"
                className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 text-zinc-500"
              >
                I have read and understood all the instructions.
              </label>
            </div>
          </CardContent>
          <CardFooter className="bg-zinc-50 border-t border-zinc-100 rounded-b-xl flex flex-col items-center gap-4 p-6">
            {test.scheduled_at && new Date(test.scheduled_at) > new Date() ? (
              <div className="w-full text-center space-y-3">
                <div className="p-4 bg-blue-50 border border-blue-100 rounded-xl text-blue-700 flex items-center justify-center gap-2">
                  <Clock className="size-5 animate-pulse" />
                  <span className="font-bold">
                    Test is scheduled to start on:{" "}
                    {new Date(test.scheduled_at).toLocaleString()}
                  </span>
                </div>
                <Button
                  type="button"
                  size="lg"
                  className="w-full sm:w-auto text-lg font-bold bg-zinc-200 cursor-not-allowed text-zinc-500 border border-zinc-300"
                  disabled={true}
                >
                  Waiting for scheduled time...
                </Button>
              </div>
            ) : (
              <Button
                type="button"
                size="lg"
                className="w-full sm:w-auto text-lg font-bold bg-blue-600 hover:bg-blue-700 text-white border-0 shadow-lg shadow-blue-500/20"
                disabled={!instructionsRead}
                onClick={() => setHasStarted(true)}
              >
                Start Test Now
              </Button>
            )}
          </CardFooter>
        </Card>
      </div>
    )
  }

  return (
    <div className="h-[calc(100vh-64px)] flex flex-col bg-zinc-50 text-zinc-800">
      {/* Top Header */}
      <header className="bg-white border-b border-zinc-200 px-4 py-2 flex justify-between items-center shadow-sm z-10 h-16">
        <div className="flex items-center gap-3">
          <div className="bg-blue-50 text-blue-600 p-1.5 rounded-lg border border-blue-100">
            <img src="/btc_logo.png" alt="BTC Logo" className="h-8 w-auto" />
          </div>
          <div>
            <h1 className="text-lg font-bold leading-none text-zinc-900 tracking-tight">
              {test.title}
            </h1>
            <p className="text-xs text-zinc-500 mt-1 font-medium">
              BTC Test Interface
            </p>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <div className="text-right">
            <span className="text-[10px] uppercase font-bold text-zinc-400 block tracking-widest">
              Time Left
            </span>
            <div
              className={cn(
                "text-xl font-mono font-bold flex items-center gap-1",
                timeLeft < 300 ? "text-red-600 animate-pulse" : "text-zinc-900",
              )}
            >
              <Clock className="size-4 opacity-50" />
              {formatTime(timeLeft)}
            </div>
          </div>
          <div className="h-8 w-px bg-zinc-200" />
          <div className="flex flex-col items-end">
            <span className="text-sm font-bold text-zinc-900">
              Student Candidate
            </span>
            <span className="text-xs text-zinc-500">ID: 2024-BTC-001</span>
          </div>
          <div className="size-10 bg-zinc-800 rounded-full overflow-hidden border border-white/10 shadow-sm">
            <img
              src={`https://api.dicebear.com/7.x/avataaars/svg?seed=Felix`}
              alt="Avatar"
            />
          </div>
        </div>
      </header>

      {warningMessage && (
        <Alert
          variant="destructive"
          className="mx-4 mt-2 py-2 bg-red-900/20 border-red-500/20 text-red-400"
        >
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Security Alert</AlertTitle>
          <AlertDescription>{warningMessage}</AlertDescription>
        </Alert>
      )}

      {/* Main Content Area */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left: Question Area */}
        <div className="flex-1 flex flex-col min-w-0 border-r border-zinc-200 bg-zinc-50">
          {/* Subject Tabs */}
          <div className="bg-white border-b border-zinc-200 px-4 py-2">
            <div className="flex gap-2 overflow-x-auto pb-1">
              {subjects.map((sub) => (
                <button
                  type="button"
                  key={sub}
                  onClick={() => jumpToSubject(sub)}
                  className={cn(
                    "px-4 py-2 text-sm font-bold rounded-t-lg border-b-2 transition-colors whitespace-nowrap",
                    activeSubject === sub
                      ? "border-blue-600 text-blue-600 bg-blue-50"
                      : "border-transparent text-zinc-500 hover:text-zinc-700 hover:bg-zinc-100",
                  )}
                >
                  {sub.toUpperCase()}
                </button>
              ))}
            </div>
          </div>

          {/* Question Header */}
          <div className="bg-white border-b border-zinc-200 px-6 py-3 flex justify-between items-center">
            <div className="flex items-center gap-3">
              <span className="font-bold text-lg text-zinc-900">
                Q{currentIndex + 1}.
              </span>
              <span className="text-xs font-mono bg-zinc-100 text-zinc-600 px-2 py-1 rounded border border-zinc-200">
                {currentQuestion?.question_type}
              </span>
              {currentQuestion?.section && (
                <span className="text-xs font-mono bg-purple-50 text-purple-600 px-2 py-1 rounded border border-purple-100">
                  {currentQuestion.section}
                </span>
              )}
            </div>
            <div className="text-sm font-bold text-green-600">
              +{currentQuestion?.marks || 1} Marks{" "}
              <span className="text-zinc-400 font-normal">
                / -{currentQuestion?.negative_marks || 0} Neg
              </span>
            </div>
          </div>

          {/* Question Scrollable Body */}
          <div className="flex-1 overflow-y-auto p-8 border-b border-zinc-200 custom-scrollbar">
            {currentQuestion ? (
              <div className="max-w-4xl">
                <div className="text-lg font-medium leading-relaxed mb-8 text-zinc-900 whitespace-pre-wrap">
                  {renderQuestionTextWithSnippet(currentQuestion)}
                </div>
                {/* Question Visual from PDF */}
                {currentQuestion.image_url && (
                  <div className="flex justify-center my-4">
                    <img
                      src={toAbsoluteBackendUrl(currentQuestion.image_url) || ""}
                      alt={`Question ${currentQuestion.question_number || currentIndex + 1} visual`}
                      className="max-w-[80%] rounded-lg border border-zinc-200 bg-white shadow-sm"
                    />
                  </div>
                )}
                {currentQuestion.has_visual &&
                  currentQuestion.page_number &&
                  currentQuestion.visual_bbox &&
                  !currentQuestion.image_url &&
                  !String(currentQuestion.question_text || "").includes(VISUAL_SNIPPET_TOKEN) && (
                    <PdfSnippet
                      url={toAbsoluteBackendUrl(test?.question_paper_url) || ""}
                      pageNumber={currentQuestion.page_number}
                      bbox={currentQuestion.visual_bbox}
                    />
                  )}

                {/* Organic Chemistry Metadata */}
                {currentQuestion.organic_metadata && (
                  <div className="mb-8 p-4 bg-emerald-50/50 border border-emerald-200 rounded-xl space-y-4">
                    <div className="flex items-center gap-2 text-emerald-700 font-bold text-sm">
                      <Beaker className="size-4" />
                      Chemical Structure Information
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      <div className="space-y-2">
                        {currentQuestion.organic_metadata.iupac_name && (
                          <div>
                            <span className="text-[10px] uppercase font-bold text-zinc-400 block tracking-widest">
                              IUPAC Name
                            </span>
                            <span className="text-zinc-800 font-medium">
                              {currentQuestion.organic_metadata.iupac_name}
                            </span>
                          </div>
                        )}
                        {currentQuestion.organic_metadata.molecular_formula && (
                          <div>
                            <span className="text-[10px] uppercase font-bold text-zinc-400 block tracking-widest">
                              Molecular Formula
                            </span>
                            <span className="text-zinc-800 font-medium tracking-wide">
                              <ReactMarkdown
                                remarkPlugins={[remarkMath]}
                                rehypePlugins={[rehypeKatex]}
                              >
                                {`$${currentQuestion.organic_metadata.molecular_formula}$`}
                              </ReactMarkdown>
                            </span>
                          </div>
                        )}
                        {currentQuestion.organic_metadata.smiles && (
                          <div className="pt-2">
                            <span className="text-[10px] uppercase font-bold text-zinc-400 block tracking-widest mb-1">
                              SMILES Notation
                            </span>
                            <code className="text-xs bg-zinc-100 p-1 rounded border border-zinc-200 block overflow-x-auto">
                              {currentQuestion.organic_metadata.smiles}
                            </code>
                          </div>
                        )}
                      </div>
                      {currentQuestion.organic_metadata.smiles && (
                        <div className="flex justify-center">
                          <SmilesRenderer
                            smiles={currentQuestion.organic_metadata.smiles}
                            width={200}
                            height={200}
                          />
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* Diagram Description (Collapsible) */}
                {currentQuestion.diagram_description && (
                  <div className="mb-8 border border-zinc-200 rounded-xl overflow-hidden bg-white shadow-sm">
                    <button
                      type="button"
                      onClick={() => setShowDiagram(!showDiagram)}
                      className="w-full flex items-center justify-between p-4 hover:bg-zinc-50 transition-colors text-left"
                    >
                      <div className="flex items-center gap-2 text-zinc-700 font-bold text-sm">
                        <Info className="size-4 text-blue-500" />
                        View Diagram Description
                      </div>
                      {showDiagram ? (
                        <ChevronUp className="size-4" />
                      ) : (
                        <ChevronDown className="size-4" />
                      )}
                    </button>
                    {showDiagram && (
                      <div className="p-4 border-t border-zinc-100 bg-zinc-50/50 text-sm text-zinc-600 leading-relaxed italic">
                        {currentQuestion.diagram_description}
                      </div>
                    )}
                  </div>
                )}

                {currentQuestion.question_type === "NUMERIC" ||
                  currentQuestion.question_type === "INTEGER" ? (
                  <div className="space-y-6">
                    <Label className="text-base font-semibold text-zinc-700">
                      Your Answer:
                    </Label>
                    <div className="flex flex-col md:flex-row gap-8 items-start">
                      <div className="space-y-4">
                        <div className="flex items-center gap-4">
                          <Input
                            type="text"
                            placeholder="Answer..."
                            className="max-w-xs text-3xl p-6 font-mono border-2 border-zinc-300 focus:ring-blue-500 focus:border-blue-500 text-blue-600 bg-white placeholder:text-zinc-400"
                            value={answers[currentQuestion.id] || ""}
                            onChange={(e) => {
                              const val = e.target.value.replace(
                                /[^0-9.-]/g,
                                "",
                              )
                              handleAnswerChange(val)
                            }}
                          />
                          <Calculator className="text-blue-500 size-8 animate-pulse opacity-50" />
                        </div>
                        <p className="text-xs text-zinc-400 max-w-xs italic">
                          Use the virtual keypad to enter your response.
                        </p>
                      </div>

                      <div className="bg-zinc-50 p-4 border border-zinc-200 rounded-2xl shadow-sm">
                        <NumericKeypad
                          value={answers[currentQuestion.id] || ""}
                          onChange={handleAnswerChange}
                        />
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {["A", "B", "C", "D"].map((opt) => {
                      const q = currentQuestion as any
                      let optionText = q[`option_${opt.toLowerCase()}`]

                      // Fallback to options dict if flat field is empty
                      if (!optionText && q.options) {
                        optionText =
                          q.options[opt] || q.options[opt.toLowerCase()]
                      }

                      if (!optionText) return null

                      return (
                        <button
                          type="button"
                          key={opt}
                          onClick={() => handleAnswerChange(opt)}
                          className={cn(
                            "w-full text-left flex items-center space-x-4 border border-zinc-200 p-4 rounded-xl transition-all cursor-pointer hover:bg-zinc-50",
                            answers[currentQuestion.id] === opt
                              ? "border-blue-500 bg-blue-50 shadow-[0_0_15px_rgba(59,130,246,0.1)]"
                              : "border-zinc-200 bg-white",
                          )}
                        >
                          <div
                            className={cn(
                              "size-8 rounded-full flex items-center justify-center font-bold border shrink-0 transition-all",
                              answers[currentQuestion.id] === opt
                                ? "bg-blue-600 border-blue-500 text-white"
                                : "border-zinc-300 text-zinc-500 bg-zinc-50",
                            )}
                          >
                            {opt}
                          </div>
                          <div className="text-lg font-medium prose-p:my-0 text-zinc-800">
                            <ReactMarkdown
                              remarkPlugins={[remarkMath]}
                              rehypePlugins={[rehypeKatex, rehypeRaw]}
                            >
                              {optionText}
                            </ReactMarkdown>
                          </div>
                        </button>
                      )
                    })}
                  </div>
                )}

                {/* Solution is hidden during test */}
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center h-full text-zinc-600">
                <Info className="size-12 mb-4 opacity-50" />
                <p>No Question Loaded.</p>
              </div>
            )}
          </div>

          {/* Bottom Action Footer */}
          <div className="border-t border-zinc-200 bg-white/90 backdrop-blur p-4 flex justify-between items-center shadow-[0_-5px_20px_rgba(0,0,0,0.05)] z-20">
            <div className="flex gap-3">
              <Button
                variant="outline"
                onClick={toggleReview}
                className={cn(
                  "border-zinc-300 bg-white hover:bg-zinc-50 text-zinc-600",
                  markedReview[currentQuestion?.id || ""]
                    ? "border-purple-500 text-purple-600 bg-purple-50 hover:bg-purple-100"
                    : "",
                )}
              >
                <Bookmark
                  className="size-4 mr-2"
                  fill={
                    markedReview[currentQuestion?.id || ""]
                      ? "currentColor"
                      : "none"
                  }
                />
                {markedReview[currentQuestion?.id || ""]
                  ? "Marked"
                  : "Mark for Review"}
              </Button>
              <Button
                variant="ghost"
                onClick={clearResponse}
                className="text-zinc-500 hover:text-zinc-700 hover:bg-zinc-100"
              >
                Clear
              </Button>
            </div>
            <div className="flex gap-3">
              <Button
                variant="secondary"
                onClick={() => setCurrentIndex((prev) => Math.max(0, prev - 1))}
                disabled={currentIndex === 0}
                className="px-6 bg-zinc-100 text-zinc-600 hover:bg-zinc-200 border border-zinc-200"
              >
                <ChevronLeft className="size-4 mr-1" /> Prev
              </Button>
              <Button
                onClick={() =>
                  setCurrentIndex((prev) =>
                    Math.min((test?.questions?.length || 1) - 1, prev + 1),
                  )
                }
                className="px-8 bg-blue-600 hover:bg-blue-700 text-white font-bold shadow-lg shadow-blue-500/20"
              >
                Save & Next <ChevronRight className="size-4 ml-1" />
              </Button>
            </div>
          </div>
        </div>

        {/* Right: Question Palette Sidebar */}
        <div className="w-80 bg-white border-l border-zinc-200 flex-col shadow-xl z-20 hidden md:flex">
          <div className="p-4 border-b border-zinc-200 bg-white">
            <h3 className="font-bold text-sm uppercase tracking-wider text-zinc-500">
              Question Palette
            </h3>
          </div>

          <div className="flex-1 overflow-y-auto p-4 custom-scrollbar">
            {/* Filter Palette by Subject */}
            {subjects.map((subject) => {
              const subjectQuestions = (test?.questions || [])
                .map((q, idx) => ({ ...q, globalIndex: idx }))
                .filter((q) => (q.subject || "General") === subject)
              if (subjectQuestions.length === 0) return null

              return (
                <div key={subject} className="mb-6">
                  <h4 className="text-xs font-black text-zinc-600 uppercase mb-3 px-1 flex justify-between">
                    {subject}
                    <span className="bg-zinc-100 text-zinc-500 px-1.5 rounded border border-zinc-200">
                      {subjectQuestions.length}
                    </span>
                  </h4>
                  <div className="grid grid-cols-5 gap-2">
                    {subjectQuestions.map((q) => {
                      const isAnswered = !!answers[q.id]
                      const isMarked = !!markedReview[q.id]
                      const isCurrent = currentIndex === q.globalIndex

                      let cls = PALETTE_COLORS.not_visited
                      if (isAnswered && isMarked)
                        cls = PALETTE_COLORS.answered_marked
                      else if (isAnswered) cls = PALETTE_COLORS.answered
                      else if (isMarked) cls = PALETTE_COLORS.marked_review

                      return (
                        <button
                          type="button"
                          key={q.id}
                          onClick={() => setCurrentIndex(q.globalIndex)}
                          className={cn(
                            "aspect-square rounded flex items-center justify-center text-xs font-bold transition-all border",
                            cls,
                            isCurrent &&
                            "ring-2 ring-blue-500 ring-offset-2 ring-offset-white scale-110 z-10 border-blue-500",
                          )}
                        >
                          {q.globalIndex + 1}
                        </button>
                      )
                    })}
                  </div>
                </div>
              )
            })}
          </div>

          <div className="p-4 border-t border-zinc-200 bg-zinc-50">
            <div className="grid grid-cols-2 gap-2 text-[10px] text-zinc-500 font-medium mb-4">
              <div className="flex items-center gap-2">
                <div
                  className={`size-3 rounded ${PALETTE_COLORS.answered.split(" ")[0]}`}
                />{" "}
                Answered
              </div>
              <div className="flex items-center gap-2">
                <div
                  className={`size-3 rounded ${PALETTE_COLORS.not_answered.split(" ")[0]}`}
                />{" "}
                Not Answered
              </div>
              <div className="flex items-center gap-2">
                <div
                  className={`size-3 rounded ${PALETTE_COLORS.not_visited.split(" ")[0]} border border-gray-300`}
                />{" "}
                Not Visited
              </div>
              <div className="flex items-center gap-2">
                <div
                  className={`size-3 rounded ${PALETTE_COLORS.marked_review.split(" ")[0]}`}
                />{" "}
                Review
              </div>
            </div>
            <Button
              type="button"
              className="w-full bg-red-600 hover:bg-red-700 shadow-lg text-white font-bold h-12 text-lg"
              onClick={handleSubmit}
              disabled={isSubmitting}
            >
              {isSubmitting ? "Submitting..." : "Submit Test"}
            </Button>
          </div>
        </div>
      </div>
    </div >
  )
}
