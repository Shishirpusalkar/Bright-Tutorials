import { zodResolver } from "@hookform/resolvers/zod"
import {
  createFileRoute,
  Link as RouterLink,
  redirect,
  useNavigate,
} from "@tanstack/react-router"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import type { Body_login_login_access_token as AccessToken } from "@/client"
import { AuthLayout } from "@/components/Common/AuthLayout"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import { PasswordInput } from "@/components/ui/password-input"
import useAuth, { isLoggedIn } from "@/hooks/useAuth"

const formSchema = z.object({
  username: z.string().email(),
  password: z
    .string()
    .min(1, { message: "Password is required" })
    .min(8, { message: "Password must be at least 8 characters" }),
}) satisfies z.ZodType<AccessToken>

type FormData = z.infer<typeof formSchema>

function Login() {
  const [role, setRole] = useState<"student" | "teacher">("student")
  const { loginMutation, logout } = useAuth()
  const navigate = useNavigate()
  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      username: "",
      password: "",
    },
  })

  const onSubmit = async (data: FormData) => {
    if (loginMutation.isPending) return

    try {
      const user = await loginMutation.mutateAsync(data)

      // Strict role enforcement
      if (user.role !== role) {
        alert(`You are a ${user.role}`)
        logout()
      } else {
        navigate({ to: "/" })
      }
    } catch (_error) {
      // Error handled by mutation
    }
  }

  return (
    <AuthLayout>
      <div className="flex flex-col gap-8">
        <div className="flex flex-col items-center gap-2 text-center">
          <div className="relative group">
            <div className="absolute -inset-4 bg-orange-500/20 rounded-full blur-2xl group-hover:bg-orange-500/30 transition-all duration-500" />
            <img
              src="/btc_logo.png"
              alt="Bright Tutorials Logo"
              className="h-32 w-auto relative drop-shadow-[0_0_20px_rgba(255,165,0,0.4)]"
            />
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white mt-4">
            Welcome Back
          </h1>
          <p className="text-sm text-orange-200/50">
            Brighten Your Future With Us
          </p>
        </div>

        <div className="flex p-1 bg-white/5 backdrop-blur-md rounded-xl border border-white/10">
          <button
            type="button"
            onClick={() => setRole("student")}
            className={`flex-1 py-2 text-sm font-semibold rounded-lg transition-all duration-300 ${
              role === "student"
                ? "bg-linear-to-r from-yellow-400 to-orange-500 text-white shadow-lg shadow-orange-500/20"
                : "text-white/40 hover:text-white/70 hover:bg-white/5"
            }`}
          >
            Student
          </button>
          <button
            type="button"
            onClick={() => setRole("teacher")}
            className={`flex-1 py-2 text-sm font-semibold rounded-lg transition-all duration-300 ${
              role === "teacher"
                ? "bg-linear-to-r from-yellow-400 to-orange-500 text-white shadow-lg shadow-orange-500/20"
                : "text-white/40 hover:text-white/70 hover:bg-white/5"
            }`}
          >
            Teacher
          </button>
        </div>

        <Form {...form}>
          <form
            onSubmit={form.handleSubmit(onSubmit)}
            className="flex flex-col gap-6"
          >
            <div className="grid gap-5">
              <FormField
                control={form.control}
                name="username"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel className="text-white/70 ml-1">
                      Email Address
                    </FormLabel>
                    <FormControl>
                      <Input
                        data-testid="email-input"
                        placeholder="user@example.com"
                        type="email"
                        className="bg-white/5 border-white/10 text-white placeholder:text-white/20 h-11 focus:ring-orange-500/50 focus:border-orange-500/50 rounded-xl"
                        {...field}
                      />
                    </FormControl>
                    <FormMessage className="text-xs text-red-400" />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="password"
                render={({ field }) => (
                  <FormItem>
                    <div className="flex items-center ml-1">
                      <FormLabel className="text-white/70">Password</FormLabel>
                      <RouterLink
                        to="/recover-password"
                        className="ml-auto text-xs text-orange-400 hover:text-orange-300 transition-colors"
                      >
                        Forgot your password?
                      </RouterLink>
                    </div>
                    <FormControl>
                      <PasswordInput
                        data-testid="password-input"
                        placeholder="••••••••"
                        className="bg-white/5 border-white/10 text-white placeholder:text-white/20 h-11 focus:ring-orange-500/50 focus:border-orange-500/50 rounded-xl"
                        {...field}
                      />
                    </FormControl>
                    <FormMessage className="text-xs text-red-400" />
                  </FormItem>
                )}
              />

              <LoadingButton
                type="submit"
                loading={loginMutation.isPending}
                className="h-11 rounded-xl bg-linear-to-r from-yellow-400 via-orange-500 to-orange-600 hover:scale-[1.02] active:scale-[0.98] transition-all shadow-xl shadow-orange-600/20 text-white font-bold border-none"
              >
                Launch Bright Future
              </LoadingButton>
            </div>

            <div className="text-center text-sm text-white/40 mt-2">
              Don't have an account?{" "}
              <RouterLink
                to="/signup"
                className="text-orange-400 font-semibold hover:text-orange-300 transition-colors underline-offset-4 hover:underline"
              >
                Register Now
              </RouterLink>
            </div>
          </form>
        </Form>
      </div>
    </AuthLayout>
  )
}

export const Route = createFileRoute("/login")({
  component: Login,
  beforeLoad: async () => {
    if (isLoggedIn()) {
      throw redirect({
        to: "/",
      })
    }
  },
  head: () => ({
    meta: [
      {
        title: "Log In - Bright Tutorials",
      },
    ],
  }),
})
