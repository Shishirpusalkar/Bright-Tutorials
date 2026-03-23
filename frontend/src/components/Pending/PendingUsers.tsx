import { Card, CardContent } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

const PendingUsers = () => (
  <Card className="bg-zinc-900/40 backdrop-blur-md border border-white/10 shadow-xl overflow-hidden">
    <CardContent className="p-0">
      <Table>
        <TableHeader className="bg-white/5 border-b border-white/10">
          <TableRow className="hover:bg-transparent border-white/10">
            <TableHead className="text-zinc-400">Full Name</TableHead>
            <TableHead className="text-zinc-400">Email</TableHead>
            <TableHead className="text-zinc-400">Role</TableHead>
            <TableHead className="text-zinc-400">Status</TableHead>
            <TableHead className="text-zinc-400">
              <span className="sr-only">Actions</span>
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {Array.from({ length: 5 }).map((_, index) => (
            <TableRow
              key={index}
              className="border-white/10 hover:bg-white/5 transition-colors"
            >
              <TableCell>
                <Skeleton className="h-4 w-32 bg-zinc-800" />
              </TableCell>
              <TableCell>
                <Skeleton className="h-4 w-40 bg-zinc-800" />
              </TableCell>
              <TableCell>
                <Skeleton className="h-5 w-20 rounded-full bg-zinc-800" />
              </TableCell>
              <TableCell>
                <div className="flex items-center gap-2">
                  <Skeleton className="size-2 rounded-full bg-zinc-800" />
                  <Skeleton className="h-4 w-12 bg-zinc-800" />
                </div>
              </TableCell>
              <TableCell>
                <div className="flex justify-end">
                  <Skeleton className="size-8 rounded-md bg-zinc-800" />
                </div>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </CardContent>
  </Card>
)

export default PendingUsers
