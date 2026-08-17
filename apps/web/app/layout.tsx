import "./globals.css";

import type { Metadata } from "next";
import { NextIntlClientProvider } from "next-intl";
import { getLocale, getMessages, getTranslations } from "next-intl/server";

import { PRODUCT_NAME } from "@/lib/branding";
import { Providers } from "@/components/providers";
import { localeDocumentTag } from "@/i18n/config";
import { fontVars } from "./fonts";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("Metadata");
  return {
    title: PRODUCT_NAME,
    description: t("description"),
    icons: {
      icon: [
        { url: "/favicon-32x32.png?v=3", sizes: "32x32", type: "image/png" },
        { url: "/sag-icon.png?v=3", sizes: "128x128", type: "image/png" },
        { url: "/favicon.ico?v=3", sizes: "any" },
      ],
      shortcut: ["/favicon-32x32.png?v=3"],
      apple: [{ url: "/apple-touch-icon.png?v=3", sizes: "180x180", type: "image/png" }],
    },
  };
}

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const locale = await getLocale();
  const messages = await getMessages();
  return (
    <html lang={localeDocumentTag(locale)} suppressHydrationWarning className={fontVars}>
      <head>
        <link rel="icon" type="image/png" sizes="32x32" href="/favicon-32x32.png?v=3" />
        <link rel="icon" type="image/png" sizes="128x128" href="/sag-icon.png?v=3" />
        <link rel="icon" href="/favicon.ico?v=3" sizes="any" />
        <link rel="apple-touch-icon" href="/apple-touch-icon.png?v=3" />
      </head>
      <body className="min-h-screen bg-background text-foreground antialiased">
        <NextIntlClientProvider locale={locale} messages={messages}>
          <Providers>{children}</Providers>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
