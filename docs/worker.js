import { loadPyodide } from 'https://cdn.jsdelivr.net/pyodide/v0.27.7/full/pyodide.mjs';
let py, initPromise;
const revision=new URL(import.meta.url).searchParams.get('v')||'dev';
const progress = text => postMessage({type:'progress',text});
async function initialize(){
 progress('正在加载本地绘图引擎，首次打开可能需要一些时间…');
 py=await loadPyodide({indexURL:'https://cdn.jsdelivr.net/pyodide/v0.27.7/full/'});
 await py.loadPackage('pillow');
 const response=await fetch('./files.json?v='+revision,{cache:'no-store'});if(!response.ok)throw Error('无法加载资源清单');
 const files=await response.json();let next=0,done=0;
 py.FS.mkdirTree('/app');
 await Promise.all(Array.from({length:4},async()=>{while(next<files.length){
  const file=files[next++],res=await fetch('./'+file+(file==='engine/b30.py'?'?v='+revision:''),file==='engine/b30.py'?{cache:'no-store'}:{});if(!res.ok)throw Error('资源加载失败：'+file);
  const path='/app/'+(file==='engine/b30.py'?'b30.py':file);
  py.FS.mkdirTree(path.slice(0,path.lastIndexOf('/')));py.FS.writeFile(path,new Uint8Array(await res.arrayBuffer()));
  progress(`正在准备字体与曲绘 ${++done}/${files.length}`);
 }}));
 py.runPython(`import sys, json, io, zipfile, gc
sys.path.insert(0,'/app')
import b30
catalog=b30.load_catalog()
records=None
custom_constants=None
community_constants=b30.load_constants('/app/assets/community-constants.csv',catalog)
`);
 return true;
}
let busy=false;
onmessage=async({data})=>{
 const {id,type}=data;if(busy){postMessage({id,error:'正在处理上一项操作，请稍后重试。'});return;}busy=true;
 try{
  initPromise??=initialize();await initPromise;
  if(type==='init')postMessage({id,result:true});
  else if(type==='save'){
   if(data.bytes.byteLength>100000000)throw Error('文件超过100MB，请选择 savestate_V3.sav。');
   py.FS.writeFile('/input.sav',new Uint8Array(data.bytes));
   let result;
   try{result=py.runPython(`records=None
parsed=b30.load_records('/input.sav')
records=parsed
json.dumps({'count':len(records),'character':records.selected_character,'warning':records.profile_warning})`);}finally{py.FS.unlink('/input.sav');}
   postMessage({id,result:JSON.parse(result)});
  }else if(type==='template'){
   postMessage({id,result:py.runPython("b30.constants_template(catalog)")});
  }else if(type==='constants'){
   py.globals.set('constants_text',data.text);
   try{py.runPython("candidate=b30.parse_constants(constants_text,catalog)\ncustom_constants=candidate");}finally{py.globals.delete('constants_text');}
   postMessage({id,result:true});
  }else if(type==='resetConstants'){
   py.runPython('custom_constants=None');postMessage({id,result:true});
  }else if(type==='render'){
   py.globals.set('options_json',JSON.stringify(data.options));
   const info=JSON.parse(py.runPython(`options=json.loads(options_json)
if records is None: raise b30.InputError('请先选择存档。')
constants=community_constants if options.get('constantSource')=='community' else custom_constants if options.get('constantSource')=='custom' else None
ranked, skipped=b30.rank_records(records,catalog,constants)
if not ranked: raise b30.InputError('存档中没有受支持的曲目成绩。')
selected=b30.filter_scores(ranked,options['difficulties'],options['minLevel'],options['maxLevel']) if options['mode']=='scores' else ranked
if not selected: raise b30.InputError('筛选范围内没有成绩。')
pages=b30.score_pages(selected) if options['mode']=='scores' else [None]
if len(pages)!=1: raise b30.InputError('绘图引擎版本过旧，请刷新页面后重新选择存档。')
recent=None
recent_info=None
if options['mode']=='b30' and options.get('includeRecent'):
 recent,recent_info=b30.recent_rating(records,catalog,constants)
progress_stats=b30.score_progress(selected,catalog,options['difficulties'],options['minLevel'],options['maxLevel'])
for page in pages:
 if page is not None: page['progress']=progress_stats
character=options['character'] if options['character']!='auto' else (records.selected_character or 'Nia')
json.dumps({'recentCount':len(recent) if recent is not None else None,'recentInfo':recent_info,'pages':len(pages),'skipped':len(skipped),'count':len(selected) if options['mode']=='scores' else min(30,len(selected))})`));
   const files=[];
   for(let i=0;i<info.pages;i++){
    progress(`正在生成第 ${i+1} / ${info.pages} 页…`);py.globals.set('page_index',i);
    py.runPython(`page=pages[page_index]
label=' / '.join(b30.DIFFS[d][0] for d in b30.DIFFS if d in options['difficulties'])
label+=f"  Lv.{options['minLevel']}-{options['maxLevel']}"
image=b30.render(page['records'] if page else ranked,catalog,options['name'],character,score_page=page,page_label=f'{page_index+1} / {len(pages)}',filter_label=label,recent=recent)
image.save('/page.png',format='PNG')
image.close()
del image
gc.collect()`);
    files.push({name:`InFalsus-${data.options.mode==='scores'?'Scores':data.options.includeRecent?'B30-R10':'B30'}-${String(i+1).padStart(2,'0')}.png`,bytes:py.FS.readFile('/page.png')});py.FS.unlink('/page.png');
   }
   postMessage({id,result:{...info,files}},files.map(f=>f.bytes.buffer));
  }else throw Error('未知操作');
 }catch(e){postMessage({id,error:String(e.message||e).split('\n').filter(Boolean).slice(-1)[0]});}
 finally{busy=false;}
};
