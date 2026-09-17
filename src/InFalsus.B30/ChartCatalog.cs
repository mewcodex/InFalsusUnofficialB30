using System.Collections.ObjectModel;
using System.Text.Json;

namespace InFalsus.B30;

internal static class Assets
{
    private static readonly IReadOnlyDictionary<string, string> Names = typeof(Assets).Assembly
        .GetManifestResourceNames().ToDictionary(n => n.Replace('\\', '/'), StringComparer.Ordinal);

    public static Stream Open(string path)
    {
        if (!Names.TryGetValue("Assets/" + path, out var name))
            throw new FileNotFoundException($"Bundled asset not found: {path}");
        return typeof(Assets).Assembly.GetManifestResourceStream(name)!;
    }
}

public sealed class ChartCatalog
{
    private readonly IReadOnlyDictionary<string, ChartInfo> byId;
    private static readonly Lazy<ChartCatalog> Bundled = new(Load);
    private ChartCatalog(IEnumerable<ChartInfo> charts)
    {
        Charts = Array.AsReadOnly(charts.ToArray());
        byId = Charts.ToDictionary(c => c.Id, StringComparer.Ordinal);
    }
    public ReadOnlyCollection<ChartInfo> Charts { get; }
    public static ChartCatalog LoadBundled() => Bundled.Value;
    public ChartInfo GetChart(string chartId) => byId.TryGetValue(chartId, out var chart)
        ? chart : throw new ArgumentException($"Unknown chart ID: {chartId}", nameof(chartId));
    public ChartInfo GetChart(string songId, ChartDifficulty difficulty) => Charts.FirstOrDefault(
        c => c.SongId == songId && c.Difficulty == difficulty)
        ?? throw new ArgumentException($"Unknown song/difficulty: {songId}/{difficulty}");
    public ChartInfo GetChart(int songId, ChartDifficulty difficulty) => Charts.FirstOrDefault(
        c => c.NumericSongId == songId && c.Difficulty == difficulty)
        ?? throw new ArgumentException($"Unknown numeric song/difficulty: {songId}/{difficulty}");
    public bool TryGetChart(string chartId, out ChartInfo? chart) => byId.TryGetValue(chartId, out chart);

    private static ChartCatalog Load()
    {
        using var stream = Assets.Open("catalog.json");
        using var doc = JsonDocument.Parse(stream);
        var charts = new List<ChartInfo>();
        foreach (var song in doc.RootElement.GetProperty("songs").EnumerateArray())
            foreach (var chart in song.GetProperty("charts").EnumerateArray())
                charts.Add(new(chart.GetProperty("id").GetString()!, song.GetProperty("base_name").GetString()!,
                    song.GetProperty("id").GetInt32(), song.GetProperty("title").GetString()!, (ChartDifficulty)chart.GetProperty("difficulty").GetInt32(),
                    chart.GetProperty("level").GetInt32(), song.GetProperty("jacket").GetString()!));
        return new ChartCatalog(charts);
    }
}
