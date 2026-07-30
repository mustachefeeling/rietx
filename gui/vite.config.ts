import { svelte } from "@sveltejs/vite-plugin-svelte";
// from vitest/config, not vite: it is the one that types the `test` key
import { defineConfig } from "vitest/config";

// The build output is COMMITTED under src/pxrdref/gui/static, so installing the
// wheel never needs node.  Two consequences shape this config:
//
//   * stable filenames, no content hashes — a dist diff has to be reviewable,
//     and a hashed filename turns every rebuild into a rename;
//   * no sourcemaps and no build timestamp anywhere, so rebuilding unchanged
//     sources produces a byte-identical tree and `git diff --exit-code` means
//     "the dist is stale", not "someone rebuilt".
export default defineConfig({
  plugins: [svelte()],
  build: {
    outDir: "../src/pxrdref/gui/static",
    emptyOutDir: true,
    sourcemap: false,
    target: "es2022",
    // one chunk: the app is ~1500 lines and code splitting would trade a
    // reviewable dist for a load time nobody can measure on localhost
    cssCodeSplit: false,
    // one chunk, no dynamic-import splitting: see the note above.  Vite 8.1
    // asks for this key in place of rollup's `inlineDynamicImports` but has not
    // added it to BuildEnvironmentOptions yet, hence the cast.
    ...({ codeSplitting: false } as Record<string, unknown>),
    rollupOptions: {
      output: {
        entryFileNames: "assets/app.js",
        chunkFileNames: "assets/[name].js",
        assetFileNames: (info) =>
          info.names?.[0]?.endsWith(".css") ? "assets/app.css" : "assets/[name][extname]",
      },
    },
  },
  // Svelte's own testing guidance: under vitest, resolve the *browser* build of
  // svelte, or `mount()` comes from the server bundle and throws
  // `lifecycle_function_unavailable` — which is how a component test that only
  // ever ran on the server announces itself.
  resolve: process.env.VITEST ? { conditions: ["browser"] } : undefined,
  test: {
    environment: "node",
    include: ["src/**/*.test.ts"],
  },
});
