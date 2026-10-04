// Conventional Commits: feat(web): add syllabus tracker
export default {
  extends: ['@commitlint/config-conventional'],
  rules: {
    'scope-enum': [1, 'always', ['web', 'api', 'ds', 'docs', 'ci', 'deps', 'db', 'product', 'tooling']],
    'subject-case': [0],
    'header-max-length': [2, 'always', 100],
  },
}
