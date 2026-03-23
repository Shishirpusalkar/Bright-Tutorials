import { createFileRoute } from "@tanstack/react-router"
import TestAnalysis from "@/components/Test/TestAnalysis"

export const Route = createFileRoute("/_layout/attempts/$attemptId")({
  component: TestAnalysis,
})
