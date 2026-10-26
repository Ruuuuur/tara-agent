// 登录、数据目录、会话操作和链路页回归；全部接口隔离替代，不调用模型或写生产数据。
const {chromium}=require(process.env.TARA_PLAYWRIGHT_MODULE||'playwright');
const fs=require('node:fs'),path=require('node:path');
const target=process.env.TARA_AUDIT_URL||'http://localhost:3000/';
const output=process.env.TARA_SURFACES_OUTPUT||'/tmp/tara-ui-surfaces/report.json';
fs.mkdirSync(path.dirname(output),{recursive:true});
const now='2026-10-26T06:00:00Z';
const query={assay:'MetaT',taxon:'Bacillariophyta',sample_names:null,group_by:'ocean_region',polar:true,limit:20,pfam_accessions:['PF00001','PF00002','PF00003'],depths:['SRF','DCM','MES']};
const span=(id,parent,name,kind,sequence)=>({id,trace_id:'fixture-trace',parent_span_id:parent,sequence_no:sequence,name,span_kind:kind,status:'completed',started_at:now,ended_at:now,duration_ms:25,retry_count:0,input_data:{query},output_data:{raw_diagnostic:'原始诊断保留'},error_code:null,error_message:null,error_data:null,model_provider:null,model_name:null,model_parameters:{},input_tokens:null,output_tokens:null,total_tokens:null,context_length:null,tool_name:kind==='tool'?'function_atlas':null,filters:{query},marker:'v4',sample_count:3,sample_ids:['A','B','C'],data_sources:[{filename:'context_general.tsv'}],artifact_refs:[],attributes:{}});
const richTrace={id:'fixture-trace',session_id:'fixture-session',question:'Inspect diatom functions',correlation_id:null,workflow_name:'tara-agent',workflow_version:'1',status:'completed',started_at:now,ended_at:now,duration_ms:100,retry_count:0,model_provider:'fixture',model_name:'fixture',markers:['v4'],sample_count:3,data_sources:[{filename:'context_general.tsv'}],error_code:null,error_message:null,created_at:now,updated_at:now,model_parameters:{},input_data:{question:'Inspect diatom functions'},output_data:{answer:'The saved English conclusion remains unchanged.',tool:{name:'function_atlas',summary:'Analyze diatom functions.'},result:{}},error_data:null,attributes:{},spans:[span('root',null,'检查分析证据并决定下一步','llm',0),span('tool','root','调用 MCP 工具 function_atlas','tool',1),span('data','tool','读取样本背景数据','data',2)]};
const health={status:'ok',data_ready:true,database_ready:true,agent_ready:true,datasets:['context_general','context_stat','18s_v4','18s_v9'].map(key=>({key,filename:key+'.tsv',ready:true})),matou:{dataset_version:'MATOU-v1.5',taxon:'Bacillariophyta',sample_counts:{MetaG:581,MetaT:581},study_ready:true,paper_reference_ready:true}};
const modes=['login','register','auth-error','data-menu','data-error','trace-rich','trace-pending','trace-empty','trace-error','chat-http-error','stream-interrupted','chart-error'];
const report={target,checks:[],failures:[],mode:'Mocked APIs; original questions, answers and raw JSON retained'};
async function scan(page){return page.evaluate(()=>{
 const values=[],walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
 for(let n;n=walker.nextNode();){const el=n.parentElement;if(!el||el.closest('pre,script,style,.language-toggle')||!el.getClientRects().length||getComputedStyle(el).visibility==='hidden')continue;const text=n.textContent.trim();if(/[\u3400-\u9fff]/.test(text))values.push(text);}
 for(const el of document.querySelectorAll('[aria-label],[title]')){if(el.closest('pre,.language-toggle')||!el.getClientRects().length)continue;for(const attribute of ['aria-label','title']){const text=el.getAttribute(attribute);if(text&&/[\u3400-\u9fff]/.test(text))values.push(attribute+': '+text);}}
 return [...new Set(values)];
});}
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.TARA_CHROME_PATH||undefined,headless:true,args:['--disable-dev-shm-usage']});
 try{for(const width of [1440,390])for(const mode of modes){
  const context=await browser.newContext({viewport:{width,height:1000},ignoreHTTPSErrors:true});
  let page;
  try{
   await context.addInitScript(()=>localStorage.setItem('tara-interface-language','en'));
   page=await context.newPage();
   if(mode==='chart-error')await page.route('**/plotly-topojson/**',route=>route.abort());
   const errors=[];page.on('pageerror',error=>errors.push(error.message));
   await page.route('**/api/v1/**',async route=>{
    const p=new URL(route.request().url()).pathname;
    let status=200,data={};
    if(p==='/api/v1/auth/me'){
     status=['login','register'].includes(mode)?401:mode==='auth-error'?503:200;
     data=status===200?{id:'surface-audit',email:'audit@example.com',display_name:'Audit',is_guest:false}:{detail:'认证服务不可用。'};
    }else if(p==='/api/v1/auth/register'){status=422;data={detail:[{loc:['body','display_name'],type:'value_error',msg:'昵称不能为空'}]};}
    else if(p==='/api/v1/auth/login'){status=401;data={detail:'邮箱或密码不正确。'};}
    else if(p==='/api/v1/health'){status=mode==='data-error'?503:200;data=health;}
    else if(p.endsWith('/traces/fixture-trace')){status=mode==='trace-error'?404:200;data=status!==200?{detail:'链路记录不存在。'}:mode==='trace-pending'?{...richTrace,output_data:null,spans:[]}:richTrace;}
    else if(p.endsWith('/traces'))data={items:mode==='trace-empty'?[]:[richTrace],page:{limit:100,offset:0,total:mode==='trace-empty'?0:1}};
    else if(p==='/api/v1/sessions')data={items:[],page:{limit:100,offset:0,total:0}};
    else if(p==='/api/v1/question-suggestions')data={items:[]};
    else if(p==='/api/v1/chat/stream'){
     if(mode==='chart-error'){const fixture=require('./ui-i18n-fixtures.cjs').cases.find(item=>item.id==='map');return route.fulfill({status:200,contentType:'text/event-stream',body:'data: '+JSON.stringify({event:'complete',response:{...fixture,answer:'This is an English map result.'}})+'\n\n'});}
     if(mode==='chat-http-error'){status=422;data={detail:[{loc:['body','question'],type:'string_too_long',ctx:{max_length:4000}}]};}
     else return route.fulfill({status:200,contentType:'text/event-stream',body:'data: '+JSON.stringify({event:'step',step:{stage:'route',title:'识别请求类型',detail:'进入当前可用的数据分析流程。'}})+'\n\n'});
    }
    return route.fulfill({status,contentType:'application/json',body:JSON.stringify(data)});
   });
   const trace=mode.startsWith('trace-');
   const url=trace?new URL(mode==='trace-empty'?'/sessions/fixture-session/traces':'/sessions/fixture-session/traces/fixture-trace',target).href:target;
   await page.goto(url,{waitUntil:'networkidle',timeout:45000});
   if(mode==='login'){
    await page.locator('input[name=email]').fill('audit@example.com');await page.locator('input[name=password]').fill('fixture-password');
    await page.locator('.auth-submit').click();await page.locator('.auth-error').waitFor();
    await page.locator('.quick-tutorial-disclosure > summary').click();
   }else if(mode==='register'){
    await page.getByRole('button',{name:'Register',exact:true}).click();
    await page.locator('input[name=display_name]').fill('Audit');await page.locator('input[name=email]').fill('audit@example.com');await page.locator('input[name=password]').fill('fixture-password');
    await page.locator('.auth-submit').click();await page.locator('.auth-error').waitFor();
   }else if(mode==='auth-error')await page.locator('.auth-service-error').waitFor();
   else if(mode.startsWith('data-'))await page.locator('.available-data > summary').click();
   else if(mode==='trace-rich'){
    await page.locator('.trace-node-button').first().waitFor();
    for(const node of await page.locator('.trace-node-button').all()){await node.click();const findings=await scan(page);if(findings.length)throw new Error(findings.join(' | '));}
    // 展开技术记录可检查外层标题，原始 JSON 不参与翻译或汉字扫描。
    for(const el of await page.locator('details.trace-section > summary').all())if(await el.isVisible()&&await el.evaluate(el=>!el.parentElement.open))await el.click();
    for(const el of await page.locator('details.json-block > summary').all())if(await el.isVisible()&&await el.evaluate(el=>!el.parentElement.open))await el.click();
   }else if(['chat-http-error','stream-interrupted','chart-error'].includes(mode)){
    await page.getByRole('textbox',{name:'Enter a Tara data question'}).fill('Find diatom samples');await page.getByRole('button',{name:'Send',exact:true}).click();await page.locator(mode==='chart-error'?'.artifact-error':'.request-error').waitFor();
   }
   if(mode==='chart-error'&&await page.locator('.artifact-error').innerText()!=='Unable to load chart')throw new Error('Missing localized chart failure message');
   let findings=await scan(page);if(findings.length)throw new Error(findings.join(' | '));
   if(mode.startsWith('data-'))await page.locator('.available-data > summary').click();
   const saved=trace?await page.locator('.trace-conclusion .trace-markdown').allTextContents():[];
   await page.locator('.language-toggle').first().click();await page.waitForFunction(()=>document.documentElement.lang==='zh-CN');
   if(mode==='trace-rich'&&JSON.stringify(await page.locator('.trace-conclusion .trace-markdown').allTextContents())!==JSON.stringify(saved))throw new Error('Saved trace answer changed with UI');
   await page.locator('.language-toggle').first().click();await page.waitForFunction(()=>document.documentElement.lang==='en');
   if(mode.startsWith('data-'))await page.locator('.available-data > summary').click();
   findings=await scan(page);if(findings.length)throw new Error(findings.join(' | '));const unexpected=errors.filter(text=>!(mode==='chart-error'&&text==='unexpected error while fetching topojson file at /plotly-topojson/world_110m.json'));
   if(unexpected.length)throw new Error(unexpected.join('; '));
   report.checks.push({width,mode,status:'passed',injectedFault:mode==='chart-error'?'Blocked topojson; localized failure shown':undefined});console.log(JSON.stringify(report.checks.at(-1)));
  }catch(error){report.failures.push({width,mode,error:error.message});console.log(JSON.stringify(report.failures.at(-1)));if(page)await page.screenshot({path:path.join(path.dirname(output),`fail-${width}-${mode}.png`),fullPage:true});}
  finally{await context.close();fs.writeFileSync(output,JSON.stringify(report,null,2));}
 }}finally{await browser.close();}
 report.status=report.failures.length?'failed':'passed';fs.writeFileSync(output,JSON.stringify(report,null,2));console.log(JSON.stringify({status:report.status,checks:report.checks.length,failures:report.failures.length}));if(report.failures.length)process.exitCode=1;
})().catch(error=>{console.error(error);process.exitCode=1});
