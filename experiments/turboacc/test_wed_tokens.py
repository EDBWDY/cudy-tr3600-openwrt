"""Execute the patched driver's actual TX allocation/accounting callbacks.

The harness replaces kernel allocation/locking primitives, not driver logic.
It checks both the MT7996 low hardware pool and legacy upper hardware pools.
This cannot establish physical Wi-Fi forwarding or firmware compatibility.
"""
from pathlib import Path
import argparse
import re
import shutil
import subprocess
import tempfile


def function(text, name):
    start = text.index(name + '(')
    start = text.rfind('\n', 0, start) + 1
    # Pointer-return functions put their return type on the preceding line.
    if name == 'mt76_token_release':
        start = text.rfind('\n', 0, start - 1) + 1
    brace = text.index('{', start)
    depth = 1
    end = brace + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]


def validate(source):
    source = Path(source)
    header = (source / 'mt7996/mt7996.h').read_text()
    defs = {name: int(value) for name, value in re.findall(
        r'#define\s+(MT7996_(?:SW|WED)_TOKEN_SIZE)\s+(\d+)', header)}
    assert defs['MT7996_SW_TOKEN_SIZE'] > 0
    assert sum(defs.values()) <= 32768  # Firmware's 15-bit TX token field.
    mmio = (source / 'mt7996/mmio.c').read_text()
    assert 'wed->wlan.token_start = 0;' in mmio
    assert 'dev->mt76.token_start = wed->wlan.nbuf;' in mmio
    assert '.token_size = MT7996_SW_TOKEN_SIZE,' in mmio
    assert mmio.index('dev->mt76.token_start = wed->wlan.nbuf;') > mmio.index('ret = mtk_wed_device_attach(wed);')
    tx = (source / 'tx.c').read_text()
    wed = (source / 'wed.c').read_text()
    callbacks = '\n'.join([function(tx, 'mt76_token_consume'), function(tx, 'mt76_token_release'),
                           function(wed, 'mt76_wed_offload_enable'), function(wed, 'mt76_wed_offload_disable')])
    harness = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#define CONFIG_NET_MEDIATEK_SOC_WED 1
#define GFP_ATOMIC 0
#define MT_TXQ_PSD 3
#define MT76_TOKEN_FREE_THR 64
#define HZ 100
#define spin_lock_bh(x) ((void)(x))
#define spin_unlock_bh(x) ((void)(x))
#define wait_event_timeout(q, condition, time) ((condition) ? 1 : 0)
#define wake_up(q) ((void)(q))
struct mt76_dev;
struct mt76_txwi_cache { int qid, phy_idx; };
struct idr { struct mt76_txwi_cache *slots[65536]; int next; };
struct mt76_queue { bool blocked; };
struct mt76_phy { int mgmt_tx_pending; struct mt76_queue *q_tx[1]; };
struct driver { int token_size; };
struct mtk_wed_device { struct mt76_dev *owner; bool active; struct { int token_start, nbuf; } wlan; };
struct mt76_dev {
 int token_lock, token_count, token_start, token_size, wed_token_count, tx_wait;
 struct idr token; struct mt76_phy phy; struct driver *drv;
 struct { struct mtk_wed_device wed; } mmio;
};
static struct mt76_phy *mt76_dev_phy(struct mt76_dev *d, int i) { (void)i; return &d->phy; }
static struct mt76_dev *mt76_wed_to_dev(struct mtk_wed_device *w) { return w->owner; }
static int mtk_wed_device_active(struct mtk_wed_device *w) { return w->active; }
static void atomic_inc(int *v) { ++*v; }
static bool atomic_dec_and_test(int *v) { return --*v == 0; }
static void __mt76_set_tx_blocked(struct mt76_dev *d, bool b) { d->phy.q_tx[0]->blocked = b; }
static int idr_alloc(struct idr *i, struct mt76_txwi_cache *p, int start, int end, int flags) {
 (void)flags;
 if (!end) end = 65536;
 if (i->next > start) start = i->next;
 for (int n = start; n < end; n++) if (!i->slots[n]) { i->slots[n] = p; return n; }
 return -28;
}
static struct mt76_txwi_cache *idr_remove(struct idr *i, int n) {
 if (n < 0 || n >= 65536) return NULL;
 struct mt76_txwi_cache *p = i->slots[n]; i->slots[n] = NULL; return p;
}
'''
    checks = r'''
