// 独立浏览器中的错误路径回归；接口全部模拟，不调用模型或写真实用户数据。
const {chromium}=require(process.env.TARA_PLAYWRIGHT_MODULE||'playwright');
const fs=require('node:fs');
const path=require('node:path');
const output=process.env.TARA_PLANNING_ERROR_OUTPUT||'/tmp/tara-planning-errors/report.json';
const rounds=Number(process.env.TARA_AUDIT_ROUNDS||2);
if(!Number.isInteger(rounds)||rounds<1)throw new Error('Invalid rounds');
const cases=[
 ['模型返回了无效的分析决定','The model could not produce a valid analysis plan. Please try again.'],
 ['模型服务暂时不可用，请稍后重试。','The model service is temporarily unavailable. Please try again later.'],
];
const report={checks:[],failures:[],mode:'API mocked; no model calls or server writes'};
fs.mkdirSync(path.dirname(output),{recursive:true});
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.TARA_CHROME_PATH||undefined,headless:true,args:['--disable-dev-shm-usage']});
 try{for(let round=1;round<=rounds;round++)for(const width of [1440,390])for(const [source,english] of cases){
  const context=await browser.newContext({viewport:{width,height:900}});
  try{
   await context.addInitScript(()=>localStorage.setItem('tara-interface-language','en'));
   const page=await context.newPage();const errors=[];page.on('pageerror',error=>errors.push(error.message));
   await page.route('**/api/v1/**',route=>{
    const p=new URL(route.request().url()).pathname;
    if(p==='/api/v1/chat/stream')return route.fulfill({status:200,contentType:'text/event-stream',body:'data: '+JSON.stringify({event:'step',step:{stage:'route',title:'识别请求类型',detail:'进入当前可用的数据分析流程。'}})+'\n\ndata: '+JSON.stringify({event:'error',error:source})+'\n\n'});
    const data=p==='/api/v1/auth/me'?{id:'error-fixture',email:'fixture@example.com',display_name:'Fixture',is_guest:false}:p==='/api/v1/sessions'?{items:[],page:{limit:100,offset:0,total:0}}:p==='/api/v1/question-suggestions'?{items:[]}:{status:'ok',data_ready:true,agent_ready:true,datasets:[]};
    return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(data)});
   });
   await page.goto(process.env.TARA_AUDIT_URL||'http://localhost:3000/',{waitUntil:'networkidle',timeout:45000});
   await page.getByRole('textbox',{name:'Enter a Tara data question'}).fill('What is the relative abundance of Dinoflagellata across V9 samples?');
   await page.getByRole('button',{name:'Send',exact:true}).click();
   await page.waitForFunction(text=>document.querySelector('.request-error')?.textContent===text,english);
   if(/[\u3400-\u9fff]/.test(await page.locator('.request-error').innerText()))throw new Error('Chinese error in English UI');
   await page.getByRole('button',{name:'切换为中文',exact:true}).first().click();
   await page.waitForFunction(text=>document.querySelector('.request-error')?.textContent===text,source);
   await page.getByRole('button',{name:'Switch to English',exact:true}).first().click();
   await page.waitForFunction(text=>document.querySelector('.request-error')?.textContent===text,english);
   if(errors.length)throw new Error(errors.join('; '));
   report.checks.push({round,width,source,english,languageSwitchChecked:true});
   console.log(JSON.stringify({round,width,source,status:'passed'}));
  }catch(error){report.failures.push({round,width,source,error:error.message});console.log(JSON.stringify(report.failures.at(-1)));}
  finally{await context.close();fs.writeFileSync(output,JSON.stringify(report,null,2));}
 }}finally{await browser.close();}
 if(report.checks.length!==rounds*4)report.failures.push({error:'Missing cases'});
 report.status=report.failures.length?'failed':'passed';fs.writeFileSync(output,JSON.stringify(report,null,2));console.log(JSON.stringify({status:report.status,checks:report.checks.length,failures:report.failures.length}));if(report.failures.length)process.exitCode=1;
})().catch(e=>{console.error(e);process.exitCode=1});
