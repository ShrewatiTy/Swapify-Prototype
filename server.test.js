const test = require('node:test');
const assert = require('node:assert/strict');
const { mergeById, mergeByUsername } = require('../server');

test('mergeById keeps listings from multiple devices', () => {
  const existing = [{ id: '1', name: 'Laptop' }];
  const incoming = [{ id: '2', name: 'Phone' }];

  const merged = mergeById(existing, incoming);

  assert.deepStrictEqual(merged.map((item) => item.id), ['1', '2']);
  assert.equal(merged[1].name, 'Phone');
});

test('mergeByUsername preserves shared accounts and updates newer profile data', () => {
  const existing = [{ username: 'Alice', premium: false, tradeRequests: [] }];
  const incoming = [{ username: 'Alice', premium: true, tradeRequests: [{ id: 'x', title: 'Swap' }] }];

  const merged = mergeByUsername(existing, incoming);

  assert.equal(merged[0].premium, true);
  assert.equal(merged[0].tradeRequests.length, 1);
});
