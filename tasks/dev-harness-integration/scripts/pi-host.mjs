// Bounded acceptance host: installed registry + installed Host API, no model calls.
import { EventEmitter } from 'node:events';
import { realpathSync } from 'node:fs';
import { writeFile } from 'node:fs/promises';
import { registerHooks } from 'node:module';
import { pathToFileURL } from 'node:url';
const [pkg, bridgePath, lab, readyPath] = process.argv.slice(2);
const installedPi = process.env.SVC_ACCEPTANCE_PI_PACKAGE ? realpathSync(process.env.SVC_ACCEPTANCE_PI_PACKAGE) : undefined;
if (installedPi) {
    registerHooks({ resolve(specifier, context, next) {
        if (specifier === '@earendil-works/pi-coding-agent') return next(specifier, { ...context, parentURL: pathToFileURL(`${installedPi}/index.js`).href });
        return next(specifier, context);
    } });
}
const { BackgroundTaskRegistry } = await import(pathToFileURL(`${pkg}/dist/src/core/registry.js`));
const { installBackgroundTaskHostApi } = await import(pathToFileURL(`${pkg}/dist/src/core/host-api.js`));
const bridge = (await import(pathToFileURL(bridgePath))).default;
const emitter = new EventEmitter();
const events = { emit: (name, data) => emitter.emit(name, data), on: (name, cb) => { emitter.on(name, cb); return () => emitter.off(name, cb); } };
const callbacks = new Map();
const ctx = { cwd: lab, sessionId: 'svc-bounded-native-acceptance', modelRegistry: { getAll: () => [] } };
let host;
const registry = new BackgroundTaskRegistry({ sendCompletionNotification: () => {}, onChange: () => host?.invalidate(), killGraceMs: 200, stopWaitMs: 2000 });
host = installBackgroundTaskHostApi({ events, registry, getContext: () => ctx, isSeen: () => false, markSeen: () => {}, readResult: async () => ({}) });
host.markReady();
bridge({ events, on: (name, cb) => callbacks.set(name, cb) });
const cleanup = async () => {
    host.close();
    for (const task of registry.allTasks()) if (task.status === 'running') await registry.stopTask(task, 'user');
    registry.setShuttingDown(true);
    await callbacks.get('session_shutdown')?.();
};
let closing = false;
process.on('SIGTERM', async () => { if (closing) return; closing = true; await cleanup(); process.exit(0); });
const expiry = setTimeout(async () => { if (closing) return; closing = true; await cleanup(); process.exit(0); }, 45000);
try {
    await callbacks.get('session_start')();
    const task = await registry.startTask(ctx, "/usr/bin/python3 -u -c 'import time; print(\"SVC native Pi acceptance\", flush=True); time.sleep(40)'", { name: 'SVC Pi 验收' });
    await writeFile(readyPath, JSON.stringify({ task: task.id, hostPid: process.pid }));
    process.on('SIGUSR1', async () => { await callbacks.get('session_start')(); });
} catch (error) { clearTimeout(expiry); await cleanup(); throw error; }
