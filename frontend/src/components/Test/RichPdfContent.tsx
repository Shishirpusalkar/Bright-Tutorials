import { useEffect, useRef, useState } from "react"
import ReactMarkdown from "react-markdown"
import rehypeKatex from "rehype-katex"
import rehypeRaw from "rehype-raw"
import remarkMath from "remark-math"
import { cn } from "@/lib/utils"

export const VISUAL_SNIPPET_TOKEN = "[[VISUAL_SNIPPET]]"
export const SOLUTION_SNIPPET_TOKEN = "[[SOLUTION_SNIPPET]]"

const PDF_JS_URL = "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js"
const PDF_JS_WORKER_URL =
  "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js"

export function PdfSnippet({
  url,
  pageNumber,
  bbox,
  inline = false,
}: {
  url: string
  pageNumber: number
  bbox: {
    x0: number
    y0: number
    x1: number
    y1: number
  }
  inline?: boolean
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [loading, setLoading] = useState(true)
  const [displaySize, setDisplaySize] = useState<{
    width: number
    height: number
  } | null>(null)

  useEffect(() => {
    if (!url || !pageNumber || !bbox) return

    const loadPdf = async () => {
      try {
        setLoading(true)
        if (!(window as any).pdfjsLib) {
          const script = document.createElement("script")
          script.src = PDF_JS_URL
          document.head.appendChild(script)
          await new Promise((resolve) => {
            script.onload = resolve
          })
        }

        const pdfjsLib = (window as any).pdfjsLib
        pdfjsLib.GlobalWorkerOptions.workerSrc = PDF_JS_WORKER_URL

        const loadingTask = pdfjsLib.getDocument(url)
        const pdf = await loadingTask.promise
        const page = await pdf.getPage(pageNumber)

        const viewport = page.getViewport({ scale: 2.0 })
        const canvas = canvasRef.current
        if (!canvas) return
        const context = canvas.getContext("2d")
        if (!context) return

        const { x0, y0, x1, y1 } = bbox
        const cropWidth = x1 - x0
        const cropHeight = y1 - y0
        const scale = viewport.scale
        const sX = x0 * scale
        const sY = y0 * scale
        const sW = cropWidth * scale
        const sH = cropHeight * scale

        canvas.width = sW
        canvas.height = sH
        setDisplaySize({
          width: Math.max(72, Math.round(cropWidth * 1.3333)),
          height: Math.max(36, Math.round(cropHeight * 1.3333)),
        })

        const renderContext = {
          canvasContext: context,
          viewport: viewport,
          transform: [1, 0, 0, 1, -sX, -sY],
        }
        await page.render(renderContext).promise
        setLoading(false)
      } catch (err) {
        console.error("PDF snippet rendering failed", err)
        setLoading(false)
      }
    }

    loadPdf()
  }, [url, pageNumber, bbox])

  return (
    <div
      className={cn(
        "overflow-hidden rounded-lg border border-zinc-200 bg-white shadow-sm",
        inline
          ? "inline-flex align-middle my-1 mx-1"
          : "my-4 flex max-w-[88%] justify-center",
      )}
    >
      {loading && (
        <div className="flex h-40 w-full items-center justify-center bg-zinc-50 animate-pulse">
          <div className="text-xs font-medium uppercase tracking-widest text-zinc-400">
            Loading Visual...
          </div>
        </div>
      )}
      <canvas
        ref={canvasRef}
        className={cn(
          inline ? "block" : "max-w-full h-auto",
          loading ? "hidden" : "block",
        )}
        style={
          inline && displaySize
            ? {
                width: `${displaySize.width}px`,
                height: `${displaySize.height}px`,
                maxWidth: "100%",
              }
            : undefined
        }
      />
    </div>
  )
}

export function RichPdfContent({
  text,
  token,
  pdfUrl,
  pageNumber,
  bbox,
  inlineSnippet = false,
}: {
  text: string
  token: string
  pdfUrl?: string | null
  pageNumber?: number | null
  bbox?: {
    x0: number
    y0: number
    x1: number
    y1: number
  } | null
  inlineSnippet?: boolean
}) {
  const canRenderSnippet = Boolean(
    text.includes(token) && pdfUrl && pageNumber && bbox,
  )

  if (!canRenderSnippet) {
    return (
      <ReactMarkdown
        remarkPlugins={[remarkMath]}
        rehypePlugins={[rehypeKatex, rehypeRaw]}
      >
        {text}
      </ReactMarkdown>
    )
  }

  return (
    <>
      {text.split(token).map((part, index, arr) => (
        <div key={`segment-${index}`} className={inlineSnippet ? "inline" : ""}>
          {part ? (
            <ReactMarkdown
              remarkPlugins={[remarkMath]}
              rehypePlugins={[rehypeKatex, rehypeRaw]}
            >
              {part}
            </ReactMarkdown>
          ) : null}
          {index < arr.length - 1 ? (
            <PdfSnippet
              url={pdfUrl!}
              pageNumber={pageNumber!}
              bbox={bbox!}
              inline={inlineSnippet}
            />
          ) : null}
        </div>
      ))}
    </>
  )
}
