// SVC managed native-task bridge v1
// This extension exposes existing Pi tasks; it registers no model tool or scheduler.
import net from "node:net";
import { promises as fs } from "node:fs";
import path from "node:path";
import os from "node:os";
import { randomUUID, randomBytes, timingSafeEqual } from "node:crypto";

const REQUEST = "pi-background-tasks:host:request:v1";
const RESPONSE = "pi-background-tasks:host:response:v1";
const MAX = 1024 * 1024;

export default function svcDev(pi) {
    let current;
    const pending = new Map();
    let off = () => {};
    const listen = () => pi.events.on(RESPONSE, (frame) => {
        const waiter = pending.get(frame?.request_id);
        if (!waiter) return;
        pending.delete(frame.request_id);
        clearTimeout(waiter.timer);
        if (frame.ok === true) waiter.resolve(frame.result);
        else waiter.reject(new Error(`${frame.error?.code ?? "NATIVE_ERROR"}: ${frame.error?.message ?? "Pi request failed"}`));
    });
    const request = (operation, payload, timeout = 1000) => new Promise((resolve, reject) => {
        const id = randomUUID();
        const timer = setTimeout(() => {
            pending.delete(id);
            reject(new Error("Pi 原生管理器未返回结果；控制结果未知，请刷新。"));
        }, timeout);
        pending.set(id, { resolve, reject, timer });
        try {
            pi.events.emit(REQUEST, { schema_version: "pi-background-tasks.host-request.v1", request_id: id, operation, payload });
        } catch (error) {
            clearTimeout(timer);
            pending.delete(id);
            reject(error);
        }
    });
    async function close() {
        const instance = current;
        current = undefined;
        if (!instance) return;
        instance.closed = true;
        for (const socket of instance.clients) socket.destroy();
        instance.server.close();
        await Promise.all([instance.descriptor, instance.socketPath].map(file => fs.unlink(file).catch(error => {
            if (error.code !== "ENOENT") console.error("[SVC] 接入清理失败", error.message);
        })));
        for (const waiter of pending.values()) {
            clearTimeout(waiter.timer);
            waiter.reject(new Error("Pi activation 已关闭。"));
        }
        pending.clear();
    }
    pi.on("session_start", async () => {
        await close();
        off();
        off = listen();
        const root = process.env.SVC_HARNESS_HOME || path.join(
            process.platform === "darwin" ? path.join(os.homedir(), "Library/Application Support") : (process.env.XDG_DATA_HOME || path.join(os.homedir(), ".local/share")),
            "SVC/harnesses");
        await fs.mkdir(root, { recursive: true, mode: 0o700 });
        const directory = await fs.lstat(root);
        if (!directory.isDirectory() || directory.isSymbolicLink() || directory.uid !== process.getuid() || (directory.mode & 0o077)) {
            throw new Error("SVC 执行来源目录必须仅当前用户可访问。");
        }
        const id = randomUUID();
        const token = randomBytes(32).toString("hex");
        const socketPath = path.join(root, `p-${process.pid}-${id.slice(0, 8)}.sock`);
        const descriptor = path.join(root, `pi-${id}.json`);
        if (Buffer.byteLength(socketPath) > 100) throw new Error("SVC socket 路径超过系统限制。");
        const instance = { id, token, socketPath, descriptor, clients: new Set(), closed: false, queue: Promise.resolve() };
        const execute = async (input) => {
            if (instance.closed) throw new Error("Pi activation 已关闭。");
            if (input?.version !== 1 || input.instance !== id || typeof input.token !== "string" ||
                Buffer.byteLength(input.token) !== Buffer.byteLength(token) || !timingSafeEqual(Buffer.from(input.token), Buffer.from(token))) {
                throw new Error("执行来源身份无效。");
            }
            if (!["list", "logs", "stop"].includes(input.operation) ||
                (input.operation !== "list" && (typeof input.task_id !== "string" || !input.task_id || input.task_id.length > 200))) {
                throw new Error("不支持的原生任务请求。");
            }
            const lease = await request("subscribe", { clientId: `svc-${id}` });
            let sequence = 0;
            const call = (operation, payload, timeout) => request(operation, {
                leaseId: lease.leaseId, activationId: lease.activationId, sequence: ++sequence, ...payload,
            }, timeout);
            try {
                if (input.operation === "list") {
                    const tasks = [];
                    let cursor;
                    do {
                        const page = await call("list", { limit: 50, ...(cursor ? { cursor } : {}) });
                        if (!Array.isArray(page.tasks)) throw new Error("Pi Host API 清单无效。");
                        tasks.push(...page.tasks);
                        cursor = page.nextCursor;
                        if (tasks.length > 256 || (tasks.length >= 256 && cursor)) throw new Error("Pi 任务超过本轮读取预算。");
                    } while (cursor);
                    return { tasks };
                }
                if (input.operation === "logs") return await call("logs", { taskId: input.task_id, maxBytes: 65536, tail: true });
                return await call("stop", { taskId: input.task_id }, 30000);
            } finally {
                // The App's existing visibility scheduler owns polling. No lease/timer remains while it is hidden.
                if (!instance.closed) await call("unsubscribe", {}).catch(() => {});
            }
        };
        const server = net.createServer((socket) => {
            instance.clients.add(socket);
            socket.unref();
            socket.setTimeout(35000, () => socket.destroy());
            let buffer = Buffer.alloc(0);
            let admitted = false;
            socket.on("data", (chunk) => {
                if (admitted) return;
                buffer = Buffer.concat([buffer, chunk]);
                if (buffer.length > MAX) return socket.destroy();
                const end = buffer.indexOf(10);
                if (end < 0) return;
                admitted = true;
                let input;
                try { input = JSON.parse(buffer.subarray(0, end).toString()); }
                catch { return socket.destroy(); }
                const run = async () => {
                    let frame;
                    try { frame = { ok: true, result: await execute(input) }; }
                    catch (error) { frame = { ok: false, error: String(error.message ?? error).slice(0, 2000) }; }
                    const line = JSON.stringify(frame) + "\n";
                    if (Buffer.byteLength(line) > MAX) socket.end(JSON.stringify({ ok: false, error: "原生结果超过 1 MiB。" }) + "\n");
                    else socket.end(line);
                };
                instance.queue = instance.queue.then(run, run);
            });
            socket.on("error", () => {});
            socket.on("close", () => instance.clients.delete(socket));
        });
        instance.server = server;
        server.maxConnections = 4;
        current = instance;
        try {
            await new Promise((resolve, reject) => {
                server.once("error", reject);
                server.listen(socketPath, resolve);
            });
            server.unref();
            await fs.chmod(socketPath, 0o600);
            await fs.writeFile(descriptor, JSON.stringify({ schema_version: 1, instance: id, socket: socketPath, token, pid: process.pid }), { mode: 0o600, flag: "wx" });
        } catch (error) {
            await close();
            throw error;
        }
    });
    pi.on("session_shutdown", async () => {
        await close();
        off();
    });
}
