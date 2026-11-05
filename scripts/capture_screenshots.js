const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

const PORT = 9333;

async function waitForPort(maxRetries = 30) {
    for (let i = 0; i < maxRetries; i++) {
        try {
            const res = await fetch(`http://127.0.0.1:${PORT}/json/list`);
            if (res.ok) {
                const list = await res.json();
                const page = list.find(item => item.type === 'page' && item.webSocketDebuggerUrl);
                if (page) return page;
            }
        } catch (e) {}
        await new Promise(r => setTimeout(r, 200));
    }
    throw new Error('Chrome debugging port or page target not ready');
}

async function main() {
    console.log('1. Getting JWT token...');
    const tokenRes = await fetch('http://127.0.0.1:18002/api/token/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: 'admin', password: 'admin' })
    });
    const tokenData = await tokenRes.json();
    const token = tokenData.token;
    console.log('Got token:', token ? 'OK' : 'FAILED');

    console.log('2. Launching headless Chrome on port ' + PORT + '...');
    const chromePath = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
    const profileDir = '/tmp/chrome-screenshot-profile-' + Date.now();
    const chromeProc = spawn(chromePath, [
        '--headless=new',
        `--remote-debugging-port=${PORT}`,
        '--no-first-run',
        '--no-default-browser-check',
        '--window-size=1440,900',
        `--user-data-dir=${profileDir}`,
        'about:blank'
    ]);

    try {
        const pageTarget = await waitForPort();
        const wsUrl = pageTarget.webSocketDebuggerUrl;

        console.log('Connecting to page WebSocket:', wsUrl);
        const ws = new WebSocket(wsUrl);

        let id = 1;
        const pending = new Map();

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.id && pending.has(data.id)) {
                pending.get(data.id)(data);
                pending.delete(data.id);
            }
        };

        await new Promise((resolve) => ws.onopen = resolve);

        function send(method, params = {}) {
            return new Promise((resolve, reject) => {
                const reqId = id++;
                pending.set(reqId, resolve);
                ws.send(JSON.stringify({ id: reqId, method, params }));
            });
        }

        // Enable domains
        await send('Page.enable');
        await send('Network.enable');
        await send('Runtime.enable');
        await send('DOM.enable');

        // Set device metrics (1440x900, scale 1.5 for crispness and reasonable file size)
        await send('Emulation.setDeviceMetricsOverride', {
            width: 1440,
            height: 900,
            deviceScaleFactor: 1.5,
            mobile: false
        });

        // Set Authorization cookie
        await send('Network.setCookie', {
            name: 'AUTHORIZATION',
            value: 'jwt ' + token,
            domain: '127.0.0.1',
            path: '/'
        });

        console.log('Navigating to http://127.0.0.1:18002/#/ ...');
        await send('Page.navigate', { url: 'http://127.0.0.1:18002/#/' });

        // Wait for page to load Vue app
        await new Promise(r => setTimeout(r, 4000));

        // Navigate to 01_精选专辑 folder
        console.log('Navigating into 01_精选专辑 folder...');
        await send('Runtime.evaluate', {
            expression: `
                (async () => {
                    const app = document.querySelector('.home-main-layout');
                    if (app && app.__vue__) {
                        app.__vue__.navigateToPath('/01_精选专辑');
                    }
                })()
            `
        });

        await new Promise(r => setTimeout(r, 2500));

        // Take overview screenshot
        console.log('Capturing workspace_overview.png...');
        const snap1 = await send('Page.captureScreenshot', { format: 'png' });
        fs.writeFileSync(
            path.join(__dirname, '../docs/images/workspace_overview.png'),
            Buffer.from(snap1.result.data, 'base64')
        );
        console.log('Saved docs/images/workspace_overview.png');

        // Click task drawer button
        console.log('Opening task drawer...');
        await send('Runtime.evaluate', {
            expression: `
                (() => {
                    const app = document.querySelector('.home-main-layout');
                    if (app && app.__vue__) {
                        app.__vue__.openTaskDrawer();
                    }
                })()
            `
        });

        await new Promise(r => setTimeout(r, 2000));

        // Take task center screenshot
        console.log('Capturing task_center_drawer.png...');
        const snap2 = await send('Page.captureScreenshot', { format: 'png' });
        fs.writeFileSync(
            path.join(__dirname, '../docs/images/task_center_drawer.png'),
            Buffer.from(snap2.result.data, 'base64')
        );
        console.log('Saved docs/images/task_center_drawer.png');

        ws.close();
    } finally {
        chromeProc.kill();
        await new Promise(r => setTimeout(r, 1000));
        try {
            fs.rmSync(profileDir, { recursive: true, force: true });
        } catch (e) {}
    }
    console.log('All screenshots captured successfully!');
}

main().catch(console.error);
