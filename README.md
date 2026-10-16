# In Falsus Player Bests — Web

GitHub Pages static website in `docs/`, branch `codex/web`.

B30 and level-grouped score sheets use the same Python/Pillow engine as desktop v1.08, running in a browser Web Worker via pinned Pyodide 0.27.7. Saves are parsed only in browser memory. No save uploads, backend, analytics or account login. The initial runtime is downloaded from jsDelivr; bundled artwork and fonts are served by GitHub Pages. Current catalog: 75 songs / 300 charts.

Users select `savestate_V3.sav` at `%USERPROFILE%\AppData\LocalLow\lowiro\infalsus\<Steam ID>\release\savestate_V3.sav`. Browser security prevents automatic Steam nickname lookup. Unknown charts are skipped. Input format checks are retained from desktop; unsupported save formats fail rather than guessing.

Serve `docs/` with any static server. Published URL: https://mewcodex.github.io/InFalsusUnofficialB30/ . GitHub Pages serves `gh-pages` / root. Publish subsequent updates with `git subtree push --prefix=docs origin gh-pages`. No build step. Python and C# source branches remain separate.

Rendering needs a modern WebAssembly-capable browser and enough memory for 2700px images. First load includes Python/Pillow and fonts. Generated pages can be downloaded individually. Refreshing the tab discards loaded save data.
