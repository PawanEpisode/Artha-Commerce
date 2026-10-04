import js from '@eslint/js'
import tseslint from 'typescript-eslint'
import reactHooks from 'eslint-plugin-react-hooks'

export default tseslint.config(
  { ignores: ['.output', 'dist', '.nitro', '.tanstack', 'node_modules', 'src/routeTree.gen.ts'] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    plugins: { 'react-hooks': reactHooks },
    rules: {
      'react-hooks/rules-of-hooks': 'error',
      'react-hooks/exhaustive-deps': 'warn',
      '@typescript-eslint/consistent-type-imports': 'warn',
      // Architecture guard: routes and modules must import through public barrels, not module internals.
      'no-restricted-imports': [
        'error',
        {
          patterns: [
            {
              group: ['~/modules/*/*/*'],
              message: 'Import from the module barrel (~/modules/<name>), not its internals.',
            },
          ],
        },
      ],
    },
  },
)
