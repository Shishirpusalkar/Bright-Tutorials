import { Instagram, Linkedin, MessageCircle } from "lucide-react"

export const SITE_CONFIG = {
  name: "Bright Tutorials",
  brandLogo: "/btc_logo.png",
  contact: {
    email: "support@brighttutorials.com", // TODO: Update with user's email
    phone: "+91 00000 00000", // TODO: Update with user's phone
    address: "Your Center Address, City", // TODO: Update with user's address
  },
  socials: [
    {
      label: "WhatsApp",
      href: "https://wa.me/your-number", // TODO: Update with user's WhatsApp
      icon: MessageCircle,
      color: "text-green-500",
    },
    {
      label: "Instagram",
      href: "https://instagram.com/your-handle", // TODO: Update with user's Instagram
      icon: Instagram,
      color: "text-pink-500",
    },
    {
      label: "LinkedIn",
      href: "https://linkedin.com/company/your-company", // TODO: Update with user's LinkedIn
      icon: Linkedin,
      color: "text-blue-500",
    },
  ],
  links: {
    privacy: "#!",
    terms: "#!",
    contactUs: "mailto:support@brighttutorials.com",
  },
}
