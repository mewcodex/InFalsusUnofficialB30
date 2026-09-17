using System.Collections.ObjectModel;

namespace InFalsus.B30;

public enum ChartDifficulty { Minimal = 1, Evolved = 2, Ultimate = 4, Forbidden = 8 }
public enum Character { Nia, Mei, Ayame, Iris, Story }

/// <summary>Exact includes Shiny; Near and Break are total counts, not early/late splits.</summary>
public sealed record JudgementCounts(int Exact, int Shiny, int Near, int Break);

/// <summary>Score is the original 100,000,000-point game score, including Shiny bonus.</summary>
public sealed record ScoreEntry(string ChartId, long Score, JudgementCounts? Judgements = null);

public sealed record ChartInfo(string Id, string SongId, int NumericSongId, string Title,
    ChartDifficulty Difficulty, int Level, string Jacket)
{
    public string DifficultyLabel => Difficulty switch
    {
        ChartDifficulty.Minimal => "MIN", ChartDifficulty.Evolved => "EVO",
        ChartDifficulty.Ultimate => "ULT", ChartDifficulty.Forbidden => "FBD",
        _ => throw new InvalidOperationException("Unknown difficulty")
    };
}

public sealed record RankedChart(ChartInfo Chart, long Score, decimal Constant,
    decimal Rating, JudgementCounts? Judgements);

public sealed class B30Result
{
    internal B30Result(IEnumerable<RankedChart> ranked, IEnumerable<string> skipped, decimal? potential = null)
    {
        RankedCharts = Array.AsReadOnly(ranked.ToArray());
        Best30 = Array.AsReadOnly(RankedCharts.Take(30).ToArray());
        SkippedChartIds = Array.AsReadOnly(skipped.Distinct(StringComparer.Ordinal).ToArray());
        Potential = potential ?? Best30.Sum(r => r.Rating) / 30m;
    }
    /// <summary>Use a host plugin's already sorted rows and its existing overall rating unchanged.</summary>
    public static B30Result FromPrecomputed(IEnumerable<RankedChart> ranked, decimal playerRating)
    {
        ArgumentNullException.ThrowIfNull(ranked);
        var rows=ranked.ToArray();
        if(rows.Any(r => r is null || r.Chart is null || r.Score < 0))
            throw new ArgumentException("Invalid precomputed chart row.");
        if(rows.Select(r=>r.Chart.Id).Distinct(StringComparer.Ordinal).Count()!=rows.Length)
            throw new ArgumentException("Precomputed rows must contain unique chart IDs.");
        foreach(var row in rows) B30Calculator.ValidateConstant(row.Constant);
        return new B30Result(rows,Array.Empty<string>(),playerRating);
    }
    public ReadOnlyCollection<RankedChart> RankedCharts { get; }
    public ReadOnlyCollection<RankedChart> Best30 { get; }
    public ReadOnlyCollection<string> SkippedChartIds { get; }
    public decimal Potential { get; }
}

public sealed record CalculationOptions
{
    /// <summary>By default unknown chart IDs throw. Set true to skip them and inspect SkippedChartIds.</summary>
    public bool IgnoreUnknownCharts { get; init; }
    /// <summary>Verify supplied judgement counts against the score (2-point rounding tolerance).</summary>
    public bool ValidateJudgementScore { get; init; } = true;
}

public sealed record RenderOptions
{
    public string RatingLabel { get; init; } = "UNOFFICIAL POTENTIAL";
    public string PlayerName { get; init; } = "PLAYER";
    public Character Character { get; init; } = Character.Nia;
    public DateOnly Date { get; init; } = DateOnly.FromDateTime(DateTime.Now);
}
