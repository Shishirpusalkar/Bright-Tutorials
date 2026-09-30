import { Check, Eye, EyeOff, X, ZoomIn } from "lucide-react"
import { useState } from "react"
import ReactMarkdown from "react-markdown"
import rehypeKatex from "rehype-katex"
import remarkGfm from "remark-gfm"
import remarkMath from "remark-math"
import "katex/dist/katex.min.css"
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog"
import { cn, toAbsoluteBackendUrl } from "@/lib/utils"

/**
 * Renders questions produced by the layout extraction engine
 * (backend/app/services/extraction). Text is Markdown + LaTeX; figures are
 * cropped PNGs referenced from the text by tokens like [[F1]] (stem),
 * listed per option ("A1"), or [[S1]] in solutions.
 */

export type ExtractedFigure = {
  url: string
  w: number
  h: number
  layout?: "block" | "inline"
  part?: "stem" | "option" | "solution"
  option?: string | null
}

export type ExtractedContent = {
  v: number
  stem: { text: string; image?: string | null }
  options: { label: string; text: string; figures: string[] }[]
  figures: Record<string, ExtractedFigure>
  crop?: string | null
  source?: { page?: number; number?: number; global_number?: number }
}

export type SolutionContent = {
  text?: string | null
  image?: string | null
  crop?: string | null
  figures?: Record<string, ExtractedFigure>
}

type Tone = "light" | "dark"

const TOKEN_RE = /\[\[([A-Z]\d+)\]\]/g

export function isExtractedContent(value: unknown): value is ExtractedContent {
  return Boolean(value && typeof value === "object" && (value as ExtractedContent).v === 2)
}

// Crops are rendered at 216 dpi (3 px per PDF point). 0.45 would be exact
// print size; figures are shown ~1.6x larger so labels, subscripts and thin
// bonds stay readable on phones and projectors.
const PRINT_SCALE = 0.72

function FigureImage({
  fig,
  alt,
  tone,
  inline = false,
}: {
  fig: ExtractedFigure
  alt: string
  tone: Tone
  inline?: boolean
}) {
  const [zoom, setZoom] = useState(false)
  const src = toAbsoluteBackendUrl(fig.url) || ""
  const width = Math.max(96, Math.round(fig.w * PRINT_SCALE))
  return (
    <>
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation()
          setZoom(true)
        }}
        className={cn(
          "group relative rounded-lg border bg-white p-1.5 shadow-sm transition hover:shadow-md",
          tone === "dark" ? "border-white/10" : "border-zinc-200",
          inline ? "float-right ml-4 mb-2 max-w-[45%]" : "my-3 block max-w-full",
        )}
        title="Tap to enlarge"
      >
        <img
          src={src}
          alt={alt}
          loading="lazy"
          style={{ width: `${width}px` }}
          className="h-auto max-w-full select-none"
          draggable={false}
        />
        <ZoomIn className="absolute right-1 top-1 size-4 text-zinc-400 opacity-0 transition group-hover:opacity-100" />
      </button>
      <Dialog open={zoom} onOpenChange={setZoom}>
        <DialogContent className="max-w-[95vw] w-fit bg-white p-4">
          <DialogTitle className="sr-only">{alt}</DialogTitle>
          <img src={src} alt={alt} className="max-h-[85vh] w-auto max-w-full" />
        </DialogContent>
      </Dialog>
    </>
  )
}

function Markdown({ text, tone }: { text: string; tone: Tone }) {
  if (!text.trim()) return null
  return (
    <div
      className={cn(
        "max-w-none leading-relaxed [&_p]:my-1.5 [&_table]:my-2 [&_table]:border-collapse [&_td]:border [&_th]:border [&_td]:px-2 [&_th]:px-2 [&_td]:py-1 [&_th]:py-1 [&_th]:font-semibold [&_ul]:list-disc [&_ol]:list-decimal [&_ul]:pl-5 [&_ol]:pl-5 [&_.katex-display]:overflow-x-auto [&_.katex-display]:overflow-y-hidden",
        tone === "dark" ? "[&_td]:border-white/15 [&_th]:border-white/15" : "[&_td]:border-zinc-300 [&_th]:border-zinc-300",
      )}
    >
      <ReactMarkdown remarkPlugins={[remarkMath, remarkGfm]} rehypePlugins={[rehypeKatex]}>
        {text}
      </ReactMarkdown>
    </div>
  )
}

