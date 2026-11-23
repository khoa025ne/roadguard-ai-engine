const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

test('failed task selection cannot retain another task mutation state', async () => {
  const elements = new Map();
  const element = id => {
    if (!elements.has(id)) elements.set(id, {value:'',disabled:false,textContent:'',replaceChildren(){},files:[]});
    return elements.get(id);
  };
  element('wf-measure-type').value = '4';
  const fixture = {projectId:'p',workId:'w',detectionIds:['d'],classMap:{},crewUserId:'crew'};
  const sandbox = {
    document:{getElementById:element,querySelectorAll:()=>[...elements.values()]},
    Option:class {constructor(label,value){this.label=label;this.value=value;}},
    crypto:{randomUUID:()=> 'operation'},
    fetch:async (url,options) => {
      if (url.endsWith('/context')) return {ok:true,json:async()=>fixture};
      const request = JSON.parse(options.body), route = request.path;
      let body = {};
      let status = 200;
      if (route.endsWith('/field-inspection-tasks')) body = [{id:'A'},{id:'B'}];
      else if (route.endsWith('/field-inspection-tasks/A')) body = {id:'A',status:'InProgress',version:'v'};
      else if (route.endsWith('/field-inspection-tasks/B')) {status=503;body={code:'unavailable'};}
      return {ok:true,json:async()=>({status,body})};
    },
  };
  const source = process.env.RG_TEST_WORKFLOW_SOURCE || path.join(__dirname,'../src/api/web/test_studio/workflow.js');
  vm.runInNewContext(fs.readFileSync(source,'utf8'),sandbox);
  for (let i=0;i<10;i++) await new Promise(setImmediate);
  element('wf-tasks').value = 'A';
  await element('wf-tasks').onchange();
  assert.equal(element('wf-upload').disabled,false);
  element('wf-tasks').value = 'B';
  await element('wf-tasks').onchange();
  for (const action of ['accept','start','upload','submit','review'])
    assert.equal(element('wf-'+action).disabled,true,action+' must remain disabled');
  assert.match(element('wf-message').textContent,/unavailable/);
});
