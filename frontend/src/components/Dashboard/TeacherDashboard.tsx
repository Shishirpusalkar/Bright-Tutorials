import { useNavigate } from "@tanstack/react-router"
import { motion } from "framer-motion"
import {
  BarChart3,
  Brain,
  CheckCircle2,
  Eye,
  EyeOff,
  FileText,
  Search,
  Trash2,
  TriangleAlert,
  Upload,
  Users,
} from "lucide-react"
import { useEffect, useState } from "react"
import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip } from "recharts"
import { TestsService } from "@/client"
import type { QuestionPublic, TestPublic } from "@/client/types.gen"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { LoadingButton } from "@/components/ui/loading-button"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import useAuth from "@/hooks/useAuth"
import { useTests } from "@/hooks/useTests"

import OmegaConfigModal from "./OmegaConfigModal"

export default function TeacherDashboard() {
  const [mounted, setMounted] = useState(false)
  useEffect(() => {
    setMounted(true)
  }, [])

  const { user: currentUser } = useAuth()
  const { tests, createTest, generateQuestions } = useTests()
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [isOMRModalOpen, setIsOMRModalOpen] = useState(false)
  const [isOmegaModalOpen, setIsOmegaModalOpen] = useState(false)
  const navigate = useNavigate()

  if (currentUser && currentUser.role !== "teacher") {
    navigate({ to: "/" })
    return null
  }

  // Animation variants
  const container = {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: {
        staggerChildren: 0.1,
      },
    },
  }

  const item = {
    hidden: { opacity: 0, y: 20 },
    show: { opacity: 1, y: 0 },
  }

  // Derived Stats
  const totalTests = tests.length
  const publishedTests = tests.filter((t) => t.is_published).length
  const totalSubmissions = tests.reduce(
    (acc, t) => acc + (t.submission_count || 0),
    0,
  )
  const avgPerformance =
    tests.length > 0
      ? Math.round(
        tests.reduce((acc, t) => acc + (t.average_score || 0), 0) /
        tests.length,
      )
      : 0

  // Chart Data
  const submissionData = tests.slice(0, 5).map((t) => ({
    name: t.title.length > 15 ? `${t.title.substring(0, 15)}...` : t.title,
    submissions: t.submission_count || 0,
  }))

  const COLORS = ["#f97316", "#a855f7", "#3b82f6", "#10b981", "#ec4899"]

  const quickActions = [
    {
      title: "Smart Generate",
      description: "AI-powered test creation",
      icon: <Brain className="size-6 text-white" />,
      gradient: "from-purple-600 to-indigo-600",
      onClick: () => setIsOmegaModalOpen(true),
    },
    {
      title: "Process OMR",
      description: "Scan and grade offline sheets",
      icon: <Upload className="size-6 text-white" />,
      gradient: "from-emerald-500 to-teal-600",
      onClick: () => setIsOMRModalOpen(true),
    },
  ]

  return (
    <div className="min-h-screen bg-transparent text-white space-y-8 p-4 md:p-8">
      {/* HEADER */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4"
      >
        <div>
          <h1 className="text-4xl md:text-5xl font-black tracking-tight mb-2">
            Teacher{" "}
            <span className="text-transparent bg-clip-text bg-linear-to-r from-blue-400 to-cyan-500">
              Dashboard
            </span>
          </h1>
          <p className="text-zinc-400 text-lg">
            Manage your curriculum and monitor student progress.
          </p>
        </div>
        <div className="flex gap-3">
          <Button
            onClick={() => setIsOmegaModalOpen(true)}
            size="lg"
            className="bg-purple-600 text-white hover:bg-purple-700 font-bold hidden md:flex border-0 shadow-lg shadow-purple-900/20"
          >
            <Brain className="mr-2 h-5 w-5" />
            Smart Generate
          </Button>
        </div>
      </motion.div>

      {/* STATS GRID */}
      <motion.div
        variants={container}
        initial="hidden"
        animate="show"
        className="grid gap-6 md:grid-cols-2 lg:grid-cols-4"
      >
        <StatsCard
          title="Total Tests"
          value={totalTests}
          icon={<FileText className="w-6 h-6 text-blue-400" />}
          gradient="from-blue-500/10 to-indigo-500/5"
          border="border-blue-500/20"
        />
        <StatsCard
          title="Published"
          value={publishedTests}
          icon={<CheckCircle2 className="w-6 h-6 text-emerald-400" />}
          gradient="from-emerald-500/10 to-teal-500/5"
          border="border-emerald-500/20"
        />
        <StatsCard
          title="Total Submissions"
          value={totalSubmissions}
          icon={<Users className="w-6 h-6 text-purple-400" />}
          gradient="from-purple-500/10 to-pink-500/5"
          border="border-purple-500/20"
        />
        <StatsCard
          title="Avg Performance"
          value={avgPerformance}
          suffix="%"
          icon={<BarChart3 className="w-6 h-6 text-orange-400" />}
          gradient="from-orange-500/10 to-amber-500/5"
          border="border-orange-500/20"
        />
      </motion.div>

      {/* QUICK ACTIONS */}
      <motion.div
        variants={container}
        initial="hidden"
        animate="show"
        className="grid gap-6 md:grid-cols-3"
      >
        {quickActions.map((action, _i) => (
          <motion.div
            key={action.title}
            variants={item}
            whileHover={{ y: -5 }}
            className="cursor-pointer"
            onClick={action.onClick}
          >
            <div
              className={`h-full p-6 rounded-2xl bg-linear-to-br ${action.gradient} border border-white/10 shadow-lg relative overflow-hidden group`}
            >
              <div className="absolute top-0 right-0 p-4 opacity-20 group-hover:opacity-30 transition-opacity transform group-hover:scale-110 duration-500">
                {action.icon}
              </div>
              <div className="relative z-10">
                <div className="p-3 bg-white/20 w-fit rounded-xl mb-4 backdrop-blur-sm">
                  {action.icon}
                </div>
                <h3 className="text-xl font-bold text-white mb-1">
                  {action.title}
                </h3>
                <p className="text-white/80 text-sm font-medium">
                  {action.description}
                </p>
              </div>
            </div>
          </motion.div>
        ))}
      </motion.div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* MAIN CONTENT Area (2/3) */}
        <div className="lg:col-span-2 space-y-8">
          {/* RECENT TESTS TABLE */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
          >
            <Card className="bg-zinc-900/40 backdrop-blur-md border border-white/10 overflow-hidden">
              <CardHeader className="flex flex-row items-center justify-between border-b border-white/5 pb-4">
                <div>
                  <CardTitle className="text-xl font-bold">
                    Recent Tests
                  </CardTitle>
                  <CardDescription className="text-zinc-400">
                    Manage and monitor your latest assessments.
                  </CardDescription>
                </div>
                <Button
                  variant="ghost"
                  className="text-zinc-400 hover:text-white"
                >
                  <Search className="w-5 h-5" />
                </Button>
              </CardHeader>
              <CardContent className="p-0">
                <Table>
                  <TableHeader className="bg-white/5 hover:bg-white/5">
                    <TableRow className="border-white/5 hover:bg-transparent">
                      <TableHead className="text-zinc-300 font-semibold px-6">
                        Title
                      </TableHead>
                      <TableHead className="text-zinc-300 font-semibold">
                        Date
                      </TableHead>
                      <TableHead className="text-zinc-300 font-semibold">
                        Status
                      </TableHead>
                      <TableHead className="text-zinc-300 font-semibold text-center">
                        Submitted
                      </TableHead>
                      <TableHead className="text-zinc-300 font-semibold text-center">
                        Avg Score
                      </TableHead>
                      <TableHead className="text-zinc-300 font-semibold text-right px-6">
                        Actions
                      </TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {tests.map((test) => (
                      <TableRow
                        key={test.id}
                        className="border-white/5 hover:bg-white/5 transition-colors"
                      >
                        <TableCell className="font-bold text-zinc-100 px-6 max-w-[200px] truncate">
                          <div className="flex items-center gap-2">
                            {test.title}
                            {test.is_symmetrical === false && (
                              <TriangleAlert
                                className="w-4 h-4 text-amber-500"
                                {...({ title: test.symmetry_message || "Symmetry Error" } as any)}
                              />
                            )}
                          </div>
                        </TableCell>
                        <TableCell>
                          <div className="flex flex-col">
                            <span className="text-sm text-zinc-200">
                              {new Date(
                                test.scheduled_at || test.created_at || "",
                              ).toLocaleDateString("en-GB", {
                                day: "2-digit",
                                month: "2-digit",
                                year: "numeric",
                              })}
                            </span>
                            <span className="text-[10px] text-zinc-500">
                              {test.scheduled_at ? "Scheduled" : "Created"}
                            </span>
                          </div>
                        </TableCell>
                        <TableCell>
                          <span
                            className={`px-2 py-1 rounded-full text-[10px] uppercase font-bold tracking-wider ${test.is_published ? "bg-emerald-500/10 text-emerald-500 border border-emerald-500/20" : "bg-amber-500/10 text-amber-500 border border-amber-500/20"}`}
                          >
                            {test.is_published ? "Published" : "Draft"}
                          </span>
                        </TableCell>
                        <TableCell className="text-center text-zinc-300">
                          {test.submission_count || 0}
                        </TableCell>
                        <TableCell className="text-center font-mono text-zinc-300">
                          {test.average_score
                            ? `${Math.round(test.average_score)}%`
                            : "-"}
                        </TableCell>
                        <TableCell className="text-right px-6">
                          <div className="flex items-center justify-end gap-2">
                            <LoadingButton
                              variant="ghost"
                              size="icon"
                              className="h-8 w-8 text-purple-400 hover:text-purple-300 hover:bg-purple-400/10"
                              loading={
                                generateQuestions.isPending &&
                                generateQuestions.variables === test.id
                              }
                              onClick={() =>
                                test.id && generateQuestions.mutate(test.id)
                              }
                              title="Generate Questions with AI"
                            >
                              <Brain className="w-4 h-4" />
                            </LoadingButton>
                            <Button
                              variant="ghost"
                              size="icon"
                              disabled={test.is_symmetrical === false}
                              onClick={async () => {
                                if (test.id) {
                                  try {
                                    const token = localStorage.getItem("access_token")
                                    const apiUrl = import.meta.env.VITE_API_URL || "http://localhost:8000"
                                    await fetch(`${apiUrl}/api/v1/tests/${test.id}`, {
                                      method: "PATCH",
                                      headers: {
                                        "Content-Type": "application/json",
                                        Authorization: `Bearer ${token}`,
                                      },
                                      body: JSON.stringify({ is_published: !test.is_published }),
                                    })
                                    window.location.reload()
                                  } catch (error) {
                                    console.error("Update failed", error)
                                  }
                                }
                              }}
                              title={
                                test.is_symmetrical === false
                                  ? "Extraction Incomplete"
                                  : (test.is_published ? "Unpublish" : "Publish")
                              }
                              className={cn(
                                "h-8 w-8",
                                test.is_symmetrical === false && "opacity-50 cursor-not-allowed"
                              )}
                            >
                              {test.is_symmetrical === false ? (
                                <TriangleAlert className="w-4 h-4 text-amber-500" />
                              ) : test.is_published ? (
                                <Eye className="w-4 h-4 text-emerald-400" />
                              ) : (
                                <EyeOff className="w-4 h-4 text-zinc-500" />
                              )}
                            </Button>
                            <ViewQuestionsButton testId={test.id as string} />
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-8 w-8 text-red-500 hover:text-red-400 hover:bg-red-500/10"
                              onClick={async () => {
                                if (
                                  test.id &&
                                  confirm(
                                    `Are you sure you want to delete "${test.title}"? This will remove all questions and student attempts.`,
                                  )
                                ) {
                                  try {
                                    const token =
                                      localStorage.getItem("access_token")
                                    const apiUrl =
                                      import.meta.env.VITE_API_URL ||
                                      "http://localhost:8000"
                                    const response = await fetch(
                                      `${apiUrl}/api/v1/tests/${test.id}`,
                                      {
                                        method: "DELETE",
                                        headers: {
                                          Authorization: `Bearer ${token}`,
                                        },
                                      },
                                    )
                                    if (response.ok) {
                                      window.location.reload()
                                    } else {
                                      const err = await response.json()
                                      alert(
                                        `Delete failed: ${err.detail || "Unknown error"}`,
                                      )
                                    }
                                  } catch (error) {
                                    console.error("Delete error:", error)
                                    alert("Failed to delete test")
                                  }
                                }
                              }}
                              title="Delete Test"
                            >
                              <Trash2 className="w-4 h-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-8 w-8 text-blue-400 hover:text-blue-300 hover:bg-blue-400/10"
                              asChild
                            >
                              <a
                                href={test.question_paper_url ?? "#"}
                                target="_blank"
                                rel="noreferrer"
                              >
                                <FileText className="w-4 h-4" />
                              </a>
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                    {tests.length === 0 && (
                      <TableRow>
                        <TableCell
                          colSpan={6}
                          className="text-center py-8 text-zinc-500"
                        >
                          No tests found. Create your first test to get started.
                        </TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </motion.div>
        </div>

        {/* SIDEBAR Area (1/3) */}
        <div className="space-y-6">
          {/* SUBMISSIONS CHART */}
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.5 }}
          >
            <Card className="bg-zinc-900/40 backdrop-blur-md border border-white/10">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-lg">
                  <BarChart3 className="w-5 h-5 text-indigo-400" />
                  Engagement
                </CardTitle>
                <CardDescription>Submissions per recent test</CardDescription>
              </CardHeader>
              <CardContent className="relative overflow-hidden p-0">
                <div className="w-full h-[350px] relative overflow-hidden">
                  {mounted && (
                    <ResponsiveContainer width="100%" height={350}>
                      <BarChart data={submissionData}>
                        <Tooltip
                          contentStyle={{
                            backgroundColor: "#18181b",
                            borderColor: "#333",
                            borderRadius: "8px",
                            color: "#fff",
                          }}
                          itemStyle={{ color: "#fff" }}
                          cursor={{ fill: "rgba(255,255,255,0.05)" }}
                        />
                        <Bar dataKey="submissions" radius={[4, 4, 0, 0]}>
                          {submissionData.map((_entry, index) => (
                            <Cell
                              key={`cell-${index}`}
                              fill={COLORS[index % COLORS.length]}
                            />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  )}
                </div>
              </CardContent>
            </Card>
          </motion.div>

          {/* OMR STATUS */}
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.6 }}
          >
            <Card className="bg-linear-to-b from-yellow-500/10 to-zinc-900/40 backdrop-blur-md border border-yellow-500/20">
              <CardHeader>
                <CardTitle className="text-lg text-yellow-400 flex items-center gap-2">
                  <Upload className="w-5 h-5" /> Pending OMRs
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-center py-6">
                  <div className="text-4xl font-black text-white mb-2">0</div>
                  <p className="text-sm text-zinc-400">
                    No pending OMR sheets to process.
                  </p>
                  <Button
                    variant="outline"
                    size="sm"
                    className="mt-4 border-yellow-500/30 text-yellow-500 hover:bg-yellow-500/10"
                    onClick={() => setIsOMRModalOpen(true)}
                  >
                    Upload New Batch
                  </Button>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        </div>
      </div>

      <UploadTestModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSubmit={(data) => {
          createTest.mutate(data, {
            onSuccess: () => setIsModalOpen(false),
          })
        }}
        isPending={createTest.isPending}
      />
      <UploadOMRModal
        isOpen={isOMRModalOpen}
        onClose={() => setIsOMRModalOpen(false)}
        tests={tests}
      />
      <OmegaConfigModal
        isOpen={isOmegaModalOpen}
        onClose={() => setIsOmegaModalOpen(false)}
      />
    </div>
  )
}

function StatsCard({ title, value, suffix = "", icon, gradient, border }: any) {
  return (
    <motion.div
      variants={{
        hidden: { opacity: 0, y: 20 },
        show: { opacity: 1, y: 0 },
      }}
    >
      <Card
        className={`relative overflow-hidden bg-linear-to-br ${gradient} ${border} bg-zinc-900/40 backdrop-blur-sm border transition-transform hover:-translate-y-1 duration-300`}
      >
        <div className="absolute top-0 right-0 p-4 opacity-10">{icon}</div>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-zinc-400 flex items-center gap-2">
            {icon} {title}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-3xl font-black tracking-tighter text-white">
            {value}
            {suffix && (
              <span className="text-lg text-zinc-500 font-medium ml-1">
                {suffix}
              </span>
            )}
          </div>
        </CardContent>
      </Card>
    </motion.div>
  )
}

function UploadOMRModal({
  isOpen,
  onClose,
  tests,
}: {
  isOpen: boolean
  onClose: () => void
  tests: TestPublic[]
}) {
  const [testId, setTestId] = useState("")
  const [file, setFile] = useState<File | null>(null)
  const [isUploading, setIsUploading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!testId || !file) return

    setIsUploading(true)
    try {
      const formData = new FormData()
      formData.append("test_id", testId)
      formData.append("file", file)

      const token = localStorage.getItem("access_token")
      const response = await fetch(
        `${import.meta.env.VITE_API_URL || "http://localhost:8000"}/api/v1/omr/process`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
          },
          body: formData,
        },
      )

      if (!response.ok) {
        const err = await response.json()
        throw new Error(err.detail || "OMR Processing Failed")
      }

      const result = await response.json()
      alert(`OMR Processed Successfully! Score: ${result.score}`)
      onClose()
      // Optionally refresh stats
    } catch (error: unknown) {
      console.error(error)
      const message =
        error instanceof Error ? error.message : "Failed to process OMR"
      alert(message)
    } finally {
      setIsUploading(false)
    }
  }

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-md bg-zinc-900 border-white/10 text-white">
        <DialogHeader>
          <DialogTitle>Upload OMR Sheet</DialogTitle>
          <DialogDescription className="text-zinc-400">
            Select the test and upload the scanned OMR sheet image (JPEG/PNG).
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="test-select" className="text-zinc-300">
              Select Test
            </Label>
            <select
              id="test-select"
              className="flex h-10 w-full rounded-md border border-white/10 bg-zinc-800 px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              value={testId}
              onChange={(e) => setTestId(e.target.value)}
              required
            >
              <option value="">-- Select Test --</option>
              {tests.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.title}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="omr-file" className="text-zinc-300">
              OMR Image
            </Label>
            <Input
              id="omr-file"
              type="file"
              accept="image/*"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
              required
              className="bg-zinc-800 border-white/10 text-white file:bg-zinc-700 file:text-white file:border-0"
            />
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="ghost"
              onClick={onClose}
              className="text-zinc-400 hover:text-white hover:bg-white/10"
            >
              Cancel
            </Button>
            <LoadingButton
              type="submit"
              loading={isUploading}
              className="bg-blue-600 hover:bg-blue-700 text-white"
            >
              Process OMR
            </LoadingButton>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function UploadTestModal({
  isOpen,
  onClose,
  onSubmit,
  isPending,
}: {
  isOpen: boolean
  onClose: () => void
  onSubmit: (data: {
    title: string
    duration_minutes: number
    scheduled_at?: string
    standard?: string
    category?: string
    file: File
    positive_marks: number
    negative_marks: number
  }) => void
  isPending: boolean
}) {
  const [title, setTitle] = useState("")
  const [duration, setDuration] = useState("60")
  const [scheduledAt, setScheduledAt] = useState("")
  const [standard, setStandard] = useState("12th")
  const [category, setCategory] = useState("JEE")
  const [positiveMarks, setPositiveMarks] = useState("4")
  const [negativeMarks, setNegativeMarks] = useState("-1")
  const [file, setFile] = useState<File | null>(null)

  const handleSumbit = (e: React.FormEvent) => {
    e.preventDefault()
    if (file) {
      onSubmit({
        title,
        duration_minutes: parseInt(duration, 10),
        scheduled_at: scheduledAt || undefined,
        standard,
        category,
        positive_marks: parseInt(positiveMarks, 10),
        negative_marks: parseFloat(negativeMarks),
        file,
      })
    }
  }

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-lg bg-zinc-900 border-white/10 text-white max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Upload Question Paper (PDF)</DialogTitle>
          <DialogDescription className="text-zinc-400">
            Upload a PDF containing objective questions. Students will be able
            to take this test.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSumbit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="title" className="text-zinc-300">
              Test Title
            </Label>
            <Input
              id="title"
              placeholder="e.g. Unit Test 1 - Mathematics"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
              className="bg-zinc-800 border-white/10 text-white"
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="duration" className="text-zinc-300">
                Duration (mins)
              </Label>
              <Input
                id="duration"
                type="number"
                value={duration}
                onChange={(e) => setDuration(e.target.value)}
                required
                className="bg-zinc-800 border-white/10 text-white"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="scheduled_at" className="text-zinc-300">
                Scheduled At
              </Label>
              <Input
                id="scheduled_at"
                type="datetime-local"
                value={scheduledAt}
                onChange={(e) => setScheduledAt(e.target.value)}
                className="bg-zinc-800 border-white/10 text-white"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="standard" className="text-zinc-300">
                Standard
              </Label>
              <select
                id="standard"
                className="flex h-10 w-full rounded-md border border-white/10 bg-zinc-800 px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                value={standard}
                onChange={(e) => setStandard(e.target.value)}
              >
                <option value="11th">11th</option>
                <option value="12th">12th</option>
                <option value="repeater">Repeater</option>
              </select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="category" className="text-zinc-300">
                Exam Category
              </Label>
              <select
                id="category"
                className="flex h-10 w-full rounded-md border border-white/10 bg-zinc-800 px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
              >
                <option value="JEE">JEE Mains</option>
                <option value="JEE Advanced">JEE Advanced</option>
                <option value="NEET">NEET (Medical)</option>
              </select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="positive_marks" className="text-zinc-300">
                Positive Marks
              </Label>
              <Input
                id="positive_marks"
                type="number"
                value={positiveMarks}
                onChange={(e) => setPositiveMarks(e.target.value)}
                required
                className="bg-zinc-800 border-white/10 text-white"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="negative_marks" className="text-zinc-300">
                Negative Marks
              </Label>
              <Input
                id="negative_marks"
                type="number"
                step="0.5"
                value={negativeMarks}
                onChange={(e) => setNegativeMarks(e.target.value)}
                required
                className="bg-zinc-800 border-white/10 text-white"
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="file" className="text-zinc-300">
              Question Paper (PDF)
            </Label>
            <Input
              id="file"
              type="file"
              accept="application/pdf"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
              required
              className="bg-zinc-800 border-white/10 text-white file:bg-zinc-700 file:text-white file:border-0"
            />
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="ghost"
              onClick={onClose}
              className="text-zinc-400 hover:text-white hover:bg-white/10"
            >
              Cancel
            </Button>
            <LoadingButton
              type="submit"
              loading={isPending}
              className="bg-blue-600 hover:bg-blue-700 text-white"
            >
              Upload Test
            </LoadingButton>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function ViewQuestionsButton({ testId }: { testId: string }) {
  const [isOpen, setIsOpen] = useState(false)
  const [testData, setTestData] = useState<TestPublic | null>(null)
  const [loading, setLoading] = useState(false)

  const fetchQuestions = async () => {
    setLoading(true)
    try {
      const data = (await TestsService.readTest({ id: testId })) as TestPublic
      setTestData(data)
      setIsOpen(true)
    } catch (error) {
      console.error(error)
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <LoadingButton
        variant="ghost"
        size="icon"
        onClick={fetchQuestions}
        loading={loading}
        className="h-8 w-8 text-emerald-400 hover:text-emerald-300 hover:bg-emerald-400/10"
        title="View Questions"
      >
        <Search className="w-4 h-4" />
      </LoadingButton>
      <Dialog open={isOpen} onOpenChange={setIsOpen}>
        <DialogContent className="max-w-3xl max-h-[80vh] overflow-y-auto bg-zinc-900 border-white/10 text-white">
          <DialogHeader>
            <DialogTitle>Test Questions: {testData?.title}</DialogTitle>
            <DialogDescription className="text-zinc-400">
              Review the questions generated for this test.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            {testData?.questions && testData.questions.length > 0 ? (
              testData.questions.map((q, i) => {
                const question = q as QuestionPublic & {
                  correct_option?: string
                }
                return (
                  <Card key={q.id} className="bg-zinc-800/50 border-white/10">
                    <CardHeader className="pb-2">
                      <div className="flex justify-between items-start">
                        <CardTitle className="text-sm font-semibold text-zinc-200">
                          Question {i + 1}
                        </CardTitle>
                        <span className="text-xs font-medium bg-blue-500/20 text-blue-400 px-2 py-0.5 rounded border border-blue-500/30">
                          {q.marks} Mark(s)
                        </span>
                      </div>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      <p className="text-sm text-zinc-300">{q.question_text}</p>
                      <div className="grid grid-cols-2 gap-3 text-xs">
                        <div
                          className={`p-2 rounded border ${question.correct_option === "A"
                            ? "bg-green-500/20 border-green-500/50 text-green-300 font-bold"
                            : "bg-zinc-900/50 border-white/10 text-zinc-400"
                            }`}
                        >
                          A: {q.option_a}
                        </div>
                        <div
                          className={`p-2 rounded border ${question.correct_option === "B"
                            ? "bg-green-500/20 border-green-500/50 text-green-300 font-bold"
                            : "bg-zinc-900/50 border-white/10 text-zinc-400"
                            }`}
                        >
                          B: {q.option_b}
                        </div>
                        <div
                          className={`p-2 rounded border ${question.correct_option === "C"
                            ? "bg-green-500/20 border-green-500/50 text-green-300 font-bold"
                            : "bg-zinc-900/50 border-white/10 text-zinc-400"
                            }`}
                        >
                          C: {q.option_c}
                        </div>
                        <div
                          className={`p-2 rounded border ${question.correct_option === "D"
                            ? "bg-green-500/20 border-green-500/50 text-green-300 font-bold"
                            : "bg-zinc-900/50 border-white/10 text-zinc-400"
                            }`}
                        >
                          D: {q.option_d}
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                )
              })
            ) : (
              <p className="text-center text-zinc-500 py-8">
                No questions found. Click "AI Generate" to create some.
              </p>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}
