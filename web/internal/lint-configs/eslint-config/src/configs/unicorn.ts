import type { Linter } from 'eslint';

import { interopDefault } from '../util';

export async function unicorn(): Promise<Linter.Config[]> {
  const [pluginUnicorn] = await Promise.all([
    interopDefault(import('eslint-plugin-unicorn')),
  ] as const);

  return [
    {
      plugins: {
        unicorn: pluginUnicorn,
      },
      rules: {
        ...pluginUnicorn.configs.recommended.rules,

        'unicorn/better-regex': 'off',
        'unicorn/consistent-destructuring': 'off',
        'unicorn/consistent-function-scoping': 'off',
        'unicorn/expiring-todo-comments': 'off',
        'unicorn/filename-case': 'off',
        'unicorn/import-style': 'off',
        'unicorn/no-array-for-each': 'off',
        'unicorn/no-null': 'off',
        'unicorn/no-useless-undefined': 'off',
        // 与 prettier 死锁：prettier 会把嵌套三元中"冗余"的括号删除、把十六进制
        // 字面量规范化为小写，而这两条规则要求保留括号/大写十六进制，二者互斥。
        // 格式化以 prettier 为准（vsh lint --format 最后执行 prettier）。
        'unicorn/no-nested-ternary': 'off',
        'unicorn/number-literal-case': 'off',
        'unicorn/prefer-at': 'off',
        'unicorn/prefer-dom-node-text-content': 'off',
        'unicorn/prefer-export-from': ['error', { ignoreUsedVariables: true }],
        'unicorn/prefer-global-this': 'off',
        'unicorn/prefer-top-level-await': 'off',
        'unicorn/prevent-abbreviations': 'off',
      },
    },
    {
      files: [
        'scripts/**/*.?([cm])[jt]s?(x)',
        'internal/**/*.?([cm])[jt]s?(x)',
      ],
      rules: {
        'unicorn/no-process-exit': 'off',
      },
    },
  ];
}
