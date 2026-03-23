import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { TestsService } from "@/client"
import useCustomToast from "./useCustomToast"

export function useTests() {
  const queryClient = useQueryClient()
  const { showSuccessToast } = useCustomToast()

  const testsQuery = useQuery({
    queryKey: ["tests"],
    queryFn: () => TestsService.readTests(),
  })

  const createTestMutation = useMutation({
    mutationFn: (data: {
      title: string
      description?: string
      duration_minutes: number
      file: File
      category?: string
      standard?: string
      scheduled_at?: string
      positive_marks?: number
      negative_marks?: number
    }) => {
      return TestsService.createTest({
        formData: {
          title: data.title,
          description: data.description || "",
          duration_minutes: data.duration_minutes,
          file: data.file as File,
          category: data.category,
          standard: data.standard,
          scheduled_at: data.scheduled_at,
          positive_marks: data.positive_marks,
          negative_marks: data.negative_marks,
        },
      })
    },
    onSuccess: () => {
      showSuccessToast("Test uploaded successfully!")
      queryClient.invalidateQueries({ queryKey: ["tests"] })
    },
    onError: (error: unknown) => {
      const message =
        error instanceof Error ? error.message : "Failed to create test"
      alert(message)
    },
  })

  const generateQuestionsMutation = useMutation({
    mutationFn: (id: string) => TestsService.generateQuestions({ id }),
    onSuccess: () => {
      showSuccessToast("Questions generated successfully!")
      queryClient.invalidateQueries({ queryKey: ["tests"] })
    },
    onError: (error: unknown) => {
      const message =
        error instanceof Error ? error.message : "Failed to generate questions"
      alert(message)
    },
  })

  return {
    tests: testsQuery.data || [],
    isLoading: testsQuery.isLoading,
    createTest: createTestMutation,
    generateQuestions: generateQuestionsMutation,
  }
}
