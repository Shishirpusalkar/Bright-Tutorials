import type React from "react"
import { useEffect, useRef } from "react"

declare global {
  interface Window {
    SmilesDrawer: any
  }
}

interface SmilesRendererProps {
  smiles: string
  width?: number
  height?: number
  className?: string
  theme?: "dark" | "light"
}

const SmilesRenderer: React.FC<SmilesRendererProps> = ({
  smiles,
  width = 250,
  height = 250,
  className = "",
  theme = "light",
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    if (canvasRef.current && window.SmilesDrawer) {
      const options = {
        width,
        height,
        bondThickness: 1.5,
        theme: theme === "dark" ? "dark" : "light",
      }

      const smilesDrawer = new window.SmilesDrawer.Drawer(options)

      window.SmilesDrawer.parse(
        smiles,
        (tree: any) => {
          smilesDrawer.draw(
            tree,
            canvasRef.current,
            theme === "dark" ? "dark" : "light",
            false,
          )
        },
        (err: any) => {
          console.error("SMILES Parse Error:", err)
        },
      )
    }
  }, [smiles, width, height, theme])

  return (
    <div
      className={`flex flex-col items-center justify-center bg-white rounded-lg p-2 border border-zinc-200 ${className}`}
    >
      <canvas ref={canvasRef} />
    </div>
  )
}

export default SmilesRenderer
