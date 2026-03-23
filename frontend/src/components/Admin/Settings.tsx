import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Loader2 } from "lucide-react"
import { useForm } from "react-hook-form"
import { SettingsService, type SystemSettingUpdate } from "@/client"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import useAuth from "@/hooks/useAuth"
import useCustomToast from "@/hooks/useCustomToast"

export default function Settings() {
  const { user } = useAuth()
  // Check if user is superuser AND NOT a teacher.
  // This overrides any potential database inconsistency where a teacher might have is_superuser=true.
  const canEdit = user?.is_superuser && user?.role !== "teacher"

  // Debugging: Console log the user status
  // console.log("Current User:", user)
  // console.log("Can Edit:", canEdit)
  const { data: settings, isLoading } = useQuery({
    queryKey: ["settings"],
    queryFn: () => SettingsService.readSettings({}),
  })

  // Helper to find setting value
  const getSettingValue = (key: string, defaultValue: string) => {
    const setting = settings?.find((s) => s.key === key)
    return setting?.value || defaultValue
  }

  if (isLoading) {
    return (
      <div className="flex justify-center p-8">
        <Loader2 className="animate-spin" />
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-in-fade">
      <div>
        <h2 className="text-3xl font-bold tracking-tight">Platform Settings</h2>
        <p className="text-muted-foreground">
          Manage global application configurations.
        </p>
      </div>

      <div className="grid gap-6">
        <FeeSettingCard
          settingKey="fee_grade_11"
          label="Grade 11 Fee (₹)"
          description="One-time subscription fee for 11th standard students."
          currentValue={getSettingValue("fee_grade_11", "500")}
          canEdit={canEdit}
        />

        <FeeSettingCard
          settingKey="fee_grade_12"
          label="Grade 12 Fee (₹)"
          description="One-time subscription fee for 12th standard students."
          currentValue={getSettingValue("fee_grade_12", "700")}
          canEdit={canEdit}
        />
      </div>
    </div>
  )
}

function FeeSettingCard({
  settingKey,
  label,
  description,
  currentValue,
  canEdit = false,
}: {
  settingKey: string
  label: string
  description: string
  currentValue: string
  canEdit?: boolean
}) {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const form = useForm({
    defaultValues: {
      value: currentValue,
    },
  })

  const mutation = useMutation({
    mutationFn: (data: SystemSettingUpdate) =>
      SettingsService.updateSetting({ key: settingKey, requestBody: data }),
    onSuccess: () => {
      showSuccessToast("Setting updated successfully")
      queryClient.invalidateQueries({ queryKey: ["settings"] })
    },
    onError: (err) => {
      showErrorToast("Failed to update setting")
      console.error(err)
    },
  })

  const onSubmit = (data: { value: string }) => {
    mutation.mutate({ value: data.value, description })
  }

  return (
    <Card className="bg-zinc-900/40 backdrop-blur-md border border-white/10">
      <CardHeader>
        <CardTitle className="text-white">{label}</CardTitle>
        <CardDescription className="text-zinc-400">
          {description}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Form {...form}>
          <form
            onSubmit={form.handleSubmit(onSubmit)}
            className="flex gap-4 items-end"
          >
            <FormField
              control={form.control}
              name="value"
              render={({ field }) => (
                <FormItem className="flex-1">
                  <FormLabel className="text-zinc-300">Amount</FormLabel>
                  <FormControl>
                    <Input
                      {...field}
                      type="number"
                      min="0"
                      disabled={!canEdit}
                      className="bg-zinc-800 border-white/10 text-white placeholder:text-zinc-500 disabled:opacity-50 disabled:cursor-not-allowed"
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            {canEdit && (
              <Button
                type="submit"
                disabled={mutation.isPending}
                className="bg-white text-black hover:bg-zinc-200"
              >
                {mutation.isPending && (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                )}
                Save
              </Button>
            )}
          </form>
        </Form>
      </CardContent>
    </Card>
  )
}
