const $=id=>document.getElementById(id);
let worker,ready=false,busy=false,hasSave=false,serial=0;
const pending=new Map(),urls=[];
function status(text,error=false){$('status').textContent=text;$('status').style.color=error?'#ffb6bd':'#bfddd5';}
function controls(){['save','constants','template','resetConstants','constantSource'].forEach(id=>$(id).disabled=!ready||busy);$('generate').disabled=!ready||busy||!hasSave;}
function request(type,payload={}){return new Promise((resolve,reject)=>{const id=++serial;pending.set(id,{resolve,reject});worker.postMessage({id,type,...payload});});}
function clearResults(){urls.forEach(URL.revokeObjectURL);urls.length=0;$('results').replaceChildren();}
function download(blob,name){const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),60000);}
async function task(fn){busy=true;controls();try{await fn();}catch(e){status(e.message,true);}finally{busy=false;controls();}}
async function boot(){
 ready=false;controls();$('retry').hidden=true;worker?.terminate();
 for(const p of pending.values())p.reject(Error('引擎已重新加载'));pending.clear();
 worker=new Worker('./worker.js?v=20261016-long-sheet-2',{type:'module'});
 worker.onmessage=({data})=>{if(data.type==='progress'){status(data.text);return;}const p=pending.get(data.id);if(!p)return;pending.delete(data.id);data.error?p.reject(Error(data.error)):p.resolve(data.result);};
 worker.onerror=e=>{const error=Error('绘图引擎加载失败，请检查网络后重试。');for(const p of pending.values())p.reject(error);pending.clear();ready=false;controls();$('retry').hidden=false;status(error.message,true);};
 try{await request('init');ready=true;status('已就绪 · 选择 savestate_V3.sav 开始');controls();}
 catch(e){status(e.message,true);$('retry').hidden=false;}
}
$('retry').onclick=()=>{hasSave=false;$('save').value='';boot();};
$('mode').onchange=()=>{$('filters').hidden=$('mode').value!=='scores';};
const catalog=await fetch('./assets/catalog.json').then(r=>{if(!r.ok)throw Error('曲库加载失败');return r.json();});
const levels=[...new Set(catalog.songs.flatMap(s=>s.charts.map(c=>c.level)))].sort((a,b)=>a-b);
for(const id of ['minLevel','maxLevel'])for(const lv of levels){const op=document.createElement('option');op.value=lv;op.textContent=lv;$(id).append(op);}
$('maxLevel').value=levels.at(-1);
// Keep the native file picker in this user gesture; clipboard failure must not block it.
$('save').addEventListener('click',()=>{
 const path=String.raw`%USERPROFILE%\AppData\LocalLow\lowiro\infalsus`;
 const hint=$('pathCopyHint');
 if(!navigator.clipboard?.writeText){hint.textContent='无法自动复制，请复制页面下方的存档目录。';return;}
 navigator.clipboard.writeText(path).then(()=>{
  hint.textContent='存档目录已复制。在文件窗口按 Ctrl+L → Ctrl+V → 回车。';
 }).catch(()=>{hint.textContent='未能复制目录，请复制页面下方的存档目录。';});
});
$('save').onchange=()=>task(async()=>{
 hasSave=false;clearResults();$('resultInfo').textContent='生成后可下载 PNG';
 const file=$('save').files[0];if(!file)return;
 if(!file.name.toLowerCase().endsWith('.sav')||file.size>100000000)throw Error('请选择不超过100MB的 .sav 游戏存档。');
 status('正在读取存档…');const info=await request('save',{bytes:await file.arrayBuffer()});
 hasSave=true;$('fileLabel').textContent=file.name;
 status(`已读取 ${info.count} 条成绩。`+(info.warning?' 当前角色无法识别，可手动选择头像。':''));
});
$('template').onclick=()=>task(async()=>download(new Blob(['\ufeff',await request('template')],{type:'text/csv;charset=utf-8'}),'InFalsus-constants.csv'));
$('constants').onchange=()=>task(async()=>{
 const file=$('constants').files[0];if(!file)return;if(file.size>2000000)throw Error('定数表文件过大。');
 const bytes=await file.arrayBuffer();let text;try{text=new TextDecoder('utf-8',{fatal:true}).decode(bytes);}catch{text=new TextDecoder('gb18030',{fatal:true}).decode(bytes);}
 await request('constants',{text});$('constantsLabel').textContent='自定义定数：'+file.name;$('constantSource').querySelector('[value=custom]').disabled=false;$('constantSource').value='custom';status('自定义定数已导入');
});
$('resetConstants').onclick=()=>task(async()=>{await request('resetConstants');$('constantsLabel').textContent='自定义定数：未导入';$('constantSource').value='default';$('constantSource').querySelector('[value=custom]').disabled=true;$('constants').value='';status('已恢复等级.0');});
$('generate').onclick=()=>task(async()=>{
 const options={name:$('name').value.trim()||'PLAYER',character:$('character').value,mode:$('mode').value,constantSource:$('constantSource').value,
 difficulties:[...document.querySelectorAll('.checks input:checked')].map(e=>Number(e.value)),minLevel:Number($('minLevel').value),maxLevel:Number($('maxLevel').value)};
 if(options.mode==='scores'&&(!options.difficulties.length||options.minLevel>options.maxLevel))throw Error('请至少选择一种难度，并确认最低等级不高于最高等级。');
 status('正在生成图片…');const result=await request('render',{options});clearResults();
 for(const file of result.files){const url=URL.createObjectURL(new Blob([file.bytes],{type:'image/png'}));urls.push(url);const page=document.createElement('div');page.className='page';const img=document.createElement('img');img.src=url;img.alt='生成的成绩图';const a=document.createElement('a');a.className='download';a.href=url;a.download=file.name;a.textContent='下载 '+file.name;page.append(img,a);$('results').append(page);}
 $('resultInfo').textContent=`${result.count} 张谱面 · ${result.pages} 页`;
 status(`生成完成。${result.skipped?`跳过 ${result.skipped} 张曲库外谱面。`:''}`);
});
boot();
