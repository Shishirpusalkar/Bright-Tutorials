import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute, redirect } from "@tanstack/react-router"
import { motion } from "framer-motion"
import {
  Activity,
  BarChart3,
  CreditCard,
  Download,
  Settings as SettingsIcon,
  ShieldCheck,
  Users,
} from "lucide-react"
import { Suspense } from "react"

import { type UserPublic, UsersService } from "@/client"
import AddUser from "@/components/Admin/AddUser"
import { columns, type UserTableData } from "@/components/Admin/columns"
import Settings from "@/components/Admin/Settings"
import { DataTable } from "@/components/Common/DataTable"
import PendingUsers from "@/components/Pending/PendingUsers"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import useAuth from "@/hooks/useAuth"

function getUsersQueryOptions() {
  return {
    queryFn: () => UsersService.readUsers({ skip: 0, limit: 100 }),
    queryKey: ["users"],
  }
}

function getAdminStatsQueryOptions() {
  return {
    queryFn: () => UsersService.getAdminStats(),
    queryKey: ["admin-stats"],
  }
}

export const Route = createFileRoute("/_layout/admin")({
  component: AdminDashboard,
  beforeLoad: async () => {
    const user = await UsersService.readUserMe()
    if (!user.is_superuser && user.role !== "teacher") {
      throw redirect({
        to: "/",
      })
    }
  },
  head: () => ({
    meta: [
      {
        title: "Admin - BTC Institute",
      },
    ],
  }),
})

function UsersTableContent() {
  const { user: currentUser } = useAuth()
  const { data: users } = useSuspenseQuery(getUsersQueryOptions())

  const isTeacher =
    currentUser?.role === "teacher" && !currentUser?.is_superuser

  const filteredUsers = users.data.filter((user: UserPublic) => {
    if (isTeacher) {
      return (
        (user.role === "student" || user.role === "teacher") &&
        !user.is_superuser
      )
    }
    return true
  })

  const tableData: UserTableData[] = filteredUsers.map((user: UserPublic) => ({
    ...user,
    isCurrentUser: currentUser?.id === user.id,
  }))

  return <DataTable columns={columns} data={tableData} />
}

function UsersTable() {
  return (
    <Suspense fallback={<PendingUsers />}>
      <UsersTableContent />
    </Suspense>
  )
}

function StatsCard({ title, value, icon, gradient, border }: any) {
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
          </div>
        </CardContent>
      </Card>
    </motion.div>
  )
}

