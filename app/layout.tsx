import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Photo2CAD | Image to CAD Prototype",
  description: "Upload an object photo and generate estimated mesh and CAD-friendly draft files."
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
