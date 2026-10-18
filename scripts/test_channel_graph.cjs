const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const source=fs.readFileSync(process.argv[2],'utf8');
const ctx=vm.createContext({view:{extend:x=>x},rpc:{declare:()=>async()=>({})},poll:{stop(){}},L:{bind:(f,o)=>f.bind(o)},E:(...x)=>x,_:x=>x,cbi_update_table:(table,rows)=>table.rows=rows});
vm.runInContext("String.prototype.format=function(...args){let i=0;return this.replace(/%[dh]/g,()=>args[i++]);}",ctx);
const app=vm.runInContext('(function(){'+source+'})()',ctx);
(async()=>{
const radio={dev:{getWifiNetworks:async()=>[{isUp:()=>true,getIfname:()=> 'test-ap'}],getName:()=> 'radio1'},band:5,graph:{offset_tbl:{36:10}},scanCache:{},table:{},loadedOnce:true};
app.active_tab='test';app.radios={test:radio};
app.resize_channel_graph=()=>{};app.add_wifi_to_graph=()=>{};
let scanName,infoName;
app.callScan=async name=>{scanName=name;return []};
app.callInfo=async name=>{infoName=name;return {frequency:5180,bssid:'02:00:00:00:00:01',channel:36,center_chan1:50,htmode:'EHT160',mode:'Master'}};
await app.handleScanRefresh();
assert.equal(scanName,'test-ap');assert.equal(infoName,'test-ap');assert.equal(radio.table.rows.length,1);assert.equal(radio.table.rows[0][0],'—');assert.equal(radio.table.rows[0][3],'160 MHz');
await app.handleScanRefresh();assert.equal(radio.table.rows.length,1);
app.callInfo=async()=>({frequency:2452,bssid:'02:00:00:00:00:02',channel:9});
await app.handleScanRefresh();assert.equal(radio.table.rows.length,0);
console.log('Passed: actual-interface scan/info, 5 GHz local entry, no duplicate on refresh, wrong-band rejection');
})().catch(e=>{console.error(e);process.exit(1)});
