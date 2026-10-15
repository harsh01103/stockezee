import puppeteer from 'puppeteer';

(async () => {
  const browser = await puppeteer.launch();
  const page = await browser.newPage();
  await page.goto('http://localhost:4000/options', { waitUntil: 'networkidle2' });
  
  // wait for table to load
  await page.waitForSelector('.group.relative', { timeout: 5000 });
  
  // click the first leg cell
  await page.click('.group.relative');
  
  // wait for dialog
  await page.waitForSelector('[role="dialog"]', { timeout: 5000 });
  
  const className = await page.$eval('[role="dialog"]', el => el.className);
  console.log("MODAL CLASSNAME:", className);
  
  const rect = await page.$eval('[role="dialog"]', el => JSON.stringify(el.getBoundingClientRect()));
  console.log("MODAL RECT:", rect);
  
  await browser.close();
})();
