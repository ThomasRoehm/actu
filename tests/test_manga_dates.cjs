const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const path=require('node:path');
process.env.TZ='Europe/Paris';
let now=Date.parse('2026-10-26T20:30:00Z');
class Clock extends Date { constructor(...args){super(...(args.length?args:[now]));} static now(){return now;} }
const context=vm.createContext({Date:Clock,Intl,URL});
vm.runInContext(fs.readFileSync(path.join(__dirname,'../app.js'),'utf8').split('function icon(')[0],context);
const get=m=>context.mangaDate(m);
test('future source date uses observed day consistently, even after midnight',()=>{
 const manga={publishedDate:'2026-10-27',firstSeenAt:'2026-10-26T20:00:00Z'};
 assert.equal(get(manga).date.toLocaleDateString('fr-FR'),'26/10/2026');assert.equal(get(manga).observed,true);
 now=Date.parse('2026-10-27T12:00:00Z');assert.equal(get(manga).date.toLocaleDateString('fr-FR'),'26/10/2026');
 now=Date.parse('2026-10-26T20:30:00Z');
});
test('legacy data uses last successful observation',()=>{assert.equal(get({publishedDate:'2026-10-27',lastSuccessAt:'2026-10-26T20:00:00Z'}).observed,true);});
test('old and unknown dates are not promoted to today',()=>{
 assert.equal(get({publishedDate:'2025-01-01',firstSeenAt:'2026-10-26T20:00:00Z'}).date.getFullYear(),2025);
 for(const publishedDate of [null,'wrong','2026-02-30','2026-10-27'])assert.equal(get({publishedDate}),null);
 assert.equal(get({firstSeenAt:'2026-10-26T20:00:00Z'}),null);
});
test('observation respects local day around midnight',()=>{
 assert.equal(get({publishedDate:'2026-10-26',firstSeenAt:'2026-10-25T23:30:00Z'}).observed,false);
 assert.equal(get({publishedDate:'2026-10-26',firstSeenAt:'2026-10-25T22:30:00Z'}).date.toLocaleDateString('fr-FR'),'25/10/2026');
});

test('external links reject scripts and embedded credentials',()=>{
 for(const url of ['javascript:alert(1)','data:text/html,test','https://user:password@example.com/']) assert.equal(vm.runInContext(`safeUrl(${JSON.stringify(url)})`,context),null);
 assert.equal(vm.runInContext('safeUrl("https://example.com/a")',context),'https://example.com/a');
});
