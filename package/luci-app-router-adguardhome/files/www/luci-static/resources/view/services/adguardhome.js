'use strict';
'require view';
return view.extend({render:function(){return E('div',{'class':'cbi-map'},[E('h2',{},'AdGuard Home'),E('div',{'class':'cbi-section'},[E('a',{'class':'cbi-button cbi-button-action','href':location.protocol+'//'+location.hostname+':3000','target':'_blank','rel':'noopener'},'打开管理界面')])]);},handleSave:null,handleSaveApply:null,handleReset:null});
