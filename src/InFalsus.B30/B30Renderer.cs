using System.Globalization;
using System.Text;
using SkiaSharp;

namespace InFalsus.B30;

/// <summary>CPU PNG renderer. Own one instance per concurrent worker and dispose it after use.</summary>
public sealed class B30Renderer : IDisposable
{
    public const int Width = 2700, Height = 3450;
    private readonly SKTypeface heading = LoadFont("Cinzel-SemiBold.ttf");
    private readonly SKTypeface latin = LoadFont("Supreme-Bold.otf");
    private readonly SKTypeface cjk = LoadFont("ChironHeiHK-SB.otf");
    private bool disposed;
    private static SKTypeface LoadFont(string name) { using var s = Assets.Open("fonts/" + name); return SKTypeface.FromStream(s) ?? throw new InvalidDataException(name); }
    private static SKBitmap Bitmap(string path) { using var s = Assets.Open(path); return SKBitmap.Decode(s) ?? throw new InvalidDataException(path); }
    private SKTypeface Face(string text, bool serif) => text.EnumerateRunes().Any(r => r.Value > 255) ? cjk : serif ? heading : latin;
    private SKFont Font(string text, float size, bool serif = false) => new(Face(text, serif), size) { Edging = SKFontEdging.SubpixelAntialias, Subpixel = true };
    private static SKColor Color(string hex) => SKColor.Parse(hex);
    private SKRect Text(SKCanvas canvas, string text, float x, float top, float size, SKColor color, float maxWidth = float.MaxValue, bool right = false, bool serif = false)
    {
        using var font = Font(text, size, serif);
        while (font.MeasureText(text) > maxWidth && font.Size > 8) font.Size -= .5f;
        font.MeasureText(text, out var bounds);
        if (right) x -= font.MeasureText(text);
        using var paint = new SKPaint { Color = color, IsAntialias = true };
        canvas.DrawText(text, x, top - bounds.Top, SKTextAlign.Left, font, paint);
        return new SKRect(x + bounds.Left, top, x + bounds.Right, top + bounds.Height);
    }
    private void Title(SKCanvas canvas, string title, float x, float baseline, float width)
    {
        using var font = Font(title, 25);
        while (font.MeasureText(title) > width && font.Size > 8) font.Size -= .5f;
        using var paint = new SKPaint { Color = SKColors.White, IsAntialias = true };
        canvas.DrawText(title, x, baseline, SKTextAlign.Left, font, paint);
    }
    private static void Image(SKCanvas canvas, string path, SKRect target, float radius = 0)
    {
        using var bitmap = Bitmap(path);
        canvas.Save();
        if (radius > 0) canvas.ClipRoundRect(new SKRoundRect(target, radius), SKClipOperation.Intersect, true);
        canvas.DrawBitmap(bitmap, target, new SKSamplingOptions(SKFilterMode.Linear));
        canvas.Restore();
    }
    private void Score(SKCanvas canvas, long score, float x, float top, float bottom, float maxWidth)
    {
        var text = score.ToString("000,000,000", CultureInfo.InvariantCulture);
        using var font = Font(text, 40);
        while (font.MeasureText(text) > maxWidth && font.Size > 12) font.Size -= .5f;
        font.MeasureText(text, out var bounds);
        var y = (top + bottom - bounds.Height) / 2 - bounds.Top;
        using var paint = new SKPaint { Color = SKColors.White, IsAntialias = true };
        canvas.DrawText(text, x, y, SKTextAlign.Left, font, paint);
        var theme = score >= 99_000_000 ? new SKColor(255,161,255) : score >= 98_000_000 ? new SKColor(206,161,255) : new SKColor(154,238,250);
        var tint = new SKColor((byte)(theme.Red * .55 + 255 * .45), (byte)(theme.Green * .55 + 255 * .45), (byte)(theme.Blue * .55 + 255 * .45));
        // Glow the full number, then redraw the crisp white/tinted foreground.
        if (score >= 98_000_000)
        {
            using var blur = SKMaskFilter.CreateBlur(SKBlurStyle.Normal, score >= 99_000_000 ? 9 : 4);
            using var glow = new SKPaint { Color = theme, IsAntialias = true, MaskFilter = blur };
            canvas.DrawText(text, x, y, SKTextAlign.Left, font, glow);
            if (score >= 99_000_000)
            {
                using var innerBlur = SKMaskFilter.CreateBlur(SKBlurStyle.Normal, 4);
                using var inner = new SKPaint { Color = theme.WithAlpha(102), IsAntialias = true, MaskFilter = innerBlur };
                canvas.DrawText(text, x, y, SKTextAlign.Left, font, inner);
            }
            canvas.DrawText(text, x, y, SKTextAlign.Left, font, paint);
        }
        canvas.Save();
        canvas.ClipRect(new SKRect(x - 4, y + bounds.Top + bounds.Height * .4f, x + maxWidth + 4, y + bounds.Bottom + 2));
        paint.Color = tint;
        canvas.DrawText(text, x, y, SKTextAlign.Left, font, paint);
        canvas.Restore();
    }
    public byte[] RenderPng(B30Result result, RenderOptions? options = null)
    {
        if (disposed) throw new ObjectDisposedException(nameof(B30Renderer));
        ArgumentNullException.ThrowIfNull(result);
        options ??= new();
        if (!Enum.IsDefined(typeof(Character), options.Character)) throw new ArgumentOutOfRangeException(nameof(options.Character));
        using var surface = SKSurface.Create(new SKImageInfo(Width, Height)) ?? throw new InvalidOperationException("Cannot allocate image.");
        var canvas = surface.Canvas;
        canvas.Scale(1.5f);
        using (var background = Bitmap("backgrounds/seiko_amphitheatre_clip.jpg"))
        {
            float sourceWidth = background.Height * 1800f / 2300f;
            float left = (background.Width - sourceWidth) * .70f;
            canvas.DrawBitmap(background, new SKRect(left, 0, left + sourceWidth, background.Height), new SKRect(0,0,1800,2300), new SKSamplingOptions(SKFilterMode.Linear));
        }
        using var veil = new SKPaint { Color = new SKColor(7,14,24,180) };
        canvas.DrawRect(0,0,1800,2300,veil);
        Image(canvas, "avatars/" + options.Character.ToString().ToLowerInvariant() + ".png", new SKRect(54,52,238,236), 16);
        Image(canvas, "logo.png", new SKRect(263,60,463,107.33f));
        var name = Text(canvas, string.IsNullOrWhiteSpace(options.PlayerName) ? "PLAYER" : options.PlayerName,263,121.33f,72,SKColors.White,1000);
        Text(canvas,"PLAYER BESTS",263,name.Bottom+20,22,Color("#d6e5ed"),1000,serif:true);
        Text(canvas,options.RatingLabel,1744,77,24,Color("#d6e5ed"),460,right:true,serif:true);
        Text(canvas,result.Potential.ToString("F4",CultureInfo.InvariantCulture),1744,121,80,SKColors.White,440,right:true);
        using var line = new SKPaint { Color = new SKColor(154,184,200,110), StrokeWidth=1, IsAntialias=true };
        canvas.DrawLine(56,262,1744,262,line);
        for(var i=0;i<result.Best30.Count;i++)
        {
            var row=result.Best30[i];
            float x=56+i%3*570, y=292+i/3*182, tx=x+174;
            using var panel = new SKPaint { Color = new SKColor(8,21,33,210),IsAntialias=true };
            canvas.DrawRoundRect(new SKRect(x,y-2,x+548,y+172),12,12,panel);
            panel.Color=new SKColor(120,154,173,65); panel.Style=SKPaintStyle.Stroke; panel.StrokeWidth=1;
            canvas.DrawRoundRect(new SKRect(x,y-2,x+548,y+172),12,12,panel);
            Image(canvas,row.Chart.Jacket,new SKRect(x+12,y+13,x+156,y+157),8);
            var difficultyColor=row.Chart.Difficulty switch {ChartDifficulty.Minimal=>"#68d5c4",ChartDifficulty.Evolved=>"#86bef3",ChartDifficulty.Ultimate=>"#f0bc74",_=>"#e899b7"};
            Text(canvas,row.Chart.DifficultyLabel+" "+row.Constant.ToString("F1",CultureInfo.InvariantCulture),tx,y+19,18,Color(difficultyColor));
            Text(canvas,row.Rating.ToString("F4",CultureInfo.InvariantCulture),x+531,y+16,26,SKColors.White,160,right:true);
            Title(canvas,row.Chart.Title,tx,y+72,358);
            Score(canvas,row.Score,tx,y+76,y+140,358);
            var j=row.Judgements;
            var parts=new[]{("E: "+(j?.Exact.ToString()??"—"),"#deb6ff"),(" (+"+(j?.Shiny.ToString()??"—")+")","#f7aef7"),("  N: "+(j?.Near.ToString()??"—"),"#a5d3de"),("  B: "+(j?.Break.ToString()??"—"),"#ff7d94")};
            float size=18;
            float MeasureParts(float s) { float w=0; foreach(var p in parts) { using var f=Font(p.Item1,s);w+=f.MeasureText(p.Item1); } return w; }
            while(MeasureParts(size)>301&&size>8)size-=.5f;
            float cursor=tx;
            foreach(var p in parts) { using var f=Font(p.Item1,size);using var ink=new SKPaint{Color=Color(p.Item2),IsAntialias=true};canvas.DrawText(p.Item1,cursor,y+155,SKTextAlign.Left,f,ink);cursor+=f.MeasureText(p.Item1); }
            Text(canvas,"#"+(i+1).ToString("D2"),x+531,y+144,17,Color("#a6bdca"),50,right:true);
        }
        canvas.DrawLine(56,2150,1744,2150,line);
        Text(canvas,"非官方成绩图 · 不代表游戏内评级",56,2182,21,Color("#cad7e0"));
        Text(canvas,options.Date.ToString("yyyy-MM-dd",CultureInfo.InvariantCulture),1744,2182,20,Color("#cad7e0"),right:true);
        using var image = surface.Snapshot();
        using var data = image.Encode(SKEncodedImageFormat.Png,100);
        return data.ToArray();
    }
    public void SavePng(string path, B30Result result, RenderOptions? options = null) => File.WriteAllBytes(path,RenderPng(result,options));
    public void Dispose() { if(disposed)return;disposed=true;heading.Dispose();latin.Dispose();cjk.Dispose(); }
}
