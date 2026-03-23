import { createFileRoute, redirect } from "@tanstack/react-router"
import { UsersService } from "@/client"
import StudentDashboard from "@/components/Dashboard/StudentDashboard"

export const Route = createFileRoute("/_layout/student-dashboard")({
  component: StudentDashboard,
  beforeLoad: async () => {
    const user = await UsersService.readUserMe()
    if (user.role !== "student" && !user.is_superuser) {
      throw redirect({
        to: "/teacher-dashboard",
      })
    }
    if (!user.is_paid && !user.is_superuser) {
      throw redirect({
        to: "/grade-selection" as any,
      })
    }
  },
})
