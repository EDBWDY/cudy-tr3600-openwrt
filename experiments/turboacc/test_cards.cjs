const fs=require('fs'),vm=require('vm'),assert=require('assert');
class Node {
 constructor(tag,attrs={},children=[]) { this.tag=tag;this.attrs=attrs;this.dataset={};this.checked=false;this.disabled=false;this.value='';this.children=Array.isArray(children)?children:[children];this.textContent=''; }
 dispatchEvent(e){this.attrs[e.type]?.();} setAttribute(k,v){this.attrs[k]=v;} replaceChildren(...nodes){this.children=nodes;}
}
let readonly=false,poll,modal,submitted;
let state={ok:true,configured:{software:true,hardware:true,wed:false,nat:'0',nat_tcp:false,cca:'cubic'},runtime:{software:true,hardware:true,wed:false},supported:{software:true,hardware:true,wed:true,nat:true,nat_tcp:false},algorithms:['reno','cubic'],bindings:3,wed_diagnostic:{state:'disabled'}};
const copy=x=>JSON.parse(JSON.stringify(x));
const context={E:(...args)=>new Node(...args),Event:class{constructor(type){this.type=type;}},document:{body:{}},getComputedStyle:()=>({backgroundColor:'rgb(255,255,255)'}),view:{extend:x=>x},L:{resource:x=>x,hasViewPermission:()=>!readonly},poll:{add:fn=>poll=fn},ui:{showModal:(title,children)=>modal=children,hideModal:()=>{},addNotification:()=>{}},rpc:{declare:d=>d.method==='getUiStatus'?()=>Promise.resolve(copy(state)):(...args)=>{submitted=args;state.configured={software:args[0],hardware:args[1],wed:args[2],nat:args[3],nat_tcp:args[4],cca:args[5]};return Promise.resolve(copy(state));}}};
const page=vm.runInNewContext('(function(){'+fs.readFileSync(__dirname+'/turboacc_cards.js','utf8')+'})()',context);
async function main(){
 page.render(copy(state));assert(page.apply.disabled);assert(page.inputs.nat_tcp.disabled);
 page.inputs.cca.value='reno';page.inputs.cca.attrs.change();await poll();assert.equal(page.inputs.cca.value,'reno');assert(!page.apply.disabled);
 await page.applySettings();assert.equal(submitted[5],'reno');assert(page.apply.disabled);
 // Clean polling never writes an unchanged select value or replaces options.
 let writes=0,current=page.inputs.cca.value;Object.defineProperty(page.inputs.cca,'value',{get:()=>current,set:v=>{current=v;writes++;}});await poll();assert.equal(writes,0);
 page.inputs.software.attrs.click();assert(!page.inputs.hardware.checked);page.inputs.hardware.attrs.click();assert(page.inputs.software.checked);
 page.inputs.nat.value='2';page.inputs.nat.attrs.change();let oldSubmitted=submitted;
 let request=page.applySettings();assert.equal(submitted,oldSubmitted);assert(modal[0].children.includes('全锥形 NAT 允许外部任意主机通过已建立的映射向内网设备发起连接，增加暴露面。'));
 modal[2].children[1].attrs.click();await request;assert.equal(submitted[3],'2');assert.equal(submitted[4],false);assert.equal(submitted[6],true);assert.equal(page.riskConfirmed,false);
 page.inputs.nat.value='1';page.inputs.nat.attrs.change();request=page.applySettings();modal[2].children[0].attrs.click();await request;assert.equal(submitted[3],'2','cancel preserves running NAT mode');page.update(copy(state),true);
 state.supported.nat_tcp=true;page.update(copy(state),true);assert(!page.inputs.nat_tcp.disabled);page.inputs.nat_tcp.checked=true;page.inputs.nat_tcp.attrs.change();request=page.applySettings();assert.equal(submitted[4],false);modal[2].children[1].attrs.click();await request;assert.equal(submitted[4],true);assert.equal(submitted[6],true);
 page.inputs.nat.value='0';page.inputs.nat.attrs.change();assert(page.inputs.nat_tcp.disabled);page.update(copy(state),true);
 state.wed_diagnostic={state:'failed',logs:'attach failed'};page.update(copy(state),true);assert.equal(page.badges.wed.textContent,'未生效');page.wedFault.children[1].open=true;await poll();assert(page.wedFault.children[1].open);
 readonly=true;page.update(copy(state),true);for(const item of Object.values(page.inputs))assert(item.disabled);assert(page.apply.disabled);
 context.getComputedStyle=()=>({backgroundColor:'rgb(25,25,25)'});await poll();assert.equal(page.root.dataset.accDark,'true');
 console.log('Card UI: edits, dropdown polling, dependencies, risk confirmation, TCP backend gating and opt-in, diagnostics, read-only and dark theme passed');
}
main().catch(e=>{console.error(e);process.exit(1);});
