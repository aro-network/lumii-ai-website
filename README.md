# LumiiAI Website

Official marketing website for [LumiiAI](https://lumii-ai.io) — Clean & Stable AI Token API Access.

## Tech Stack

- **Vite 5** — build tooling & dev server
- **Tailwind CSS v4** — utility-first styling (via `@tailwindcss/vite`)
- **Vanilla JS** — no framework overhead; copy button, mobile nav, smooth scroll
- **Google Fonts** — Space Grotesk (headlines) + Inter (body) + JetBrains Mono (code)
- **Material Symbols** — icons

## Project Structure

```
lumii-ai-website/
├── src/
│   ├── index.html       # Main page (Vite root)
│   ├── style.css        # Tailwind v4 + custom tokens & utilities
│   └── main.js          # Copy button, mobile nav, smooth scroll
├── public/
│   ├── favicon.svg      # Favicon (place your SVG here)
│   ├── favicon.png      # Fallback favicon
│   └── og-image.png     # Open Graph / Twitter card image (1200×630)
├── spec/
│   ├── website-spec-en.md   # Product/content specification
│   ├── DESIGN.md            # Design system: Technical Etherealism
│   ├── code.html            # Stitch-generated reference design
│   └── screen.png           # Reference screenshot
├── dist/                # Build output (gitignored)
├── package.json
├── vite.config.js
├── vercel.json          # Vercel deployment config
├── netlify.toml         # Netlify deployment config
└── .gitignore
```

## Getting Started

### Prerequisites

- Node.js 18+
- npm 9+ (or pnpm / yarn)

### Install

```bash
npm install
```

### Dev Server

```bash
npm run dev
```

Opens at `http://localhost:5173` with HMR.

### Build for Production

```bash
npm run build
```

Output goes to `dist/`. The build is a fully static site — no server required.

### Preview Build Locally

```bash
npm run preview
```

## Deployment

### Vercel (recommended)

```bash
# Push to GitHub, then import repo at vercel.com
# Root: ./   Build command: npm run build   Output: dist
```

Or with the CLI:

```bash
npx vercel --prod
```

### Netlify

```bash
# Push to GitHub, connect at netlify.com
# Build command: npm run build   Publish dir: dist
```

Or drag & drop the `dist/` folder at [app.netlify.com/drop](https://app.netlify.com/drop).

### GitHub Pages

```bash
npm run build
npx gh-pages -d dist
```

## Before Going Live

1. **Add assets** — place `favicon.svg`, `favicon.png`, and `og-image.png` (1200×630) in `public/`
2. **Update URLs** — replace `https://lumii-ai.io` canonical/og URLs in `src/index.html`
3. **Wire up CTAs** — replace `href="#"` links with real URLs (sign-up, docs, status, etc.)
4. **Copyright year** — currently set to 2026 in footer

## Design System

See [`spec/DESIGN.md`](spec/DESIGN.md) for the full **Technical Etherealism** design system. Key principles:

- Monochromatic grayscale — no chromatic accents
- "No-line" rule — sections separated by tonal transitions, not borders
- Space Grotesk headlines at tight letter-spacing
- Ambient shadows (high blur, low opacity) instead of heavy drop shadows

## License

Copyright © 2026 LumiiAI. All rights reserved.
