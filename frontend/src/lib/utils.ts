import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * Converts a relative `/static/...` path from the backend into an absolute URL.
 * This is necessary because static files are served by the backend, not the frontend dev server.
 */
export function toAbsoluteBackendUrl(url: string | null | undefined): string | null | undefined {
  if (!url) return url
  if (url.startsWith("http://") || url.startsWith("https://")) return url
  const base = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/$/, "")
  return `${base}${url}`
}
