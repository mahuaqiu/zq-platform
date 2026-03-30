import type { DefaultTheme } from 'vitepress';

import { defineConfig } from 'vitepress';

import { version } from '../../../package.json';

export const en = defineConfig({
  description: 'ZQ Platform & Enterprise level management system framework',
  lang: 'en-US',
  themeConfig: {
    darkModeSwitchLabel: 'Theme',
    darkModeSwitchTitle: 'Switch to Dark Mode',
    docFooter: {
      next: 'Next Page',
      prev: 'Previous Page',
    },
    footer: {
      copyright: `Copyright © 2020-${new Date().getFullYear()} ZQ-Platform`,
    },
    langMenuLabel: 'Language',
    lastUpdated: {
      formatOptions: {
        dateStyle: 'short',
        timeStyle: 'medium',
      },
      text: 'Last updated on',
    },
    lightModeSwitchTitle: 'Switch to Light Mode',
    nav: nav(),
    outline: {
      label: 'Navigate',
    },
    returnToTopLabel: 'Back to top',
    sidebar: {},
  },
});

function nav(): DefaultTheme.NavItem[] {
  return [
    {
      activeMatch: '^/(guide|components)/',
      text: 'Doc',
      items: [
        {
          activeMatch: '^/guide/',
          link: '/guide/introduction/vben',
          text: 'Guide',
        },
        {
          activeMatch: '^/components/',
          link: '/components/introduction',
          text: 'Components',
        },
        {
          text: 'Historical Versions',
          items: [
            {
              link: 'https://doc.vvbin.cn',
              text: '2.x Version Documentation',
            },
          ],
        },
      ],
    },
    {
      text: version,
      items: [
        {
          link: '/guide/introduction/changelog',
          text: 'Changelog',
        },
        {
          link: '/guide/introduction/roadmap',
          text: 'Roadmap',
        },
      ],
    },
  ];
}