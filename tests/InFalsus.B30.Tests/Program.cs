using InFalsus.B30;
using SkiaSharp;

int passed=0;
void Check(bool condition,string label) { if(!condition)throw new Exception(label);passed++; }
void Throws(Action f,string label) { try {f();}catch(ArgumentException){passed++;return;}throw new Exception(label); }
Check(B30Calculator.CalculateRating(10,100_001_000)==12,"cap");
Check(B30Calculator.CalculateRating(10,99_000_000)==11.5m,"99m");
Check(B30Calculator.CalculateRating(10,98_000_000)==11,"98m");
Check(B30Calculator.CalculateRating(10,95_000_000)==10,"95m");
Check(B30Calculator.CalculateRating(1,1)==0,"floor");
Throws(()=>B30Calculator.CalculateRating(1.01m,100),"precision");
Throws(()=>B30Calculator.CalculateRating(10,-1),"negative score");
var catalog=ChartCatalog.LoadBundled();
Check(catalog.Charts.Count==280,"catalog count");
var first=catalog.Charts[0];var second=catalog.Charts[1];
Check(catalog.GetChart(first.NumericSongId,first.Difficulty)==first,"numeric lookup");
var result=B30Calculator.Calculate(new[]{new ScoreEntry(first.Id,98_000_000),new ScoreEntry(first.Id,100_000_000),new ScoreEntry(second.Id,99_000_000)});
Check(result.Best30.Count==2,"dedup and independent difficulties");
Check(result.Potential==((decimal)first.Level+2+second.Level+1.5m)/30,"zero padded average");
Throws(()=>B30Calculator.Calculate(new[]{new ScoreEntry("missing",1)}),"unknown");
Check(B30Calculator.Calculate(new[]{new ScoreEntry("missing",1)},options:new(){IgnoreUnknownCharts=true}).SkippedChartIds.Count==1,"skip reporting");
var table=ConstantTable.FromOverrides(new Dictionary<string,decimal>{{first.Id,19.9m}});
Check(ConstantTable.FromJson(table.ToJson())[first.Id]==19.9m,"constant roundtrip");
Check(B30Calculator.Calculate(new[]{new ScoreEntry(first.Id,100_000_000)},table).Best30[0].Rating==21.9m,"custom constant");
Throws(()=>ConstantTable.FromJson("{\"alamode0\":1.01}"),"constant precision");
Throws(()=>ConstantTable.FromJson("{\"unknown\":1}"),"unknown constant");
Check(B30Calculator.Calculate(new[]{new ScoreEntry(first.Id,100_000_900,new(1000,900,0,0))}).Best30.Count==1,"shiny subset score");
Throws(()=>B30Calculator.Calculate(new[]{new ScoreEntry(first.Id,100_000_000,new(1000,1001,0,0))}),"invalid shiny");
Throws(()=>B30Calculator.Calculate(new[]{new ScoreEntry(first.Id,99_000_000,new(1000,900,0,0))}),"mismatched counts");
var supplied=B30Result.FromPrecomputed(result.Best30.Reverse(),123.456m);
Check(supplied.Potential==123.456m&&supplied.Best30[0]==result.Best30.Last(),"precomputed unchanged");
var output=args.Length>0?args[0]:"test-output";Directory.CreateDirectory(output);
using var renderer=new B30Renderer();
var all=B30Calculator.Calculate(catalog.Charts.Select((c,i)=>new ScoreEntry(c.Id,96_000_000+i%41*100_000L)));
renderer.SavePng(Path.Combine(output,"sample.png"),all,new(){PlayerName="SAMPLE PLAYER",Character=Character.Mei});
// Render every bundled jacket and localized title, all avatars, and missing judgement placeholders.
for(int page=0;page<10;page++) {
 var rows=catalog.Charts.Skip(page*30).Take(30).Select((c,i)=>new RankedChart(c,97_000_000+(i%4)*1_000_000,c.Level,c.Level+1,null));
 var batch=B30Result.FromPrecomputed(rows,12.3456m);
 var png=renderer.RenderPng(batch,new(){PlayerName="玩家テスト · Test",Character=(Character)(page%5)});
 using var bitmap=SKBitmap.Decode(png);Check(bitmap.Width==2700&&bitmap.Height==3450,"render page "+page);
 if(page==0)File.WriteAllBytes(Path.Combine(output,"all-titles-page1.png"),png);
}
var empty=renderer.RenderPng(B30Calculator.Calculate(Array.Empty<ScoreEntry>()));Check(empty.Length>1000,"empty render");
Console.WriteLine($"PASS: {passed} assertions; all 280 chart images rendered.");
