// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import starlightLinksValidator from 'starlight-links-validator';

const repo = 'https://github.com/different-ai/openwork-bench';

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
