import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SkinStyle AI — Colour styling for your skin tone",
  description:
    "Upload a selfie to discover the clothing colours that complement your skin tone, then preview them with virtual try-on.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="flex min-h-full flex-col bg-stone-50 text-stone-900">
        {children}
      </body>
    </html>
  );
}
