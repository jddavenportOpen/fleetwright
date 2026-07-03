import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Fleetwright',
  description: 'Self-hosted agent operations cockpit',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
