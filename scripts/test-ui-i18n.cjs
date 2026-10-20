// 独立浏览器中的合成数据回归；所有 API 均被本地替代，不写服务器数据或调用模型。
const {chromium}=require(process.env.TARA_PLAYWRIGHT_MODULE||'playwright');
const fs=require('node:fs');
const path=require('node:path');
const {cases:fixtures}=require('./ui-i18n-fixtures.cjs');
const contentLanguage=process.env.TARA_AUDIT_CONTENT_LANGUAGE||'en';
if(!['en','zh'].includes(contentLanguage))throw new Error('TARA_AUDIT_CONTENT_LANGUAGE must be en or zh');
const cases=contentLanguage==='en'?fixtures:fixtures.map(item=>({...item,answer:'这些样本的分析结果已保留。可通过“选择更多结果”查看。',reasoning:'根据可用数据执行分析。'}));
const rounds=Number(process.env.TARA_AUDIT_ROUNDS||3), output=process.env.TARA_AUDIT_OUTPUT||'/tmp/tara-i18n-audit/report.json';
if(!Number.isInteger(rounds)||rounds<1)throw new Error('TARA_AUDIT_ROUNDS must be a positive integer');
fs.mkdirSync(path.dirname(output),{recursive:true});
const assets=new Map();
const report={started:new Date().toISOString(),target:process.env.TARA_AUDIT_URL||'http://localhost:3000/',checks:[],failures:[],contentLanguage,mode:'API mocked in isolated browser contexts; no server data writes or model calls'};
// 中文回答模式专测内容保持；中文正文是预期内容，不运行英文残留扫描。
const scan=async page=>contentLanguage==='zh'?[]:page.evaluate(()=>{
 const found=[];
 const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
 for(let node;node=walker.nextNode();){const el=node.parentElement; if(!el||el.closest('script,style,pre,code,.language-toggle,.modebar')||!el.getClientRects().length||getComputedStyle(el).visibility==='hidden')continue; const text=node.textContent.trim();if(/[\u3400-\u9fff]/.test(text))found.push({text,element:el.tagName,class:el.className});}
 for(const el of document.querySelectorAll('button[aria-label],input[aria-label],textarea[aria-label]')){if(el.closest('.language-toggle')||!el.getClientRects().length)continue;const text=el.getAttribute('aria-label');if(/[\u3400-\u9fff]/.test(text))found.push({text,element:el.tagName,attribute:'aria-label'});}
 for(const el of document.querySelectorAll('.js-plotly-plot')){ for(const trace of el.data||[])for(const text of [trace.name,...(Array.isArray(trace.text)?trace.text:[]),...(Array.isArray(trace.customdata)?trace.customdata:[])])if(typeof text==='string'&&/[\u3400-\u9fff]/.test(text))found.push({text,element:'Plotly hover or legend'}); const l=el._fullLayout;if(!l)continue;for(const text of [l.title?.text,l.xaxis?.title?.text,l.yaxis?.title?.text])if(text&&/[\u3400-\u9fff]/.test(text))found.push({text,element:'Plotly layout'});}
 return found;
});
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.TARA_CHROME_PATH||undefined,headless:true,args:['--disable-dev-shm-usage']});
 try{for(let round=1;round<=rounds;round++)for(const width of [1440,390])for(const item of cases){
  const context=await browser.newContext({viewport:{width,height:1000},acceptDownloads:true});let page;
  try{
   // API 拦截会禁用浏览器缓存；仅按包含版本哈希的 URL 复用公开静态资源，避免重复下载大型绘图库。
   await context.route(/\/(?:_next\/static|plotly-topojson)\//,async route=>{
    const url=route.request().url();
    if(!assets.has(url)) assets.set(url,(async()=>{
     const response=await route.fetch(); const headers=response.headers();
     delete headers['content-encoding'];delete headers['content-length'];delete headers['transfer-encoding'];
     return {status:response.status(),headers,body:await response.body()};
    })());
    await route.fulfill(await assets.get(url));
   });
   await context.addInitScript(()=>localStorage.setItem('tara-interface-language','en'));
   page=await context.newPage(); let saved=false; const now=new Date().toISOString(); const summary={id:'fixture-session',title:'Synthetic history '+item.id,status:'active',metadata:{},created_at:now,updated_at:now,archived_at:null,pinned_at:null}; const errors=[];page.on('pageerror',e=>errors.push(e.message));
   await page.route('**/api/v1/**',async route=>{const path=new URL(route.request().url()).pathname;
    if(path==='/api/v1/sessions/fixture-session'){const common={session_id:summary.id,trace_id:null,sequence_no:0,message_type:'text',status:'completed',content_parts:[],metadata:{},created_at:now,updated_at:now};return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({...summary,messages:[{...common,id:'fixture-user',role:'user',content:'Synthetic fixture: '+item.id,parent_message_id:null,agent_response:null},{...common,id:'fixture-assistant',role:'assistant',content:item.answer,parent_message_id:'fixture-user',agent_response:item}]})});}
    if(path==='/api/v1/chat/stream'){saved=true;return route.fulfill({status:200,contentType:'text/event-stream',body:'data: '+JSON.stringify({event:'complete',response:item})+'\n\n'});}
    const data=path==='/api/v1/auth/me'?{id:'ui-audit',email:'ui-audit@example.com',display_name:'UI audit',is_guest:false}:path==='/api/v1/sessions'?{items:saved?[summary]:[],page:{limit:100,offset:0,total:saved?1:0}}:path==='/api/v1/question-suggestions'?{items:[{id:'sample-selection',category:'样本筛选',question:'查找 DCM 水层且粒径为 20-180 的样本',task_type:'data_query',datasets:['context_general.tsv'],availability:'available'}]}:{status:'ok',data_ready:true,agent_ready:true,datasets:[]};
    return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(data)});
   });
   await page.goto(process.env.TARA_AUDIT_URL||'http://localhost:3000/',{waitUntil:'networkidle',timeout:45000});
   const initial=await scan(page);
   await page.getByRole('textbox',{name:'Enter a Tara data question'}).fill('Synthetic fixture: '+item.id);
   await page.getByRole('button',{name:'Send',exact:true}).click();
   await page.locator('.answer-text').waitFor();
   if(item.id==='core'){
    const metricNote=contentLanguage==='en'?'Sequencing read counts are sequencing observations and cannot be interpreted directly as cell abundance.':'测序读数是测序观测信号，不能直接解释为细胞丰度。';
    if(!await page.locator('.analysis-notes').getByText(metricNote,{exact:true}).count())throw new Error('Expected screenshot metric note in response language');
   }
   const originalAnswer=await page.locator('.answer-text').allTextContents();

   if(contentLanguage==='en'&&(!originalAnswer.some(text=>text.includes('More results'))||originalAnswer.some(text=>text.includes('选择更多结果'))))throw new Error('Model-quoted app label must use the saved English answer language');
   if(!originalAnswer.length||originalAnswer.every(text=>!text.trim()))throw new Error('Expected a generated answer');
   const assertAnswerUnchanged=async stage=>{
    const actual=await page.locator('.answer-text').allTextContents();
    if(JSON.stringify(actual)!==JSON.stringify(originalAnswer))throw new Error('Generated answer changed '+stage);
   };
   if(await page.locator('.artifact-picker').count()){
    await page.locator('.artifact-picker > summary').click();
    for(const box of await page.locator('.artifact-picker input[type=checkbox]').all())await box.check();
   }
   const cards=page.locator('.response-card-controls button').first(); await cards.click(); await cards.click();
   if(item.charts.length)await page.waitForFunction(n=>[...document.querySelectorAll('.js-plotly-plot')].filter(el=>el._fullLayout).length===n,item.charts.length,{timeout:45000});
   if(item.id==='taxonomy'){
    const unresolved=page.locator('td[data-column="taxon_label"]').filter({hasText:contentLanguage==='en'?'Unresolved genus':'未鉴定到属'}).first();
    const expected=contentLanguage==='en'?'Unresolved genus (Root;Eukaryota;Stramenopiles;Ochrophyta;Bacillariophyta;unclassified_X)':'未鉴定到属（Root;Eukaryota;Stramenopiles;Ochrophyta;Bacillariophyta;unclassified_X）';
    if(await unresolved.textContent()!==expected||await unresolved.getAttribute('title')!==expected)throw new Error('Unresolved taxonomy text and tooltip must use response language and retain full path');
   }
   let findings=[...initial,...await scan(page)];
   for(const point of (await page.locator('.scatterlayer .point').all()).slice(0,1)){
    try{await point.hover({timeout:1000});findings.push(...await scan(page));}catch{}
   }
   if(['pagination','taxonomy'].includes(item.id)){
    await page.getByRole('button',{name:'Next',exact:true}).click();findings.push(...await scan(page));
    await page.getByRole('button',{name:'Previous',exact:true}).click();
   }
   const contentSnapshot=async()=>page.evaluate(()=>({
    answers:[...document.querySelectorAll('.answer-text,.reasoning-content')].map(el=>el.textContent),
    process:[...document.querySelectorAll('.process-panel ol')].map(el=>el.textContent),
    notes:[...document.querySelectorAll('.analysis-notes')].map(el=>el.textContent),
    tables:[...document.querySelectorAll('.table-scroll table')].map(el=>el.textContent),
    tableTitles:[...document.querySelectorAll('.table-scroll td[title]')].map(el=>el.getAttribute('title')),
    scopes:[...document.querySelectorAll('.artifact-heading-scope,.chart-reading-note')].map(el=>el.textContent),
    plots:[...document.querySelectorAll('.js-plotly-plot')].map(el=>({data:el.data?.map(trace=>Object.fromEntries(['type','x','y','z','text','customdata','name','lat','lon','values','labels'].filter(key=>key in trace).map(key=>[key,trace[key]]))),title:el._fullLayout?.title?.text,x:el._fullLayout?.xaxis?.title?.text,y:el._fullLayout?.yaxis?.title?.text})),
   }));
   const originalContent=JSON.stringify(await contentSnapshot());
   const assertContentUnchanged=async stage=>{
    if(JSON.stringify(await contentSnapshot())!==originalContent)throw new Error('Generated result content changed '+stage);
   };
   await page.getByRole('button',{name:'切换为中文',exact:true}).first().click();
   await assertContentUnchanged('after switching UI to Chinese');
   if(!await page.locator('.process-panel > summary').filter({hasText:'分析过程'}).count())throw new Error('Panel heading must follow Chinese UI');
   await assertAnswerUnchanged('after switching UI to Chinese');
   if(round===1&&width===1440&&item.id==='core')await page.screenshot({path:path.join(path.dirname(output),`fixed-${contentLanguage}-content-chinese-ui.png`),fullPage:true});
   await page.getByRole('button',{name:'Switch to English',exact:true}).first().click();
   await assertAnswerUnchanged('after switching UI to English');
   await page.waitForFunction(({n,english})=>document.documentElement.lang==='en'&&document.querySelectorAll('.js-plotly-plot').length===n&&[...document.querySelectorAll('.js-plotly-plot')].every(el=>el._fullLayout&&(!english||![el._fullLayout.title?.text,el._fullLayout.xaxis?.title?.text,el._fullLayout.yaxis?.title?.text].some(t=>/[\u3400-\u9fff]/.test(t||'')))),{n:item.charts.length,english:contentLanguage==='en'});
   await assertContentUnchanged('after switching UI back to English');
   findings.push(...await scan(page));
   let csvChecked=false;
   const csv=page.locator('.result-panel .artifact-download').filter({hasText:'Download CSV'});
   if(!await csv.count())throw new Error('Expected a CSV download control');
   if(await csv.count()){
    const [download]=await Promise.all([page.waitForEvent('download'),csv.first().click()]);
    if(contentLanguage==='en'&&/[\u3400-\u9fff]/.test(download.suggestedFilename())) findings.push({text:download.suggestedFilename(),element:'CSV filename'});
    const content=fs.readFileSync(await download.path(),'utf8');
    if(!content.trim())throw Error('Empty CSV');
    if(item.id==='taxonomy'&&(!content.includes('未鉴定到属（Root;Eukaryota;Stramenopiles;Ochrophyta;Bacillariophyta;unclassified_X）')||!content.includes('443272')||content.includes('Unresolved genus')))throw new Error('Taxonomy CSV must retain the source labels, full paths and counts');
    if(['pagination','taxonomy'].includes(item.id)&&content.split('\n').length!==106)throw Error('CSV must contain all 105 samples');
    csvChecked=true;
   }
   let historyChecked=false;
   if(width===1440){
    await page.reload({waitUntil:'networkidle'});
    await page.locator('.session-open').first().click();await page.locator('.answer-text').waitFor();
    await assertAnswerUnchanged('after restoring saved history');
    if(await page.locator('.artifact-picker').count()){
     await page.locator('.artifact-picker > summary').click();
     for(const box of await page.locator('.artifact-picker input[type=checkbox]').all())await box.check();
    }
    if(item.charts.length)await page.waitForFunction(n=>[...document.querySelectorAll('.js-plotly-plot')].filter(el=>el._fullLayout).length===n,item.charts.length,{timeout:45000});
    await assertContentUnchanged('after restoring saved history');
    findings.push(...await scan(page));
    await page.locator('.session-more').first().click(); findings.push(...await scan(page));
    await page.getByRole('menuitem',{name:'Rename',exact:true}).click(); findings.push(...await scan(page));
    await page.getByRole('button',{name:'Cancel renaming',exact:true}).click();
    await page.locator('.session-more').first().click();
    await page.getByRole('menuitem',{name:'Delete',exact:true}).click(); findings.push(...await scan(page));
    await page.getByRole('button',{name:'Cancel',exact:true}).last().click();
    historyChecked=true;
   }
   const unique=[...new Map(findings.map(f=>[f.text+f.attribute, f])).values()];
   const entry={round,width,case:item.id,findings:unique,errors,csvChecked,historyChecked,answerInvariantChecked:true,resultContentInvariantChecked:true};report.checks.push(entry);
   if(unique.length||errors.length){report.failures.push(entry);await page.screenshot({path:path.join(path.dirname(output),`fail-${round}-${width}-${item.id}.png`),fullPage:true});}
   console.log(JSON.stringify({round,width,case:item.id,findings:unique.length,errors:errors.length}));
  }catch(error){report.failures.push({round,width,case:item.id,error:error.message});console.log(JSON.stringify({round,width,case:item.id,error:error.message}));}
  finally{await context.close();fs.writeFileSync(output,JSON.stringify(report,null,2));}
 }}finally{await browser.close();}
 if(report.checks.some(x=>!x.resultContentInvariantChecked||!x.answerInvariantChecked||!x.csvChecked||(x.width===1440&&!x.historyChecked)))report.failures.push({error:'Required CSV or history coverage missing'});
 if(report.checks.length!==rounds*2*cases.length)report.failures.push({error:'Not all browser cases completed'});
 report.staticAssetCount=assets.size;report.rounds=rounds;report.viewports=[1440,390];report.completed=new Date().toISOString();report.status=report.failures.length?'failed':'passed';fs.writeFileSync(output,JSON.stringify(report,null,2));console.log(JSON.stringify({status:report.status,checks:report.checks.length,failures:report.failures.length}));if(report.failures.length)process.exitCode=1;
})().catch(e=>{console.error(e);process.exitCode=1});
