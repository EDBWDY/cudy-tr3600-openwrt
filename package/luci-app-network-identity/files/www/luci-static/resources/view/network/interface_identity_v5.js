'use strict';
'require view';
'require rpc';
'require ui';
'require poll';
'require uci';
'require dom';
'require request';
'require network';

var getStatus = rpc.declare({object:'interface.identity',method:'status',params:['device'],expect:{}});
var saveProfile = rpc.declare({object:'interface.identity',method:'save',params:['device','id','name','mac','hostname'],expect:{}});
var removeProfile = rpc.declare({object:'interface.identity',method:'remove',params:['device','id'],expect:{}});
var applyProfile = rpc.declare({object:'interface.identity',method:'apply',params:['device','id','preview'],expect:{}});

var confirmProfile=rpc.declare({object:'interface.identity',method:'confirm',params:['device'],expect:{}});
var rollbackProfile=rpc.declare({object:'interface.identity',method:'rollback',params:['device'],expect:{}});
function checked(result) {
 if (!result || !result.ok) throw new Error(result && result.error || '路由器未返回有效结果。');
 return result;
}
function button(text, kind, action, disabled) {
 return E('button',{type:'button',class:'cbi-button '+(kind||'cbi-button-neutral'),click:action,disabled:disabled?'':null},text);
}
function macText(value) { return E('span',{style:'font-family:monospace;white-space:nowrap'},value); }
var layoutCSS = '\n.wan-identity .wan-id-table{display:table!important;width:calc(100% - 32px)!important;table-layout:auto;border-collapse:collapse;margin:12px 16px 16px;color:inherit}\n.wan-identity .wan-id-table thead{display:table-header-group!important}\n.wan-identity .wan-id-table tbody{display:table-row-group!important}\n.wan-identity .wan-id-table tr{display:table-row!important}\n.wan-identity .wan-id-table th,.wan-identity .wan-id-table td{display:table-cell!important;float:none!important;width:auto;vertical-align:middle;text-align:left;padding:12px 10px;line-height:1.5;border-bottom:1px solid rgba(128,128,128,.2);overflow-wrap:anywhere}\n.wan-identity .wan-id-table th{font-weight:600;white-space:nowrap}\n.wan-identity .wan-id-table td:before{display:none!important}\n.wan-identity .wan-id-table .wan-id-action-cell{text-align:left;min-width:170px}\n.wan-identity .wan-id-actions{display:flex;align-items:center;justify-content:flex-end;gap:6px;flex-wrap:wrap}\n.wan-identity .wan-id-actions .cbi-button,.wan-id-form .cbi-button{margin:0!important;white-space:nowrap;line-height:1.4;min-height:36px}\n.wan-id-form .cbi-value{display:grid!important;grid-template-columns:140px minmax(0,1fr);align-items:start;gap:12px;padding:10px 0}\n.wan-id-form .cbi-value-title{float:none!important;width:auto!important;margin:0!important;padding:9px 0!important;text-align:left;line-height:1.5}\n.wan-id-form .cbi-value-field{margin:0!important;padding:0!important;min-width:0}\n.wan-id-form .cbi-input-text{box-sizing:border-box;width:100%!important;min-width:0!important;max-width:100%;margin:0!important}\n.wan-id-form .wan-id-mac-input{display:flex;align-items:center;gap:8px;flex-wrap:wrap}\n.wan-id-form .wan-id-mac-input input{flex:1 1 190px}\n.wan-id-form .wan-id-mac-input button{flex:0 0 auto}\n.wan-id-form .cbi-value-description{margin-top:6px;line-height:1.6}\n@media(max-width:760px){\n.wan-identity .wan-id-table,.wan-identity .wan-id-table tbody{display:block!important}\n.wan-identity .wan-id-table thead{display:none!important}\n.wan-identity .wan-id-table tr{display:grid!important;grid-template-columns:minmax(0,1fr);padding:8px 0;border-bottom:1px solid rgba(128,128,128,.2)}\n.wan-identity .wan-id-table td{display:grid!important;grid-template-columns:112px minmax(0,1fr);gap:8px;padding:8px 0;border:0;text-align:left;min-width:0}\n.wan-identity .wan-id-table td:before{display:block!important;content:attr(data-title);font-weight:600}\n.wan-identity .wan-id-table .wan-id-action-cell{min-width:0;text-align:left}\n.wan-identity .wan-id-actions{justify-content:flex-start}\n.wan-id-form .cbi-value{grid-template-columns:minmax(0,1fr);gap:4px}\n.wan-id-form .cbi-value-title{text-align:left;padding:0!important}\n}\n';
layoutCSS += '.modal.wan-id-modal{position:fixed!important;left:50%!important;top:50%!important;transform:translate(-50%,-50%)!important;margin:0!important;width:600px;min-width:0!important;max-width:calc(100vw - 32px)!important;max-height:calc(100dvh - 32px);overflow-y:auto;box-sizing:border-box}';
layoutCSS += '.wan-id-selector{padding:16px;display:flex;align-items:center;gap:14px}.wan-id-selector>label{font-weight:600}.wan-id-selector .cbi-dropdown{min-width:260px;max-width:100%}.wan-id-network-choice{display:inline-flex;align-items:center;gap:8px;white-space:nowrap}.wan-id-port-icons{display:inline-flex;align-items:center;gap:3px}.wan-id-port-icons img{width:18px!important;height:18px!important}@media(max-width:600px){.wan-id-selector{align-items:flex-start;flex-direction:column}.wan-id-selector .cbi-dropdown{min-width:0;width:100%}.wan-id-network-choice{flex-wrap:wrap;white-space:normal}}';
layoutCSS += '.wan-identity .wan-id-live{display:flex;flex-direction:column;gap:16px}.wan-identity .wan-id-live>.cbi-section{margin:0!important;flex:none}.wan-identity .wan-id-note{margin:0!important;padding:0 16px 18px!important;line-height:1.65;clear:both;overflow-wrap:anywhere}.wan-identity .wan-id-live .cbi-section-create{display:flex!important;justify-content:flex-end;align-items:center;margin:0!important;padding:0 16px 16px!important}.wan-identity .wan-id-live .cbi-section-create .cbi-button{margin:0!important}';
function table(headers, rows) {
 return E('table',{class:'wan-id-table'},[
  E('thead',{},E('tr',{},headers.map(function(h){return E('th',{scope:'col',class:h==='操作'?'wan-id-action-cell':''},h);}))),
  E('tbody',{},rows.map(function(row){return E('tr',{class:'wan-id-row'},row.map(function(cell,i){
   return E('td',{class:headers[i]==='操作'?'wan-id-action-cell':'','data-title':headers[i]},cell);
  }));}))
 ]);
}

