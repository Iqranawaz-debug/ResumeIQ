import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { transformWithOxc } from 'vite'
import { filterCandidates, validateBatch, EMPTY_FILTERS, REVIEW_STATUSES } from '../src/recruiterState.js'

const sample = [{ id: 'one', name: 'Synthetic Person', skills: ['Python'], education: ['BSc in progress'], employment_titles: ['Developer'], status: 'Not Reviewed', analysis_state: 'completed', score_source: 'rule-based', matched_skills: ['python'], missing_skills: ['docker'], processing_status: 'completed' }, { id: 'two', name: 'Other', skills: ['React'], status: 'Shortlisted', analysis_state: 'outdated', processing_status: 'completed' }]
const filter = (value) => filterCandidates(sample, { ...EMPTY_FILTERS, ...value })
test('search covers case-insensitive names skills education roles and status', () => {
  for (const search of ['sYntHetic', 'python', 'bsc', 'developer', 'not reviewed']) assert.deepEqual(filter({ search }).map(row=>row.id),['one'])
})
test('filters combine without ranking or treating missing skill as absence',()=>{
  assert.equal(filter({review:'Not Reviewed',source:'rule-based',matched:'PYTHON',missing:'DOCKER',analysis:'completed',processing:'completed'}).length,1)
  assert.equal(filter({review:'Shortlisted',matched:'python'}).length,0)
  assert.deepEqual(filter({}).map(row=>row.id),['one','two'])
})
test('untrusted search is literal and missing optional fields are safe',()=>{
  assert.equal(filter({search:'[.*<script>'}).length,0)
  assert.equal(filterCandidates([{}],EMPTY_FILTERS).length,1)
  assert.equal(filterCandidates(null,EMPTY_FILTERS).length,0)
  assert.equal(filter({source:'invented'}).length,0)
})
test('batch selection bounds file count and aggregate size',()=>{
  const limits={files:5,batch_bytes:10}
  assert.ok(validateBatch([],limits)); assert.ok(validateBatch(Array(6).fill({size:1}),limits))
  assert.ok(validateBatch([{size:6},{size:5}],limits))
  assert.equal(validateBatch([{size:5},{size:5}],limits),'')
})

const cache=new Map()
async function compile(name) {
  if(cache.has(name)) return cache.get(name)
  const source=await readFile(new URL(`../src/${name}.jsx`,import.meta.url),'utf8')
  const transformed=await transformWithOxc(source,`${name}.jsx`,{jsx:{runtime:'classic'}})
  let code=transformed.code.replace(/(['"])react\1/g,JSON.stringify(import.meta.resolve('react')))
  for(const file of ['ExplainableResults','RecruiterComparison']) if(code.includes(`./${file}`)) code=code.replace(new RegExp(`(['"])\\./${file}\\1`,'g'),JSON.stringify(await compile(file)))
  for(const file of ['recruiterState','api']) code=code.replace(new RegExp(`(['"])\\./${file}\\1`,'g'),JSON.stringify(new URL(`../src/${file}.js`,import.meta.url).href))
  const url=`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`; cache.set(name,url); return url
}
const {default:Comparison}=await import(await compile('RecruiterComparison'))
const render=(rows)=>renderToStaticMarkup(React.createElement(Comparison,{rows,onReview:()=>{}}))
test('comparison distinguishes missing evidence and score provenance',()=>{
  const html=render([{...sample[0],candidate:{},analysis:{overall_score:42,resume_quality_score:80,job_fit_score:25,job_fit_method:'ai'}}])
  assert.match(html,/Score source: ai/); assert.match(html,/Overall: 42/)
  assert.match(html,/Not evidenced in resume/); assert.match(html,/does not verify graduation/)
  assert.match(html,/older analysis/)
})
test('comparison exposes reversible human review controls and source content',()=>{
  const html=render([{...sample[0],candidate:{experience:[{title:'Developer',details:['Built Python tools.']}],projects:[{title:'Demo',details:['Used SQL.']}]}}])
  for(const status of REVIEW_STATUSES) assert.ok(html.includes(status))
  assert.match(html,/Built Python tools/); assert.match(html,/Projects \(not employment\)/)
  assert.match(html,/do not change scores/)
})
test('candidate and filename text is escaped including long Unicode content',()=>{
  const html=render([{...sample[0],name:'<script>bad()</script>',filename:'候補者'.repeat(60),candidate:{}}])
  assert.ok(!html.includes('<script>')); assert.match(html,/&lt;script&gt;/)
  assert.ok(html.includes('候補者'.repeat(60))); assert.equal(render([]),'<div class="recruiter-comparison" aria-label="Candidate comparison"></div>')
})
test('review component dispatches only explicit manual selections',()=>{
  const actions=[]
  function walk(element) { return !element || typeof element!=='object' ? [] : [element,...React.Children.toArray(element.props?.children).flatMap(walk)] }
  const tree=walk(Comparison({rows:[sample[0]],onReview:(row,status)=>actions.push([row.id,status])}))
  assert.equal(actions.length,0)
  tree.find(node=>node.type==='select').props.onChange({target:{value:'Shortlisted'}})
  assert.deepEqual(actions,[['one','Shortlisted']])
})
