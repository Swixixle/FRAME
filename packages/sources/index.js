/**
 * Entry shim: scripts import `../packages/sources/index.js`. After `tsc`, compiled
 * output lives in `dist/`. This file re-exports so relative imports resolve on Render
 * without changing every script path.
 */
export * from "./dist/index.js";
