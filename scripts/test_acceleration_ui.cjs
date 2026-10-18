const fs = require('fs'), vm = require('vm'), assert = require('assert');
class Node {
    constructor(tag,attrs={},children=[]) { this.tag=tag; this.attrs=attrs; this.dataset={}; this.checked=!!attrs.checked; this.disabled=!!attrs.disabled; this.children=Array.isArray(children)?children:[children]; this.textContent=''; this.className=attrs.class||''; }
    dispatchEvent(e) { if(this.attrs[e.type]) this.attrs[e.type](); }
    setAttribute(k,v) { this.attrs[k]=v; }
    replaceChildren(...nodes) { this.children=nodes; }
}
let state={ok:true,configured:{software:true,hardware:true,wed:false},runtime:{software:true,hardware:true,wed:false},supported:{software:true,hardware:true,wed:true},bindings:5,wed_pending:false,client_policies:0}, readOnly=false, submitted=null;
const clone=x=>JSON.parse(JSON.stringify(x));
const ctx={ Event: class { constructor(type) { this.type=type; } }, E:(...a)=>new Node(...a), view:{extend:x=>x}, rpc:{declare: d=>d.method==='status'?()=>Promise.resolve(clone(state)):(software,hardware,wed)=>{
    submitted={software,hardware,wed}; state.configured=submitted; state.runtime={software,hardware,wed:false}; state.wed_pending=wed; return Promise.resolve(clone(state));
}}, poll:{add:()=>{}}, ui:{addNotification:()=>{}}, document:{body:{}}, L:{hasViewPermission:()=>!readOnly,resource:x=>'/'+x},getComputedStyle:()=>({backgroundColor:'rgb(255,255,255)'}) };
const source=fs.readFileSync('package/luci-app-tr3600-acceleration/files/www/luci-static/resources/view/network/tr3600-acceleration.js','utf8');
const page=vm.runInNewContext('(function(){'+source+'})()',ctx);
async function main() {
    page.render(clone(state));
    assert(page.inputs.software.checked && page.inputs.hardware.checked && !page.inputs.wed.checked);
    assert(page.apply.disabled);
    page.inputs.software.attrs.click();
    assert(!page.inputs.hardware.checked && !page.apply.disabled);
    page.inputs.hardware.attrs.click();
    assert(page.inputs.software.checked && page.inputs.hardware.checked);
    page.inputs.wed.attrs.click();
    assert(page.inputs.wed.attrs['aria-checked']==='true');
    page.update(clone(state),false);
    assert(page.inputs.wed.checked,'Polling preserves edits');
    await page.applySettings();
    assert(submitted.wed && page.badges.wed.textContent==='待重启' && page.runtime.wed.textContent==='当前状态 · 关闭');
    assert(page.apply.disabled && !page.inputs.wed.disabled);
    state.configured.software=false; state.configured.hardware=false; state.runtime.software=false; state.runtime.hardware=false;
    page.update(clone(state),false);
    assert(!page.inputs.software.checked && !page.inputs.hardware.checked,'External changes refresh clean form');
    ctx.getComputedStyle=()=>({backgroundColor:'rgb(30,30,35)'}); page.update(clone(state),false);
    assert(page.root.dataset.accDark==='true');
    readOnly=true; page.update(clone(state),false);
    assert(page.inputs.software.disabled && page.inputs.hardware.disabled && page.inputs.wed.disabled);
    state.wed_pending=false; state.configured.wed=true; state.runtime.wed=false;
    state.wed_diagnostic={state:'failed',logs:'[11] failed to attach wed device',logs_available:true};
    page.update(clone(state),true);
    assert(page.inputs.wed.checked && page.badges.wed.textContent==='未生效');
    assert(!page.wedFault.hidden && page.wedLog.textContent===state.wed_diagnostic.logs);
    page.wedFault.children[1].open=true;
    page.update(clone(state),false);
    assert(page.wedFault.children[1].open,'Polling preserves expanded log');
    state.wed_diagnostic={state:'running',logs:'old failure',logs_available:true};state.runtime.wed=true;
    page.update(clone(state),true);assert(page.wedFault.hidden && page.badges.wed.textContent==='已开启');
    state.wed_diagnostic={state:'unknown',logs:'',logs_available:false};state.runtime.wed=false;
    page.update(clone(state),true);assert(page.badges.wed.textContent==='状态未知' && !page.wedFault.hidden);
    console.log('13 UI interaction checks passed');
}
main().catch(e=>{console.error(e);process.exit(1)});
