// ESLint 9 flat config — React + TypeScript + Vite.
// Composta dai pacchetti già presenti in node_modules (@eslint/js e globals sono
// dipendenze di eslint; il parser/plugin TS sono dichiarati in devDependencies).
// Non usiamo l'umbrella `typescript-eslint`: parser + plugin diretti bastano.
import js from '@eslint/js';
import globals from 'globals';
import tsParser from '@typescript-eslint/parser';
import tsPlugin from '@typescript-eslint/eslint-plugin';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';

export default [
  { ignores: ['dist', 'docs', 'coverage', 'playwright-report', 'test-results'] },

  // Regole base ESLint (tutti i file: src, config, scripts).
  js.configs.recommended,

  // Codice applicativo React + TypeScript.
  {
    files: ['src/**/*.{ts,tsx}'],
    languageOptions: {
      ecmaVersion: 2020,
      sourceType: 'module',
      parser: tsParser,
      globals: { ...globals.browser },
    },
    plugins: {
      '@typescript-eslint': tsPlugin,
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
    },
    rules: {
      ...tsPlugin.configs.recommended.rules,
      ...reactHooks.configs.recommended.rules,
      // TypeScript copre già i simboli non definiti: la regola base genera solo
      // falsi positivi su tipi/globali. Standard typescript-eslint.
      'no-undef': 'off',
      // Sostituita dalla variante TS, che capisce type-only import ed enum.
      'no-unused-vars': 'off',
      // Formalizza la convenzione underscore già usata nel codice per
      // argomenti/variabili/catch intenzionalmente ignorati.
      '@typescript-eslint/no-unused-vars': [
        'error',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_', caughtErrorsIgnorePattern: '^_' },
      ],
      // allowConstantExport: default del template Vite (permette `export const X`
      // accanto al componente senza rompere il fast-refresh).
      'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],
    },
  },

  // Bottoni raw vietati fuori dal kit UI: ogni superficie tappabile deve saper
  // esprimere lo stato pending (spec 2026-07-16, DESIGN.md §Buttons).
  {
    files: ['src/**/*.tsx'],
    ignores: ['src/components/ui/**'],
    rules: {
      'no-restricted-syntax': [
        'error',
        {
          selector: "JSXOpeningElement[name.name='button']",
          message: 'Bottone raw vietato: usa Button, IconButton o Pressable da components/ui/ (feedback pending integrato).',
        },
        {
          selector: "JSXOpeningElement[name.object.name='m'][name.property.name='button']",
          message: 'm.button raw vietato: usa Button, IconButton o Pressable da components/ui/ (feedback pending integrato).',
        },
      ],
    },
  },

  // File di config / script Node (vite.config.ts, playwright config, scripts/*).
  {
    files: ['*.{js,cjs,mjs,ts}', 'scripts/**/*.{js,mjs}'],
    languageOptions: { globals: { ...globals.node } },
  },

  // Perf harness (scripts/perf/): oltre al codice Node, usa page.evaluate()
  // per callback eseguite nel contesto browser della WebView/Chrome tracciata.
  {
    files: ['scripts/perf/**/*.mjs'],
    languageOptions: { globals: { ...globals.node, ...globals.browser } },
  },

  // Spec E2E Playwright: scaffolding di test, NON codice React.
  // - niente plugin React → niente falsi positivi di rules-of-hooks su helper non-React;
  // - `no-explicit-any` off → gli E2E usano any per i payload di page.evaluate e i cast lato browser.
  {
    files: ['tests/**/*.{ts,tsx}'],
    languageOptions: {
      sourceType: 'module',
      parser: tsParser,
      globals: { ...globals.node, ...globals.browser },
    },
    plugins: { '@typescript-eslint': tsPlugin },
    rules: {
      ...tsPlugin.configs.recommended.rules,
      'no-undef': 'off',
      'no-unused-vars': 'off',
      '@typescript-eslint/no-explicit-any': 'off',
      '@typescript-eslint/no-unused-vars': [
        'error',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_', caughtErrorsIgnorePattern: '^_' },
      ],
    },
  },
];
