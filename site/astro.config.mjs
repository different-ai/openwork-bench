// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import starlightLinksValidator from 'starlight-links-validator';

const repo = 'https://github.com/different-ai/openwork-bench';
// The image link previews show for docs pages too (scripts/og-image.mjs renders it).
const ogImage = 'https://different-ai.github.io/openwork-bench/og.png';
const ogAlt = 'OpenWork Bench: which open models can you trust with real work?';

export default defineConfig({
  site: 'https://different-ai.github.io',
  base: '/openwork-bench',
  trailingSlash: 'always',
  integrations: [
    starlight({
      title: 'OpenWork Bench',
      description: 'An open benchmark of open-weight AI models on real knowledge work: which ones you can trust, at what cost, speed and risk.',
      social: [{ icon: 'github', label: 'GitHub', href: repo }],
      head: [
        { tag: 'meta', attrs: { property: 'og:image', content: ogImage } },
        { tag: 'meta', attrs: { property: 'og:image:width', content: '1200' } },
        { tag: 'meta', attrs: { property: 'og:image:height', content: '630' } },
        { tag: 'meta', attrs: { property: 'og:image:alt', content: ogAlt } },
        { tag: 'meta', attrs: { name: 'twitter:image', content: ogImage } },
        { tag: 'meta', attrs: { name: 'twitter:image:alt', content: ogAlt } },
        { tag: 'link', attrs: { rel: 'preconnect', href: 'https://fonts.googleapis.com' } },
        { tag: 'link', attrs: { rel: 'preconnect', href: 'https://fonts.gstatic.com', crossorigin: true } },
        {
          tag: 'link',
          attrs: {
            rel: 'stylesheet',
            href: 'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap',
          },
        },
      ],
      // The leaderboard at the site root is an Astro page, not a docs page.
      plugins: [starlightLinksValidator({ errorOnLocalLinks: false, exclude: ['/openwork-bench/'] })],
      sidebar: [{ label: 'Documentation', items: [{ autogenerate: { directory: 'docs' } }] }],
    }),
  ],
});
