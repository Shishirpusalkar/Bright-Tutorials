import type { ColumnDef } from "@tanstack/react-table"

import type { UserPublic } from "@/client"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import { UserActionsMenu } from "./UserActionsMenu"

export type UserTableData = UserPublic & {
  isCurrentUser: boolean
}

export const columns: ColumnDef<UserTableData>[] = [
  {
    accessorKey: "full_name",
    header: "Full Name",
    cell: ({ row }) => {
      const fullName = row.original.full_name
      return (
        <div className="flex items-center gap-2">
          <span
            className={cn("font-medium", !fullName && "text-muted-foreground")}
          >
            {fullName || "N/A"}
          </span>
          {row.original.isCurrentUser && (
            <Badge variant="outline" className="text-xs">
              You
            </Badge>
          )}
        </div>
      )
    },
  },
  {
    accessorKey: "email",
    header: "Email",
    cell: ({ row }) => (
      <span className="text-muted-foreground">{row.original.email}</span>
    ),
  },
  {
    accessorKey: "role",
    header: "Role",
    cell: ({ row }) => {
      const role = row.original.role
      const isSuperuser = row.original.is_superuser
      return (
        <Badge
          variant={
            isSuperuser
              ? "default"
              : role === "teacher"
                ? "outline"
                : "secondary"
          }
        >
          {isSuperuser ? "Admin" : role.charAt(0).toUpperCase() + role.slice(1)}
        </Badge>
      )
    },
  },
  {
    accessorKey: "standard",
    header: "Standard",
    cell: ({ row }) => row.original.standard || "N/A",
  },
  {
    accessorKey: "stream",
    header: "Stream",
    cell: ({ row }) =>
      row.original.stream
        ? row.original.stream === "engineering"
          ? "JEE"
          : "NEET"
        : "N/A",
  },

  {
    id: "actions",
    header: () => <span className="sr-only">Actions</span>,
    cell: ({ row }) => (
      <div className="flex justify-end">
        <UserActionsMenu user={row.original} />
      </div>
    ),
  },
]
