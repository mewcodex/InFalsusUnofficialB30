using InFalsus.B30;
using System.Text.Json;

// Input: [{"ChartId":"alamode0","Score":99000000,"Judgements":null}, ...]
// Omit judgement counts unless all four counters belong to that specific score.
// No arguments generates synthetic example data; no save file is read.
var catalog = ChartCatalog.LoadBundled();
var scores = args.Length > 0
    ? JsonSerializer.Deserialize<ScoreEntry[]>(File.ReadAllText(args[0]), new JsonSerializerOptions { PropertyNameCaseInsensitive = true })!
    : catalog.Charts.Select((c,i) => new ScoreEntry(c.Id, 96_000_000 + i % 41 * 100_000L)).ToArray();
var constants = args.Length > 2 ? ConstantTable.FromJson(File.ReadAllText(args[2])) : null;
var result = B30Calculator.Calculate(scores, constants);
using var renderer = new B30Renderer();
var output = args.Length > 1 ? args[1] : "player-bests.png";
renderer.SavePng(output, result, new RenderOptions { PlayerName = "SAMPLE PLAYER", Character = Character.Mei });
Console.WriteLine($"{Path.GetFullPath(output)} | B30: {result.Potential:F4}");
