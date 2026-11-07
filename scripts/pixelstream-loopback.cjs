'use strict';
// UE5.6's reference CLI has no bind-address option. Scope this preload to
// its Node process; keep Epic's server and signalling protocol unchanged.
const net = require('node:net');
const listen = net.Server.prototype.listen;
net.Server.prototype.listen = function (...args) {
    let options;
    let callback;
    if (typeof args[0] === 'object' && args[0] !== null) {
        options = { ...args[0] };
        callback = args.find(arg => typeof arg === 'function');
    } else if (typeof args[0] === 'number' || /^\d+$/.test(args[0])) {
        options = { port: Number(args[0]) };
        const backlog = args.slice(1).find(arg => typeof arg === 'number');
        if (backlog !== undefined) options.backlog = backlog;
        callback = args.find(arg => typeof arg === 'function');
    } else {
        throw new Error('Local Pixel Streaming only permits TCP listeners.');
    }
    if (options.port === undefined || options.path || options.fd || options.handle) {
        throw new Error('Local Pixel Streaming requires an explicit TCP port.');
    }
    options.host = '127.0.0.1';
    options.ipv6Only = false;
    return callback ? listen.call(this, options, callback) : listen.call(this, options);
};
