import type { Metadata, Viewport } from "next";

import { Providers } from "@/app/providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "Trading journal",
  description: "A private trading journal.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  // Both themes are supported; the browser picks the matching chrome.
  themeColor: [
    { media: "(prefers-color-scheme: dark)", color: "#07060d" },
    { media: "(prefers-color-scheme: light)", color: "#f7f6fb" },
  ],
};

/*
  Runs before first paint so the page never flashes the wrong theme.

  It has to be inline and synchronous: anything deferred would paint the
  default palette first. Kept deliberately tiny, and wrapped in try/catch
  because localStorage throws in a private window with site data blocked.
*/
const THEME_SCRIPT = `(function(){try{
var c=localStorage.getItem("tj:theme")||"system";
var d=c==="dark"||(c==="system"&&!window.matchMedia("(prefers-color-scheme: light)").matches);
var t=d?"dark":"light";
document.documentElement.dataset.theme=t;
document.documentElement.style.colorScheme=t;
}catch(e){document.documentElement.dataset.theme="dark";}})();`;

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full" data-theme="dark" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
      </head>
      <body className="min-h-full font-sans antialiased bg-bg-0 text-text-0">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
