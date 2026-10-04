import js from '@eslint/js'
import jsxA11y from 'eslint-plugin-jsx-a11y'
import reactHooks from 'eslint-plugin-react-hooks'
import simpleImportSort from 'eslint-plugin-simple-import-sort'
import unusedImports from 'eslint-plugin-unused-imports'
import globals from 'globals'
import tseslint from 'typescript-eslint'

export default tseslint.config(
  {
    ignores: [
      '**/node_modules/**',
      '**/.output/**',
      '**/dist/**',
      '**/.nitro/**',
      '**/.tanstack/**',
      '**/.vercel/**',
      '**/routeTree.gen.ts',
      'apps/api/**',
    ],
  },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ['**/*.{ts,tsx}'],
    languageOptions: { globals: { ...globals.browser, ...globals.node } },
    plugins: {
      'react-hooks': reactHooks,
      'jsx-a11y': jsxA11y,
      'simple-import-sort': simpleImportSort,
      'unused-imports': unusedImports,
    },
    rules: {
      ...jsxA11y.flatConfigs.recommended.rules,
      'react-hooks/set-state-in-effect': 'off',
      'react-hooks/rules-of-hooks': 'error',
      'react-hooks/exhaustive-deps': 'warn',

      // Imports: sorted automatically, no dead imports.
      'simple-import-sort/imports': 'error',
      'simple-import-sort/exports': 'error',
      'unused-imports/no-unused-imports': 'error',
      '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_', varsIgnorePattern: '^_' }],
      '@typescript-eslint/consistent-type-imports': ['error', { fixStyle: 'inline-type-imports' }],

      // Code quality.
      eqeqeq: ['error', 'always'],
      'no-console': ['warn', { allow: ['warn', 'error'] }],
      'prefer-const': 'error',
      'no-var': 'error',
      '@typescript-eslint/no-explicit-any': 'error',
      '@typescript-eslint/no-non-null-assertion': 'warn',

      // Architecture guards (see .claude/skills/frontend-architecture).
      'no-restricted-imports': [
        'error',
        {
          patterns: [
            {
              group: ['~/modules/*/*/*'],
              message: 'Import from the module barrel (~/modules/<name>), not its internals.',
            },
            {
              group: ['@artha/design-system/src/*'],
              message: "Import from '@artha/design-system', not its source files.",
            },
          ],
        },
      ],
    },
  },
  {
    files: ['apps/web/src/**/*.{ts,tsx}'],
    rules: {
      'no-restricted-imports': [
        'error',
        {
          patterns: [
            {
              group: ['~/modules/*/*/*'],
              message: 'Import from the module barrel (~/modules/<name>), not its internals.',
            },
            {
              group: ['@artha/design-system/src/*'],
              message: "Import from '@artha/design-system', not its source files.",
            },
            { group: ['**/components/ui/*'], message: 'UI primitives live in @artha/design-system.' },
          ],
        },
      ],
    },
  },
  {
    // Module code must not reach into routes.
    files: ['apps/web/src/modules/**/*.{ts,tsx}'],
    rules: {
      'no-restricted-imports': [
        'error',
        {
          patterns: [
            { group: ['~/routes/*'], message: 'Modules must not import from routes.' },
            {
              group: ['~/modules/*/*/*'],
              message: 'Import from the module barrel (~/modules/<name>), not its internals.',
            },
            {
              group: ['@artha/design-system/src/*'],
              message: "Import from '@artha/design-system', not its source files.",
            },
            { group: ['**/components/ui/*'], message: 'UI primitives live in @artha/design-system.' },
          ],
        },
      ],
    },
  },
  {
    // Primitives forward children through props, which the a11y rule cannot see.
    files: ['packages/design-system/src/**/*.tsx'],
    rules: { 'jsx-a11y/heading-has-content': 'off' },
  },
  {
    files: ['**/*.test.{ts,tsx}'],
    rules: { '@typescript-eslint/no-non-null-assertion': 'off' },
  },
  {
    files: ['**/scripts/**/*.{js,mjs}', '*.config.{js,mjs,ts}', 'apps/web/vite.config.ts'],
    languageOptions: { globals: { ...globals.node } },
    rules: { 'no-console': 'off' },
  },
)
