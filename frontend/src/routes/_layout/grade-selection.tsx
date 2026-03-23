import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { CheckCircle2, GraduationCap, ShieldCheck } from "lucide-react"
import { useEffect, useState } from "react"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import useAuth from "@/hooks/useAuth"
import useCustomToast from "@/hooks/useCustomToast"

export const Route = createFileRoute("/_layout/grade-selection" as any)({
  component: GradeSelection,
})

declare global {
  interface Window {
    Razorpay: any
  }
}

function GradeSelection() {
  const [loading, setLoading] = useState<number | null>(null)
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const navigate = useNavigate()

  useEffect(() => {
    // Load Razorpay Script
    const script = document.createElement("script")
    script.src = "https://checkout.razorpay.com/v1/checkout.js"
    script.async = true
    document.body.appendChild(script)
  }, [])

  const handlePayment = async (grade: number) => {
    setLoading(grade)
    try {
      // 1. Create Order
      const response = await fetch("/api/v1/create-order", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("access_token")}`,
        },
        body: JSON.stringify({ grade }),
      })

      if (!response.ok) {
        const errorText = await response.text()
        console.error("Create order failed:", response.status, errorText)
        throw new Error(
          `Failed to create order: ${response.status} ${errorText}`,
        )
      }

      const order = await response.json()

      // 2. Open Razorpay Popup
      const options = {
        key: order.razorpay_key,
        amount: order.amount,
        currency: "INR",
        name: "BTC Institute",
        description: `Full Access - Std ${grade}th`,
        order_id: order.order_id,
        handler: async (response: any) => {
          try {
            // 3. Verify Payment
            const verifyRes = await fetch("/api/v1/verify-payment", {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
                Authorization: `Bearer ${localStorage.getItem("access_token")}`,
              },
              body: JSON.stringify({
                razorpay_order_id: response.razorpay_order_id,
                razorpay_payment_id: response.razorpay_payment_id,
                razorpay_signature: response.razorpay_signature,
              }),
            })

            if (verifyRes.ok) {
              showSuccessToast("Payment Successful! Welcome aboard.")
              navigate({ to: "/student-dashboard" as any })
            } else {
              throw new Error("Payment verification failed")
            }
          } catch (_err) {
            showErrorToast("Verification failed. Please contact support.")
          }
        },
        prefill: {
          name: "",
          email: "",
        },
        theme: {
          color: "#ea580c", // orange-600
        },
      }

      const rzp = new window.Razorpay(options)
      rzp.on("payment.failed", (response: any) => {
        showErrorToast(response.error.description)
      })
      rzp.open()
    } catch (error) {
      console.error("Payment initiation error:", error)
      showErrorToast("Could not initiate payment. Check console for details.")
    } finally {
      setLoading(null)
    }
  }

  const { user } = useAuth()
  const now = new Date()
  const expiryDate = user?.premium_expiry ? new Date(user.premium_expiry) : null
  const isExpired = expiryDate ? now > expiryDate : false
  const standard = user?.standard || "11th"

  // Logic to determine which plan to show
  // 1. If never paid, show their registered standard plan
  // 2. If 11th and expired, show 12th plan (upgrade)
  // 3. If 12th and expired, show "Services Completed"

  const show11th =
    standard === "11th" && (!user?.is_paid || (user.is_paid && !isExpired))
  const show12th =
    (standard === "12th" && (!user?.is_paid || (user.is_paid && !isExpired))) ||
    (standard === "11th" && isExpired)
  const servicesCompleted = standard === "12th" && isExpired

  return (
    <div className="flex flex-col items-center justify-center min-h-[80vh] gap-8 animate-in-fade px-4">
      <div className="text-center space-y-4">
        <h1 className="text-4xl font-black tracking-tight text-white">
          {servicesCompleted ? (
            "Journey <span className='text-orange-500'>Completed</span>"
          ) : (
            <>
              Select Your{" "}
              <span className="text-orange-500">Academic Journey</span>
            </>
          )}
        </h1>
        <p className="text-zinc-400 max-w-lg mx-auto">
          {servicesCompleted
            ? "Your subscription for the 12th standard has concluded. You can still access all your previous test results and analysis from the dashboard."
            : "Upgrade to premium and unlock artificial intelligence powered test analysis, OMR extraction, and real JEE/NEET exam simulations."}
        </p>
      </div>

      <div className="flex justify-center w-full max-w-xl">
        {servicesCompleted && (
          <Card className="bg-zinc-900/50 border-orange-500/20 w-full text-center py-12">
            <CardHeader>
              <div className="mx-auto bg-orange-500/10 w-20 h-20 rounded-full flex items-center justify-center mb-4">
                <CheckCircle2 className="text-orange-500" size={40} />
              </div>
              <CardTitle className="text-2xl font-bold italic">
                Well Done!
              </CardTitle>
              <CardDescription className="text-zinc-400 mt-2">
                You have successfully completed your services with BTC
                Institute.
                <br />
                Your history will be preserved forever.
              </CardDescription>
            </CardHeader>
            <CardFooter className="justify-center">
              <Button
                variant="outline"
                className="border-zinc-700 text-zinc-300 hover:bg-zinc-800"
                onClick={() => navigate({ to: "/student-dashboard" as any })}
              >
                Go to Dashboard
              </Button>
            </CardFooter>
          </Card>
        )}

        {/* Class 11 Plan */}
        {!servicesCompleted && show11th && (
          <Card className="bg-zinc-900/50 border-white/10 hover:border-orange-500/50 transition-all group relative overflow-hidden w-full">
            <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
              <GraduationCap size={80} />
            </div>
            <CardHeader>
              <CardTitle className="text-2xl font-bold">
                Standard 11th
              </CardTitle>
              <CardDescription>Foundation for Excellence</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="text-4xl font-black">
                ₹500{" "}
                <span className="text-sm font-medium text-zinc-500">
                  / till March 31st
                </span>
              </div>
              <ul className="space-y-2">
                <li className="flex items-center gap-2 text-sm text-zinc-300">
                  <CheckCircle2 className="text-orange-500" size={16} /> Full AI
                  Analysis access
                </li>
                <li className="flex items-center gap-2 text-sm text-zinc-300">
                  <CheckCircle2 className="text-orange-500" size={16} /> OMR
                  Test Submissions
                </li>
                <li className="flex items-center gap-2 text-sm text-zinc-300">
                  <CheckCircle2 className="text-orange-500" size={16} />{" "}
                  Unlimited Practice Tests
                </li>
              </ul>
            </CardContent>
            <CardFooter>
              <Button
                className="w-full bg-orange-600 hover:bg-orange-700 text-white font-bold h-12"
                onClick={() => handlePayment(11)}
                disabled={loading !== null}
              >
                {loading === 11 ? "Processing..." : "Pay ₹500"}
              </Button>
            </CardFooter>
          </Card>
        )}

        {/* Class 12 Plan */}
        {!servicesCompleted && show12th && (
          <Card className="bg-zinc-900/50 border-white/10 hover:border-orange-500/50 transition-all group relative overflow-hidden w-full">
            <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity text-orange-500">
              <ShieldCheck size={80} />
            </div>
            <CardHeader>
              <CardTitle className="text-2xl font-bold">
                Standard 12th
              </CardTitle>
              <CardDescription>
                {standard === "11th"
                  ? "Upgrade to Target JEE / NEET"
                  : "Target JEE / NEET Boards"}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="text-4xl font-black">
                ₹700{" "}
                <span className="text-sm font-medium text-zinc-500">
                  / till May 31st
                </span>
              </div>
              <ul className="space-y-2">
                <li className="flex items-center gap-2 text-sm text-zinc-300">
                  <CheckCircle2 className="text-orange-500" size={16} /> Full AI
                  Analysis access
                </li>
                <li className="flex items-center gap-2 text-sm text-zinc-300">
                  <CheckCircle2 className="text-orange-500" size={16} />{" "}
                  JEE/NEET Advanced Simulators
                </li>
                <li className="flex items-center gap-2 text-sm text-zinc-300">
                  <CheckCircle2 className="text-orange-500" size={16} /> Board
                  Exam Preparation Kit
                </li>
              </ul>
            </CardContent>
            <CardFooter>
              <Button
                className="w-full bg-linear-to-r from-orange-600 to-orange-500 hover:from-orange-500 hover:to-yellow-500 text-white font-bold h-12"
                onClick={() => handlePayment(12)}
                disabled={loading !== null}
              >
                {loading === 12
                  ? "Processing..."
                  : isExpired
                    ? "Upgrade to 12th (₹700)"
                    : "Pay ₹700"}
              </Button>
            </CardFooter>
          </Card>
        )}
      </div>

      {!servicesCompleted && (
        <p className="text-zinc-500 text-sm flex items-center gap-2">
          <ShieldCheck size={14} /> Secured by Razorpay - Standard Encryption
          Applied
        </p>
      )}
    </div>
  )
}