function AdminDashboard() {
  const { data: usersData } = useSuspenseQuery(getUsersQueryOptions())
  const { data: stats } = useSuspenseQuery(getAdminStatsQueryOptions())
  const users = usersData?.data || []

  // Stats
  const totalUsers = users.length
  const students = users.filter((u: UserPublic) => u.role === "student").length
  const teachers = users.filter((u: UserPublic) => u.role === "teacher").length

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

  const handleExportCSV = async () => {
    try {
      const token = localStorage.getItem("access_token")
      const response = await fetch(
        `${import.meta.env.VITE_API_URL}/api/v1/users/export-csv`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        },
      )

      if (!response.ok) {
        throw new Error("Failed to export CSV")
      }

      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = `fees_report_${new Date().toISOString().split("T")[0]}.csv`
      document.body.appendChild(a)
      a.click()
      a.remove()
      window.URL.revokeObjectURL(url)
    } catch (error) {
      console.error("Export failed:", error)
    }
  }

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
            Admin{" "}
            <span className="text-transparent bg-clip-text bg-linear-to-r from-purple-400 to-pink-500">
              Dashboard
            </span>
          </h1>
          <p className="text-zinc-400 text-lg">
            Manage users, configure settings, and monitor platform health.
          </p>
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
          title="Total Users"
          value={totalUsers}
          icon={<Users className="w-6 h-6 text-blue-400" />}
          gradient="from-blue-500/10 to-indigo-500/5"
          border="border-blue-500/20"
        />
        <StatsCard
          title="Total Students"
          value={students}
          icon={<Activity className="w-6 h-6 text-emerald-400" />}
          gradient="from-emerald-500/10 to-teal-500/5"
          border="border-emerald-500/20"
        />
        <StatsCard
          title="Total Teachers"
          value={teachers}
          icon={<ShieldCheck className="w-6 h-6 text-purple-400" />}
          gradient="from-purple-500/10 to-pink-500/5"
          border="border-purple-500/20"
        />
        <StatsCard
          title="Active Now"
          value={stats.active_now || 0}
          icon={<Activity className="w-6 h-6 text-orange-400" />}
          gradient="from-orange-500/10 to-amber-500/5"
          border="border-orange-500/20"
        />
      </motion.div>

      <Tabs defaultValue="users" className="space-y-8">
        <TabsList className="bg-zinc-900/40 backdrop-blur-md border border-white/10 p-1 h-auto rounded-xl inline-flex gap-1">
          <TabsTrigger
            value="users"
            className="px-6 py-2.5 rounded-lg data-[state=active]:bg-white/10 data-[state=active]:text-white data-[state=active]:shadow-none text-zinc-400 hover:text-white hover:bg-white/5 transition-all text-sm font-medium"
          >
            <Users className="w-4 h-4 mr-2" />
            Users
          </TabsTrigger>
          <TabsTrigger
            value="fees"
            className="px-6 py-2.5 rounded-lg data-[state=active]:bg-white/10 data-[state=active]:text-white data-[state=active]:shadow-none text-zinc-400 hover:text-white hover:bg-white/5 transition-all text-sm font-medium"
          >
            <CreditCard className="w-4 h-4 mr-2" />
            Fees & Payments
          </TabsTrigger>
          <TabsTrigger
            value="monitoring"
            className="px-6 py-2.5 rounded-lg data-[state=active]:bg-white/10 data-[state=active]:text-white data-[state=active]:shadow-none text-zinc-400 hover:text-white hover:bg-white/5 transition-all text-sm font-medium"
          >
            <Activity className="w-4 h-4 mr-2" />
            Live Monitor
          </TabsTrigger>
          <TabsTrigger
            value="analytics"
            className="px-6 py-2.5 rounded-lg data-[state=active]:bg-white/10 data-[state=active]:text-white data-[state=active]:shadow-none text-zinc-400 hover:text-white hover:bg-white/5 transition-all text-sm font-medium"
          >
            <BarChart3 className="w-4 h-4 mr-2" />
            Analytics
          </TabsTrigger>
          <TabsTrigger
            value="settings"
            className="px-6 py-2.5 rounded-lg data-[state=active]:bg-white/10 data-[state=active]:text-white data-[state=active]:shadow-none text-zinc-400 hover:text-white hover:bg-white/5 transition-all text-sm font-medium"
          >
            <SettingsIcon className="w-4 h-4 mr-2" />
            Settings
          </TabsTrigger>
        </TabsList>

        <TabsContent value="users" className="space-y-4 outline-none">
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <Card className="bg-zinc-900/40 backdrop-blur-md border border-white/10 overflow-hidden">
              <CardHeader className="flex flex-row items-center justify-between border-b border-white/5 pb-6">
                <div>
                  <CardTitle className="text-xl font-bold">
                    User Database
                  </CardTitle>
                  <p className="text-sm text-zinc-400 mt-1">
                    View and manage all registered users.
                  </p>
                </div>
                <AddUser />
              </CardHeader>
              <CardContent className="p-0">
                <UsersTable />
              </CardContent>
            </Card>
          </motion.div>
        </TabsContent>

        <TabsContent value="fees" className="space-y-4 outline-none">
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <Card className="bg-zinc-900/40 backdrop-blur-md border border-white/10">
              <CardHeader className="flex flex-row items-center justify-between border-b border-white/5">
                <div>
                  <CardTitle className="text-xl font-bold">
                    Fee Management
                  </CardTitle>
                  <p className="text-sm text-zinc-400 mt-1">
                    Manage student fee overrides and exemptions.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={handleExportCSV}
                  className="flex items-center gap-2 bg-zinc-800 hover:bg-zinc-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors border border-white/10"
                >
                  <Download className="w-4 h-4" /> Export CSV
                </button>
              </CardHeader>
              <CardContent className="p-0">
                <UsersTable />
              </CardContent>
            </Card>
          </motion.div>
        </TabsContent>

        <TabsContent value="monitoring" className="space-y-4 outline-none">
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <Card className="bg-zinc-900/40 backdrop-blur-md border border-white/10 overflow-hidden">
              <CardHeader className="border-b border-white/5">
                <CardTitle className="text-xl font-bold text-orange-400 flex items-center gap-2">
                  <Activity className="w-5 h-5 animate-pulse" /> Real-time
                  Activity
                </CardTitle>
                <p className="text-sm text-zinc-400">
                  Users active in the last 5 minutes.
                </p>
              </CardHeader>
              <div className="p-6">
                <div className="grid gap-4">
                  {users
                    .filter(
                      (u) =>
                        u.last_active_at &&
                        new Date(u.last_active_at).getTime() >
                          Date.now() - 300000,
                    )
                    .map((u) => (
                      <div
                        key={u.id}
                        className="flex items-center justify-between p-4 bg-white/5 border border-white/10 rounded-xl"
                      >
                        <div className="flex items-center gap-3">
                          <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                          <div>
                            <p className="font-bold">
                              {u.full_name || u.email}
                            </p>
                            <p className="text-xs text-zinc-500">{u.role}</p>
                          </div>
                        </div>
                        <div className="text-right">
                          <p className="text-xs font-mono text-purple-400 bg-purple-400/10 px-2 py-1 rounded">
                            {u.current_path || "/"}
                          </p>
                          <p className="text-[10px] text-zinc-600 mt-1">
                            {new Date(u.last_active_at!).toLocaleTimeString()}
                          </p>
                        </div>
                      </div>
                    ))}
                  {users.filter(
                    (u) =>
                      u.last_active_at &&
                      new Date(u.last_active_at).getTime() >
                        Date.now() - 300000,
                  ).length === 0 && (
                    <div className="text-center py-12 text-zinc-500">
                      No active users in the last 5 minutes.
                    </div>
                  )}
                </div>
              </div>
            </Card>
          </motion.div>
        </TabsContent>

        <TabsContent value="analytics" className="space-y-4 outline-none">
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <Card className="bg-zinc-900/40 backdrop-blur-md border border-white/10 overflow-hidden min-h-[400px]">
              <CardHeader>
                <CardTitle>Platform Analytics</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                  <div className="p-6 rounded-2xl bg-indigo-500/10 border border-indigo-500/20">
                    <p className="text-zinc-400 text-sm mb-1 uppercase tracking-wider font-bold">
                      Total Tests Scheduled
                    </p>
                    <p className="text-5xl font-black text-indigo-400">
                      {stats.total_tests}
                    </p>
                  </div>
                  <div className="p-6 rounded-2xl bg-emerald-500/10 border border-emerald-500/20">
                    <p className="text-zinc-400 text-sm mb-1 uppercase tracking-wider font-bold">
                      Student Submissions
                    </p>
                    <p className="text-5xl font-black text-emerald-400">
                      {stats.total_attempts}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        </TabsContent>

        <TabsContent value="settings" className="space-y-4 outline-none">
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <Settings />
          </motion.div>
        </TabsContent>
      </Tabs>
    </div>
  )
}
