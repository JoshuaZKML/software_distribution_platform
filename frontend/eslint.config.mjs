// eslint.config.mjs
import { defineConfig, globalIgnores } from 'eslint/config';
import nextVitals from 'eslint-config-next/core-web-vitals';
import nextTs from 'eslint-config-next/typescript';

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  globalIgnores([
    '.next/**',
    'out/**',
    'build/**',
    'next-env.d.ts',
    '**/*.generated.ts',
    '**/api/generated.ts',
  ]),
  {
    rules: {
      'react/no-unescaped-entities': 'off',
    },
  },
  {
    files: ['**/api/generated.ts'],
    rules: {
      '@typescript-eslint/no-unused-vars': 'off',
    },
  },
]);

export default eslintConfig;