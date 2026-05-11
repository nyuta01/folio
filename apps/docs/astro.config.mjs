import { defineConfig } from "astro/config";
import starlight from "@astrojs/starlight";

// https://astro.build/config
//
// Hosting: GitHub Pages under https://nyuta01.github.io/folio/. The `base`
// is read by Astro to prefix internal asset URLs and Starlight slugs so the
// site works under a sub-path. Override either with the SITE / BASE env vars
// at build time when deploying to a different host.
const SITE = process.env.SITE ?? "https://nyuta01.github.io";
const BASE = process.env.BASE ?? "/folio";

export default defineConfig({
  site: SITE,
  base: BASE,
  integrations: [
    starlight({
      title: "Folio",
      tagline: "Portable, AI-native data sheets.",
      logo: {
        light: "./src/assets/logo-light.svg",
        dark: "./src/assets/logo-dark.svg",
        replacesTitle: false,
      },
      favicon: "/favicon.svg",
      head: [
        // Apple home-screen icon when the docs are pinned on iOS.
        {
          tag: "link",
          attrs: {
            rel: "apple-touch-icon",
            sizes: "180x180",
            href: BASE + "/apple-touch-icon.png",
          },
        },
        // Open Graph card for Twitter, Slack, Discord, LinkedIn, etc.
        {
          tag: "meta",
          attrs: { property: "og:type", content: "website" },
        },
        {
          tag: "meta",
          attrs: {
            property: "og:image",
            content: SITE + BASE + "/og-image.png",
          },
        },
        {
          tag: "meta",
          attrs: { property: "og:image:width", content: "1200" },
        },
        {
          tag: "meta",
          attrs: { property: "og:image:height", content: "630" },
        },
        // Twitter / X surfaces a card preview when og:image is present and
        // twitter:card is declared. summary_large_image gives the wide layout.
        {
          tag: "meta",
          attrs: { name: "twitter:card", content: "summary_large_image" },
        },
        {
          tag: "meta",
          attrs: {
            name: "twitter:image",
            content: SITE + BASE + "/og-image.png",
          },
        },
      ],
      social: {
        github: "https://github.com/nyuta01/folio",
      },
      editLink: {
        baseUrl:
          "https://github.com/nyuta01/folio/edit/main/apps/docs/",
      },
      tableOfContents: { minHeadingLevel: 2, maxHeadingLevel: 4 },
      customCss: [
        "./src/styles/tokens.css",
        "./src/styles/starlight-overrides.css",
      ],
      sidebar: [
        {
          label: "Introduction",
          items: [
            { label: "What is Folio", slug: "introduction/what-is-folio" },
            { label: "Concepts", slug: "introduction/concepts" },
            { label: "Architecture", slug: "introduction/architecture" },
          ],
        },
        {
          label: "Get started",
          items: [
            { label: "Installation", slug: "get-started/installation" },
            { label: "Quickstart with folio init", slug: "get-started/quickstart" },
            { label: "Your first sheet", slug: "get-started/your-first-sheet" },
            { label: "Materialize lifecycle", slug: "get-started/materialize-lifecycle" },
            { label: "Editing and provenance", slug: "get-started/editing-and-provenance" },
          ],
        },
        {
          label: "Sheet specification",
          items: [
            { label: "contract.yaml", slug: "sheet/contract" },
            { label: "records.jsonl", slug: "sheet/records" },
            {
              label: "Derivations",
              items: [
                { label: "Overview", slug: "sheet/derivations/overview" },
                { label: "ai", slug: "sheet/derivations/ai" },
                { label: "import", slug: "sheet/derivations/import" },
                { label: "python", slug: "sheet/derivations/python" },
                { label: "sql", slug: "sheet/derivations/sql" },
                { label: "http", slug: "sheet/derivations/http" },
                { label: "cross_sheet", slug: "sheet/derivations/cross-sheet" },
              ],
            },
            { label: "provenance.jsonl", slug: "sheet/provenance" },
            { label: "skills/", slug: "sheet/skills" },
            { label: "Edit permissions", slug: "sheet/editable-by" },
            { label: "Portability", slug: "sheet/portability" },
            { label: "Cache and runtime", slug: "sheet/cache-and-runtime" },
          ],
        },
        {
          label: "CLI",
          items: [
            { label: "Overview", slug: "cli/overview" },
            { label: "init", slug: "cli/init" },
            { label: "validate", slug: "cli/validate" },
            { label: "query", slug: "cli/query" },
            { label: "list", slug: "cli/list" },
            { label: "count", slug: "cli/count" },
            { label: "upsert", slug: "cli/upsert" },
            { label: "delete", slug: "cli/delete" },
            { label: "materialize", slug: "cli/materialize" },
            { label: "status", slug: "cli/status" },
            { label: "provenance", slug: "cli/provenance" },
            { label: "serve", slug: "cli/serve" },
            { label: "script", slug: "cli/script" },
            { label: "skill", slug: "cli/skill" },
            { label: "export", slug: "cli/export" },
          ],
        },
        {
          label: "Python SDK",
          items: [
            { label: "Overview", slug: "sdk/overview" },
            { label: "open_sheet", slug: "sdk/open-sheet" },
            { label: "Sheet API", slug: "sdk/sheet-api" },
            { label: "AI client", slug: "sdk/ai-client" },
            { label: "HTTP transport", slug: "sdk/http-transport" },
            { label: "Errors", slug: "sdk/errors" },
          ],
        },
        {
          label: "MCP server",
          items: [
            { label: "Overview", slug: "mcp/overview" },
            { label: "Tools", slug: "mcp/tools" },
            { label: "Deploy", slug: "mcp/deploy" },
          ],
        },
        {
          label: "Viewer",
          items: [
            { label: "Overview", slug: "viewer/overview" },
            { label: "Install and run", slug: "viewer/install-and-run" },
            { label: "REST API", slug: "viewer/rest-api" },
            { label: "Events (SSE)", slug: "viewer/events" },
            { label: "Frontend build", slug: "viewer/frontend" },
          ],
        },
        {
          label: "Guides",
          items: [
            { label: "Customer master enrichment", slug: "guides/customer-master" },
            { label: "Working memory for agents", slug: "guides/working-memory" },
            { label: "Research notes", slug: "guides/research-notes" },
            { label: "Onboarding worklist", slug: "guides/onboarding-worklist" },
          ],
        },
        {
          label: "Reference",
          items: [
            { label: "contract.yaml spec", slug: "reference/contract-spec" },
            { label: "Frictionless export", slug: "reference/datapackage" },
            { label: "ADRs", slug: "reference/adrs" },
            { label: "Glossary", slug: "reference/glossary" },
          ],
        },
      ],
    }),
  ],
});
