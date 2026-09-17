# InFalsus.B30 — C# handoff v1.0.0

C# library branch: [codex/csharp](https://github.com/mewcodex/InFalsusUnofficialB30/tree/codex/csharp). Python desktop generator: [codex/python](https://github.com/mewcodex/InFalsusUnofficialB30/tree/codex/python).

This source branch excludes compiled artifacts and generated images. Run `./build.ps1` to create `bin/win-x64/` and `packages/`; run the sample to create a synthetic score image.

.NET 6 class library for calculating player bests from score records and rendering a 2700 × 3450 PNG. It ports the existing standalone generator's calculation and layout. This is **library code for integration**, not a ready-to-install BepInEx plugin.

The runtime target matches ATres001/InFalsusRating (BepInEx 6 IL2CPP / .NET 6). There are no Unity, Harmony, BepInEx, save-file, Steam or game-object dependencies. The host supplies scores, player name and avatar; game data access and UI entry points are left to the recipient.

## Quick start

Reference `src/InFalsus.B30/InFalsus.B30.csproj` from a .NET 6 project, or use the local NuGet package in `packages/`. NuGet restores SkiaSharp 4.152.0 and its native libraries. For an existing plugin, project reference is the easiest route while editing.

```csharp
using InFalsus.B30;

var catalog = ChartCatalog.LoadBundled();
// Lookup by the game's numeric song ID and difficulty; no guessed chart suffixes.
var chart = catalog.GetChart(2, ChartDifficulty.Ultimate);
var scores = new[] { new ScoreEntry(chart.Id, 99_000_000) };
var bests = B30Calculator.Calculate(scores);
using var renderer = new B30Renderer();
renderer.SavePng("player-bests.png", bests, new RenderOptions {
    PlayerName = "PLAYER",
    Character = Character.Mei
});
```

`ScoreEntry.Score` is the original integer score (about 100 million), not accuracy percent or the displayed potential. One song's different difficulties are separate entries. Duplicate chart entries retain the highest score; zero scores are excluded. Unknown chart IDs throw by default. To skip newer/unmapped charts, set `CalculationOptions.IgnoreUnknownCharts = true` and inspect `B30Result.SkippedChartIds`.

`ChartCatalog.Charts` contains 70 songs / 280 charts, including internal chart ID, numeric song ID, localized title, difficulty, level and jacket asset. Difficulty enum values are the game's flags: Minimal=1, Evolved=2, Ultimate=4, Forbidden=8. Do not cast a zero-based difficulty index directly.

## Use the host's rating instead

**InFalsusRating's formula is different from this generator's formula.** Do not feed already-calculated ratings into `Calculate`. If the host must retain its existing ranking, weighting or pace bonus, construct rows in its desired order and supply its overall rating:

```csharp
var rows = new[] {
    new RankedChart(chart, 99_000_000, 10.0m, 11.2345m, null)
};
var bests = B30Result.FromPrecomputed(rows, playerRating: 11.2345m);
using var renderer = new B30Renderer();
renderer.SavePng("player-bests.png", bests);
```

This path preserves order, each supplied rating and the supplied overall value. Only the first 30 rows are drawn. Inputs must contain unique chart IDs. Use catalog `ChartInfo` objects to resolve packaged artwork.

## Our calculation

For chart constant C and score S:

- S >= 100,000,000: C + 2.
- 98,000,000 <= S < 100,000,000: C + 1 + (S − 98,000,000) / 2,000,000.
- Below 98,000,000: max(0, C + (S − 95,000,000) / 3,000,000).

Sort by rating, score, constant descending; ties by internal song name then difficulty ascending. Overall = sum of the best 30 / 30, including zeroes for missing entries. There is no R10, pace bonus or top-position weighting. This is unofficial and is not the game's rating.

## Custom constants

Constants default to displayed difficulty level `.0`. Custom values must be nonnegative with at most one decimal place. Keys are internal **chart IDs**, not numeric song IDs.

```csharp
File.WriteAllText("constants.json", ConstantTable.FromOverrides().ToJson());
var constants = ConstantTable.FromJson(File.ReadAllText("constants.json"));
var bests = B30Calculator.Calculate(scores, constants);
// Alternatively: FromOverrides(new Dictionary<string,decimal> { [chart.Id] = 10.5m });
```