/** Markdown with [[F1]] figure tokens swapped for the cropped images. */
export function RichText({
  text,
  figures,
  tone = "light",
}: {
  text: string
  figures: Record<string, ExtractedFigure>
  tone?: Tone
}) {
  const parts: { kind: "text" | "fig"; value: string }[] = []
  let last = 0
  for (const m of text.matchAll(TOKEN_RE)) {
    const idx = m.index ?? 0
    if (idx > last) parts.push({ kind: "text", value: text.slice(last, idx) })
    parts.push({ kind: "fig", value: m[1] })
    last = idx + m[0].length
  }
  if (last < text.length) parts.push({ kind: "text", value: text.slice(last) })

  return (
    <div className="flow-root">
      {parts.map((p, i) =>
        p.kind === "text" ? (
          <Markdown key={`t${i}`} text={p.value} tone={tone} />
        ) : figures[p.value] ? (
          <FigureImage
            key={`f${i}`}
            fig={figures[p.value]}
            alt={`Figure ${p.value}`}
            tone={tone}
            inline={figures[p.value].layout === "inline"}
          />
        ) : null,
      )}
    </div>
  )
}

function OriginalImage({ url, tone, label }: { url: string; tone: Tone; label: string }) {
  return (
    <div
      className={cn(
        "overflow-x-auto rounded-xl border bg-white p-2",
        tone === "dark" ? "border-white/10" : "border-zinc-200",
      )}
    >
      <img
        src={toAbsoluteBackendUrl(url) || ""}
        alt={label}
        className="h-auto max-w-full"
        style={{ maxWidth: "min(100%, 760px)" }}
      />
    </div>
  )
}

type OptionState = "idle" | "selected" | "correct" | "wrong" | "missed"

