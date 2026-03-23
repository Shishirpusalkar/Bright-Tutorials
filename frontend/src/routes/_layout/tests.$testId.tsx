import { createFileRoute } from "@tanstack/react-router"
import TestInterface from "@/components/Test/TestInterface"

export const Route = createFileRoute("/_layout/tests/$testId")({
  component: TestInterface,
})
