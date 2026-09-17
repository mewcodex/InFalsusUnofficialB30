namespace InFalsus.B30;

public static class B30Calculator
{
    public static decimal CalculateRating(decimal constant, long score)
    {
        ValidateConstant(constant);
        if (score < 0) throw new ArgumentOutOfRangeException(nameof(score));
        if (score >= 100_000_000) return constant + 2m;
        if (score >= 98_000_000) return constant + 1m + (score - 98_000_000m) / 2_000_000m;
        return Math.Max(0m, constant + (score - 95_000_000m) / 3_000_000m);
    }

    internal static void ValidateConstant(decimal value)
    {
        if (value < 0 || decimal.Round(value, 1) != value)
            throw new ArgumentOutOfRangeException(nameof(value), "Constants must be nonnegative with at most one decimal place.");
        // Reject arithmetic overflow before a record enters the calculation.
        _ = checked(value + 2m);
    }

    public static B30Result Calculate(IEnumerable<ScoreEntry> scores, ConstantTable? constants = null,
        CalculationOptions? options = null, ChartCatalog? catalog = null)
    {
        ArgumentNullException.ThrowIfNull(scores);
        catalog ??= ChartCatalog.LoadBundled();
        options ??= new();
        var best = new Dictionary<string, RankedChart>(StringComparer.Ordinal);
        var skipped = new List<string>();
        foreach (var entry in scores)
        {
            if (entry is null || string.IsNullOrWhiteSpace(entry.ChartId))
                throw new ArgumentException("Every score must have a chart ID.", nameof(scores));
            if (entry.Score < 0) throw new ArgumentOutOfRangeException(nameof(scores), "Scores cannot be negative.");
            if (!catalog.TryGetChart(entry.ChartId, out var chart))
            {
                if (!options.IgnoreUnknownCharts) throw new ArgumentException($"Unknown chart ID: {entry.ChartId}");
                skipped.Add(entry.ChartId); continue;
            }
            if (entry.Judgements is { } counts) ValidateJudgements(counts, entry.Score, options.ValidateJudgementScore);
            if (entry.Score == 0) continue;
            var constant = constants?[chart!.Id] ?? chart!.Level;
            var row = new RankedChart(chart, entry.Score, constant, CalculateRating(constant, entry.Score), entry.Judgements);
            if (!best.TryGetValue(entry.ChartId, out var prior) || row.Score > prior.Score ||
                (row.Score == prior.Score && prior.Judgements is null && row.Judgements is not null))
                best[entry.ChartId] = row;
        }
        var ranked = best.Values.OrderByDescending(r => r.Rating).ThenByDescending(r => r.Score)
            .ThenByDescending(r => r.Constant).ThenBy(r => r.Chart.SongId, StringComparer.Ordinal)
            .ThenBy(r => (int)r.Chart.Difficulty);
        return new B30Result(ranked, skipped);
    }

    private static void ValidateJudgements(JudgementCounts counts, long score, bool checkScore)
    {
        if (counts.Exact < 0 || counts.Shiny < 0 || counts.Near < 0 || counts.Break < 0 || counts.Shiny > counts.Exact)
            throw new ArgumentException("Invalid judgement counts: Shiny is a subset of Exact; all counts must be nonnegative.");
        var total = (long)counts.Exact + counts.Near + counts.Break;
        if (!checkScore) return;
        if (total == 0) throw new ArgumentException("Judgement counts cannot all be zero.");
        var expected = decimal.Ceiling(100_000_000m * (counts.Exact + counts.Near / 2m) / total + counts.Shiny);
        if (Math.Abs(expected - score) > 2m)
            throw new ArgumentException($"Judgement counts do not match score {score}. Expected approximately {expected}.");
    }
}
