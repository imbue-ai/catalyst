import { defineConfig } from 'vite';

export default defineConfig({
  base: '/openhost/',
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    // Use terser instead of the default esbuild minifier. esbuild mis-minifies
    // xterm.js 6.0.0's `requestMode` (DECRQM handler), dropping a `let`
    // declaration and emitting an assignment to an undeclared variable. Under
    // ES-module strict mode that throws `ReferenceError: assignment to
    // undeclared variable` the first time a program sends a DECRQM query
    // (`CSI ?2026$p`), aborting the terminal write and leaving a blank screen.
    // The `agy` harness is the only one that emits DECRQM, so only its auth
    // terminal was affected. terser compiles the same code correctly.
    minify: 'terser',
  },
});
