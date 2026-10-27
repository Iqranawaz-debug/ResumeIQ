// Real browser journeys; use the same isolated servers as browser-qa.mjs.
import assert from 'node:assert/strict'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { resolve } from 'node:path'
import { pathToFileURL } from 'node:url'
import { randomUUID } from 'node:crypto'
const { chromium } = await import(pathToFileURL(resolve(process.env.QA_PLAYWRIGHT, 'index.mjs')).href)
const out=resolve('../test-results/phase6'), fixtures=resolve('../test-results/phase51')
await mkdir(out,{recursive:true})
const browser=await chromium.launch({executablePath:process.env.QA_BROWSER,headless:true})
const context=await browser.newContext({viewport:{width:1440,height:900}})
const page=await context.newPage(); page.setDefaultTimeout(10000)
const base='http://127.0.0.1:5175',api='http://127.0.0.1:8003'
const results=[],errors=[],consoleErrors=[],unexpected=[],failures=[],timings=[]
await context.route('**/*',route=>{
  const url=new URL(route.request().url())
  if([base,api].includes(url.origin)||['blob:','data:'].includes(url.protocol)) return route.continue()
  unexpected.push(url.origin); return route.abort()
})
page.on('pageerror',error=>errors.push(error.message))
page.on('console',message=>{if(message.type()==='error')consoleErrors.push(message.text())})
page.on('requestfailed',request=>failures.push({path:new URL(request.url()).pathname,error:request.failure()?.errorText}))
const button=name=>page.getByRole('button',{name,exact:true})
const table=()=>page.getByRole('region',{name:'Candidate list, scroll horizontally if needed'})
const candidates=()=>table().locator('tbody tr')
const workspace=()=>page.getByRole('region',{name:'Recruitment workspaces',exact:true})
let groupId,firstId,token,version=1,score
async function scenario(name,fn){try{await fn();results.push({name,result:'passed'});console.log('PASS',name)}catch(error){results.push({name,result:'failed',error:error.message.split('\n').slice(0,4).join('\n')});console.log('FAIL',name,error.message.split('\n')[0]);await page.screenshot({path:resolve(out,`failure-${results.length}.png`),fullPage:true}).catch(()=>{})}}
async function signup(){await button('Create an account').click();await page.getByLabel('Full name').fill('Fictional Recruiter');await page.getByLabel('Work email').fill(`qa-${randomUUID()}@example.invalid`);await page.getByLabel('Password').fill(randomUUID());const pending=page.waitForResponse(`${api}/api/signup`);await button('Create Account').click();token=(await(await pending).json()).token;await page.getByRole('heading',{name:'Upload a resume',exact:true}).waitFor()}
async function create(title){await page.getByLabel('Job title',{exact:true}).fill(title);await page.getByLabel('Shared job description').fill('Required skills: Python, React.js, NodeJS, SQL. Preferred skills: Docker. 2 years experience.');const pending=page.waitForResponse(r=>r.url()===`${api}/api/workspaces`&&r.request().method()==='POST');await button('Create workspace').click();const data=await(await pending).json();groupId=data.id;version=data.version;await page.getByRole('heading',{name:'Bulk upload',exact:true}).waitFor()}
async function uploadFiles(files,label){await page.getByLabel('Select resumes',{exact:true}).setInputFiles(files);const pending=page.waitForResponse(r=>r.url()===`${api}/api/workspaces/${groupId}/uploads`&&r.request().method()==='POST');const start=Date.now();await button('Process selected files').click();const response=await pending;const data=await response.json();timings.push({label,ms:Date.now()-start,total:data.total});assert.equal(response.status(),200);await button('Analyze group locally').waitFor();return data}
async function waitIdle(){await page.waitForFunction(()=>{const b=[...document.querySelectorAll('button')].find(n=>n.textContent==='Analyze group locally');return b&&!b.disabled})}
async function analyze(){await button('Analyze group locally').click();await page.getByText(/Analysis pass finished/).waitFor();await waitIdle()}
async function selectTwo(){await candidates().nth(0).getByRole('checkbox').check();await candidates().nth(1).getByRole('checkbox').check();await button('Compare selected candidates').click();await page.locator('.recruiter-comparison article').nth(1).waitFor()}
try{
 await page.goto(base)
 await scenario('Authenticated recruiter navigation preserves individual upload screen',async()=>{await signup();await button('Recruitment').click();await page.getByRole('heading',{name:'Recruitment workspaces',exact:true}).waitFor();assert.ok((await workspace().innerText()).includes('server memory only'))})
 for(const [width,height]of [[1440,900],[1366,768],[768,1024],[390,844],[360,800]])await scenario(`Workspace creation viewport ${width}x${height}`,async()=>{
   await page.setViewportSize({width,height});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false)
   await page.getByLabel('Job title',{exact:true}).focus();await page.keyboard.press('Tab');assert.equal(await page.getByLabel('Shared job description').evaluate(n=>n===document.activeElement),true)
 })
 await page.setViewportSize({width:1440,height:900})
 await scenario('Create a private job workspace with shared description',async()=>{await create('Synthetic engineering role');assert.ok((await workspace().innerText()).includes('Job version 1'))})
 await scenario('Multiple-file selection and removal before submission',async()=>{await page.getByLabel('Select resumes',{exact:true}).setInputFiles([resolve(fixtures,'synthetic.pdf'),resolve(fixtures,'synthetic.docx')]);await button('Remove file 2').click();assert.equal(await button('Remove file 2').count(),0);assert.ok((await workspace().innerText()).includes('synthetic.pdf'))})
 await scenario('Mixed PDF DOCX and corrupt file preserve partial success',async()=>{
   const data=await uploadFiles([{name:'synthetic.pdf',mimeType:'application/pdf',buffer:await readFile(resolve(fixtures,'synthetic.pdf'))},{name:'synthetic.docx',mimeType:'application/octet-stream',buffer:await readFile(resolve(fixtures,'synthetic.docx'))},{name:'broken.pdf',mimeType:'application/pdf',buffer:Buffer.from('harmless invalid')}],'mixed three files')
   assert.equal(data.completed,2);assert.equal(data.failed,1);firstId=data.outcomes[0].candidate_id
   await waitIdle();assert.equal(await candidates().count(),2);assert.ok((await workspace().innerText()).includes('broken.pdf: failed'))
 })
 await scenario('Retry failed selection with valid replacement',async()=>{const data=await uploadFiles([resolve(out,'candidate-1.docx')],'replacement one');assert.equal(data.failed,0);await waitIdle();assert.equal(await candidates().count(),3)})
 await scenario('Duplicate bytes with different filename do not create candidates',async()=>{const data=await uploadFiles([{name:'renamed.pdf',mimeType:'application/pdf',buffer:await readFile(resolve(fixtures,'synthetic.pdf'))}],'duplicate one');assert.equal(data.outcomes[0].kind,'duplicate');await waitIdle();assert.equal(await candidates().count(),3)})
 await scenario('Analyze shared job locally and compare two candidates',async()=>{await analyze();await selectTwo();const text=await page.locator('.recruiter-comparison').innerText();assert.ok(text.includes('Score source: rule-based'));assert.ok(text.includes('Not evidenced')||text.includes('Requirements not evidenced'));assert.ok(text.toLowerCase().includes('docker'));assert.ok(text.includes('Python'));score=await candidates().first().locator('td').nth(2).innerText()})
 await scenario('Manual review statuses reversible and do not change score',async()=>{
   const select=candidates().first().getByRole('combobox')
   for(const status of ['Under Review','Shortlisted','Not Selected','Not Reviewed']){await select.selectOption(status);await page.getByText('Manual review status saved. Evaluation scores are unchanged.').waitFor();await waitIdle();assert.equal(await select.inputValue(),status);assert.equal(await candidates().first().locator('td').nth(2).innerText(),score)}
 })
 await scenario('Search combined skill and review filters and clear',async()=>{
   await page.getByLabel('Search candidates',{exact:true}).fill('mOrGaN');assert.equal(await candidates().count(),1)
   await page.getByLabel('Matched skill filter',{exact:true}).fill('PYTHON');assert.equal(await candidates().count(),1)
   await page.getByLabel('Not-evidenced skill filter',{exact:true}).fill('Docker');assert.equal(await candidates().count(),1)
   await page.getByLabel('Review filter').selectOption('Shortlisted');assert.equal(await candidates().count(),0)
   await button('Clear filters').click();assert.equal(await candidates().count(),3)
 })
 for(const [width,height]of [[1440,900],[1366,768],[768,1024],[390,844],[360,800]])await scenario(`Recruiter list comparison and controls viewport ${width}x${height}`,async()=>{
   await page.setViewportSize({width,height});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false)
   await page.getByLabel('Search candidates',{exact:true}).focus();await page.keyboard.press('Tab');assert.equal(await page.getByLabel('Review filter').evaluate(n=>n===document.activeElement),true)
   await page.screenshot({path:resolve(out,`recruiter-${width}.png`),fullPage:true})
   await page.locator('.recruiter-comparison article').first().scrollIntoViewIfNeeded()
   await page.screenshot({path:resolve(out,`comparison-viewport-${width}.png`)})
 })
 await page.setViewportSize({width:1440,height:900})
 await scenario('Job-description edit invalidates comparison until reanalysis',async()=>{
   await page.getByLabel('Shared job description').fill('Required skills: Python, Docker, Kubernetes.')
   await button('Save job changes').click();await page.getByText(/Workspace saved/).waitFor();version++
   assert.ok((await workspace().innerText()).includes(`Job version ${version}`))
   assert.ok((await candidates().first().innerText()).includes('outdated'))
   await candidates().first().getByRole('checkbox').check();await button('Compare selected candidates').click();await workspace().getByRole('alert').waitFor()
   assert.ok((await workspace().getByRole('alert').innerText()).includes('Analyze every selected'))
   await analyze();await candidates().nth(1).getByRole('checkbox').check();await button('Compare selected candidates').click();await page.locator('.recruiter-comparison article').nth(1).waitFor()
 })
 await scenario('Endpoint failure preserves existing candidates and permits retry',async()=>{
   await page.route('**/api/workspaces/*/uploads',route=>route.fulfill({status:503,contentType:'application/json',body:'{"detail":"Temporary QA failure"}'}))
   await page.getByLabel('Select resumes',{exact:true}).setInputFiles(resolve(out,'candidate-2.docx'));await button('Process selected files').click();await workspace().getByRole('alert').waitFor();assert.equal(await candidates().count(),3)
   await page.unroute('**/api/workspaces/*/uploads');await uploadFiles([resolve(out,'candidate-2.docx')],'recovery one');await waitIdle();assert.equal(await candidates().count(),4)
 })
 await scenario('Connection refusal preserves candidate list',async()=>{
   await page.route('**/api/workspaces/*/uploads',route=>route.abort('connectionrefused'))
   await page.getByLabel('Select resumes',{exact:true}).setInputFiles(resolve(out,'candidate-3.docx'));await button('Process selected files').click();await workspace().getByRole('alert').waitFor();assert.equal(await candidates().count(),4)
   await page.unroute('**/api/workspaces/*/uploads')
 })
 await scenario('Five-file medium batch completes within configured count limit',async()=>{
   await button('New workspace').click();await create('Synthetic medium batch')
   const data=await uploadFiles([1,2,3,4,5].map(n=>resolve(out,`candidate-${n}.docx`)),'medium five files')
   assert.equal(data.completed,5);await waitIdle();assert.equal(await candidates().count(),5)
 })
 await scenario('Comparison selection limited to four and individual details accessible',async()=>{
   for(let i=0;i<4;i++)await candidates().nth(i).getByRole('checkbox').check()
   assert.equal(await candidates().nth(4).getByRole('checkbox').isDisabled(),true)
   await candidates().first().getByRole('button',{name:'Review candidate',exact:true}).click();await page.locator('.recruiter-comparison article').waitFor();assert.ok((await page.locator('.recruiter-comparison').innerText()).includes('Professional experience'))
 })
 await scenario('Excess file count rejected before request',async()=>{
   await page.getByLabel('Select resumes',{exact:true}).setInputFiles([1,2,3,4,5,1].map(n=>resolve(out,`candidate-${n}.docx`)));await button('Process selected files').click();await workspace().getByRole('alert').waitFor();assert.ok((await workspace().getByRole('alert').innerText()).includes('Select 1–5'));assert.equal(await candidates().count(),5)
 })
 await scenario('Workspace reopening and browser refresh preserve server-owned review data',async()=>{
   const own=groupId;await page.reload();await button('Recruitment').click();await page.getByLabel('Open workspace').selectOption(own);await candidates().nth(4).waitFor();assert.equal(await candidates().count(),5)
 })
 await scenario('Second account cannot read or change another workspace or candidate',async()=>{
   await button('Log out').click();await page.getByRole('heading',{name:'Welcome back',exact:true}).waitFor();await signup()
   for(const [method,path,body]of [['GET',`/api/workspaces/${groupId}`],['GET',`/api/workspaces/${groupId}/candidates/${firstId}`],['PATCH',`/api/workspaces/${groupId}/candidates/${firstId}/review`,{status:'Shortlisted',revision:0}]]){
     const response=await context.request.fetch(`${api}${path}`,{method,headers:{Authorization:`Bearer ${token}`},...(body?{data:body}:{})});assert.equal(response.status(),404)
   }
   await button('Recruitment').click();await page.getByRole('heading',{name:'Recruitment workspaces',exact:true}).waitFor();assert.equal(await page.getByLabel('Open workspace').locator('option').count(),1)
 })
 await scenario('No runtime exceptions or third-party network origins',async()=>{assert.deepEqual(errors,[]);assert.deepEqual(unexpected,[])})
}finally{
 await writeFile(resolve(out,'browser-results.json'),JSON.stringify({browser:browser.version(),mode:'headless',platform:process.platform,results,errors,consoleErrors,unexpected,failures,timings},null,2))
 console.log(JSON.stringify({browser:browser.version(),passed:results.filter(r=>r.result==='passed').length,failed:results.filter(r=>r.result==='failed').length,timings}))
 await browser.close()
}
if(results.some(r=>r.result==='failed'))process.exitCode=1