int main(void) {
 struct mt76_dev *d = calloc(1, sizeof(*d)); assert(d);
 struct mt76_queue q = {0}; struct driver drv = { SW_SIZE };
 struct mt76_txwi_cache t = {0}, *p = &t; bool wake = false;
 d->drv = &drv; d->phy.q_tx[0] = &q; d->mmio.wed.owner = d; d->mmio.wed.active = true;
 d->mmio.wed.wlan.nbuf = HW_SIZE; d->token_start = HW_SIZE; d->token_size = SW_SIZE;
 assert(mt76_wed_offload_enable(&d->mmio.wed) == 0);
 assert(d->token_size == SW_SIZE);
 for (int n = HW_SIZE; n < HW_SIZE + SW_SIZE; n++) {
  d->token.next = n;
  assert(mt76_token_consume(d, &p) == n);
  assert(d->wed_token_count == 0);
 }
 assert(q.blocked); assert(d->token_count == SW_SIZE);
 assert(mt76_token_consume(d, &p) == -28); assert(d->wed_token_count == 0);
 assert(mt76_wed_offload_enable(&d->mmio.wed) == 0);
 for (int n = HW_SIZE; n < HW_SIZE + SW_SIZE; n++) assert(mt76_token_release(d, n, &wake) == &t);
 assert(d->token_count == 0 && d->wed_token_count == 0 && wake);
 mt76_wed_offload_disable(&d->mmio.wed); assert(d->token_size == SW_SIZE);
 // Older mt76 drivers use upper hardware IDs borrowed from their host pool.
 drv.token_size = 16384; d->token_start = 0; d->token_size = 16384;
 d->mmio.wed.wlan.token_start = 8192; d->mmio.wed.wlan.nbuf = 8192;
 d->token.next = 8192; assert(mt76_token_consume(d, &p) == 8192);
 assert(d->wed_token_count == 1);
 assert(mt76_wed_offload_enable(&d->mmio.wed) != 0); assert(d->token_size == 8192);
 assert(mt76_token_release(d, 8192, &wake) == &t); assert(d->wed_token_count == 0);
 assert(mt76_wed_offload_enable(&d->mmio.wed) == 0);
 mt76_wed_offload_disable(&d->mmio.wed); assert(d->token_size == 16384);
 d->token.next = 0; p->qid = MT_TXQ_PSD;
 assert(mt76_token_consume(d, &p) == 0); assert(d->phy.mgmt_tx_pending == 1);
 assert(mt76_token_release(d, 0, &wake) == &t); assert(d->phy.mgmt_tx_pending == 0);
 free(d); puts("Actual driver token callbacks: disjoint pools, exhaustion, enable/disable, management TX and legacy drain passed");
 return 0;
}
'''.replace('SW_SIZE', str(defs['MT7996_SW_TOKEN_SIZE'])).replace('HW_SIZE', str(defs['MT7996_WED_TOKEN_SIZE']))
    cc = shutil.which('cc') or shutil.which('gcc')
    if not cc:
        raise RuntimeError('A C compiler is required to execute the driver callbacks')
    with tempfile.TemporaryDirectory(prefix='wed-token-test-') as temporary:
        root = Path(temporary)
        (root / 'test.c').write_text(harness + callbacks + checks)
        subprocess.run([cc, '-std=c11', '-Wall', '-Wextra', '-Werror', '-fsanitize=undefined',
                        str(root / 'test.c'), '-o', str(root / 'test')], check=True)
        subprocess.run([str(root / 'test')], check=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source')
    validate(parser.parse_args().source)
