'use strict';
// Run: node --test scripts/test-pixelstream-loopback.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const net = require('node:net');
require('./pixelstream-loopback.cjs');

for (const mode of ['options', 'port']) {
    test(`TCP ${mode} listener binds only IPv4 loopback`, async () => {
        const server = net.createServer();
        try {
            await new Promise((resolve, reject) => {
                server.once('error', reject);
                if (mode === 'options') server.listen({port: 0, host: '0.0.0.0'}, resolve);
                else server.listen(0, '::', resolve);
            });
            assert.equal(server.address().address, '127.0.0.1');
            const client = net.connect(server.address().port, '127.0.0.1');
            await new Promise((resolve, reject) => {
                client.once('connect', resolve);
                client.once('error', reject);
            });
            client.destroy();
        } finally {
            await new Promise(resolve => server.close(resolve));
        }
    });
}
test('pipe and inherited handles cannot bypass loopback binding', () => {
    assert.throws(() => net.createServer().listen({path: 'unexpected-pipe'}), /explicit TCP port/);
    assert.throws(() => net.createServer().listen({fd: 3}), /explicit TCP port/);
});
