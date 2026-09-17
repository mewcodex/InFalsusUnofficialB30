using System.Collections.ObjectModel;
using System.Text.Json;

namespace InFalsus.B30;

public sealed class ConstantTable
{
    private readonly IReadOnlyDictionary<string, decimal> values;
    private ConstantTable(Dictionary<string, decimal> values) => this.values = new ReadOnlyDictionary<string, decimal>(values);
    public decimal this[string chartId] => values[chartId];
    public IReadOnlyDictionary<string, decimal> Values => values;
    public static ConstantTable FromOverrides(IReadOnlyDictionary<string, decimal>? overrides = null, ChartCatalog? catalog = null)
    {
        catalog ??= ChartCatalog.LoadBundled();
        var values = catalog.Charts.ToDictionary(c => c.Id, c => (decimal)c.Level, StringComparer.Ordinal);
        if (overrides is not null) foreach (var pair in overrides)
        {
            if (!values.ContainsKey(pair.Key)) throw new ArgumentException($"Unknown chart ID: {pair.Key}");
            B30Calculator.ValidateConstant(pair.Value);
            values[pair.Key] = pair.Value;
        }
        return new(values);
    }
    public static ConstantTable FromJson(string json) => FromOverrides(
        JsonSerializer.Deserialize<Dictionary<string, decimal>>(json) ?? throw new ArgumentException("Expected a JSON object."));
    public string ToJson() => JsonSerializer.Serialize(values, new JsonSerializerOptions { WriteIndented = true });
}
