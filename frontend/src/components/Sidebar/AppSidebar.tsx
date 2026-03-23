import { BookOpen, GraduationCap, Home, LogOut, Users } from "lucide-react"

import { SidebarAppearance } from "@/components/Common/Appearance"
import { Logo } from "@/components/Common/Logo"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar"
import useAuth from "@/hooks/useAuth"
import { type Item, Main } from "./Main"
import { User } from "./User"

const baseItems: Item[] = [{ icon: Home, title: "Dashboard", path: "/" }]

export function AppSidebar() {
  const { user: currentUser, logout } = useAuth()

  const items = [...baseItems]

  if (currentUser?.role === "admin" || currentUser?.role === "teacher") {
    items.push({ icon: Users, title: "Admin", path: "/admin" })
  }

  if (currentUser?.role === "student") {
    items.push({
      icon: GraduationCap,
      title: "Self Study",
      path: "/student-dashboard",
    })
  } else if (currentUser?.role === "teacher") {
    items.push({
      icon: BookOpen,
      title: "Manage Tests",
      path: "/teacher-dashboard",
    })
  }

  return (
    <Sidebar collapsible="icon" className="glass border-r">
      <SidebarHeader className="px-4 py-6 group-data-[collapsible=icon]:px-0 group-data-[collapsible=icon]:items-center">
        <Logo variant="responsive" />
      </SidebarHeader>
      <SidebarContent>
        <Main items={items} />
      </SidebarContent>
      <SidebarFooter>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              tooltip="Logout"
              onClick={() => {
                if (window.confirm("Are you sure you want to logout?")) {
                  logout()
                }
              }}
              className="text-destructive hover:text-destructive hover:bg-destructive/10"
            >
              <LogOut className="size-4" />
              <span>Logout</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
        <SidebarAppearance />
        {currentUser && <User user={currentUser} />}
      </SidebarFooter>
    </Sidebar>
  )
}

export default AppSidebar
