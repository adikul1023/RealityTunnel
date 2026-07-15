const puppeteer = require('puppeteer');

(async () => {
    const browser = await puppeteer.launch({ headless: "new" });
    const page = await browser.newPage();
    
    // Intercept requests
    await page.setRequestInterception(true);
    page.on('request', request => {
        if (request.url().includes('/api/auth/login')) {
            console.log('REQUEST TO:', request.url());
            console.log('METHOD:', request.method());
            console.log('POST DATA:', request.postData());
        }
        request.continue();
    });

    page.on('response', async response => {
        if (response.url().includes('/api/auth/login')) {
            console.log('RESPONSE FROM:', response.url());
            console.log('STATUS:', response.status());
            const text = await response.text();
            console.log('BODY:', text);
        }
    });

    await page.goto('https://stealthy.co.in/login', { waitUntil: 'networkidle2' });
    
    // Attempt login (use dummy credentials just to see where it goes)
    await page.type('input[type="text"], input[name="accountId"], input[id="accountId"]', 'test-account');
    await page.type('input[type="password"]', 'test-password');
    await page.click('button[type="submit"]');
    
    await new Promise(r => setTimeout(r, 5000));
    await browser.close();
})();
