import { createFileRoute, redirect } from "@tanstack/react-router"
import { UsersService } from "@/client"
import TeacherDashboard from "@/components/Dashboard/TeacherDashboard"

export const Route = createFileRoute("/_layout/teacher-dashboard")({
  component: TeacherDashboard,
  beforeLoad: async () => {
    const user = await UsersService.readUserMe()
    if (user.role !== "teacher" && !user.is_superuser) {
      throw redirect({
        to: "/student-dashboard",
      })
    }
  },
})
