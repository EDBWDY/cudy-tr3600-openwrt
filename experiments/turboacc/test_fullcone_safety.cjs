// Exercise the real LuCI helper's enable/cancel/dismiss behavior without a router.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
let modal = null, dialogs = 0, value = '0', safety;
const ui = {
  showModal(title, children) { modal = { title, children }; dialogs++; },
  hideModal() { modal = null; }
};
const E = (tag, attrs, children) => ({ tag, attrs, children });
const widget = { setValue(next) { value = next; safety.confirmFullCone(option, 'config', next); } };
const option = { getUIElement(id) { assert.equal(id, 'config'); return widget; } };
const source = fs.readFileSync(path.join(__dirname, 'turboacc_safety.js'), 'utf8');
safety = new Function('ui', 'E', '_', source)(ui, E, text => text);
function buttons(node) {
  if (Array.isArray(node)) return node.flatMap(buttons);
  if (!node || typeof node !== 'object') return [];
  return node.tag === 'button' ? [node] : buttons(node.children);
}
safety.confirmFullCone(option, 'config', '0');
assert.equal(dialogs, 0);
widget.setValue('2');
assert.equal(value, '0');
assert.ok(modal.title.includes('security warning'));
buttons(modal.children)[0].attrs.click();
assert.equal(value, '0');
assert.equal(modal, null);
widget.setValue('2');
ui.hideModal(); // Closing the modal without confirmation also keeps it off.
assert.equal(value, '0');
widget.setValue('2');
buttons(modal.children)[1].attrs.click();
assert.equal(value, '2');
assert.equal(modal, null);
assert.equal(dialogs, 3); // Programmatic setValue must not recursively warn.
widget.setValue('0');
widget.setValue('2');
assert.equal(value, '0');
assert.ok(modal);
assert.equal(dialogs, 4);
console.log('FULLCONE_DEFAULT_OFF_AND_CONFIRMATION_TESTS_PASSED');