return view.extend({
 handleSave:null, handleSaveApply:null, handleReset:null,
 load:function(){
  return Promise.all([getStatus('').then(checked),network.getNetworks()]).then(function(result){
   return {status:result[0],networks:result[1].filter(function(n){return n.getName()!=='loopback';})};
  });
 },
 statusForSelection:function(){
  if(this.selected)return getStatus(this.selected).then(checked);
  return Promise.resolve({ok:true,current:{device:'—',proto:'none',mac:'—',editable:false,reason:'此接口当前没有可修改 MAC 的设备',up:false},profiles:[]});
 },
 refresh:function(manual){
  if(this.refreshing)return Promise.resolve();
  this.refreshing=true;var selected=this.selectedNetwork;
  return this.statusForSelection().then(L.bind(function(data){if(this.selectedNetwork!==selected)return;this.data=data;dom.content(this.root,this.draw(data));},this))
   .catch(function(err){if(manual)ui.addNotification(null,E('p',{},err.message),'error');})
   .finally(L.bind(function(){this.refreshing=false;if(this.selectedNetwork!==selected)this.refresh(manual);else this.root.inert=false;},this));
 },
 edit:function(profile,copy){
  var self=this,c=this.data.current,p=profile||{name:'',mac:c.mac,hostname:c.hostname};
  var name=E('input',{id:'wan-profile-name',class:'cbi-input-text',type:'text',maxlength:80,value:copy?p.name+' 副本':p.name});
  var mac=E('input',{id:'wan-profile-mac',class:'cbi-input-text',type:'text',maxlength:17,value:p.mac,spellcheck:'false'});
  var host=E('input',{id:'wan-profile-hostname',class:'cbi-input-text',type:'text',maxlength:63,value:p.hostname,placeholder:c.system_hostname,spellcheck:'false'});
  var error=E('p',{role:'alert',style:'color:var(--error-color,#d65a5a);min-height:1.5em'});
  var save=button('保存','cbi-button-save',function(){
   error.textContent='';
   var n=name.value.trim(),m=mac.value.trim().replace(/-/g,':').toUpperCase(),h=host.value.trim();
   if(!n){error.textContent='请输入方案名称。';name.focus();return;}
   if(!/^[0-9A-F][02468ACE](:[0-9A-F]{2}){5}$/.test(m)||m==='00:00:00:00:00:00'){
    error.textContent='请输入有效的单播 MAC 地址。';mac.focus();return;
   }
   if(h&&!/^[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?$/.test(h)){
    error.textContent='主机名仅支持字母、数字和中划线，首尾不能是中划线。';host.focus();return;
   }
   save.disabled=true;
   saveProfile(self.selected,profile&&!copy?p.id:'',n,m,c.proto==='dhcp'?h:'').then(checked).then(function(){ui.hideModal();return self.refresh(true);})
    .catch(function(err){error.textContent=err.message;save.disabled=false;});
  });
  function field(id,label,input,description){return E('div',{class:'cbi-value'},[
   E('label',{class:'cbi-value-title',for:id},label),
   E('div',{class:'cbi-value-field'},[input,E('div',{class:'cbi-value-description'},description||'')])
  ]);}
  var random=button('随机生成','cbi-button-neutral',function(){
   var bytes=new Uint8Array(6);crypto.getRandomValues(bytes);bytes[0]=(bytes[0]|2)&254;
   mac.value=Array.from(bytes,function(v){return v.toString(16).padStart(2,'0');}).join(':').toUpperCase();
  });
  var clone=button('复制本机 MAC','cbi-button-neutral',function(){
   error.textContent='';clone.disabled=true;
   request.post('/cgi-bin/wan-identity-client',JSON.stringify({sid:rpc.getSessionID()}),{cache:false,headers:{'Content-Type':'application/json'}}).then(function(response){return response.json();}).then(checked)
    .then(function(result){mac.value=result.mac;})
    .catch(function(err){error.textContent=err.message||'无法识别本机 MAC，请手动填写';})
    .finally(function(){clone.disabled=false;});
  });
  ui.showModal(profile&&!copy?'编辑方案':'添加方案',[
   E('div',{class:'cbi-map wan-id-form'},[
    field('wan-profile-name','方案名称',name),
    field('wan-profile-mac','MAC 地址',E('div',{class:'wan-id-mac-input'},[mac,random,clone]),'随机生成本地管理的单播地址。'),
    c.proto==='dhcp'?field('wan-profile-hostname','DHCP 主机名',host,'留空时使用系统主机名'):[],error
   ]),
   E('div',{class:'right'},[button('取消','cbi-button-reset',ui.hideModal),' ',save])
  ]);
  name.closest('.modal').classList.add('wan-id-modal');
  name.focus();
 },
 remove:function(p){
  var self=this;
  ui.showModal('删除方案',[
   E('p',{},'确定删除「'+p.name+'」？'),
   E('div',{class:'right'},[button('取消','cbi-button-reset',ui.hideModal),' ',button('删除','cbi-button-remove',function(){
    removeProfile(self.selected,p.id).then(checked).then(function(){ui.hideModal();return self.refresh(true);})
     .catch(function(err){ui.addNotification(null,E('p',{},err.message),'error');});
   })])
  ]);
 },
 apply:function(p){
  var self=this;
  if(this.switching||this.data.busy)return;
  this.switching=true;dom.content(this.root,this.draw(this.data));
  uci.changes().then(function(changes){
   if((changes.network&&changes.network.length)||(changes.wireless&&changes.wireless.length))throw new Error('请先应用或撤销其他待处理的网络配置修改。');
   return applyProfile(self.selected,p.id,false);
  }).then(checked).then(function(){return self.refresh(true);})
   .catch(function(err){ui.addNotification(null,E('p',{},err.message),'error');})
   .finally(function(){self.switching=false;dom.content(self.root,self.draw(self.data));});
 },
 draw:function(data){
  var self=this,c=data.current,op=data.operation||{},busy=!!data.busy||!!this.switching;
  var current=data.profiles.filter(function(p){return p.active;})[0];
  var content=[];
  if(c.reason)content.push(E('p',{class:'cbi-section-descr'},c.reason));
  if(op.message)content.push(E('div',{class:'alert-message '+(/failed|rolled_back/.test(op.state)?'warning':'notice'),role:'status'},op.message));
  if(op.state==='awaiting_confirmation') content.push(E('div',{class:'cbi-section',style:'padding:16px'},[
   button('保留修改','cbi-button-action',function(){return confirmProfile(self.selected).then(checked).then(function(){return self.refresh(true);});}),
   ' ',button('立即恢复','cbi-button-reset',function(){return rollbackProfile(self.selected).then(checked).then(function(){return self.refresh(true);});})
  ]));
  content.push(E('div',{class:'cbi-section'},[
   E('h3',{},'当前配置'),
   table(['状态','MAC 地址','DHCP 上报主机名','IPv4 地址','接口'],[[
    busy?'正在切换':c.up?'已连接':'未连接',macText(c.mac),c.proto==='dhcp'?(c.reported||c.hostname):'—',c.ipv4||'未分配',c.device+' / '+c.proto.toUpperCase()
   ]]),
   E('div',{class:'cbi-section-descr'},'当前方案：'+(current?current.name:'自定义')+(c.reported&&c.reported!==c.hostname?'；配置的 DHCP 主机名：'+c.hostname:'')),
  ]));
  var rows=data.profiles.map(function(p){
   var actions=[button(p.active?'当前方案':'切换','cbi-button-action',function(){self.apply(p);},busy||p.active||c.editable===false),' ',
    button(p.initial?'复制':'编辑','cbi-button-edit',function(){self.edit(p,!!p.initial);},busy||c.editable===false)];
   if(!p.initial)actions.push(' ',button('删除','cbi-button-remove',function(){self.remove(p);},busy||p.active));
   return [p.name,macText(p.mac),c.proto==='dhcp'?(p.hostname||('跟随系统：'+c.system_hostname)):'—',p.active?'正在使用':p.initial?'初始配置':'已保存',E('div',{class:'wan-id-actions'},actions)];
  });
  content.push(E('div',{class:'cbi-section cbi-tblsection'},[
   E('h3',{},'已保存的方案'),
   E('div',{class:'cbi-section-descr'},'已保存 '+data.profiles.length+' / 32 组'),
   table(['方案名称','MAC 地址','DHCP 主机名','状态','操作'],rows),
   E('div',{class:'cbi-section-create'},button('添加','cbi-button-add',function(){self.edit();},busy||c.editable===false||data.profiles.length>=32)),
   E('p',{class:'wan-id-note'},'修改接口可能短暂断开连接；非 WAN 接口需在 60 秒内点击保留，否则自动恢复')
  ]));
  return content;
 },
 render:function(loaded){
  ui.menu.flushCache();var self=this,choices={},names=[];
  this.networks=loaded.networks;this.networkDevices={};
  this.networks.forEach(function(n){
   var name=n.getName(),dev=n.getL3Device()||n.getDevice();
   names.push(name);self.networkDevices[name]=dev?dev.getName():null;
   function icon(d,alias){return E('img',{class:'middle',style:'width:20px;height:20px',title:d?d.getTypeI18n():'设备未连接',src:L.resource('icons/'+(alias?'alias':d?d.getType():'ethernet')+(d&&d.isUp()?'':'_disabled')+'.svg')});}
   var badge=[icon(dev,n.isAlias()),E('strong',{},name.toUpperCase()),E('span',{style:'opacity:.7'},dev?dev.getName():'设备未连接')];
   var ports=dev?dev.getPorts():[];
   if(ports&&ports.length)badge.push(E('span',{class:'wan-id-port-icons'},['('].concat(ports.map(function(p){return icon(p,false);}),[')'])));
   choices[name]=E('span',{class:'wan-id-network-choice'},badge);
  });
  this.selectedNetwork=names.indexOf('wan')>=0?'wan':names[0];
  this.selected=this.networkDevices[this.selectedNetwork];
  this.selector=new ui.Dropdown(this.selectedNetwork,choices,{id:'network-identity-select',sort:names,multiple:false,optional:false,create:false,dropdown_items:Math.max(1,Math.min(names.length,8))});
  var select=this.selector.render();
  select.addEventListener('cbi-dropdown-change',function(){
   var name=self.selector.getValue();
   if(name===self.selectedNetwork)return;
   self.selectedNetwork=name;self.selected=self.networkDevices[name];self.root.inert=true;
   return self.refresh(true);
  });
  this.root=E('div',{class:'wan-id-live','aria-live':'polite'});
  var page=E('div',{class:'cbi-map wan-identity'},[
   E('style',{},layoutCSS),E('h2',{},'网络身份'),
   E('div',{class:'cbi-map-descr'},'按接口保存和切换 MAC 地址，DHCP 接口可设置上报主机名'),
   E('div',{class:'cbi-section wan-id-selector'},[E('label',{for:'network-identity-select'},'接口'),select]),this.root
  ]);
  this.data=loaded.status;
  if(this.selected===loaded.status.current.device)dom.content(this.root,this.draw(this.data));
  else this.refresh(true);
  poll.add(L.bind(function(){return this.refresh(false);},this),5);
  return page;
 }
});
