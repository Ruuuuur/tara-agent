// 独立浏览器验证首页导览，接口使用合成数据，不写入真实用户记录。
const {chromium}=require(process.env.TARA_PLAYWRIGHT_MODULE||'playwright');
const fs=require('node:fs');
const outputDir=process.env.TARA_HOMEPAGE_OUTPUT||'/tmp/tara-homepage-audit';
const target=process.env.TARA_AUDIT_URL||'http://localhost:3000/';
fs.mkdirSync(outputDir,{recursive:true});
(async()=>{
const browser=await chromium.launch({executablePath:process.env.TARA_CHROME_PATH||undefined,headless:true,args:['--disable-dev-shm-usage']});
const report={target,checks:[],failures:[],mode:'Deployed frontend over SSH tunnel; mocked API in isolated contexts'};
try{for(const width of [1440,390])for(const auth of [false,true])for(const language of ['en','zh']){
 const context=await browser.newContext({viewport:{width,height:1000},permissions:['clipboard-read','clipboard-write']});
 const key=`${width}-${auth?'workspace':'login'}-${language}`;
 try{
 await context.addInitScript(lang=>localStorage.setItem('tara-interface-language',lang),language);
 const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/api/v1/**',route=>{
 const pathname=new URL(route.request().url()).pathname;
 if(pathname==='/api/v1/auth/me')return route.fulfill({status:auth?200:401,contentType:'application/json',body:JSON.stringify(auth?{id:'homepage-audit',email:'audit@example.com',display_name:'Audit',is_guest:false}:{detail:'Authentication required'})});
 return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(pathname==='/api/v1/sessions'?{items:[],page:{limit:100,offset:0,total:0}}:pathname==='/api/v1/question-suggestions'?{items:[]}:{data_ready:true,database_ready:true,agent_ready:true,status:'ok',datasets:[]})});
 });
 await page.goto(target,{waitUntil:'networkidle',timeout:45000});
 const disclosure=page.locator(auth?'.workspace-intro':'.quick-tutorial-disclosure');
 await disclosure.waitFor();
 if(await disclosure.getAttribute('open')!==null)throw new Error('Tutorial must start collapsed');
 if(!auth&&width===390){const form=await page.locator('.auth-card').boundingBox(),intro=await page.locator('.project-intro').boundingBox();if(!form||!intro||form.y>=intro.y||form.y>200)throw new Error('Mobile sign-in form must precede the introduction');}
 if(auth){
  if(await page.evaluate(()=>scrollY)>10)throw new Error('Empty conversation should start at the top');
  await page.evaluate(()=>window.scrollTo(0,document.documentElement.scrollHeight));
  await page.getByRole('button',{name:language==='en'?'New conversation':'新建对话',exact:true}).first().click();
  await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
  if(await page.evaluate(()=>scrollY)>10)throw new Error('New conversation should remain at the top');
 }
 await disclosure.locator(':scope > summary').click();
 const tutorial=page.locator('.quick-tutorial');await tutorial.waitFor();
 if(await tutorial.locator('.tutorial-steps > li').count()!==5)throw new Error('Expected five tutorial steps');
 if(await tutorial.locator('.tutorial-copy').count()!==5)throw new Error('Expected five copy buttons');
 const prompts=await tutorial.locator('.tutorial-prompt').allTextContents();
 await tutorial.locator('.tutorial-copy').first().click();
 if(await page.evaluate(()=>navigator.clipboard.readText())!==prompts[0])throw new Error('Copy did not preserve the prompt');
 const intro=page.locator('.project-intro');
 for(const href of ['https://www.tara-oceans-science.org/tara-oceans-expedition/','https://oga.mio.osupytheas.fr/ocean-gene-atlas/','https://www.nature.com/articles/s41467-025-58027-7'])if(await intro.locator(`a[href="${href}"][target="_blank"][rel="noopener noreferrer"]`).count()!==1)throw new Error('Resource link missing or unsafe');
 await page.locator('.language-toggle').first().click();
 if(JSON.stringify(await tutorial.locator('.tutorial-prompt').allTextContents())!==JSON.stringify(prompts))throw new Error('Literal tutorial prompts changed with UI language');
 await page.locator('.language-toggle').first().click();
 const expected=language==='en'?'Complete an analysis in five steps':'五步完成一次分析';
 if(await tutorial.locator('h3').textContent()!==expected)throw new Error('Tutorial heading language mismatch');
 if(language==='en'&&/[\u3400-\u9fff]/.test(await intro.textContent()))throw new Error('Chinese text in English onboarding');
 if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1))throw new Error('Horizontal page overflow');
 if(errors.length)throw new Error(errors.join('; '));
 await page.screenshot({path:`${outputDir}/${key}.png`,fullPage:true});
 report.checks.push({key,status:'passed',steps:5,copy:true,resources:true,languageSwitch:true});console.log(key+' passed');
 }catch(e){report.failures.push({key,error:e.message});console.log(key+' FAILED '+e.message);}
 finally{await context.close();}
}}finally{await browser.close();}
report.status=report.failures.length?'failed':'passed';fs.writeFileSync(`${outputDir}/report.json`,JSON.stringify(report,null,2));console.log(JSON.stringify({status:report.status,checks:report.checks.length,failures:report.failures}));if(report.failures.length)process.exitCode=1;
})().catch(e=>{console.error(e);process.exitCode=1});
