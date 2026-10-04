export default {
  '*.{ts,tsx,js,mjs}': ['eslint --fix --max-warnings=0 --no-warn-ignored', 'prettier --write'],
  '*.{json,css,yml,yaml}': ['prettier --write'],
  'apps/api/**/*.py': ['bash scripts/ruff-staged.sh'],
}
