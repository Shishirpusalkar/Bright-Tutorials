import { useQuery } from "@tanstack/react-query"
import { Link } from "@tanstack/react-router"
import { motion } from "framer-motion"
import { useEffect, useState } from "react"
import {
  BookOpen,
  CheckCircle2,
  ChevronRight,
  Clock,
  Crown,
  GraduationCap,
  Target,
  Trophy,
  Zap,
} from "lucide-react"
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import {
  type AttemptAnswerPublic,
  type AttemptPublic,
  AttemptsService,
  type TestPublic,
} from "@/client"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import useAuth from "@/hooks/useAuth"
import { useTests } from "@/hooks/useTests"

interface TestWithSubject extends TestPublic {
  subject?: { name: string }
}

interface AttemptWithTest extends AttemptPublic {
  test?: TestWithSubject
}

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
  hidden: { y: 20, opacity: 0 },
  show: { y: 0, opacity: 1 },
}

export default function StudentDashboard() {
  const [mounted, setMounted] = useState(false)
  useEffect(() => {
    setMounted(true)
  }, [])

  const { user: currentUser } = useAuth()
  const { tests } = useTests()

  interface AttemptStats {
    attempt_count: number
    is_premium: boolean
  }

  const { data: stats } = useQuery({
    queryKey: ["attemptStats"],
    queryFn: () =>
      AttemptsService.getAttemptStats() as unknown as Promise<AttemptStats>,
    enabled: !!currentUser,
  })

  const { data: userAttempts } = useQuery({
    queryKey: ["userAttempts"],
    queryFn: () => AttemptsService.readUserAttempts(),
    enabled: !!currentUser,
  })

  // --- Data Processing ---
  const recentAttemptsList = (userAttempts as AttemptWithTest[]) || []
  const attemptCount = stats?.attempt_count || 0
  const isPremium = stats?.is_premium || currentUser?.is_premium || false
  const limitReached = !isPremium && attemptCount >= 3

  // Stream-based Filtering
  const userStream = currentUser?.stream?.toLowerCase()
  const relevantSubjects =
    userStream === "medical"
      ? ["Physics", "Chemistry", "Biology"]
      : userStream === "engineering"
        ? ["Physics", "Chemistry", "Maths"]
        : ["Physics", "Chemistry", "Maths", "Biology"] // Default/Fallback

  // Calculate Accuracy Data
  const subjectStats: Record<string, { total: number; correct: number }> = {}
  recentAttemptsList.forEach((attempt) => {
    // AttemptPublic doesn't have a nested subject in the test property as per the SDK
    const subject = attempt.test?.subject?.name || "General"

    if (!subjectStats[subject]) subjectStats[subject] = { total: 0, correct: 0 }
    const correct =
      attempt.answers?.filter((a: AttemptAnswerPublic) => a.is_correct)
        .length || 0
    const total = attempt.answers?.length || 0
    subjectStats[subject].total += total
    subjectStats[subject].correct += correct
  })

  // Filter accuracy data so we only show relevant subjects (plus any distinct ones they actually took)
  const accuracyData = Object.entries(subjectStats)
    .filter(
      ([subject]) =>
        relevantSubjects.includes(subject) || subject === "General",
    )
    .map(([subject, data]) => ({
      subject,
      accuracy:
        data.total > 0 ? Math.round((data.correct / data.total) * 100) : 0,
      fullMark: 100,
    }))

  if (accuracyData.length === 0) {
    // Mock Data for "Empty State" visualization based on stream
    relevantSubjects.forEach((subject) => {
      accuracyData.push({ subject, accuracy: 0, fullMark: 100 })
    })
  }

  // Calculate Progress Data (Score Trend) - for future use or removal
  // const progressData = recentAttemptsList.slice(0, 5).reverse().map((attempt, index) => ({ name: `Test ${index + 1}`, score: attempt.score }))

  const completedTestsCount = recentAttemptsList.filter(
    (a) => a.status === "submitted",
  ).length

  const totalScore = recentAttemptsList.reduce(
    (sum, a) => sum + (a.score || 0),
    0,
  )
  const avgScore =
    recentAttemptsList.length > 0
      ? Math.round(totalScore / recentAttemptsList.length)
      : 0

  const COLORS = ["#f97316", "#a855f7", "#3b82f6", "#10b981"]

  return (
    <div className="min-h-screen bg-transparent text-white space-y-8 p-4 md:p-8">
      {/* --- HERO SECTION --- */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4"
      >
        <div>
          <h1 className="text-4xl md:text-5xl font-black tracking-tight mb-2">
            Welcome back,{" "}
            <span className="text-transparent bg-clip-text bg-linear-to-r from-orange-400 to-amber-600">
              {currentUser?.full_name?.split(" ")[0] || "Student"}
            </span>
          </h1>
          <p className="text-zinc-400 text-lg">
            Target:{" "}
            <span className="text-white font-semibold capitalize">
              {userStream === "medical"
                ? "NEET (Medical)"
                : userStream === "engineering"
                  ? "JEE (Engineering)"
                  : "Board Exams"}
            </span>
            . Let's verify your progress.
          </p>
        </div>
        {!isPremium && (
          <Button
            asChild
            size="lg"
            className="bg-linear-to-r from-purple-600 to-indigo-600 hover:from-purple-700 hover:to-indigo-700 border-0 shadow-lg shadow-purple-500/20"
          >
            <Link
              to="/grade-selection"
              className="flex items-center gap-2 font-bold"
            >
              <Crown className="w-5 h-5" />
              Upgrade to Premium
            </Link>
          </Button>
        )}
      </motion.div>

      {/* --- STATS GRID --- */}
      <motion.div
        variants={container}
        initial="hidden"
        animate="show"
        className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6"
      >
        <StatsCard
          title="Tests Completed"
          value={completedTestsCount}
          icon={<CheckCircle2 className="w-6 h-6 text-emerald-400" />}
          gradient="from-emerald-500/10 to-teal-500/5"
          border="border-emerald-500/20"
          delay={0}
        />
        <StatsCard
          title="Average Score"
          value={avgScore}
          suffix=" Marks"
          icon={<Trophy className="w-6 h-6 text-amber-400" />}
          gradient="from-amber-500/10 to-orange-500/5"
          border="border-amber-500/20"
          delay={0.1}
        />
        <StatsCard
          title="Accuracy Rate"
          value={
            accuracyData.length > 0
              ? Math.round(
                accuracyData.reduce((acc, curr) => acc + curr.accuracy, 0) /
                accuracyData.length,
              )
              : 0
          }
          suffix="%"
          icon={<Target className="w-6 h-6 text-blue-400" />}
          gradient="from-blue-500/10 to-cyan-500/5"
          border="border-blue-500/20"
          delay={0.2}
        />
        <StatsCard
          title="Tests Attempted"
          value={recentAttemptsList.length}
          icon={<GraduationCap className="w-6 h-6 text-purple-400" />}
          gradient="from-purple-500/10 to-pink-500/5"
          border="border-purple-500/20"
          delay={0.3}
        />
      </motion.div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* --- CHARTS SECTION (2/3 width) --- */}
        <div className="lg:col-span-2 space-y-8">
          {/* Performance Chart */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
          >
            <Card className="bg-zinc-900/40 backdrop-blur-md border border-white/10 overflow-hidden">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-xl font-bold">
                  <Zap className="w-5 h-5 text-orange-500" />
                  Performance Analytics
                </CardTitle>
              </CardHeader>
              <CardContent className="w-full relative overflow-hidden p-0">
                <div className="w-full h-[350px] relative overflow-hidden">
                  {mounted && (
                    <ResponsiveContainer width="100%" height={350}>
                      <BarChart data={accuracyData}>
                        <CartesianGrid
                          strokeDasharray="3 3"
                          stroke="#333"
                          vertical={false}
                        />
                        <XAxis
                          dataKey="subject"
                          stroke="#888"
                          tick={{ fill: "#888", fontSize: 12 }}
                          axisLine={false}
                          tickLine={false}
                        />
                        <YAxis
                          stroke="#888"
                          tick={{ fill: "#888", fontSize: 12 }}
                          axisLine={false}
                          tickLine={false}
                          domain={[0, 100]}
                        />
                        <Tooltip
                          contentStyle={{
                            backgroundColor: "#18181b",
                            borderColor: "#333",
                            borderRadius: "8px",
                          }}
                          itemStyle={{ color: "#fff" }}
                        />
                        <Bar dataKey="accuracy" radius={[4, 4, 0, 0]}>
                          {accuracyData.map((entry) => (
                            <Cell
                              key={`cell-${entry.subject}`}
                              fill={
                                COLORS[
                                accuracyData.indexOf(entry) % COLORS.length
                                ]
                              }
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

          {/* Recent History */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.5 }}
          >
            <Card className="bg-zinc-900/40 backdrop-blur-md border border-white/10">
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle className="text-xl font-bold">
                  Recent Attempts
                </CardTitle>
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-zinc-400 hover:text-white"
                >
                  View All
                </Button>
              </CardHeader>
              <CardContent className="space-y-4">
                {recentAttemptsList.slice(0, 3).map((attempt) => (
                  <div
                    key={attempt.id}
                    className="group flex items-center justify-between p-3 rounded-lg bg-zinc-800/30 hover:bg-zinc-800/50 transition-colors border border-white/5 hover:border-white/10"
                  >
                    <div className="flex items-center gap-4">
                      <div className="w-10 h-10 rounded-full bg-zinc-700/50 flex items-center justify-center">
                        <BookOpen className="w-5 h-5 text-zinc-400 group-hover:text-orange-400 transition-colors" />
                      </div>
                      <div>
                        <div className="font-semibold text-zinc-200 group-hover:text-white transition-colors">
                          {attempt.test?.title || "Test Attempt"}
                        </div>
                        <div className="text-xs text-zinc-500 flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          {new Date(
                            attempt.submitted_at || attempt.started_at,
                          ).toLocaleDateString()}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-4">
                      <div className="text-right">
                        <div
                          className={`font-black text-lg ${attempt.score >= 50 ? "text-emerald-400" : "text-rose-400"}`}
                        >
                          {attempt.score}
                        </div>
                        <div className="text-[10px] uppercase tracking-wider text-zinc-500 font-bold">
                          Marks
                        </div>
                      </div>
                      <Button
                        variant="secondary"
                        size="icon"
                        asChild
                        className="h-8 w-8 rounded-full"
                      >
                        <Link
                          to="/attempts/$attemptId"
                          params={{ attemptId: attempt.id }}
                        >
                          <ChevronRight className="w-4 h-4" />
                        </Link>
                      </Button>
                    </div>
                  </div>
                ))}
                {recentAttemptsList.length === 0 && (
                  <div className="text-center py-8 text-zinc-500">
                    No tests taken yet. Start with a mock test!
                  </div>
                )}
              </CardContent>
            </Card>
          </motion.div>
        </div>

        {/* --- SIDEBAR (1/3 width) --- */}
        <div className="space-y-6">
          {/* Quick Start / Upcoming */}
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.6 }}
          >
            <Card className="bg-linear-to-b from-orange-500/10 to-zinc-900/40 backdrop-blur-md border border-orange-500/20">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-orange-400">
                  <Target className="w-5 h-5" />
                  Quick Start
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <p className="text-sm text-zinc-400 mb-4">
                  Select a test to begin immediately.
                </p>
                {(tests as unknown as TestPublic[])?.slice(0, 3).map((test) => (
                  <div
                    key={test.id}
                    className="flex items-center justify-between p-2 rounded bg-zinc-900/50 border border-white/5"
                  >
                    <span className="text-sm font-medium truncate max-w-[150px]">
                      {test.title}
                    </span>
                    <Button
                      size="sm"
                      className="h-7 text-xs bg-zinc-100 text-zinc-900 hover:bg-white font-bold"
                      disabled={limitReached}
                      asChild={!limitReached}
                    >
                      {limitReached ? (
                        <span>Locked</span>
                      ) : (
                        <Link to="/tests/$testId" params={{ testId: test.id }}>
                          Start
                        </Link>
                      )}
                    </Button>
                  </div>
                ))}

                {!isPremium && (
                  <div className="mt-4 p-3 rounded bg-purple-500/10 border border-purple-500/20 text-center">
                    <p className="text-xs text-purple-300 mb-2">
                      {attemptCount} / 3 Free Tests Used
                    </p>
                    <Progress
                      value={(attemptCount / 3) * 100}
                      className="h-1.5 bg-purple-900/50"
                    />
                  </div>
                )}
              </CardContent>
            </Card>
          </motion.div>

          {/* Motivational / Modules */}
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.7 }}
          >
            <Card className="bg-zinc-900/40 backdrop-blur-md border border-white/10">
              <CardHeader>
                <CardTitle className="text-lg">Study Modules</CardTitle>
              </CardHeader>
              <CardContent className="grid grid-cols-2 gap-3">
                {relevantSubjects.map((subject, i) => (
                  <div
                    key={subject}
                    className="aspect-square rounded-xl bg-zinc-800/40 border border-white/5 flex flex-col items-center justify-center gap-2 hover:bg-zinc-700/40 transition-colors cursor-pointer group"
                  >
                    <div
                      className={`w-8 h-8 rounded-full flex items-center justify-center bg-zinc-700 group-hover:scale-110 transition-transform ${i === 0 ? "text-blue-400" : i === 1 ? "text-rose-400" : i === 2 ? "text-amber-400" : "text-emerald-400"}`}
                    >
                      <BookOpen className="w-4 h-4" />
                    </div>
                    <span className="text-xs font-medium text-zinc-300">
                      {subject}
                    </span>
                  </div>
                ))}
              </CardContent>
            </Card>
          </motion.div>
        </div>
      </div>
    </div>
  )
}

interface StatsCardProps {
  title: string
  value: string | number
  suffix?: string
  icon: React.ReactNode
  gradient: string
  border: string
  delay?: number
}

function StatsCard({
  title,
  value,
  suffix = "",
  icon,
  gradient,
  border,
  delay = 0,
}: StatsCardProps) {
  return (
    <motion.div
      variants={item}
      initial="hidden"
      animate="show"
      transition={{ delay }}
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
