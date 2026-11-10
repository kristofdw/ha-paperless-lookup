import { defineConfig } from "vitest/config";

// One ES module with the panel, the card and its editor, committed to the integration because
// The Marketplace (formerly HACS) does not run build tools.
export default defineConfig({
  build: {
    outDir: "../custom_components/paperless_lookup/frontend",
    emptyOutDir: true,
    target: "es2022",
    lib: {
      entry: "src/main.ts",
      formats: ["es"],
      fileName: () => "paperless-lookup.js",
    },
    sourcemap: false,
    reportCompressedSize: false,
  },
  test: {
    environment: "happy-dom",
    environmentOptions: {
      happyDOM: {
        // The preview iframe points at Home Assistant; never load it in tests.
        settings: { disableIframePageLoading: true, handleDisabledFileLoadingAsSuccess: true },
      },
    },
    globals: true,
    include: ["tests/**/*.test.ts"],
  },
});
