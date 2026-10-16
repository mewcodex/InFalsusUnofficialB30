# In Falsus Player Bests — Web

GitHub Pages static website in `docs/`, branch `codex/web`.

B30 and level-grouped score sheets use the same Python/Pillow engine as desktop v1.08, running in a browser Web Worker via pinned Pyodide 0.27.7. Saves are parsed only in browser memory. No save uploads, backend, analytics or account login. The initial runtime is downloaded from jsDelivr; bundled artwork and fonts are served by GitHub Pages. Current catalog: 75 songs / 300 charts.

Users select `savestate_V3.sav` at `%USERPROFILE%\AppData\LocalLow\lowiro\infalsus\<Steam ID>\release\savestate_V3.sav`. Browser security prevents automatic Steam nickname lookup. Unknown charts are skipped. Input format checks are retained from desktop; unsupported save formats fail rather than guessing.

Serve `docs/` with any static server. Published URL: https://mewcodex.github.io/InFalsusUnofficialB30/ . GitHub Pages serves `gh-pages` / root. Publish subsequent updates with `git subtree push --prefix=docs origin gh-pages`. No build step. Python and C# source branches remain separate.

Rendering needs a modern WebAssembly-capable browser and enough memory for 2700px images. First load includes Python/Pillow and fonts. Score sheets use four columns in one full-height PNG; B30 keeps its original three-column layout. Refreshing the tab discards loaded save data.

## Community constants and score progress

The optional community constants (By @安小璃) are transcribed from the user-provided chart dated 2026-10-15. Charts not listed use game level + 0.5. The complete 300-chart CSV is downloadable from the page; default mode continues to use level.0, and imported custom tables remain available.

Score sheets display EX (score >= 98,000,000, including EX+) and EX+ (>= 99,000,000) counts across the complete active filter. The denominator includes all catalog charts in that filter, including unplayed charts. The single score sheet displays overall progress.

## Optional legacy-style R10

B30 mode optionally reconstructs a 30-entry recent pool from saved historical runs, in timestamp order (storage order breaks ties). It selects the highest rating per chart, then the best 10 distinct charts. Overall potential is (sum of B30 + sum of R10) / 40, with empty slots worth zero. The image includes both sections and their separate averages. Score-sheet mode does not use R10.

The requested first-play/new-best/EX/failure protection follows the queue algorithm described by [Arcaea Server's author](https://arcaea.lost-msth.cn/Arcaea-Server/mechanism/potential.html), a legacy-style reference rather than a claim about current official Arcaea behavior. Protected runs replace the lowest strictly weaker eligible candidate (oldest on ties); if no candidate exists, the run does not enter the pool. Other runs evict the oldest eligible candidate. Both paths preserve at least ten distinct charts when available. EX uses In Falsus's 98,000,000 threshold. First plays and new bests are determined from the available history, not today's highscore aggregate.

Verified GameResultV4 fields: Lamp at byte 3, CalculatedResultClear at byte 4, signed CalculatedPaceValue (Dive) at byte 8, score at byte 80, UTC timestamp at byte 88. Failure protection uses the individual run's DiveFailed/Fail flags, not the chart's aggregate best clear. Historical song mappings take precedence over current song IDs. Missing or unsupported histories produce an explicit error or warning; missing histories are never replaced with the highest scores. An incomplete history can make reconstructed R10 differ from a lifetime calculation.

Run `python tests/test_web_recent.py` with Pillow installed for protection and queue tests.