export function QuestionContent({
  content,
  questionType,
  selected = [],
  correct,
  onSelect,
  tone = "light",
  showOriginalToggle = true,
}: {
  content: ExtractedContent
  questionType?: string | null
  /** Letters currently chosen by the student. */
  selected?: string[]
  /** Correct letters; when given the options are shown in review colours. */
  correct?: string[]
  onSelect?: (label: string) => void
  tone?: Tone
  showOriginalToggle?: boolean
}) {
  const [showOriginal, setShowOriginal] = useState(false)
  const figures = content.figures || {}
  const review = Boolean(correct)
  const options = content.options || []
  const compact =
    options.length > 0 &&
    options.every(
      (o) => (o.figures?.length ?? 0) > 0 || (o.text.length < 42 && !o.text.includes("\n")),
    )

  const stateOf = (label: string): OptionState => {
    const isSel = selected.includes(label)
    if (!review) return isSel ? "selected" : "idle"
    const isCorrect = correct!.includes(label)
    if (isCorrect && isSel) return "correct"
    if (isCorrect) return "missed"
    if (isSel) return "wrong"
    return "idle"
  }

  const dark = tone === "dark"
  const optionClass: Record<OptionState, string> = {
    idle: dark
      ? "border-white/10 bg-white/[0.02] hover:bg-white/5"
      : "border-zinc-200 bg-white hover:bg-zinc-50",
    selected: dark
      ? "border-blue-400 bg-blue-500/10"
      : "border-blue-500 bg-blue-50 shadow-[0_0_15px_rgba(59,130,246,0.1)]",
    correct: dark ? "border-emerald-400 bg-emerald-500/10" : "border-emerald-500 bg-emerald-50",
    missed: dark
      ? "border-emerald-400/60 border-dashed bg-emerald-500/5"
      : "border-emerald-500 border-dashed bg-emerald-50/50",
    wrong: dark ? "border-red-400 bg-red-500/10" : "border-red-500 bg-red-50",
  }
  const badgeClass: Record<OptionState, string> = {
    idle: dark ? "border-white/20 text-zinc-400" : "border-zinc-300 text-zinc-500 bg-zinc-50",
    selected: "bg-blue-600 border-blue-500 text-white",
    correct: "bg-emerald-600 border-emerald-500 text-white",
    missed: "bg-emerald-600/80 border-emerald-500 text-white",
    wrong: "bg-red-600 border-red-500 text-white",
  }

  return (
    <div className="space-y-5">
      <div className={cn("text-lg font-medium", dark ? "text-zinc-100" : "text-zinc-900")}>
        {content.stem.image ? (
          <OriginalImage url={content.stem.image} tone={tone} label="Question" />
        ) : (
          <RichText text={content.stem.text || ""} figures={figures} tone={tone} />
        )}
      </div>

      {options.length > 0 && !content.stem.image && (
        <div className={cn("grid gap-3", compact ? "sm:grid-cols-2" : "grid-cols-1")}>
          {options.map((opt) => {
            const state = stateOf(opt.label)
            const optFigures = (opt.figures || []).map((id) => [id, figures[id]] as const)
            return (
              <button
                type="button"
                key={opt.label}
                disabled={!onSelect}
                onClick={() => onSelect?.(opt.label)}
                className={cn(
                  "flex w-full items-start gap-4 rounded-xl border p-4 text-left transition-all",
                  onSelect ? "cursor-pointer" : "cursor-default",
                  optionClass[state],
                )}
              >
                <span
                  className={cn(
                    "flex size-8 shrink-0 items-center justify-center rounded-full border font-bold",
                    badgeClass[state],
                  )}
                >
                  {state === "correct" || state === "missed" ? (
                    <Check className="size-4" />
                  ) : state === "wrong" ? (
                    <X className="size-4" />
                  ) : (
                    opt.label
                  )}
                </span>
                <span className={cn("min-w-0 flex-1 text-base", dark ? "text-zinc-200" : "text-zinc-800")}>
                  {review && state !== "idle" && (
                    <span
                      className={cn(
                        "mb-1 block text-[10px] font-bold uppercase tracking-widest",
                        state === "wrong" ? "text-red-500" : "text-emerald-500",
                      )}
                    >
                      ({opt.label}){" "}
                      {state === "correct"
                        ? "Your answer · Correct"
                        : state === "wrong"
                          ? "Your answer"
                          : "Correct answer"}
                    </span>
                  )}
                  {opt.text && <RichText text={opt.text} figures={figures} tone={tone} />}
                  {optFigures.map(([id, fig]) =>
                    fig ? <FigureImage key={id} fig={fig} alt={`Option ${opt.label}`} tone={tone} /> : null,
                  )}
                  {!opt.text && optFigures.length === 0 && (
                    <span className="text-sm italic opacity-60">See original</span>
                  )}
                </span>
              </button>
            )
          })}
        </div>
      )}

      {content.stem.image && options.length > 0 && onSelect && (
        <div className="flex flex-wrap gap-3">
          {options.map((opt) => {
            const state = stateOf(opt.label)
            return (
              <button
                type="button"
                key={opt.label}
                onClick={() => onSelect(opt.label)}
                className={cn(
                  "flex size-12 items-center justify-center rounded-full border text-lg font-bold",
                  badgeClass[state],
                )}
              >
                {opt.label}
              </button>
            )
          })}
        </div>
      )}

      {showOriginalToggle && content.crop && !content.stem.image && (
        <div className="space-y-2">
          <button
            type="button"
            onClick={() => setShowOriginal((v) => !v)}
            className={cn(
              "inline-flex items-center gap-1.5 text-xs font-semibold",
              dark ? "text-zinc-400 hover:text-zinc-200" : "text-zinc-500 hover:text-zinc-800",
            )}
          >
            {showOriginal ? <EyeOff className="size-3.5" /> : <Eye className="size-3.5" />}
            {showOriginal ? "Hide original" : "View original from paper"}
          </button>
          {showOriginal && <OriginalImage url={content.crop} tone={tone} label="Original question" />}
        </div>
      )}
      {questionType === "MCQ" && onSelect && (
        <p className={cn("text-xs", dark ? "text-zinc-500" : "text-zinc-400")}>
          One or more options may be correct.
        </p>
      )}
    </div>
  )
}

export function SolutionView({
  solution,
  tone = "dark",
}: {
  solution: SolutionContent
  tone?: Tone
}) {
  const [showOriginal, setShowOriginal] = useState(false)
  const figures = solution.figures || {}
  const hasText = Boolean(solution.text && solution.text.replace(TOKEN_RE, "").trim())
  return (
    <div className="space-y-3">
      {solution.image ? (
        <OriginalImage url={solution.image} tone={tone} label="Solution" />
      ) : hasText || Object.keys(figures).length ? (
        <RichText text={solution.text || ""} figures={figures} tone={tone} />
      ) : solution.crop ? (
        <OriginalImage url={solution.crop} tone={tone} label="Solution" />
      ) : null}
      {solution.crop && !solution.image && (hasText || Object.keys(figures).length > 0) && (
        <>
          <button
            type="button"
            onClick={() => setShowOriginal((v) => !v)}
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-zinc-400 hover:text-zinc-200"
          >
            {showOriginal ? <EyeOff className="size-3.5" /> : <Eye className="size-3.5" />}
            {showOriginal ? "Hide original solution" : "View original solution"}
          </button>
          {showOriginal && <OriginalImage url={solution.crop} tone={tone} label="Original solution" />}
        </>
      )}
    </div>
  )
}