A partial override map is allowed; omitted charts use defaults. Unknown keys and invalid precision throw. This JSON format is deliberately simple and is not the target plugin's `const.json` format; the recipient can map its own constants directly.

## Judgements

```csharp
new ScoreEntry(chart.Id, 100_000_900, new JudgementCounts(
    Exact: 1000, Shiny: 900, Near: 0, Break: 0));
```

Exact **includes** Shiny. The four counters must all correspond to that score's play. Missing counts are `null` and display dashes. Never combine a historical best Shiny/Exact count with a different play's high score. In particular, the target project's current `ExactCount` field represents historical Shiny count and cannot supply these four counters.

By default supplied counts are checked against `ceil(100,000,000 × (Exact + Near/2) / (Exact + Near + Break) + Shiny)` with 2-point tolerance. `ValidateJudgementScore=false` disables that cross-check, but negative counts and Shiny > Exact still throw.

## Rendering and plugin deployment

Bundled resources include optimized jackets, fixed `seiko_amphitheatre_clip.jpg` background, five avatars, logo and fonts. They are embedded into `InFalsus.B30.dll`; no runtime game unpacking or downloads occur. Names use Chinese game localization, including Japanese titles retained by that localization. Scores are padded to nine digits; their bottom 60% uses pale grade colors with purple/pink glow. No score data is bundled in the library.

`bin/win-x64/` contains the library, managed `SkiaSharp.dll`, native `libSkiaSharp.dll`, and dependency notices. It targets the 64-bit Windows game process; it is not a standalone executable. Keep managed dependencies available to the plugin loader and native `libSkiaSharp.dll` on a native DLL search path. The recipient may need to arrange dependency loading in its BepInEx deployment. Do not overwrite a different SkiaSharp installation blindly. Native and managed SkiaSharp must be the same version.

For deployment without NuGet, reference the two managed DLLs. A plain .NET 6 consumer using exactly these three DLLs was tested on Windows x64. Actual BepInEx injection/loading has **not** been tested. Do not copy a new .NET runtime into the game.

Snapshot game data on the game's thread into plain `ScoreEntry` records. Rendering is synchronous and CPU-based; run it off the UI/game thread if desired. Use a separate renderer per concurrent worker and dispose it. The renderer never reads game objects, accesses Steam or modifies a save. `RenderPng` returns PNG bytes; `SavePng` overwrites only the specified output file. The output folder must exist.

## Build and test

Requires .NET SDK 6 or newer and NuGet access. The example uses synthetic scores when no input file is supplied.

```powershell
dotnet build src/InFalsus.B30 -c Release
dotnet run --project tests/InFalsus.B30.Tests -c Release
dotnet run --project samples/GenerateB30 -c Release
# Optional: scores JSON, output PNG, custom constants JSON
dotnet run --project samples/GenerateB30 -c Release -- scores.json out.png constants.json
dotnet pack src/InFalsus.B30 -c Release -o packages
```

Example input: `[{"ChartId":"alamode0","Score":99000000,"Judgements":null}]`.

Tests cover rating boundaries, constant precision, deduplication, missing-entry averaging, judgement validation, precomputed values, numeric song lookup, all 280 chart renders, five avatars and empty input. The generated sample image uses synthetic data, not someone's save or a real player score sheet.

## 中文交接说明

这是提供给对方修改接入的 .NET 6 类库源码，不是完整 BepInEx 插件。输入普通成绩对象即可生成图片；也可以传入对方已算好的排名和总评级，仅使用出图功能。无需读取存档、连接 Steam 或运行时拆包。自定义定数支持一位小数，默认难度 `.0`。

对方主要需要补上：从游戏读取成绩并转换为 `ScoreEntry`、传入用户名/头像、添加调用入口，以及安排 BepInEx 环境中的依赖加载。不要把历史最高闪亮判定数当成该次最高分的完整判定数据；无对应判定时传 `null`。

See `THIRD-PARTY-NOTICES.md` for bundled asset provenance and dependency notices.
